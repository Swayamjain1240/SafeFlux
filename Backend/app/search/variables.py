"""The allowlisted search variables (Part 7).

The search is driven by a fixed table of *allowlisted* scenario knobs. Every
knob maps to a concrete, typed effect on the deterministic simulator input — a
process fault, a sensor fault, or a safeguard delay. Nothing is evaluated:
there is no ``eval``/``exec``, no generated Python and no shell anywhere in this
package, so a variable name outside this table can never reach the simulator.

That is the whole point of the allowlist (SAFEFLUX_MASTER.md §17): the API
accepts a variable *name* from a client, and the only thing that name can ever
do is select one of the entries below.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.search.constants import VALUE_DECIMALS
from app.simulator.scenario import (
    FaultSpec,
    FaultType,
    SensorFailureMode,
    SensorFault,
    SensorType,
)


class SearchVariable(str, Enum):
    """Every knob the search may vary. Nothing else is accepted."""

    COOLING_FACTOR = "cooling_factor"
    FEED_FACTOR = "feed_factor"
    OUTLET_FACTOR = "outlet_factor"
    VALVE_TARGET_PCT = "valve_target_pct"
    PUMP_FACTOR = "pump_factor"
    SHUTDOWN_DELAY_S = "shutdown_delay_s"
    TEMPERATURE_SENSOR_BIAS_C = "temperature_sensor_bias_c"


class RiskDirection(str, Enum):
    """Which end of a range is expected to be the dangerous one.

    This is a *presentation* hint (it orders an axis and labels an endpoint in
    the UI). It is never used to decide a safety verdict, and the search never
    assumes it is true — a non-monotonic result is a valid outcome.
    """

    DECREASING = "decreasing"
    INCREASING = "increasing"
    NEUTRAL = "neutral"


@dataclass(frozen=True)
class VariableSpec:
    """Bounds and the concrete effect of one allowlisted variable."""

    variable: SearchVariable
    label: str
    unit: str
    minimum: float
    maximum: float
    default: float
    direction: RiskDirection
    fault_type: FaultType | None = None
    sensor: SensorType | None = None
    is_safeguard: bool = False
    # Sensors report, they never actuate: a sensor variable can change what the
    # plant *observes* but never the true trajectory, and the result marks it.
    is_observation_only: bool = False
    #: Value at which this variable does nothing at all (a multiplicative identity
    #: of 1, or a zero sensor bias). ``None`` means the identity depends on the
    #: plant's own configuration, so any value is treated as material.
    neutral: float | None = None

    def contains(self, value: float) -> bool:
        return self.minimum <= value <= self.maximum

    def is_active(self, value: float) -> bool:
        """Whether ``value`` actually changes the simulator input.

        A no-op must not be recorded as a fault: a 0 °C sensor bias or a 1.0
        multiplier is the plant as configured, and counting it as an active
        variable would mislabel a case as sensor-affected or faulted.
        """
        if self.neutral is None:
            return True
        return abs(canonical_value(value) - self.neutral) > 1e-12

    def to_dict(self) -> dict:
        return {
            "variable": self.variable.value,
            "label": self.label,
            "unit": self.unit,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "default": self.default,
            "neutral": self.neutral,
            "direction": self.direction.value,
            "is_safeguard": self.is_safeguard,
            "is_observation_only": self.is_observation_only,
        }


SPECS: dict[SearchVariable, VariableSpec] = {
    SearchVariable.COOLING_FACTOR: VariableSpec(
        variable=SearchVariable.COOLING_FACTOR,
        label="Cooling degradation",
        unit="fraction of cooling retained",
        minimum=0.0,
        maximum=1.0,
        default=1.0,
        direction=RiskDirection.DECREASING,
        fault_type=FaultType.COOLING_DEGRADATION,
        neutral=1.0,
    ),
    SearchVariable.FEED_FACTOR: VariableSpec(
        variable=SearchVariable.FEED_FACTOR,
        label="Feed increase",
        unit="feed-flow multiplier",
        minimum=0.5,
        maximum=5.0,
        default=1.0,
        direction=RiskDirection.INCREASING,
        fault_type=FaultType.FEED_INCREASE,
        neutral=1.0,
    ),
    SearchVariable.OUTLET_FACTOR: VariableSpec(
        variable=SearchVariable.OUTLET_FACTOR,
        label="Outlet restriction",
        unit="fraction of outlet capacity retained",
        minimum=0.0,
        maximum=1.0,
        default=1.0,
        direction=RiskDirection.DECREASING,
        fault_type=FaultType.OUTLET_RESTRICTION,
        neutral=1.0,
    ),
    SearchVariable.VALVE_TARGET_PCT: VariableSpec(
        variable=SearchVariable.VALVE_TARGET_PCT,
        label="Valve stuck position",
        unit="% open",
        minimum=0.0,
        maximum=100.0,
        default=50.0,
        direction=RiskDirection.DECREASING,
        fault_type=FaultType.VALVE_STUCK,
    ),
    SearchVariable.PUMP_FACTOR: VariableSpec(
        variable=SearchVariable.PUMP_FACTOR,
        label="Pump variation",
        unit="pump output multiplier",
        minimum=0.0,
        maximum=2.0,
        default=1.0,
        direction=RiskDirection.NEUTRAL,
        fault_type=FaultType.PUMP_VARIATION,
        neutral=1.0,
    ),
    SearchVariable.SHUTDOWN_DELAY_S: VariableSpec(
        variable=SearchVariable.SHUTDOWN_DELAY_S,
        label="Shutdown delay",
        unit="s",
        minimum=0.0,
        maximum=600.0,
        default=0.0,
        direction=RiskDirection.INCREASING,
        is_safeguard=True,
    ),
    SearchVariable.TEMPERATURE_SENSOR_BIAS_C: VariableSpec(
        variable=SearchVariable.TEMPERATURE_SENSOR_BIAS_C,
        label="Temperature sensor bias",
        unit="°C",
        minimum=-50.0,
        maximum=50.0,
        default=0.0,
        direction=RiskDirection.NEUTRAL,
        sensor=SensorType.TEMPERATURE,
        is_observation_only=True,
        neutral=0.0,
    ),
}

VARIABLE_NAMES: tuple[str, ...] = tuple(spec.variable.value for spec in SPECS.values())

# Variables that are process faults (as opposed to safeguard/observation knobs),
# in a stable order — used by the sensitivity pass and the capabilities payload.
FAULT_VARIABLES: tuple[SearchVariable, ...] = tuple(
    spec.variable
    for spec in SPECS.values()
    if spec.fault_type is not None and spec.variable is not SearchVariable.COOLING_FACTOR
) + (SearchVariable.COOLING_FACTOR,)


def spec_for(variable: SearchVariable | str) -> VariableSpec:
    """Look up the spec, raising a plain ``KeyError`` for anything unknown.

    Callers translate that into a validation error; the message never echoes the
    submitted value.
    """
    if isinstance(variable, SearchVariable):
        return SPECS[variable]
    try:
        return SPECS[SearchVariable(variable)]
    except ValueError:
        raise KeyError(variable) from None


def canonical_value(value: float) -> float:
    """Round a sampled value so derived case keys are stable across runs."""
    return round(float(value), VALUE_DECIMALS)


@dataclass(frozen=True)
class VariableEffect:
    """What one sampled value does to a deterministic simulator input."""

    fault: FaultSpec | None = None
    sensor_fault: SensorFault | None = None
    shutdown_delay_s: float | None = None

    @property
    def observation_only(self) -> bool:
        return self.sensor_fault is not None


def effect_for(spec: VariableSpec, value: float, start_s: float) -> VariableEffect:
    """Map ``(variable, value)`` onto its typed simulator effect.

    A neutral value yields an empty effect: it is the plant as configured, not a
    fault, so nothing is injected.
    """
    value = canonical_value(value)
    if not spec.is_active(value):
        return VariableEffect()
    if spec.is_safeguard:
        return VariableEffect(shutdown_delay_s=value)
    if spec.sensor is not None:
        return VariableEffect(
            sensor_fault=SensorFault(
                sensor=spec.sensor,
                start_s=start_s,
                mode=SensorFailureMode.BIAS,
                magnitude=value,
            )
        )
    if spec.fault_type is FaultType.VALVE_STUCK:
        return VariableEffect(fault=FaultSpec(type=spec.fault_type, start_s=start_s, target_pct=value))
    if spec.fault_type is FaultType.COOLING_LOSS:
        return VariableEffect(fault=FaultSpec(type=spec.fault_type, start_s=start_s))
    return VariableEffect(fault=FaultSpec(type=spec.fault_type, start_s=start_s, factor=value))


def capabilities() -> dict:
    """Public description of the allowlist (no secrets, no internals)."""
    return {
        "variables": [spec.to_dict() for spec in SPECS.values()],
        "variable_names": list(VARIABLE_NAMES),
    }


__all__ = [
    "FAULT_VARIABLES",
    "SPECS",
    "RiskDirection",
    "SearchVariable",
    "VARIABLE_NAMES",
    "VariableEffect",
    "VariableSpec",
    "canonical_value",
    "capabilities",
    "effect_for",
    "spec_for",
]
