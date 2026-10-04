"""Pydantic schemas for plant setup and configuration.

The backend is the security and correctness boundary: every range below is
re-validated server-side regardless of what the wizard sent. Units live in
field names. `extra="forbid"` rejects unknown fields, and errors never echo
submitted values (SAFEFLUX_MASTER.md §17).

Bounds are deliberately conservative "engineering sanity" ranges for the
locked MVP process — they are design limits, never live control setpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# --- sane engineering bounds for the MVP process -------------------------
FEED_FLOW_MAX_LPM = 500.0
COOLING_MIN_PCT, COOLING_MAX_PCT = 0.0, 100.0
VALVE_MIN_PCT, VALVE_MAX_PCT = 0.0, 100.0
HEATER_MIN_PCT, HEATER_MAX_PCT = 0.0, 100.0
SHUTDOWN_DELAY_MAX_S = 3600
TRIP_DELAY_MAX_S = 3600

TEMPERATURE_MIN_C, TEMPERATURE_MAX_C = -50.0, 1000.0
PRESSURE_MIN_BAR, PRESSURE_MAX_BAR = 0.0, 500.0
LEVEL_MIN_PCT, LEVEL_MAX_PCT = 0.0, 100.0

NAME_MIN, NAME_MAX = 1, 120
DESCRIPTION_MAX = 500
LOCATION_MAX = 120


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PlantConfigIn(_StrictModel):
    """Step 2 — operating conditions."""

    feed_flow_lpm: float = Field(ge=0, le=FEED_FLOW_MAX_LPM)
    cooling_pct: float = Field(ge=COOLING_MIN_PCT, le=COOLING_MAX_PCT)
    valve_position_pct: float = Field(ge=VALVE_MIN_PCT, le=VALVE_MAX_PCT)
    heater_power_pct: float = Field(ge=HEATER_MIN_PCT, le=HEATER_MAX_PCT)
    shutdown_delay_s: int = Field(ge=0, le=SHUTDOWN_DELAY_MAX_S)


class PlantStateIn(_StrictModel):
    """Step 3 — equipment / initial process state."""

    pump_running: bool
    temperature_c: float = Field(ge=TEMPERATURE_MIN_C, le=TEMPERATURE_MAX_C)
    pressure_bar: float = Field(ge=PRESSURE_MIN_BAR, le=PRESSURE_MAX_BAR)
    level_pct: float = Field(ge=LEVEL_MIN_PCT, le=LEVEL_MAX_PCT)


class SafetyLimitsIn(_StrictModel):
    """Step 4a — configured trip limits."""

    max_temperature_c: float = Field(ge=TEMPERATURE_MIN_C, le=TEMPERATURE_MAX_C)
    max_pressure_bar: float = Field(ge=PRESSURE_MIN_BAR, le=PRESSURE_MAX_BAR)
    max_level_pct: float = Field(ge=LEVEL_MIN_PCT, le=LEVEL_MAX_PCT)


class SafeguardConfigIn(_StrictModel):
    """Step 4b — armed safeguards and their timing."""

    auto_shutdown_enabled: bool = True
    high_temperature_trip: bool = True
    high_pressure_trip: bool = True
    high_level_trip: bool = True
    trip_delay_s: int = Field(default=2, ge=0, le=TRIP_DELAY_MAX_S)


class PlantCreate(_StrictModel):
    """POST /plants — identity + all nested configuration in one payload."""

    name: str = Field(min_length=NAME_MIN, max_length=NAME_MAX)
    description: str = Field(default="", max_length=DESCRIPTION_MAX)
    location: str = Field(default="", max_length=LOCATION_MAX)
    config: PlantConfigIn
    state: PlantStateIn
    safety_limits: SafetyLimitsIn
    safeguards: SafeguardConfigIn = Field(default_factory=SafeguardConfigIn)

    @model_validator(mode="after")
    def _initial_condition_below_limits(self) -> "PlantCreate":
        """The initial state must not already sit above a configured trip limit."""
        if self.state.temperature_c > self.safety_limits.max_temperature_c:
            raise ValueError(
                "Initial temperature exceeds the configured maximum temperature limit."
            )
        if self.state.pressure_bar > self.safety_limits.max_pressure_bar:
            raise ValueError(
                "Initial pressure exceeds the configured maximum pressure limit."
            )
        if self.state.level_pct > self.safety_limits.max_level_pct:
            raise ValueError(
                "Initial level exceeds the configured maximum level limit."
            )
        return self


class PlantUpdate(_StrictModel):
    """PATCH /plants/{id} — every field optional; only provided fields change.

    Nested blocks are replaced wholesale when present so a partial nested
    object can never silently drop validation. Ownership is never part of
    the payload.
    """

    name: str | None = Field(default=None, min_length=NAME_MIN, max_length=NAME_MAX)
    description: str | None = Field(default=None, max_length=DESCRIPTION_MAX)
    location: str | None = Field(default=None, max_length=LOCATION_MAX)
    config: PlantConfigIn | None = None
    state: PlantStateIn | None = None
    safety_limits: SafetyLimitsIn | None = None
    safeguards: SafeguardConfigIn | None = None


# --- response models (never expose owner_id) -----------------------------


class PlantConfigOut(PlantConfigIn):
    pass


class PlantStateOut(PlantStateIn):
    pass


class SafetyLimitsOut(SafetyLimitsIn):
    pass


class SafeguardConfigOut(SafeguardConfigIn):
    pass


class PlantSummary(BaseModel):
    """List row — no nested blocks, keeps the list payload small."""

    id: str
    name: str
    description: str
    location: str
    created_at: datetime
    updated_at: datetime


class PlantDetail(BaseModel):
    id: str
    name: str
    description: str
    location: str
    config: PlantConfigOut
    state: PlantStateOut
    safety_limits: SafetyLimitsOut
    safeguards: SafeguardConfigOut
    created_at: datetime
    updated_at: datetime


class PlantListData(BaseModel):
    plants: list[PlantSummary]


class PlantDetailData(BaseModel):
    plant: PlantDetail


class PlantStateData(BaseModel):
    """GET /plants/{id}/state — the initial dynamic condition only."""

    plantId: str
    state: PlantStateOut


class PlantListEnvelope(BaseModel):
    success: Literal[True] = True
    data: PlantListData


class PlantDetailEnvelope(BaseModel):
    success: Literal[True] = True
    data: PlantDetailData


class PlantStateEnvelope(BaseModel):
    success: Literal[True] = True
    data: PlantStateData
