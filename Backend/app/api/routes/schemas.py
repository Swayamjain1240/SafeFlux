"""Typed response models for API routes."""

from typing import Literal

from pydantic import BaseModel, Field


class HealthData(BaseModel):
    status: Literal["ok"] = "ok"
    service: str
    version: str
    environment: str


class HealthResponse(BaseModel):
    """Success envelope: {"success": true, "data": {...}}"""

    success: Literal[True] = True
    data: HealthData


class ErrorBody(BaseModel):
    code: str = Field(examples=["NOT_FOUND"])
    message: str
    details: list[dict[str, str]] | None = None


class ErrorResponse(BaseModel):
    """Error envelope: {"success": false, "error": {...}}"""

    success: Literal[False] = False
    error: ErrorBody

