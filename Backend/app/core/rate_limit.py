"""Baseline in-memory rate limiting for expensive API endpoints.

Fixed window per client IP. Health checks are exempt so monitoring never
gets throttled. Hard-bounded memory: stale keys are purged and the table is
reset if it ever grows past a safe size.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.responses import error_response

logger = logging.getLogger("safeflux.ratelimit")

_MAX_KEYS = 10_000


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
        self._limit = limit
        self._window = window_seconds
        self._exempt = exempt_paths
        self._buckets: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def _client_key(self, request: Request) -> str:
        # Only the direct connection is trusted; X-Forwarded-For is attacker-controlled.
        return request.client.host if request.client else "unknown"

    def _allow(self, key: str, now: float) -> bool:
        with self._lock:
            if len(self._buckets) > _MAX_KEYS:
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
        if len(self._buckets) > _MAX_KEYS:
            logger.warning("Rate-limit table overflow; resetting buckets")
            self._buckets.clear()

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.url.path in self._exempt or request.method == "OPTIONS":
            return await call_next(request)

        now = time.monotonic()
        if not self._allow(self._client_key(request), now):
            logger.warning(
                "Rate limit exceeded for %s on %s", self._client_key(request), request.url.path
            )
            return error_response(
                429,
                "RATE_LIMITED",
                "Too many requests. Please slow down and try again.",
                headers={"Retry-After": str(self._window)},
            )
        return await call_next(request)
