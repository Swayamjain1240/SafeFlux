"""Signed session tokens (JWT, HS256) — issued and verified with JWT_SECRET.

Rejects expired tokens, invalid signatures, wrong issuer, and malformed
input. Error categories are safe to surface; raw token contents never are.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal

import jwt
from pydantic import SecretStr

ISSUER = "safeflux"
ALGORITHM = "HS256"

TokenErrorReason = Literal["expired", "invalid"]


class TokenValidationError(Exception):
    """Raised when a session token cannot be trusted. Carries a safe reason."""

    def __init__(self, reason: TokenErrorReason) -> None:
        super().__init__(reason)
        self.reason = reason


def create_session_token(user_id: str, secret: SecretStr, ttl_minutes: int) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id,
        "iat": now,
        "exp": now + timedelta(minutes=ttl_minutes),
        "iss": ISSUER,
        "typ": "session",
    }
    return jwt.encode(payload, secret.get_secret_value(), algorithm=ALGORITHM)


def decode_session_token(token: str, secret: SecretStr) -> str:
    """Validate a token and return its subject (user id).

    Raises TokenValidationError with reason "expired" or "invalid" for any
    untrusted input: bad signature, malformed base64/JSON, wrong issuer,
    wrong/absent claims, or an expired `exp`.
    """
    try:
        claims = jwt.decode(
            token,
            secret.get_secret_value(),
            algorithms=[ALGORITHM],
            issuer=ISSUER,
            options={"require": ["sub", "exp", "iat", "iss"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise TokenValidationError("expired") from exc
    except jwt.InvalidTokenError as exc:  # decode/signature/issuer/claim errors
        raise TokenValidationError("invalid") from exc

    subject = claims.get("sub")
    if not isinstance(subject, str) or not subject or len(subject) > 64:
        raise TokenValidationError("invalid")
    if claims.get("typ") != "session":
        raise TokenValidationError("invalid")
    return subject
