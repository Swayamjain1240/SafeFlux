"""In-memory fixed-window rate limiting for API endpoints.

Two layers:
1. `RateLimitMiddleware` — global per-IP budget over /api/v1/*.
2. Per-endpoint dependencies — tighter, isolated buckets: `auth_rate_limit(bucket)`
   (signup/login, per IP), `simulation_rate_limit` (per IP), `search_rate_limit`
   (per IP) and `ai_rate_limit` (per authenticated **user**, because AI analysis is
   the only endpoint that can spend provider money; rule 8 of Part 8).

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

from fastapi import Depends, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.auth.dependencies import get_current_user
from app.core.config import Settings
from app.core.responses import error_response
from app.models import User

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


def _server_limiter(
    request: Request,
    store_name: str,
    bucket: str,
    limit: int,
    window_seconds: int,
) -> FixedWindowLimiter:
    """Lazily create and cache one per-app limiter bucket."""
    buckets: dict[str, FixedWindowLimiter] = getattr(request.app.state, store_name)
    limiter = buckets.get(bucket)
    if limiter is None:
        limiter = FixedWindowLimiter(limit, window_seconds)
        buckets[bucket] = limiter
    return limiter


def _auth_limiter(request: Request, bucket: str) -> FixedWindowLimiter:
    settings: Settings = request.app.state.settings
    return _server_limiter(
        request,
        "auth_limiters",
        bucket,
        settings.AUTH_RATE_LIMIT_ATTEMPTS,
        settings.AUTH_RATE_LIMIT_WINDOW_SECONDS,
    )


def _simulation_limiter(request: Request) -> FixedWindowLimiter:
    settings: Settings = request.app.state.settings
    return _server_limiter(
        request,
        "simulation_limiters",
        "run",
        settings.SIM_RATE_LIMIT_RUNS,
        settings.SIM_RATE_LIMIT_WINDOW_SECONDS,
    )


def _search_limiter(request: Request) -> FixedWindowLimiter:
    settings: Settings = request.app.state.settings
    return _server_limiter(
        request,
        "search_limiters",
        "run",
        settings.SEARCH_RATE_LIMIT_RUNS,
        settings.SEARCH_RATE_LIMIT_WINDOW_SECONDS,
    )


def _enforce(limiter: FixedWindowLimiter, key: str, ip: str, label: str, message: str) -> None:
    """Reject with the standard 429 envelope once a bucket is exhausted."""
    if limiter.allow(f"{key}:{ip}"):
        return
    logger.warning("%s rate limit exceeded for %s", label, ip)
    raise HTTPException(
        status_code=429,
        detail=message,
        headers={"Retry-After": str(limiter.window_seconds)},
    )


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


async def simulation_rate_limit(request: Request) -> None:
    """Per-IP budget for the expensive deterministic simulation endpoint.

    Simulation is compute-heavy, so it gets its own tight bucket independent
    of the auth buckets and the global limiter (rule 8).
    """
    _enforce(
        _simulation_limiter(request),
        "simulate",
        _client_ip(request),
        "Simulation",
        "Too many simulation requests. Please wait and try again.",
    )


async def search_rate_limit(request: Request) -> None:
    """Per-IP budget for POST /searches/run.

    A search runs many simulations in one request, so it is the most expensive
    endpoint in the API and gets the tightest bucket of its own (rule 8).
    """
    _enforce(
        _search_limiter(request),
        "search",
        _client_ip(request),
        "Search",
        "Too many search requests. Please wait and try again.",
    )


def _ai_limiter(request: Request) -> FixedWindowLimiter:
    settings: Settings = request.app.state.settings
    return _server_limiter(
        request,
        "ai_limiters",
        "run",
        settings.AI_RATE_LIMIT_RUNS,
        settings.AI_RATE_LIMIT_WINDOW_SECONDS,
    )


def _analysis_limiter(request: Request) -> FixedWindowLimiter:
    """Per-user budget for the Part 9 analysis endpoints.

    One autonomous run executes many simulations (and may spend provider
    tokens for its summary), so like AI analysis it is budgeted per
    authenticated user rather than per IP (rule 8).
    """
    settings: Settings = request.app.state.settings
    return _server_limiter(
        request,
        "analysis_limiters",
        "run",
        settings.ANALYSIS_RATE_LIMIT_RUNS,
        settings.ANALYSIS_RATE_LIMIT_WINDOW_SECONDS,
    )


async def analysis_rate_limit(request: Request, user: User = Depends(get_current_user)) -> None:
    """Per-authenticated-user budget for POST /analyses and comparisons."""
    _enforce(
        _analysis_limiter(request),
        "analysis",
        str(user.id),
        "Analysis",
        "Too many analyses. Please wait and try again.",
    )


async def ai_rate_limit(request: Request, user: User = Depends(get_current_user)) -> None:
    """Per-authenticated-user budget for POST /investigations/run.

    This is the only endpoint that can spend money and model tokens, so it is
    budgeted per *user* rather than per IP: one engineer cannot exhaust the
    provider quota for everyone else behind the same address, and a shared
    office IP does not throttle unrelated users (rule 8 of Part 8).
    """
    _enforce(
        _ai_limiter(request),
        "analysis",
        str(user.id),
        "AI analysis",
        "Too many AI analyses. Please wait and try again.",
    )


async def auth_rate_limit(request: Request, bucket: str) -> None:
    """Tighter per-IP budget for one sensitive endpoint.

    Raises a 429 HTTPException (converted to the standard RATE_LIMITED
    envelope with Retry-After by the exception handler) when the bucket
    is exhausted. Buckets are isolated per endpoint name so failed
    logins never block session checks.
    """
    _enforce(
        _auth_limiter(request, bucket),
        bucket,
        _client_ip(request),
        f"Auth ({bucket})",
        "Too many attempts. Please wait and try again.",
    )
