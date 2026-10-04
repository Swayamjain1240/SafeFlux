"""In-memory fixed-window rate limiting for API endpoints.

Two layers:
1. `RateLimitMiddleware` — global per-IP budget over /api/v1/*.
2. `auth_rate_limit(bucket)` — tighter per-IP budgets for sensitive auth
   endpoints (signup/login), read from Settings.

Health checks are exempt from the global limiter so monitoring is never
throttled. Hard-bounded memory: stale keys are purged and the table is
reset if it ever grows past a safe size. State is per-process (fine for
the single-process MVP; revisit if multi-worker deployment is added).
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque

from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import Settings
from app.core.responses import error_response

logger = logging.getLogger("safeflux.ratelimit")

_MAX_KEYS = 10_000


class FixedWindowLimiter:
    """Thread-safe sliding-record fixed-window counter keyed by arbitrary string."""

    def __init__(self, limit: int, window_seconds: int, max_keys: int = _MAX_KEYS) -> None:
        self._limit = limit
        self._window = window_seconds
        self._max_keys = max_keys
        self._buckets: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    @property
    def window_seconds(self) -> int:
        return self._window

    def allow(self, key: str, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        with self._lock:
            if len(self._buckets) > self._max_keys:
                self._reset_locked(now)
            bucket = self._buckets.get(key)
            if bucket is None:
                bucket = deque()
                self._buckets[key] = bucket
            cutoff = now - self._window
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= self._limit:
                return False
            bucket.append(now)
            return True

    def _reset_locked(self, now: float) -> None:
        cutoff = now - self._window
        for key in list(self._buckets):
            bucket = self._buckets[key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if not bucket:
                del self._buckets[key]
        if len(self._buckets) > self._max_keys:
            logger.warning("Rate-limit table overflow; resetting buckets")
            self._buckets.clear()


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(
        self,
        app,  # noqa: ANN001 - ASGI app
        *,
        limit: int,
        window_seconds: int,
        exempt_paths: frozenset[str] | set[str] = frozenset(),
    ) -> None:
        super().__init__(app)
        self._limiter = FixedWindowLimiter(limit, window_seconds)
        self._exempt = exempt_paths

    def _client_key(self, request: Request) -> str:
        # Only the direct connection is trusted; X-Forwarded-For is attacker-controlled.
        return request.client.host if request.client else "unknown"

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self._exempt or request.method == "OPTIONS":
            return await call_next(request)

        key = self._client_key(request)
        if not self._limiter.allow(key):
            logger.warning("Rate limit exceeded for %s on %s", key, request.url.path)
            return error_response(
                429,
                "RATE_LIMITED",
                "Too many requests. Please slow down and try again.",
                headers={"Retry-After": str(self._limiter.window_seconds)},
            )
        return await call_next(request)


# Per-app limiter buckets for sensitive auth endpoints, keyed by bucket
# name. Stored on app.state so each app (and test client) is isolated and
# always uses that app's Settings.


def _auth_limiter(request: Request, bucket: str) -> FixedWindowLimiter:
    buckets: dict[str, FixedWindowLimiter] = request.app.state.auth_limiters
    limiter = buckets.get(bucket)
    if limiter is None:
        settings: Settings = request.app.state.settings
        limiter = FixedWindowLimiter(
            settings.AUTH_RATE_LIMIT_ATTEMPTS,
            settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
        )
        buckets[bucket] = limiter
    return limiter


def _simulation_limiter(request: Request) -> FixedWindowLimiter:
    buckets: dict[str, FixedWindowLimiter] = request.app.state.simulation_limiters
    limiter = buckets.get("run")
    if limiter is None:
        settings: Settings = request.app.state.settings
        limiter = FixedWindowLimiter(
            settings.SIM_RATE_LIMIT_RUNS,
            settings.SIM_RATE_LIMIT_WINDOW_SECONDS,
        )
        buckets["run"] = limiter
    return limiter


async def simulation_rate_limit(request: Request) -> None:
    """Per-IP budget for the expensive deterministic simulation endpoint.

    Simulation is compute-heavy, so it gets its own tight bucket independent
    of the auth buckets and the global limiter (rule 8).
    """
    limiter = _simulation_limiter(request)
    ip = request.client.host if request.client else "unknown"
    if not limiter.allow(f"simulate:{ip}"):
        logger.warning("Simulation rate limit exceeded for %s", ip)
        raise HTTPException(
            status_code=429,
            detail="Too many simulation requests. Please wait and try again.",
            headers={"Retry-After": str(limiter.window_seconds)},
        )


async def auth_rate_limit(request: Request, bucket: str) -> None:
    """Tighter per-IP budget for one sensitive endpoint.

    Raises a 429 HTTPException (converted to the standard RATE_LIMITED
    envelope with Retry-After by the exception handler) when the bucket
    is exhausted. Buckets are isolated per endpoint name so failed
    logins never block session checks.
    """
    limiter = _auth_limiter(request, bucket)
    ip = request.client.host if request.client else "unknown"
    if not limiter.allow(f"{bucket}:{ip}"):
        logger.warning("Auth rate limit (%s) exceeded for %s", bucket, ip)
        raise HTTPException(
            status_code=429,
            detail="Too many attempts. Please wait and try again.",
            headers={"Retry-After": str(limiter.window_seconds)},
        )
