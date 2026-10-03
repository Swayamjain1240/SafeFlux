"""Authentication endpoints: signup, login, logout, session.

Paths are `/api/v1/auth/*` (Part 1 fixed the API prefix at /api/v1; the
Part 2 brief's `/api/auth/*` maps onto it — documented in ARCHITECTURE §9).

Security posture:
- passwords hashed with Argon2id, plaintext never stored or logged,
- session lives in an HttpOnly cookie signed with JWT_SECRET,
- duplicate emails rejected case-insensitively (409),
- per-IP rate limits on signup/login,
- responses only ever expose {id, fullName, email}.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.passwords import burn_verify_time, hash_password, verify_password
from app.auth.session import clear_session_cookie, set_session_cookie
from app.auth.tokens import create_session_token
from app.core.config import Settings
from app.core.rate_limit import auth_rate_limit
from app.core.responses import error_response, success_response
from app.database import get_db
from app.models import User
from app.schemas import LoginRequest, SessionEnvelope, SignupRequest

logger = logging.getLogger("safeflux.auth")

router = APIRouter(prefix="/auth")

_SESSION_DESCRIPTION = {"description": "Authenticated session"}


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _session_payload(user: User) -> dict:
    return {
        "user": {
            "id": user.id,
            "fullName": user.full_name,
            "email": user.email,
        }
    }


def _issue_session(response: Response, user: User, settings: Settings) -> dict:
    token = create_session_token(
        user_id=user.id,
        secret=settings.JWT_SECRET,
        ttl_minutes=settings.SESSION_TTL_MINUTES,
    )
    set_session_cookie(response, token, settings)
    return success_response(_session_payload(user))


async def signup_rate_limit(request: Request) -> None:
    await auth_rate_limit(request, "signup")


async def login_rate_limit(request: Request) -> None:
    await auth_rate_limit(request, "login")


@router.post(
    "/signup",
    status_code=status.HTTP_201_CREATED,
    response_model=SessionEnvelope,
    responses={409: _SESSION_DESCRIPTION, 422: _SESSION_DESCRIPTION, 429: _SESSION_DESCRIPTION},
    summary="Create an account and start a session",
)
def signup(
    payload: SignupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _: None = Depends(signup_rate_limit),
) -> dict:
    settings = _settings(request)
    email = str(payload.email).strip().lower()

    existing = db.scalar(select(User).where(func.lower(User.email) == email))
    if existing is not None:
        return error_response(
            status.HTTP_409_CONFLICT,
            "CONFLICT",
            "An account with this email already exists.",
        )

    user = User(
        full_name=payload.fullName.strip(),
        email=email,
        password_hash=hash_password(payload.password),
        is_active=True,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        # Unique-email race: another request registered between check and insert.
        db.rollback()
        logger.info("Signup race on duplicate email")
        return error_response(
            status.HTTP_409_CONFLICT,
            "CONFLICT",
            "An account with this email already exists.",
        )
    db.refresh(user)
    logger.info("User registered: %s", user.id)
    return _issue_session(response, user, settings)


@router.post(
    "/login",
    response_model=SessionEnvelope,
    responses={401: _SESSION_DESCRIPTION, 422: _SESSION_DESCRIPTION, 429: _SESSION_DESCRIPTION},
    summary="Sign in and start a session",
)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _: None = Depends(login_rate_limit),
) -> dict:
    settings = _settings(request)
    email = str(payload.email).strip().lower()

    user = db.scalar(select(User).where(func.lower(User.email) == email))
    if user is None:
        # Equalize CPU time so response timing cannot enumerate accounts.
        burn_verify_time(payload.password)
        return error_response(
            status.HTTP_401_UNAUTHORIZED,
            "UNAUTHORIZED",
            "Invalid email or password.",
        )

    if not verify_password(user.password_hash, payload.password) or not user.is_active:
        return error_response(
            status.HTTP_401_UNAUTHORIZED,
            "UNAUTHORIZED",
            "Invalid email or password.",
        )

    logger.info("Login succeeded for user %s", user.id)
    return _issue_session(response, user, settings)


@router.post(
    "/logout",
    status_code=status.HTTP_200_OK,
    summary="Clear the session cookie",
)
def logout(request: Request, response: Response) -> dict:
    # Stateless JWT: clearing the cookie ends this client's session.
    # Always idempotent, never reveals whether a session existed.
    clear_session_cookie(response, _settings(request))
    return success_response({"message": "Signed out."})


@router.get(
    "/me",
    response_model=SessionEnvelope,
    responses={401: _SESSION_DESCRIPTION},
    summary="Current authenticated user",
)
def me(user: User = Depends(get_current_user)) -> dict:
    return success_response(_session_payload(user))


# The frontend AuthProvider queries GET /auth/session; it is a strict
# alias of /auth/me so there is exactly one session-check implementation.
@router.get(
    "/session",
    response_model=SessionEnvelope,
    responses={401: _SESSION_DESCRIPTION},
    summary="Current authenticated user (session alias)",
    include_in_schema=False,
)
def session(user: User = Depends(get_current_user)) -> dict:
    return success_response(_session_payload(user))
