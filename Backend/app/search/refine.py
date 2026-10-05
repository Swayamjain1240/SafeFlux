"""Boundary refinement (Part 7).

The coarse sweep gives a bracket: a sampled value that is still acceptable and
the next one that is not. Refinement narrows that bracket.

The important part is *how*. Bisection is only sound when the risk moves in one
direction across the bracket, so this module asks
:func:`app.search.monotonic.classify_monotonic` first:

- **monotonic** → bisect. Each step keeps the invariant that one end is
  acceptable and the other is not, so the bracket halves and the reported
  uncertainty is real.
- **non-monotonic or flat** → do **not** bisect. Densify the bracket instead and
  report the tightest crossing actually observed, with the method named so nobody
  mistakes it for a bisected boundary.

Every evaluation is charged to the shared budget, so refinement can never run
away, and repeated points are replayed from the evaluator cache for free.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.search.budgets import SearchBudgetExceeded
from app.search.constants import MAX_REFINEMENT_EVALUATIONS, VALUE_TOLERANCE
from app.search.evaluate import CaseOutcome, ScenarioEvaluator
from app.search.monotonic import Monotonicity, classify_monotonic, supports_bisection
from app.search.spec import make_case
from app.search.sweep import SweepOutcome

#: A safeguard firing, or a violation, is what an engineer must review. The
#: boundary is the transition into that region — not merely into the near band.
_FAILING_RANKS = 2


def _crossing(
    points: list[CaseOutcome], variable: str
) -> tuple[CaseOutcome | None, CaseOutcome | None]:
    """First (acceptable, failing) adjacent pair in traversal order."""
    previous: CaseOutcome | None = None
    for point in points:
        if point.rank >= _FAILING_RANKS:
            return previous, point
        previous = point
    return None, None


def _tightest_crossing(
    collected: dict[float, CaseOutcome],
) -> tuple[float | None, float | None, float | None]:
    """Smallest-gap adjacent pair in value order that straddles the boundary."""
    values = sorted(collected)
    best: tuple[float, float, float] | None = None
    for low, high in zip(values, values[1:]):
        low_point, high_point = collected[low], collected[high]
        if low_point.rank >= _FAILING_RANKS and high_point.rank >= _FAILING_RANKS:
            continue
        if low_point.rank < _FAILING_RANKS and high_point.rank < _FAILING_RANKS:
            continue
        gap = high - low
        if best is None or gap < best[2]:
            best = (low, high, gap)
    if best is None:
        return None, None, None
    low, high, gap = best
    safe = low if collected[low].rank < _FAILING_RANKS else high
    unsafe = high if collected[high].rank >= _FAILING_RANKS else low
    return safe, unsafe, gap


@dataclass
class RefinementOutcome:
    """Where the boundary sits and how it was found."""

    variable: str
    last_safe: float | None = None
    first_unsafe: float | None = None
    boundary_estimate: float | None = None
    uncertainty: float | None = None
    monotonicity: Monotonicity = Monotonicity.INSUFFICIENT
    method: str = "none"
    refined: bool = False
    evaluations: int = 0
    stop_reason: str | None = None
    points: list[CaseOutcome] = field(default_factory=list)

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
            "stop_reason": self.stop_reason,
        }


def refine_boundary(
    sweep: SweepOutcome,
    evaluator: ScenarioEvaluator,
    *,
    depth: int,
    trace: list[dict],
    max_evaluations: int = MAX_REFINEMENT_EVALUATIONS,
) -> RefinementOutcome:
    """Narrow the sweep's boundary, bisecting only where that is valid."""
    name = sweep.variable
    outcome = RefinementOutcome(variable=name)
    outcome.monotonicity = classify_monotonic(sweep.ranks_in_value_order())

    acceptable, failing = _crossing(sweep.points, name)
    if acceptable is None or failing is None:
        # No transition in the coarse grid: nothing to refine, and the coarse
        # result already says so. Refining anyway would invent a boundary.
        return outcome

    budget = max(0, int(max_evaluations))
    case_variable = sweep.axis.variable
    #: Every point refinement actually evaluated, so the result counts the
    #: scenarios it ran rather than only the two that ended up bracketing.
    evaluated: list[CaseOutcome] = []
    collected: dict[float, CaseOutcome] = {
        float(point.values[name]): point
        for point in sweep.points
        if point.values.get(name) is not None
    }

    if supports_bisection(outcome.monotonicity):
        outcome.method = "bisection"
        low = float(acceptable.values[name])
        high = float(failing.values[name])
        for _ in range(max(0, int(depth))):
            if outcome.evaluations >= budget:
                break
            mid = (low + high) / 2.0
            if abs(high - low) <= VALUE_TOLERANCE or mid in (low, high):
                break
            try:
                point = evaluator.evaluate(
                    make_case({case_variable: mid}, label=f"refine {name}={mid}")
                )
            except SearchBudgetExceeded as exc:
                outcome.stop_reason = exc.kind
                trace.append(
                    {"kind": "stop", "detail": {"reason": exc.kind, "phase": "refine", "variable": name}}
                )
                break
            outcome.evaluations += 1
            evaluated.append(point)
            point_value = float(point.values[name])
            collected[point_value] = point
            trace.append(
                {
                    "kind": "refine",
                    "detail": {
                        "phase": "refine",
                        "method": "bisection",
                        "variable": name,
                        "value": point_value,
                        "status": point.status.value,
                        "cached": point.cached,
                    },
                }
            )
            if point.rank >= _FAILING_RANKS:
                high = point_value
            else:
                low = point_value
        outcome.refined = outcome.evaluations > 0
    else:
        outcome.method = "densify"
        low = float(acceptable.values[name])
        high = float(failing.values[name])
        steps = max(1, min(int(depth) * 2, budget))
        span = high - low
        for index in range(1, steps + 1):
            if outcome.evaluations >= budget:
                break
            mid = low + span * index / (steps + 1)
            if abs(mid - low) <= VALUE_TOLERANCE or abs(mid - high) <= VALUE_TOLERANCE:
                continue
            try:
                point = evaluator.evaluate(
                    make_case({case_variable: mid}, label=f"densify {name}={mid}")
                )
            except SearchBudgetExceeded as exc:
                outcome.stop_reason = exc.kind
                trace.append(
                    {"kind": "stop", "detail": {"reason": exc.kind, "phase": "refine", "variable": name}}
                )
                break
            outcome.evaluations += 1
            evaluated.append(point)
            point_value = float(point.values[name])
            collected[point_value] = point
            trace.append(
                {
                    "kind": "refine",
                    "detail": {
                        "phase": "refine",
                        "method": "densify",
                        "variable": name,
                        "value": point_value,
                        "status": point.status.value,
                        "cached": point.cached,
                    },
                }
            )
        outcome.refined = outcome.evaluations > 0

    safe_value, unsafe_value, gap = _tightest_crossing(collected)
    outcome.last_safe = safe_value
    outcome.first_unsafe = unsafe_value
    outcome.uncertainty = gap
    if safe_value is not None and unsafe_value is not None:
        outcome.boundary_estimate = (safe_value + unsafe_value) / 2.0
    outcome.points = evaluated
    return outcome


__all__ = ["RefinementOutcome", "refine_boundary"]
