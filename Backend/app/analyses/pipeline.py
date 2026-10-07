"""Pure assembly of the Part 9 documents (failure detail, reverify, report).

These builders turn the *stored result document* plus one real simulation into
the shapes the pages and the PDF renderer consume. They never invent values:
every trajectory comes from the Part 4 simulator through the Part 5 assessor,
every comparison status from the same evaluator the search used, and every
summary sentence is quoted from fixed, reviewable strings.
"""

from __future__ import annotations

from typing import Any

from app.analyses.constants import (
    NO_UNSAFE_DETECTED_NOTE,
    SAFEGUARD_LANGUAGE_NOTE,
    SERIES_KEYS,
    UNSAFE_DETECTED_NOTE,
)
from app.search.variables import SearchVariable

#: Bounded resolution for stored trajectories (a 600 s / 1 s run is 601 points;
#: the UI draws every point, so nothing is thinned below this).
_MAX_SERIES_POINTS = 2000


def bounded_series(result: Any) -> dict[str, list]:
    """The simulator series a page may draw, bounded to the storage limits."""
    series = getattr(result, "series", None) or {}
    out: dict[str, list] = {}
    for key in SERIES_KEYS:
        values = series.get(key)
        if values is None:
            continue
        values = list(values)[:_MAX_SERIES_POINTS]
        out[key] = values
    return out


def failure_detail(
    *,
    analysis_id: str,
    failure: dict,
    original: dict,
    series: dict[str, list],
    safeguards: list[dict],
    limits: dict | None = None,
) -> dict:
    """One failure's full evidence page, straight from stored/recomputed facts."""
    configured_limits = limits or ((original.get("plan") or {}).get("safety_limits")) or {}
    findings = failure.get("findings") or []
    first_violation = None
    for finding in findings:
        if finding.get("status") == "violation":
            first_violation = finding
            break
    return {
        "analysis_id": analysis_id,
        "failure_id": failure.get("key") or "",
        "case_label": failure.get("label") or "",
        "scenario": {
            "values": failure.get("values") or {},
            "duration_s": (original.get("plan") or {}).get("duration_s"),
            "time_step_s": (original.get("plan") or {}).get("time_step_s"),
        },
        "configured_limits": configured_limits,
        "first_violation": first_violation,
        "peaks": failure.get("peaks") or {},
        "status": failure.get("status"),
        "findings": findings,
        "safeguard_events": safeguards,
        "series": series,
        "search_context": {
            "mode": original.get("mode"),
            "counts": original.get("counts"),
            "boundaries": original.get("boundaries"),
            "notes": original.get("notes"),
        },
        "note": UNSAFE_DETECTED_NOTE if failure else NO_UNSAFE_DETECTED_NOTE,
    }


def locate_failure(analysis_result: dict | None, failure_id: str) -> dict | None:
    """Find one stored failure by its canonical case key (exact match only)."""
    if not analysis_result:
        return None
    for failure in analysis_result.get("failures") or []:
        if failure.get("key") == failure_id:
            return failure
    return None


# ---------------------------------------------------------------------------
# Reverify
# ---------------------------------------------------------------------------

#: Engineer-facing labels for the mitigation keys (route re-checks the values).
MITIGATION_LABELS: dict[str, str] = {
    "shutdown_delay_s": "shutdown delay",
    "cooling_capacity_pct": "cooling capacity",
    "operating_target_pct": "operating target",
    "feed_factor": "feed factor",
    "outlet_factor": "outlet factor",
    "cooling_factor": "cooling factor",
}

#: Bounds per mitigation (the same allowlist logic the search variables use).
MITIGATION_BOUNDS: dict[str, tuple[float, float]] = {
    "shutdown_delay_s": (0.0, 120.0),
    "cooling_capacity_pct": (0.0, 150.0),
    "operating_target_pct": (0.0, 100.0),
    "feed_factor": (0.0, 2.0),
    "outlet_factor": (0.0, 2.0),
    "cooling_factor": (0.0, 1.5),
}


