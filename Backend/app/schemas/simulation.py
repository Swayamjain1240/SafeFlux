"""Pydantic schemas for the simulation endpoint.

Strict (``extra=\"forbid\"``) request models for one deterministic run. Numeric
*sanity* bounds live here; the hard compute budgets (max duration, min time
step, max samples) are enforced server-side against Settings by the route so
they stay centrally configurable. Validation errors never echo submitted values.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.simulator.scenario import FaultType, SensorFailureMode, SensorType

MAX_FAULTS = 32
MAX_SENSOR_FAULTS = 8


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class FaultIn(_StrictModel):
    """One deterministic process fault."""

    type: FaultType
    start_s: float = Field(ge=0, le=1_000_000)
    factor: float | None = Field(default=None, ge=0, le=100)
    target_pct: float | None = Field(default=None, ge=0, le=100)

    @model_validator(mode="after")
    def _required_parameters(self) -> "FaultIn":
        needs_factor = {
            FaultType.COOLING_DEGRADATION,
            FaultType.OUTLET_RESTRICTION,
            FaultType.FEED_INCREASE,
            FaultType.PUMP_VARIATION,
        }
        if self.type in needs_factor and self.factor is None:
            raise ValueError("This fault type requires a 'factor'.")
        if self.type is FaultType.VALVE_STUCK and self.target_pct is None:
            raise ValueError("valve_stuck requires a 'target_pct'.")
        return self


class SensorFaultIn(_StrictModel):
    """A sensor fault that affects observed readings only."""

    sensor: SensorType
    start_s: float = Field(ge=0, le=1_000_000)
    mode: SensorFailureMode = SensorFailureMode.BIAS
    magnitude: float = Field(default=0.0, ge=-1000, le=1000)


class ScenarioIn(_StrictModel):
    duration_s: float = Field(gt=0)
    time_step_s: float = Field(gt=0)
    label: str = Field(default="scenario", max_length=120)
    faults: list[FaultIn] = Field(default_factory=list, max_length=MAX_FAULTS)
    sensor_faults: list[SensorFaultIn] = Field(default_factory=list, max_length=MAX_SENSOR_FAULTS)

    @model_validator(mode="after")
    def _starts_within_duration(self) -> "ScenarioIn":
        for fault in self.faults:
            if fault.start_s > self.duration_s:
                raise ValueError("A fault start time is beyond the scenario duration.")
        for sensor_fault in self.sensor_faults:
            if sensor_fault.start_s > self.duration_s:
                raise ValueError("A sensor fault start time is beyond the scenario duration.")
        return self


class SimulationRunRequest(_StrictModel):
    """POST /simulations/run — the plant supplies config, state, limits and safeguards."""

    plant_id: str = Field(min_length=1, max_length=64)
    scenario: ScenarioIn = Field(default_factory=lambda: ScenarioIn(duration_s=300, time_step_s=1.0))
