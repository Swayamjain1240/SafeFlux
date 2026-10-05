"""Deterministic search orchestration (Part 7).

    Search → Simulator → Safety Engine → Evidence

One entry point runs a resolved ``SearchSpec`` under a hard ``SearchBudget`` and
returns a reproducible ``SearchResult``. There is no AI anywhere in this file,
and no unbounded loop: every mode stops on its own structural limits *and* on the
shared scenario/timeout budget, and whichever limit stopped it is reported.

Hitting a limit is a normal outcome, not an error — the result is marked
truncated and the reason is carried in ``budget`` and ``notes``, because a
partial search that says it is partial is useful evidence, while a partial search
that pretends to be complete is a hazard.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.safety import SafetyThresholds
from app.safety.constants import (
    DEFAULT_NEAR_LIMIT_FRACTION,
    SAFETY_ENGINE_VERSION,
)
from app.simulator import SimulationLimits
from app.simulator.constants import MODEL_NAME, MODEL_VERSION, SIMULATOR_VERSION

from app.search.budgets import SearchBudget, SearchLimits
from app.search.combinations import run_combinations
from app.search.constants import (
    MAX_REPORTED_FAILURES,
    MAX_TRACE_ENTRIES,
    METHOD_VERSION,
    SEARCH_DISCLAIMER,
    SEARCH_ENGINE_VERSION,
)
from app.search.evaluate import CaseOutcome, PlantProfile, ScenarioEvaluator
from app.search.refine import refine_boundary
from app.search.result import SearchResult, count_statuses
from app.search.sensitivity import run_sensitivity
from app.search.spec import SearchMode, SearchSpec
from app.search.sweep import run_sweep

#: A monitored variable that never changes cannot be reported as a boundary.
_OBSERVATION_AXIS_NOTE = (
    "A sensor variable was searched: sensor faults change observed readings only. "
    "Because SafeFlux never actuates real equipment, they cannot alter the true "
    "simulated trajectory, and any flat result is the honest answer."
)

_NON_MONOTONIC_NOTE = (
    "The sampled status is not monotonic along this axis, so the bracket was "
    "densified instead of bisected. Bisection on a non-monotonic series converges "
    "on the wrong point."
)

_NO_BOUNDARY_NOTE = (
    "No failing boundary was found inside the tested range: every sampled point "
    "stayed acceptable. Widen the range or vary another variable."
)


@dataclass
class SearchRun:
    """A finished search: the result document plus the evaluator that produced it."""

    result: SearchResult
    evaluator: ScenarioEvaluator


def versions() -> dict:
    """Version block recorded in every result so evidence stays comparable."""
    return {
        "search_engine_version": SEARCH_ENGINE_VERSION,
        "search_method_version": METHOD_VERSION,
        "simulator_version": SIMULATOR_VERSION,
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "safety_engine_version": SAFETY_ENGINE_VERSION,
        "deterministic": True,
        "ai_involved": False,
    }


def _resolve_thresholds(
    profile: PlantProfile, spec: SearchSpec, settings: object | None
) -> SafetyThresholds:
    fraction = spec.near_limit_fraction
    if fraction is None:
        fraction = getattr(settings, "SAFETY_NEAR_LIMIT_FRACTION", None)
    if fraction is None:
        fraction = DEFAULT_NEAR_LIMIT_FRACTION
    return SafetyThresholds(
        max_temperature_c=profile.safety_limits.max_temperature_c,
        max_pressure_bar=profile.safety_limits.max_pressure_bar,
        max_level_pct=profile.safety_limits.max_level_pct,
        near_limit_fraction=float(fraction),
    )


def _dedupe(outcomes: list[CaseOutcome]) -> list[CaseOutcome]:
    """Distinct cases only — the same case key is the same simulation."""
    seen: dict[str, CaseOutcome] = {}
    for outcome in outcomes:
        seen.setdefault(outcome.key, outcome)
    return list(seen.values())


def run_search(
    *,
    profile: PlantProfile,
    spec: SearchSpec,
    limits: SearchLimits,
    settings: object | None = None,
    runner=None,
) -> SearchRun:
    """Run one bounded, deterministic search."""
    thresholds = _resolve_thresholds(profile, spec, settings)
    budget = SearchBudget(limits=limits)
    sim_limits = SimulationLimits(
        max_duration_s=limits.max_duration_s,
        min_time_step_s=limits.min_time_step_s,
        max_samples=limits.max_samples,
    )
    evaluator = ScenarioEvaluator(
        profile=profile,
        spec=spec,
        thresholds=thresholds,
        limits=sim_limits,
        budget=budget,
        runner=runner,
    )

    trace: list[dict] = []
    notes: list[str] = [SEARCH_DISCLAIMER]
    boundaries: list[dict] = []
    sensitivity_rows: list[dict] = []
    collected: list[CaseOutcome] = []
    combination_meta: dict | None = None
    truncated = False

    if spec.mode is SearchMode.SENSITIVITY:
        sensitivity = run_sensitivity(evaluator, trace)
        truncated = truncated or sensitivity.truncated
        sensitivity_rows = [row.to_dict() for row in sensitivity.rows]
        collected.extend(sensitivity.outcomes)
        if sensitivity.truncated:
            notes.append(
                "Sensitivity was cut short by the search budget; the rows shown are "
                "the variables that completed."
            )

    elif spec.mode is SearchMode.COMBINATIONS:
        combination = run_combinations(
            spec.axes_for_mode(), evaluator, limit=limits.max_combinations, trace=trace
        )
        truncated = truncated or combination.truncated
        collected.extend(combination.rows)
        combination_meta = combination.to_dict()
        if combination.skipped:
            notes.append(
                f"The combination grid is larger than the configured limit, so "
                f"{combination.skipped} combination(s) were skipped rather than run."
            )
        if combination.truncated:
            notes.append(
                "Combination search stopped early: the scenario budget was exhausted."
            )

    else:
        axes = spec.axes_for_mode()
        if axes:
            sweep = run_sweep(axes[0], evaluator, trace)
            truncated = truncated or sweep.truncated
            collected.extend(sweep.points)
            if sweep.truncated:
                notes.append(
                    "The sweep stopped early: the scenario budget was exhausted."
                )
            if spec.refine and sweep.points:
                refinement = refine_boundary(
                    sweep,
                    evaluator,
                    depth=spec.refinement_depth,
                    trace=trace,
                )
                if refinement.refined:
                    collected.extend(refinement.points)
                boundaries.append(refinement.to_dict())
                if refinement.monotonicity.value == "non_monotonic":
                    notes.append(_NON_MONOTONIC_NOTE)
                if refinement.last_safe is None and refinement.first_unsafe is None:
                    notes.append(_NO_BOUNDARY_NOTE)
                if refinement.stop_reason:
                    notes.append(
                        "Boundary refinement stopped early: the search budget was exhausted."
                    )

    if any(
        outcome.observation_only for outcome in collected
    ):
        notes.append(_OBSERVATION_AXIS_NOTE)

    distinct = _dedupe(collected)
    counts = count_statuses(distinct)
    counts["evaluations"] = budget.scenarios
    counts["cache_hits"] = evaluator.cache_hits
    counts["distinct_cases"] = len(distinct)
    counts["boundary_candidates"] = len(boundaries)

    failures = [
        outcome.to_dict() for outcome in sorted(distinct, key=lambda item: (-item.rank, item.key))
        if outcome.failing
    ]
    if len(failures) > MAX_REPORTED_FAILURES:
        failures = failures[:MAX_REPORTED_FAILURES]
        notes.append(
            f"Only the {MAX_REPORTED_FAILURES} most severe failing scenarios are listed."
        )

    if budget.exceeded == "scenarios":
        truncated = True
        notes.append(
            "The search hit the maximum scenario budget and stopped. Narrow the range "
            "or raise the budget to cover the rest."
        )
    elif budget.exceeded == "timeout":
        truncated = True
        notes.append("The search hit its overall timeout and stopped.")

    if len(trace) > MAX_TRACE_ENTRIES:
        trace = trace[:MAX_TRACE_ENTRIES]
        notes.append("The search trace was truncated to its maximum length.")

    result = SearchResult(
        plant=profile.to_dict(),
        mode=spec.mode.value,
        status="truncated" if truncated else "complete",
        truncated=truncated,
        counts=counts,
        cases=[outcome.to_dict() for outcome in distinct],
        failures=failures,
        boundaries=boundaries,
        sensitivity=sensitivity_rows,
        trace=trace,
        budget=budget.to_dict(),
        config={
            "versions": versions(),
            "spec": spec.to_dict(),
            "limits": limits.to_dict(),
            "thresholds": thresholds.to_dict(),
            "combination": combination_meta,
        },
        notes=notes,
    )
    return SearchRun(result=result, evaluator=evaluator)


__all__ = ["SearchRun", "run_search", "versions"]
