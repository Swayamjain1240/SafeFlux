"""Scenario and fault definitions (deterministic inputs to the simulator).

A scenario is a duration, a time step, a deterministic list of faults and an
optional list of sensor faults. Everything here is data: no randomness, no
side effects. The engine applies faults at their scheduled start time and
sensor faults to *observed* readings only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FaultType(str, Enum):
    """Deterministic process faults understood by the simulator."""

    COOLING_DEGRADATION = "cooling_degradation"
    COOLING_LOSS = "cooling_loss"
    OUTLET_RESTRICTION = "outlet_restriction"
    VALVE_STUCK = "valve_stuck"
    FEED_INCREASE = "feed_increase"
    PUMP_VARIATION = "pump_variation"


class SensorType(str, Enum):
    TEMPERATURE = "temperature"
    PRESSURE = "pressure"


class SensorFailureMode(str, Enum):
    """How a failed sensor reports relative to the true value."""

    BIAS = "bias"  # observed = true + magnitude
    FREEZE = "freeze"  # observed holds the reading captured when the fault began


@dataclass(frozen=True)
class FaultSpec:
    """One scheduled process fault.

    ``factor`` / ``target_pct`` meaning depends on ``type``:

    - ``cooling_degradation``: ``factor`` in (0, 1] = remaining cooling fraction.
    - ``cooling_loss``: no parameters (equivalent to remaining cooling fraction 0).
    - ``outlet_restriction``: ``factor`` in (0, 1] = remaining outlet capacity.
    - ``valve_stuck``: ``target_pct`` in [0, 100] = pinned valve opening.
    - ``feed_increase``: ``factor`` >= 1 = feed-flow multiplier.
    - ``pump_variation``: ``factor`` >= 0 = pump output multiplier.
    """

    type: FaultType
    start_s: float
    factor: float | None = None
    target_pct: float | None = None


@dataclass(frozen=True)
class SensorFault:
    """A sensor that stops reporting the true value (observed-only effect)."""

    sensor: SensorType
    start_s: float
    mode: SensorFailureMode = SensorFailureMode.BIAS
    magnitude: float = 0.0


@dataclass(frozen=True)
class Scenario:
    """A single deterministic simulation scenario."""

    duration_s: float
    time_step_s: float
    faults: tuple[FaultSpec, ...] = field(default_factory=tuple)
    sensor_faults: tuple[SensorFault, ...] = field(default_factory=tuple)
    label: str = "baseline"
