"""Deterministic SafeFlux safety engine (Part 5).

Classifies simulator trajectories against configured limits and models
safeguard timing. No LLM participates: the engine is numeric and reproducible,
and every verdict carries a disclaimer that it never speaks about a real plant
(SAFEFLUX_MASTER.md §8 / §24).
"""

from __future__ import annotations

from app.safety.constants import (
    DEFAULT_NEAR_LIMIT_FRACTION,
    MONITORED_VARIABLES,
    SAFETY_ENGINE_VERSION,
    SAFETY_LANGUAGE_DISCLAIMER,
)
from app.safety.assess import alarm_driven_input, assess_scenario
from app.safety.evaluator import evaluate_simulation
from app.safety.findings import (
    SafetyAssessment,
    SafetyFinding,
    SafetyStatus,
    SafetyThresholds,
    status_rank,
    worst_status,
)
from app.safety.safeguards import SafeguardTiming, evaluate_safeguards
from app.simulator.engine import SafeguardSettings
from app.simulator.result import SimulationResult


def assess_simulation(
    result: SimulationResult,
    thresholds: SafetyThresholds,
    safeguards: SafeguardSettings | None = None,
    scenario_id: str | None = None,
) -> SafetyAssessment:
    """Full deterministic assessment: findings plus safeguard timing."""
    assessment = evaluate_simulation(result, thresholds, scenario_id=scenario_id)
    if safeguards is not None:
        assessment.safeguards = evaluate_safeguards(result, thresholds, safeguards)
    return assessment


__all__ = [
    "DEFAULT_NEAR_LIMIT_FRACTION",
    "MONITORED_VARIABLES",
    "SAFETY_ENGINE_VERSION",
    "SAFETY_LANGUAGE_DISCLAIMER",
    "SafetyAssessment",
    "SafetyFinding",
    "SafetyStatus",
    "SafetyThresholds",
    "SafeguardTiming",
    "alarm_driven_input",
    "assess_scenario",
    "assess_simulation",
    "evaluate_safeguards",
    "evaluate_simulation",
    "status_rank",
    "worst_status",
]
