"""Safety statuses, configurable thresholds and evidence records (Part 5).

A ``SafetyFinding`` records *what was measured, where, against which limit, in
which scenario, and with what status*. Truth is numeric and reproducible: the
engine only reads simulator series and the simulator's own events — it never
invents values and never lets an LLM decide whether a limit was exceeded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from app.safety.constants import (
    DEFAULT_NEAR_LIMIT_FRACTION,
    MAX_NEAR_LIMIT_FRACTION,
    MIN_NEAR_LIMIT_FRACTION,
    MONITORED_VARIABLES,
)


class SafetyStatus(str, Enum):
    """Classification of one monitored variable in one scenario."""

    SAFE = "safe"
    NEAR_LIMIT = "near_limit"
    SAFEGUARD_ACTIVATED = "safeguard_activated"
    VIOLATION = "violation"


# Worst-first ordering used to roll many findings into a single assessment
# status. VIOLATION outranks SAFEGUARD_ACTIVATED outranks NEAR_LIMIT.
_STATUS_RANK: dict[SafetyStatus, int] = {
    SafetyStatus.SAFE: 0,
    SafetyStatus.NEAR_LIMIT: 1,
    SafetyStatus.SAFEGUARD_ACTIVATED: 2,
    SafetyStatus.VIOLATION: 3,
}

_SEVERITY_LABEL: dict[SafetyStatus, str] = {
    SafetyStatus.SAFE: "none",
    SafetyStatus.NEAR_LIMIT: "low",
    SafetyStatus.SAFEGUARD_ACTIVATED: "high",
    SafetyStatus.VIOLATION: "critical",
}


def status_rank(status: SafetyStatus) -> int:
    """Numeric risk rank (SAFE=0 … VIOLATION=3).

    Single source of truth for 'worse than': the roll-up uses it to reduce many
    findings to one status, and the scenario search uses it to compare sampled
    points along a variable.
    """
    return _STATUS_RANK[status]


def worst_status(statuses: list[SafetyStatus]) -> SafetyStatus:
    """Return the most severe status (SAFE when the list is empty)."""
    if not statuses:
        return SafetyStatus.SAFE
    return max(statuses, key=lambda status: _STATUS_RANK[status])


@dataclass(frozen=True)
class SafetyThresholds:
    """Configured limits plus the configurable near-limit band."""

    max_temperature_c: float
    max_pressure_bar: float
    max_level_pct: float
    near_limit_fraction: float = DEFAULT_NEAR_LIMIT_FRACTION

    def __post_init__(self) -> None:
        if not (MIN_NEAR_LIMIT_FRACTION <= self.near_limit_fraction <= MAX_NEAR_LIMIT_FRACTION):
            raise ValueError("near_limit_fraction must be between 0.5 and 1.0")

    def limit_for(self, variable: str) -> float:
        return {
            "temperature_c": self.max_temperature_c,
            "pressure_bar": self.max_pressure_bar,
            "level_pct": self.max_level_pct,
        }[variable]

    def near_limit_for(self, variable: str) -> float:
        return self.limit_for(variable) * self.near_limit_fraction

    def to_dict(self) -> dict:
        return {
            "max_temperature_c": self.max_temperature_c,
            "max_pressure_bar": self.max_pressure_bar,
            "max_level_pct": self.max_level_pct,
            "near_limit_fraction": self.near_limit_fraction,
        }


@dataclass(frozen=True)
class SafetyFinding:
    """One deterministic, evidence-backed safety observation."""

    variable: str
    status: SafetyStatus
    timestamp_s: float | None
    measured_value: float | None
    limit: float
    near_limit: float
    scenario_id: str | None
    message: str

    @property
    def severity(self) -> str:
        return _SEVERITY_LABEL[self.status]

    def to_dict(self) -> dict:
        return {
            "type": self.variable,
            "status": self.status.value,
            "severity": self.severity,
            "timestamp_s": self.timestamp_s,
            "measured_value": self.measured_value,
            "limit": self.limit,
            "near_limit": self.near_limit,
            "scenario_id": self.scenario_id,
            "message": self.message,
        }


@dataclass
class SafetyAssessment:
    """Roll-up of every finding (plus safeguard timing) for one scenario."""

    status: SafetyStatus
    findings: list[SafetyFinding] = field(default_factory=list)
    safeguards: list = field(default_factory=list)
    scenario_id: str | None = None
    summary: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "findings": [finding.to_dict() for finding in self.findings],
            "safeguards": [
                timing.to_dict() if hasattr(timing, "to_dict") else timing
                for timing in self.safeguards
            ],
            "scenario_id": self.scenario_id,
            "summary": self.summary,
            "metadata": self.metadata,
        }


__all__ = [
    "MONITORED_VARIABLES",
    "SafetyAssessment",
    "SafetyFinding",
    "SafetyStatus",
    "SafetyThresholds",
    "status_rank",
    "worst_status",
]
