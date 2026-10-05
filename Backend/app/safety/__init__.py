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
from app.safety.evaluator import evaluate_simulation
from app.safety.findings import (
    SafetyAssessment,
    SafetyFinding,
    SafetyStatus,
    SafetyThresholds,
    worst_status,
)

__all__ = [
    "DEFAULT_NEAR_LIMIT_FRACTION",
    "MONITORED_VARIABLES",
    "SAFETY_ENGINE_VERSION",
    "SAFETY_LANGUAGE_DISCLAIMER",
    "SafetyAssessment",
    "SafetyFinding",
    "SafetyStatus",
    "SafetyThresholds",
    "evaluate_simulation",
    "worst_status",
]
