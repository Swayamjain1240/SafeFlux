"""Coarse parameter sweep (Part 7).

Walks one allowlisted variable across its range and classifies each point, so an
engineer never has to type 100, 110, 120 … by hand.

Points are visited from the *expected safe end* towards the *expected dangerous
end* (using the variable's risk direction), which is what makes the trace read
like the brief's example — ``100 SAFE, 70 SAFE, 50 NEAR, 40 VIOLATION`` — and
leaves the boundary as the last safe / first unsafe adjacent pair.

The direction is only used to choose a visiting order and label an endpoint. It
is never used to conclude anything: every point is simulated and classified by
the deterministic safety engine, and a non-monotonic outcome is reported as such.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.search.budgets import SearchBudgetExceeded
from app.search.evaluate import CaseOutcome, ScenarioEvaluator
from app.search.spec import SweepAxis, make_case
from app.search.variables import SPECS, RiskDirection


def traverse_order(axis: SweepAxis) -> list[float]:
    """Values ordered safe-end first according to the variable's direction."""
    values = axis.values()
    if SPECS[axis.variable].direction is RiskDirection.DECREASING:
        return list(reversed(values))
    return values


def ascending(points: list[CaseOutcome], variable: str) -> list[CaseOutcome]:
    """Points ordered by their sampled value, for monotonicity reasoning."""
    return sorted(points, key=lambda point: point.values.get(variable, 0.0))


@dataclass
class SweepOutcome:
    """Every classified point along one axis, plus how far it got."""

    axis: SweepAxis
    points: list[CaseOutcome] = field(default_factory=list)
    truncated: bool = False
    stop_reason: str | None = None

    @property
    def variable(self) -> str:
        return self.axis.variable.value

    def ranks_in_value_order(self) -> list[float]:
        return [float(point.rank) for point in ascending(self.points, self.variable)]

    def statuses_in_value_order(self) -> list[dict[str, Any]]:
        return [
            {"value": point.values.get(self.variable), "status": point.status.value}
            for point in ascending(self.points, self.variable)
        ]

    def to_dict(self) -> dict:
        return {
            "axis": self.axis.to_dict(),
            "truncated": self.truncated,
            "stop_reason": self.stop_reason,
            "points": [
                {
                    "value": point.values.get(self.variable),
                    "status": point.status.value,
                    "rank": point.rank,
                    "observations": 1,
                }
                for point in self.points
            ],
        }


def run_sweep(
    axis: SweepAxis,
    evaluator: ScenarioEvaluator,
    trace: list[dict],
) -> SweepOutcome:
    """Evaluate every point on ``axis``, stopping cleanly when the budget runs out."""
    outcome = SweepOutcome(axis=axis)
    for value in traverse_order(axis):
        case = make_case({axis.variable: value}, label=f"{axis.variable.value}={value}")
        try:
            result = evaluator.evaluate(case)
        except SearchBudgetExceeded as exc:
            outcome.truncated = True
            outcome.stop_reason = exc.kind
            trace.append(
                {
                    "kind": "stop",
                    "detail": {
                        "reason": exc.kind,
                        "phase": "sweep",
                        "variable": axis.variable.value,
                        "at_value": value,
                    },
                }
            )
            break
        outcome.points.append(result)
        trace.append(
            {
                "kind": "case",
                "detail": {
                    "phase": "sweep",
                    "variable": axis.variable.value,
                    "value": value,
                    "status": result.status.value,
                    "cached": result.cached,
                },
            }
        )
    return outcome


__all__ = ["SweepOutcome", "ascending", "run_sweep", "traverse_order"]
