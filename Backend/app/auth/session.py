"""Session cookie helpers.

The session token lives ONLY in an HttpOnly cookie — never in JavaScript,
localStorage, or response bodies (SAFEFLUX_MASTER.md §12).

Cookie policy:
- HttpOnly: always (no script access)
- Secure: production only (dev runs over plain http://localhost)
- SameSite=Lax: blocks cross-site POST CSRF while allowing normal
  top-level navigation; frontend and API share an origin in dev and a
  first-party relationship in production
- Path=/: whole app
- Max-Age: matches JWT expiry (SESSION_TTL_MINUTES)
"""

from __future__ import annotations

from starlette.responses import Response

from app.core.config import Settings

SESSION_COOKIE_NAME = "safeflux_session"


def set_session_cookie(response: Response, token: str, settings: Settings) -> None:
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        max_age=settings.SESSION_TTL_MINUTES * 60,
        path="/",
        secure=settings.is_production,
        httponly=True,
        samesite="lax",
    )


def clear_session_cookie(response: Response, settings: Settings) -> None:
    response.delete_cookie(
        key=SESSION_COOKIE_NAME,
        path="/",
        secure=settings.is_production,
        httponly=True,
        samesite="lax",
    )
