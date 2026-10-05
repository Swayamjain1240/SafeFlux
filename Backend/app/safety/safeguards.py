"""Deterministic safeguard timing (Part 5).

Models the alarm/shutdown layer over one simulator result and records, for each
safeguard in the tested scenario:

- **trigger time** — when the safeguard's setpoint was first crossed,
- **response time** — when the modelled action became effective,
- **violation time** — when the *actual* protected trajectory first exceeded a
  configured limit (``None`` if the safeguard averted it).

A verdict of *prevented* means the tested simulation stayed within limits; it is
never a statement about a real plant.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.safety.constants import NO_REAL_PLANT_CLAIM, NO_UNSAFE_CONDITION
from app.safety.findings import SafetyThresholds
from app.simulator.engine import SafeguardSettings
from app.simulator.result import SimulationResult

_ALARM_VARIABLES: tuple[tuple[str, str, str], ...] = (
    # (safeguard name, monitored variable, series key)
    ("high_temperature_alarm", "temperature_c", "true_temperature_c"),
    ("high_pressure_alarm", "pressure_bar", "true_pressure_bar"),
    ("high_level_alarm", "level_pct", "level_pct"),
)

_ARMED_ATTR: dict[str, str] = {
    "high_temperature_alarm": "high_temperature_trip",
    "high_pressure_alarm": "high_pressure_trip",
    "high_level_alarm": "high_level_trip",
}

_ACTUAL_SERIES: dict[str, str] = {
    "temperature_c": "true_temperature_c",
    "pressure_bar": "true_pressure_bar",
    "level_pct": "level_pct",
}


@dataclass(frozen=True)
class SafeguardTiming:
    """Trigger / response / violation timing for one modelled safeguard."""

    safeguard: str
    variable: str | None
    trigger_time_s: float | None
    response_time_s: float | None
    violation_time_s: float | None
    prevented: bool | None
    note: str

    def to_dict(self) -> dict:
        return {
            "safeguard": self.safeguard,
            "variable": self.variable,
            "trigger_time_s": self.trigger_time_s,
            "response_time_s": self.response_time_s,
            "violation_time_s": self.violation_time_s,
            "prevented": self.prevented,
            "note": self.note,
        }


def _first_exceed_time(times: list[float], values: list[float], limit: float) -> float | None:
    for index, value in enumerate(values):
        if value > limit:
            return times[index] if index < len(times) else None
    return None


def _first_at_or_above_time(times: list[float], values: list[float], threshold: float) -> float | None:
    for index, value in enumerate(values):
        if value >= threshold:
            return times[index] if index < len(times) else None
    return None


def _shutdown_time(events: list[dict]) -> float | None:
    for event in events:
        if event.get("kind") == "shutdown":
            return float(event["time_s"])
    return None


def _trip_crossings(events: list[dict]) -> list[tuple[float, str]]:
    crossings: list[tuple[float, str]] = []
    for event in events:
        if event.get("kind") == "limit_exceeded":
            crossings.append((float(event["time_s"]), event["detail"].get("variable")))
    return sorted(crossings)


def evaluate_safeguards(
    result: SimulationResult,
    thresholds: SafetyThresholds,
    safeguards: SafeguardSettings,
) -> list[SafeguardTiming]:
    """Return timing/verdict records for alarms and emergency shutdown."""
    times = [float(value) for value in result.series.get("time_s", [])]
    timings: list[SafeguardTiming] = []

    # --- alarms: fire when the variable reaches its near-limit band ----------
    for name, variable, series_key in _ALARM_VARIABLES:
        if not getattr(safeguards, _ARMED_ATTR[name]):
            continue
        values = [float(value) for value in result.series.get(series_key, [])]
        if not values:
            continue
        trigger = _first_at_or_above_time(times, values, thresholds.near_limit_for(variable))
        violation = _first_exceed_time(times, values, thresholds.limit_for(variable))
        prevented = None if trigger is None else violation is None
        note = (
            "alarm setpoint not reached in the tested scenario"
            if trigger is None
            else NO_UNSAFE_CONDITION
            if prevented
            else "the tested trajectory still exceeded the limit after the alarm."
        )
        timings.append(
            SafeguardTiming(
                safeguard=name,
                variable=variable,
                trigger_time_s=trigger,
                response_time_s=trigger,  # an alarm annunciates immediately
                violation_time_s=violation,
                prevented=prevented,
                note=note,
            )
        )

    # --- emergency shutdown: response to the first armed trip -----------------
    if safeguards.auto_shutdown_enabled:
        response = _shutdown_time(result.events)
        crossings = _trip_crossings(result.events)
        trigger = crossings[0][0] if crossings else None
        # First actual exceedance across all monitored variables in the
        # protected trajectory.
        violation: float | None = None
        for variable, series_key in _ACTUAL_SERIES.items():
            values = [float(value) for value in result.series.get(series_key, [])]
            if not values:
                continue
            candidate = _first_exceed_time(times, values, thresholds.limit_for(variable))
            if candidate is not None and (violation is None or candidate < violation):
                violation = candidate
        prevented = None if response is None else violation is None
        if response is None:
            note = "no armed trip crossing was reached in the tested scenario"
        elif prevented:
            note = f"{NO_UNSAFE_CONDITION} {NO_REAL_PLANT_CLAIM}"
        else:
            note = (
                "the simulated response was too late: the protected trajectory still "
                f"exceeded a limit at {violation:.3g}s. {NO_REAL_PLANT_CLAIM}"
            )
        timings.append(
            SafeguardTiming(
                safeguard="emergency_shutdown",
                variable=crossings[0][1] if crossings else None,
                trigger_time_s=trigger,
                response_time_s=response,
                violation_time_s=violation,
                prevented=prevented,
                note=note,
            )
        )

    return timings


__all__ = ["SafeguardTiming", "evaluate_safeguards"]
