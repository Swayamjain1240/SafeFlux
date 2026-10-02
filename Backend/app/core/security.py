"""HTTP security controls: headers middleware + strict CORS allowlist.

Rules: X-Content-Type-Options, Referrer-Policy, frame/CSP protection,
HSTS in production, no wildcard CORS with credentials
(SAFEFLUX_MASTER.md §10–§12).
"""

from __future__ import annotations

import logging

from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.config import Settings
from app.core.responses import error_payload

logger = logging.getLogger("safeflux.security")

# Backend serves JSON only — deny everything by default.
_CSP = (
    "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; "
    "form-action 'none'; img-src 'self' data:; media-src 'self'"
)

_HSTS = "max-age=31536000; includeSubDomains"


def _apply_headers(response: Response, *, settings: Settings, secure_transport: bool) -> None:
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Content-Security-Policy", _CSP)
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
    response.headers.setdefault("Cross-Origin-Resource-Policy", "same-site")
    if settings.is_production and secure_transport:
        response.headers.setdefault("Strict-Transport-Security", _HSTS)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Adds security headers to every response and converts any unhandled
    exception into a safe 500 envelope (no stack traces reach clients)."""

    def __init__(self, app, settings: Settings):  # noqa: ANN001 - ASGI app
        super().__init__(app)
        self._settings = settings

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001 - deliberate catch-all for safe 500s
            logger.exception(
                "Unhandled error on %s %s", request.method, request.url.path
            )
            response = JSONResponse(
                status_code=500,
                content=error_payload(
                    "INTERNAL_ERROR",
                    "An unexpected error occurred. Please try again later.",
                ),
            )
        _apply_headers(
            response,
            settings=self._settings,
            secure_transport=request.url.scheme == "https",
        )
        return response


def add_cors_middleware(app, settings: Settings) -> None:  # noqa: ANN001
    """Strict CORS: explicit origin allowlist, credentials allowed, never `*`."""
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Accept", "Content-Type", "Origin", "X-Requested-With"],
        expose_headers=["Retry-After"],
        max_age=600,
    )