def _apply_mitigations(values: dict, mitigations: dict[str, float]) -> tuple[dict, list[str]]:
    """Fold engineer mitigations into a case, returning applied changes.

    Mitigations whose keys are outside the allowlist are rejected by the route
    before this runs; a value outside a bound raises ``ValueError``.
    """
    applied: dict[str, float] = {}
    changed: list[str] = []
    for key, raw in mitigations.items():
        if key not in MITIGATION_BOUNDS:
            raise ValueError(f"unknown mitigation: {key}")
        low, high = MITIGATION_BOUNDS[key]
        value = float(raw)
        if not (low <= value <= high):
            raise ValueError(f"mitigation {key} is outside its allowed range")
        applied[key] = value

    case_values = dict(values)
    for key, value in applied.items():
        if key in ("shutdown_delay_s", "cooling_capacity_pct", "operating_target_pct"):
            # These map onto allowlisted variables with known neutral targets.
            if key == "shutdown_delay_s":
                case_values[SearchVariable.SHUTDOWN_DELAY_S.value] = float(value)
            elif key == "cooling_capacity_pct":
                # A percentage of the configured cooling: express it as a factor
                # of the *configured* cooling so the plant's own setpoint moves.
                case_values[SearchVariable.COOLING_FACTOR.value] = round(value / 100.0, 6)
            else:
                # Operating target: the valve position percent.
                case_values[SearchVariable.VALVE_TARGET_PCT.value] = float(value)
        else:
            case_values[key] = float(value)
        changed.append(key)
    return case_values, changed


def reverify_verdict(after_summary: dict) -> str:
    """The *only* verdict sentence a reverify may carry (required language)."""
    failing = int(after_summary.get("failing_after", 0) or 0)
    if failing:
        return UNSAFE_DETECTED_NOTE
    return NO_UNSAFE_DETECTED_NOTE


def build_reverify_document(
    *,
    parent: Any,
    mitigations: dict[str, float],
    after_rows: list[dict],
) -> dict:
    """The stored comparison document for one reverify run.

    ``after_rows`` are the real per-case results the route produced by
    re-simulating the parent's failing scenarios with the mitigations applied.
    This builder only assembles; it never simulates.
    """
    parent_result = getattr(parent, "result", None) or {}
    pivot_values = (parent_result.get("pivot") or {}).get("values") or {}
    case_values, changed = _apply_mitigations(pivot_values, mitigations)
    failing_after = sum(1 for row in after_rows if row.get("status_after") in ("violation", "safeguard_activated"))
    failing_before = sum(1 for row in after_rows if row.get("status_before") in ("violation", "safeguard_activated"))
    summary = {
        "scenarios_retested": len(after_rows),
        "failing_before": failing_before,
        "failing_after": failing_after,
    }
    return {
        "kind": "reverify",
        "parent_id": str(getattr(parent, "id", "")),
        "mitigations": dict(mitigations),
        "mitigation_labels": [MITIGATION_LABELS.get(key, key) for key in mitigations],
        "changed": changed,
        "case_values": case_values,
        "comparison": summary,
        "rows": after_rows,
        "verdict": reverify_verdict(summary),
        "note": (
            "Re-verification re-ran the affected scenarios with the requested "
            "mitigations applied. " + SAFEGUARD_LANGUAGE_NOTE
        ),
    }


__all__ = [
    "MITIGATION_BOUNDS",
    "MITIGATION_LABELS",
    "apply_mitigations_to_case",
    "bounded_series",
    "build_reverify_document",
    "failure_detail",
    "locate_failure",
    "reverify_verdict",
]


def apply_mitigations_to_case(values: dict, mitigations: dict[str, float]) -> dict:
    """Public form of the mitigation mapping used by the route to build cases."""
    case_values, _changed = _apply_mitigations(values, mitigations)
    return case_values

