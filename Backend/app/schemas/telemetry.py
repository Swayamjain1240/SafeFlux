"""Pydantic response schemas for telemetry endpoints (Part 5).

These document and type the read-only telemetry API. They never expose owner
ids or internals — only simulated process values, configured limits and status.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class TelemetryFrameOut(BaseModel):
    type: Literal["telemetry"] = "telemetry"
    plant_id: str
    sequence: int
    time_s: float
    status: str
    values: dict[str, float]
    observed: dict[str, float]
    limits: dict[str, float]
    near_limits: dict[str, float]
    pump_running: bool


class TelemetryCurrentData(BaseModel):
    plantId: str
    frame: TelemetryFrameOut | None = None


class TelemetryHistoryData(BaseModel):
    plantId: str
    count: int
    limit: int
    frames: list[TelemetryFrameOut]


class TelemetryCurrentEnvelope(BaseModel):
    success: Literal[True] = True
    data: TelemetryCurrentData


class TelemetryHistoryEnvelope(BaseModel):
    success: Literal[True] = True
    data: TelemetryHistoryData
