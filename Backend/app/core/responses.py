"""Consistent API response envelope (SAFEFLUX_MASTER.md §17).

Success: {"success": true, "data": ...}
Error:   {"success": false, "error": {"code": ..., "message": ..., "details": [...]}}
"""

from __future__ import annotations

from typing import Any, Literal

from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field


class FieldError(BaseModel):
    """Sanitized per-field validation message. Never contains submitted values."""

    field: str
    message: str


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: list[FieldError] | None = None


class ApiError(BaseModel):
    success: Literal[False] = False
    error: ErrorDetail


class ApiSuccess(BaseModel):
    success: Literal[True] = True
    data: Any


def success_response(data: Any) -> dict[str, Any]:
    """Wrap a payload in the success envelope."""
    return {"success": True, "data": data}


def error_payload(
    code: str,
    message: str,
    details: list[FieldError] | None = None,
) -> dict[str, Any]:
    """Build the error envelope body (no internal details, ever)."""
    return {
        "success": False,
        "error": ErrorDetail(code=code, message=message, details=details).model_dump(
            exclude_none=True
        ),
    }


def error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[FieldError] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Return a JSON error response in the standard envelope."""
    return JSONResponse(
        status_code=status_code,
        content=error_payload(code, message, details),
        headers=headers,
    )
