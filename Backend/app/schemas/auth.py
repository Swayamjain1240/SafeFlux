"""Pydantic request/response schemas for authentication.

Backend is the security boundary: every rule the frontend validates is
re-validated here (email format, name length, password policy). Error
messages never echo submitted values (SAFEFLUX_MASTER.md §17).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

_NAME_MIN = 2
_NAME_MAX = 120
_PASSWORD_MIN = 8
_PASSWORD_MAX = 128


class SignupRequest(BaseModel):
    """POST /auth/signup — strict extra='forbid' rejects unknown fields."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    fullName: str = Field(min_length=_NAME_MIN, max_length=_NAME_MAX)
    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=_PASSWORD_MIN, max_length=_PASSWORD_MAX)

    @field_validator("password")
    @classmethod
    def _password_not_all_whitespace(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Password must not be only whitespace.")
        return value


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: EmailStr = Field(max_length=254)
    password: str = Field(min_length=1, max_length=_PASSWORD_MAX)


class SessionUser(BaseModel):
    """Never includes password_hash or any credential material."""

    id: str
    fullName: str
    email: str


class SessionData(BaseModel):
    user: SessionUser


class SessionEnvelope(BaseModel):
    """{"success": true, "data": {"user": {...}}}"""

    success: Literal[True] = True
    data: SessionData
