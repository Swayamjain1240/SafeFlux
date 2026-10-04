"""Deterministic fault injection.

Process faults are **step changes** applied at a scheduled time, in start-time
order (ties keep declaration order). There is no randomness: the same fault list
always yields the same parameter trajectory.

Sensor faults are handled separately and deliberately: they alter only the
*observed* reading, never the integrated true state. A failed temperature sensor
cannot cool or heat the vessel — it only misreports it. This keeps
``true_temperature_c`` and ``observed_temperature_c`` separable (Part 4 brief).

Shutdown-delay timing is grid-resolved: a limit crossing detected at a sample
time schedules the pump stop ``trip_delay_s`` later, rounded to the time step.
This is a documented simplification.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from app.simulator.model import ProcessParameters, clamp
from app.simulator.scenario import (
    FaultSpec,
    FaultType,
    SensorFailureMode,
    SensorFault,
    SensorType,
)


def apply_fault(params: ProcessParameters, fault: FaultSpec) -> ProcessParameters:
    """Return ``params`` with one fault applied (pure, no mutation)."""
    kind = fault.type
    if kind is FaultType.COOLING_DEGRADATION:
        factor = clamp(fault.factor if fault.factor is not None else 1.0, 0.0, 1.0)
        return params.with_(cooling_factor=params.cooling_factor * factor)
    if kind is FaultType.COOLING_LOSS:
        return params.with_(cooling_factor=0.0)
    if kind is FaultType.OUTLET_RESTRICTION:
        factor = clamp(fault.factor if fault.factor is not None else 1.0, 0.0, 1.0)
        return params.with_(outlet_factor=params.outlet_factor * factor)
    if kind is FaultType.VALVE_STUCK:
        target = clamp(fault.target_pct if fault.target_pct is not None else 0.0, 0.0, 100.0)
        return params.with_(valve_position_pct=target)
    if kind is FaultType.FEED_INCREASE:
        factor = max(fault.factor if fault.factor is not None else 1.0, 0.0)
        return params.with_(feed_factor=params.feed_factor * factor)
    if kind is FaultType.PUMP_VARIATION:
        factor = max(fault.factor if fault.factor is not None else 1.0, 0.0)
        return params.with_(pump_factor=params.pump_factor * factor)
    raise ValueError(f"unsupported fault type: {kind!r}")


class FaultSchedule:
    """Applies scheduled faults to a base parameter set as time advances."""

    def __init__(self, base: ProcessParameters, faults: Sequence[FaultSpec]) -> None:
        # Stable sort by start time keeps declaration order for ties.
        self._base = base
        self._faults = sorted(faults, key=lambda item: item.start_s)

    @property
    def breakpoints(self) -> list[float]:
        """Scheduled fault times (strictly inside the run) for the integrator."""
        return [f.start_s for f in self._faults if f.start_s > 0.0]

    def params_at(self, t: float) -> ProcessParameters:
        params = self._base
        for fault in self._faults:
            if t >= fault.start_s:
                params = apply_fault(params, fault)
        return params

    def events(self, duration_s: float) -> list[dict[str, object]]:
        """Fault activation events within the run window (for the result)."""
        events: list[dict[str, object]] = []
        for fault in self._faults:
            if fault.start_s > duration_s:
                continue
            detail: dict[str, object] = {"type": fault.type.value}
            if fault.factor is not None:
                detail["factor"] = fault.factor
            if fault.target_pct is not None:
                detail["target_pct"] = fault.target_pct
            events.append(
                {
                    "time_s": float(fault.start_s),
                    "kind": "fault_applied",
                    "detail": detail,
                }
            )
        return events


def apply_sensor_faults(
    true_values: np.ndarray,
    times: np.ndarray,
    sensor_faults: Sequence[SensorFault],
    sensor: SensorType,
) -> np.ndarray:
    """Derive observed readings from true values for one sensor.

    ``BIAS`` shifts every reading after the fault by ``magnitude``.
    ``FREEZE`` holds the reading captured at the first sample at/after the fault
    start (grid-resolved). In both cases the true array is left untouched.
    """
    observed = np.array(true_values, dtype=float, copy=True)
    for fault in sensor_faults:
        if fault.sensor is not sensor:
            continue
        active = np.nonzero(times >= fault.start_s)[0]
        if active.size == 0:
            continue
        start_index = int(active[0])
        if fault.mode is SensorFailureMode.FREEZE:
            observed[start_index:] = observed[start_index]
        else:
            observed[start_index:] = observed[start_index:] + fault.magnitude
    return observed


def sensor_events(
    sensor_faults: Sequence[SensorFault], duration_s: float
) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    for fault in sensor_faults:
        if fault.start_s > duration_s:
            continue
        events.append(
            {
                "time_s": float(fault.start_s),
                "kind": "sensor_fault_applied",
                "detail": {
                    "sensor": fault.sensor.value,
                    "mode": fault.mode.value,
                    "magnitude": fault.magnitude,
                },
            }
        )
    return events
