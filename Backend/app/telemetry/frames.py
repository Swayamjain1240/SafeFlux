"""Telemetry frames built from deterministic simulator output (Part 5).

A ``TelemetryFrame`` is one timestep of the current-state store. True process
values and observed sensor values stay separate, exactly as in the simulator
(``temperature_c`` vs ``observed_temperature_c``), so a sensor fault can never
change the physics shown to the operator.

Per-frame status is a cheap deterministic comparison against the configured
near-limit band; it is display telemetry, not the scenario verdict — the full
verdict comes from the safety engine's ``SafetyAssessment``.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.safety.findings import SafetyStatus
from app.telemetry.constants import TELEMETRY_VERSION
from app.simulator.result import SimulationResult

_NUMERIC_SERIES: dict[str, str] = {
    "temperature_c": "true_temperature_c",
    "pressure_bar": "true_pressure_bar",
    "level_pct": "level_pct",
    "feed_flow_lpm": "feed_flow_lpm",
    "outlet_flow_lpm": "outlet_flow_lpm",
}
_OBSERVED_SERIES: dict[str, str] = {
    "temperature_c": "observed_temperature_c",
    "pressure_bar": "observed_pressure_bar",
}
_STATUS_RANK = {
    SafetyStatus.SAFE: 0,
    SafetyStatus.NEAR_LIMIT: 1,
    SafetyStatus.SAFEGUARD_ACTIVATED: 2,
    SafetyStatus.VIOLATION: 3,
}


@dataclass(frozen=True)
class TelemetryFrame:
    """One timestamped sample of simulated plant telemetry."""

    plant_id: str
    sequence: int
    time_s: float
    status: str
    values: dict[str, float]
    observed: dict[str, float]
    limits: dict[str, float]
    near_limits: dict[str, float]
    pump_running: bool

    def to_dict(self) -> dict:
        return {
            "type": "telemetry",
            "plant_id": self.plant_id,
            "sequence": self.sequence,
            "time_s": self.time_s,
            "status": self.status,
            "values": self.values,
            "observed": self.observed,
            "limits": self.limits,
            "near_limits": self.near_limits,
            "pump_running": self.pump_running,
        }


def _frame_status(values: dict[str, float], near_limits: dict[str, float], limits: dict[str, float]) -> SafetyStatus:
    status = SafetyStatus.SAFE
    for variable, value in values.items():
        if variable not in limits:
            continue
        if value > limits[variable]:
            candidate = SafetyStatus.VIOLATION
        elif value >= near_limits[variable]:
            candidate = SafetyStatus.NEAR_LIMIT
        else:
            candidate = SafetyStatus.SAFE
        if _STATUS_RANK[candidate] > _STATUS_RANK[status]:
            status = candidate
    return status


def build_frames(
    result: SimulationResult,
    plant_id: str,
    limits: dict[str, float],
    near_limits: dict[str, float],
    start_sequence: int = 0,
) -> list[TelemetryFrame]:
    """Convert a simulator result into one frame per sample (chronological)."""
    series = result.series
    times = series.get("time_s", [])
    frames: list[TelemetryFrame] = []
    for index, time_s in enumerate(times):
        values = {
            name: float(series[key][index])
            for name, key in _NUMERIC_SERIES.items()
            if key in series and index < len(series[key])
        }
        observed = {
            name: float(series[key][index])
            for name, key in _OBSERVED_SERIES.items()
            if key in series and index < len(series[key])
        }
        pump_running = bool(series.get("pump_running", [True] * len(times))[index])
        frames.append(
            TelemetryFrame(
                plant_id=plant_id,
                sequence=start_sequence + index,
                time_s=float(time_s),
                status=_frame_status(values, near_limits, limits).value,
                values=values,
                observed=observed,
                limits=dict(limits),
                near_limits=dict(near_limits),
                pump_running=pump_running,
            )
        )
    return frames


def telemetry_metadata() -> dict:
    return {"telemetry_version": TELEMETRY_VERSION, "source": "deterministic-simulator"}


__all__ = ["TelemetryFrame", "build_frames", "telemetry_metadata"]
