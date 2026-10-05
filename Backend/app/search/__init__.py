"""Deterministic, bounded scenario search (Part 7).

    Search → Simulator → Safety Engine → Evidence

SafeFlux explores a space of dangerous conditions on its own, so an engineer
never has to type 100, 110, 120 … by hand. Nothing here is AI: every verdict comes
from the Part 4 simulator and the Part 5 safety engine, and every search is
bounded by hard budgets (SAFEFLUX_MASTER.md rule 8).

The two rules this package exists to uphold:

- **No unbounded search.** Scenario, combination, depth and time limits are
  enforced before and during a run; hitting one is reported, never hidden.
- **No unsafe search.** Variables come from a fixed allowlist and map to typed
  simulator effects. There is no ``eval``/``exec``, no generated code and no
  shell — a client picks a name, nothing more.
"""

from __future__ import annotations

from app.search.budgets import (
    SearchBudget,
    SearchBudgetExceeded,
    SearchLimits,
    resolve_limits,
)
from app.search.combinations import CombinationOutcome, grid_size, run_combinations
from app.search.constants import (
    METHOD_VERSION,
    SEARCH_DISCLAIMER,
    SEARCH_ENGINE_VERSION,
)
from app.search.engine import SearchRun, run_search, versions
from app.search.evaluate import CaseOutcome, PlantProfile, ScenarioEvaluator
from app.search.monotonic import Monotonicity, classify_monotonic, supports_bisection
from app.search.refine import RefinementOutcome, refine_boundary
from app.search.result import SearchResult
from app.search.sensitivity import SensitivityOutcome, run_sensitivity
from app.search.spec import (
    ScenarioPlan,
    SearchCase,
    SearchMode,
    SearchSpec,
    SweepAxis,
    default_axis,
    make_case,
    planned_scenarios,
)
from app.search.sweep import SweepOutcome, run_sweep
from app.search.variables import (
    SPECS,
    VARIABLE_NAMES,
    RiskDirection,
    SearchVariable,
    VariableSpec,
    capabilities,
)

__all__ = [
    "METHOD_VERSION",
    "SEARCH_DISCLAIMER",
    "SEARCH_ENGINE_VERSION",
    "SPECS",
    "VARIABLE_NAMES",
    "CaseOutcome",
    "CombinationOutcome",
    "Monotonicity",
    "PlantProfile",
    "RefinementOutcome",
    "RiskDirection",
    "ScenarioEvaluator",
    "ScenarioPlan",
    "SearchBudget",
    "SearchBudgetExceeded",
    "SearchCase",
    "SearchLimits",
    "SearchMode",
    "SearchResult",
    "SearchRun",
    "SearchSpec",
    "SearchVariable",
    "SensitivityOutcome",
    "SweepAxis",
    "SweepOutcome",
    "VariableSpec",
    "capabilities",
    "classify_monotonic",
    "default_axis",
    "grid_size",
    "make_case",
    "planned_scenarios",
    "refine_boundary",
    "resolve_limits",
    "run_combinations",
    "run_search",
    "run_sensitivity",
    "run_sweep",
    "supports_bisection",
    "versions",
]
