"""Argon2id password hashing (SAFEFLUX_MASTER.md §12/§17).

Plaintext passwords are never stored, logged, or returned. Verification
failures (wrong password, malformed/foreign hash) are all treated as
`False` so callers cannot distinguish them.
"""

from __future__ import annotations

import logging

from argon2 import PasswordHasher
from argon2.exceptions import (
    HashingError,
    InvalidHashError,
    VerificationError,
    VerifyMismatchError,
)

logger = logging.getLogger("safeflux.auth")

# OWASP-aligned defaults (argon2id): ~19 MiB, t=2, p=1 by library default.
_hasher = PasswordHasher()

# Lazily built dummy hash used to equalize timing when an email is unknown.
_dummy_hash: str | None = None


def hash_password(password: str) -> str:
    """Return a salted Argon2id hash. Raises HashingError only on real failure."""
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Constant-behaviour verification: True only on exact match."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False
    except Exception:  # noqa: BLE001 - never leak argon2 internals to callers
        logger.exception("Unexpected password verification failure")
        return False


def burn_verify_time(password: str) -> None:
    """Spend comparable CPU on unknown accounts to blunt user-enumeration timing."""
    global _dummy_hash
    if _dummy_hash is None:
        try:
            _dummy_hash = hash_password("timing-equalization-dummy-password")
        except HashingError:  # pragma: no cover - argon2 misconfiguration
            logger.exception("Could not build dummy password hash")
            return
    verify_password(_dummy_hash, password)
