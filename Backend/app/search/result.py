"""Search result document (Part 7).

A result is evidence, so it is assembled from what was actually run: the counts,
every failing scenario with its finding, the boundary candidates with the method
that produced them, the search trace, and the configuration/version block that
makes the whole thing reproducible.

Counting lives in one helper here so the numbers in the document are derived the
same way in every mode — and are unit-testable without running a simulation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Sequence

from app.safety import SafetyStatus, status_rank
from app.search.monotonic import Monotonicity


def count_statuses(outcomes: Iterable[object]) -> dict:
    """Tally evaluated outcomes by status (plus the evidence-bearing extras)."""
    counts = {
        "scenarios": 0,
        "safe": 0,
        "near_limit": 0,
        "safeguard_activated": 0,
        "violation": 0,
        "failing": 0,
        "observation_only": 0,
    }
    for outcome in outcomes:
        counts["scenarios"] += 1
        status = getattr(outcome, "status")
        key = status.value if isinstance(status, SafetyStatus) else str(status)
        if key in counts:
            counts[key] += 1
        if getattr(outcome, "failing", False):
            counts["failing"] += 1
        if getattr(outcome, "observation_only", False):
            counts["observation_only"] += 1
    return counts


@dataclass
class BoundaryCandidate:
    """The edge between the last safe point and the first unsafe one."""

    variable: str
    last_safe: float | None
    first_unsafe: float | None
    boundary_estimate: float | None
    monotonicity: Monotonicity
    method: str
    refined: bool
    evaluations: int
    uncertainty: float | None
    def to_dict(self) -> dict:
        return {
            "variable": self.variable,
            "last_safe": self.last_safe,
            "first_unsafe": self.first_unsafe,
            "boundary_estimate": self.boundary_estimate,
            "uncertainty": self.uncertainty,
            "monotonicity": self.monotonicity.value,
            "method": self.method,
            "refined": self.refined,
            "evaluations": self.evaluations,
        }


@dataclass
class SensitivityRow:
    """How much one variable matters, measured by perturbing it alone."""

    variable: str
    #: ``None`` when the baseline used the plant's own configured value.
    baseline_value: float | None
    baseline_status: str
    low_value: float
    low_status: str
    high_value: float
    high_status: str
    worst_delta: int
    influence: str
    note: str
    def to_dict(self) -> dict:
        return {
            "variable": self.variable,
            "baseline_value": self.baseline_value,
            "baseline_status": self.baseline_status,
            "low_value": self.low_value,
            "low_status": self.low_status,
            "high_value": self.high_value,
            "high_status": self.high_status,
            "worst_delta": self.worst_delta,
            "influence": self.influence,
            "note": self.note,
        }


def influence_label(worst_delta: int) -> str:
    """Plain-language label so the UI never has to interpret raw ranks."""
    if worst_delta >= 3:
        return "critical"
    if worst_delta == 2:
        return "high"
    if worst_delta == 1:
        return "moderate"
    return "none"


def worst_rank(outcomes: Sequence[object]) -> int:
    ranks = [
        status_rank(getattr(outcome, "status")) if isinstance(getattr(outcome, "status"), SafetyStatus)
        else int(getattr(outcome, "rank", 0))
        for outcome in outcomes
    ]
    return max(ranks) if ranks else 0


@dataclass
class SearchResult:
    """The complete, reproducible document returned by a search."""

    plant: dict
    mode: str
    status: str
    counts: dict
    cases: list[dict] = field(default_factory=list)
    failures: list[dict] = field(default_factory=list)
    boundaries: list[dict] = field(default_factory=list)
    sensitivity: list[dict] = field(default_factory=list)
    trace: list[dict] = field(default_factory=list)
    budget: dict = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    truncated: bool = False

    def to_dict(self) -> dict:
        return {
            "plant": dict(self.plant),
            "mode": self.mode,
            "status": self.status,
            "truncated": self.truncated,
            "counts": dict(self.counts),
            "cases": list(self.cases),
            "failures": list(self.failures),
            "boundaries": list(self.boundaries),
            "sensitivity": list(self.sensitivity),
            "trace": list(self.trace),
            "budget": dict(self.budget),
            "config": dict(self.config),
            "notes": list(self.notes),
        }


__all__ = [
    "BoundaryCandidate",
    "SearchResult",
    "SensitivityRow",
    "count_statuses",
    "influence_label",
    "worst_rank",
]
