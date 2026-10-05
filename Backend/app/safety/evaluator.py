"""Deterministic trajectory classification (Part 5).

Reads a simulator result's series and events and classifies each monitored
variable into one of four statuses. No LLM, no heuristics over prose — only
numeric comparisons against configured limits.

Precedence per variable:

- **VIOLATION** — the *actual* (post-safeguard) trajectory exceeds the limit.
- **SAFEGUARD_ACTIVATED** — this variable tripped in the unprotected pass and an
  emergency shutdown was applied, after which the tested run stayed within the
  limit (i.e. the safeguard prevented the violation in the simulation).
- **NEAR_LIMIT** — the trajectory entered the configurable near-limit band but
  never exceeded the limit.
- **SAFE** — nothing approached the limit.
"""

from __future__ import annotations

from app.safety.constants import (
    MONITORED_VARIABLES,
    NO_UNSAFE_CONDITION,
    SAFETY_ENGINE_VERSION,
    SAFETY_LANGUAGE_DISCLAIMER,
)
from app.safety.findings import (
    SafetyAssessment,
    SafetyFinding,
    SafetyStatus,
    SafetyThresholds,
    worst_status,
)
from app.simulator.result import SimulationResult

# Monitored variable → the series it is judged from (true, not observed state).
_SERIES_KEY: dict[str, str] = {
    "temperature_c": "true_temperature_c",
    "pressure_bar": "true_pressure_bar",
    "level_pct": "level_pct",
}


def _first_exceeding(values: list[float], limit: float) -> tuple[int | None, float | None]:
    """Return (index-of-first-exceedance, value) or (None, None)."""
    for index, value in enumerate(values):
        if value > limit:
            return index, float(value)
    return None, None


def _first_at_or_above(values: list[float], threshold: float) -> tuple[int | None, float | None]:
    for index, value in enumerate(values):
        if value >= threshold:
            return index, float(value)
    return None, None


def _crossing_variables(events: list[dict]) -> set[str]:
    return {
        event["detail"].get("variable")
        for event in events
        if event.get("kind") == "limit_exceeded"
    }


def _shutdown_time(events: list[dict]) -> float | None:
    for event in events:
        if event.get("kind") == "shutdown":
            return float(event["time_s"])
    return None


def _classify_variable(
    variable: str,
    times: list[float],
    values: list[float],
    thresholds: SafetyThresholds,
    scenario_id: str | None,
    crossed: set[str],
    shutdown_time: float | None,
) -> SafetyFinding:
    limit = thresholds.limit_for(variable)
    near_limit = thresholds.near_limit_for(variable)
    peak_index = max(range(len(values)), key=lambda i: values[i]) if values else None
    peak = values[peak_index] if peak_index is not None else None
    peak_time = times[peak_index] if peak_index is not None else None

    exceed_index, exceed_value = _first_exceeding(values, limit)
    if exceed_index is not None:
        return SafetyFinding(
            variable=variable,
            status=SafetyStatus.VIOLATION,
            timestamp_s=times[exceed_index] if exceed_index < len(times) else None,
            measured_value=exceed_value,
            limit=limit,
            near_limit=near_limit,
            scenario_id=scenario_id,
            message=(
                f"{variable} exceeded its configured limit in the tested simulation "
                "(the applied safeguard was not sufficient)."
            ),
        )

    if variable in crossed and shutdown_time is not None:
        at_shutdown = values[min(range(len(values)), key=lambda i: abs(times[i] - shutdown_time))] if values else None
        return SafetyFinding(
            variable=variable,
            status=SafetyStatus.SAFEGUARD_ACTIVATED,
            timestamp_s=shutdown_time,
            measured_value=at_shutdown,
            limit=limit,
            near_limit=near_limit,
            scenario_id=scenario_id,
            message=(
                f"{variable} tripped in the unprotected pass; the applied safeguard "
                "kept the tested run within its limit."
            ),
        )

    near_index, near_value = _first_at_or_above(values, near_limit)
    if near_index is not None:
        return SafetyFinding(
            variable=variable,
            status=SafetyStatus.NEAR_LIMIT,
            timestamp_s=times[near_index] if near_index < len(times) else None,
            measured_value=near_value,
            limit=limit,
            near_limit=near_limit,
            scenario_id=scenario_id,
            message=f"{variable} entered the near-limit band without exceeding its limit.",
        )

    return SafetyFinding(
        variable=variable,
        status=SafetyStatus.SAFE,
        timestamp_s=peak_time,
        measured_value=peak,
        limit=limit,
        near_limit=near_limit,
        scenario_id=scenario_id,
        message=NO_UNSAFE_CONDITION,
    )


def evaluate_simulation(
    result: SimulationResult,
    thresholds: SafetyThresholds,
    scenario_id: str | None = None,
) -> SafetyAssessment:
    """Classify every monitored variable in one deterministic simulator result."""
    series = result.series
    times = [float(value) for value in series.get("time_s", [])]
    events = list(result.events)
    crossed = _crossing_variables(events)
    shutdown_time = _shutdown_time(events)

    findings: list[SafetyFinding] = []
    for variable in MONITORED_VARIABLES:
        values = [float(value) for value in series.get(_SERIES_KEY[variable], [])]
        if not values:
            continue
        findings.append(
            _classify_variable(
                variable,
                times,
                values,
                thresholds,
                scenario_id,
                crossed,
                shutdown_time,
            )
        )

    overall = worst_status([finding.status for finding in findings])
    summary = {
        "variables": len(findings),
        "violations": [
            f.variable for f in findings if f.status is SafetyStatus.VIOLATION
        ],
        "near_limit": [
            f.variable for f in findings if f.status is SafetyStatus.NEAR_LIMIT
        ],
        "safeguards_activated": [
            f.variable for f in findings if f.status is SafetyStatus.SAFEGUARD_ACTIVATED
        ],
        "worst_severity": findings[0].severity if findings else "none",
    }
    # Recompute worst severity from the overall status for accuracy.
    summary["worst_severity"] = {
        SafetyStatus.SAFE: "none",
        SafetyStatus.NEAR_LIMIT: "low",
        SafetyStatus.SAFEGUARD_ACTIVATED: "high",
        SafetyStatus.VIOLATION: "critical",
    }[overall]

    metadata = {
        "engine_version": SAFETY_ENGINE_VERSION,
        "deterministic": True,
        "thresholds": thresholds.to_dict(),
        "variables": list(MONITORED_VARIABLES),
        "disclaimer": SAFETY_LANGUAGE_DISCLAIMER,
    }

    return SafetyAssessment(
        status=overall,
        findings=findings,
        scenario_id=scenario_id,
        summary=summary,
        metadata=metadata,
    )
