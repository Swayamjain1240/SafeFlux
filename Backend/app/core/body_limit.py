"""Request body size guard (SAFEFLUX_MASTER.md §6 form/request validation).

Rejects oversized request bodies *before* they are parsed by the framework,
returning the standard 413 error envelope. Applies to body-carrying methods
only; health probes and normal GETs are unaffected.
"""

from __future__ import annotations

import logging

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.responses import error_response

logger = logging.getLogger("safeflux.bodylimit")

_BODY_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class BodySizeLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, max_bytes: int):  # noqa: ANN001 - ASGI app
        super().__init__(app)
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in _BODY_METHODS:
            declared = request.headers.get("content-length")
            if declared is not None and declared.isdigit() and int(declared) > self._max_bytes:
                logger.warning(
                    "Rejected oversized request (%s bytes) on %s",
                    declared,
                    request.url.path,
                )
                return error_response(
                    413,
                    "PAYLOAD_TOO_LARGE",
                    "The request body is too large.",
                )
        return await call_next(request)
