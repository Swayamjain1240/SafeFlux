"""Reusable authorization dependencies.

`get_current_user()` is the single source of truth for identity on every
protected endpoint. It never accepts a user id from the request body,
query, or headers — identity comes only from the verified session cookie
(SAFEFLUX_MASTER.md §12: never trust frontend-supplied owner IDs).
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.auth.session import SESSION_COOKIE_NAME
from app.auth.tokens import TokenValidationError, decode_session_token
from app.database import get_db
from app.models import User


def _unauthorized(message: str) -> HTTPException:
    # Cookie-based sessions don't use WWW-Authenticate (no Authorization header).
    return HTTPException(status_code=401, detail=message)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Resolve the authenticated, active user from the session cookie.

    Raises 401 for: missing cookie, expired token, tampered/malformed
    token, unknown user, and deactivated accounts. Safe, generic messages
    only — no token contents, no user enumeration.
    """
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        raise _unauthorized("You must be signed in to perform this action.")

    try:
        user_id = decode_session_token(token, request.app.state.settings.JWT_SECRET)
    except TokenValidationError as exc:
        if exc.reason == "expired":
            raise _unauthorized("Your session has expired. Please sign in again.") from exc
        raise _unauthorized("Your session is invalid. Please sign in again.") from exc

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _unauthorized("Your session is invalid. Please sign in again.")
    return user
