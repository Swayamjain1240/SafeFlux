"""Limited combination search (Part 7).

Sometimes no single fault is unsafe and a *pair* is — which is exactly the kind
of hidden interaction this project exists to find. This mode takes a bounded
cartesian product over at most two axes.

Two independent caps keep it finite: a structural one (two axes, and few points
per axis) and a hard one (``max_combinations``). When the grid is larger than the
cap the search evaluates the first ``limit`` points in a deterministic order and
reports the rest as **skipped** — never silently pretends to have covered them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from itertools import product

from app.search.budgets import SearchBudgetExceeded
from app.search.evaluate import CaseOutcome, ScenarioEvaluator
from app.search.spec import SweepAxis, make_case
from app.search.sweep import traverse_order


def grid_size(axes: tuple[SweepAxis, ...]) -> int:
    total = 1
    for axis in axes:
        total *= max(1, len(axis.values()))
    return total


@dataclass
class CombinationOutcome:
    """Evaluated combinations plus how many were left out."""

    axes: tuple[SweepAxis, ...] = ()
    rows: list[CaseOutcome] = field(default_factory=list)
    skipped: int = 0
    truncated: bool = False
    stop_reason: str | None = None
    grid_size: int = 0

    @property
    def worst(self) -> CaseOutcome | None:
        """The most severe combination evaluated (None when nothing ran)."""
        if not self.rows:
            return None
        return max(self.rows, key=lambda row: (row.rank, row.key))

    def to_dict(self) -> dict:
        return {
            "axes": [axis.to_dict() for axis in self.axes],
            "grid_size": self.grid_size,
            "evaluated": len(self.rows),
            "skipped": self.skipped,
            "truncated": self.truncated,
            "stop_reason": self.stop_reason,
            "worst": self.worst.to_dict() if self.worst else None,
            "rows": [row.to_dict() for row in self.rows],
        }


def run_combinations(
    axes: tuple[SweepAxis, ...],
    evaluator: ScenarioEvaluator,
    *,
    limit: int,
    trace: list[dict],
) -> CombinationOutcome:
    """Evaluate a bounded cartesian grid over ``axes``."""
    outcome = CombinationOutcome(axes=axes, grid_size=grid_size(axes))
    if not axes:
        return outcome

    per_axis = [traverse_order(axis) for axis in axes]
    cap = max(1, int(limit))
    evaluated = 0

    for values in product(*per_axis):
        if evaluated >= cap:
            outcome.skipped = outcome.grid_size - evaluated
            trace.append(
                {
                    "kind": "skip",
                    "detail": {
                        "phase": "combinations",
                        "reason": "combination_limit",
                        "skipped": outcome.skipped,
                    },
                }
            )
            break
        points = {axis.variable: value for axis, value in zip(axes, values)}
        label = ", ".join(f"{variable.value}={value}" for variable, value in points.items())
        try:
            row = evaluator.evaluate(make_case(points, label=label))
        except SearchBudgetExceeded as exc:
            outcome.truncated = True
            outcome.stop_reason = exc.kind
            outcome.skipped = outcome.grid_size - evaluated
            trace.append({"kind": "stop", "detail": {"reason": exc.kind, "phase": "combinations"}})
            break
        outcome.rows.append(row)
        evaluated += 1
        trace.append(
            {
                "kind": "combination",
                "detail": {
                    "phase": "combinations",
                    "values": {variable.value: value for variable, value in points.items()},
                    "status": row.status.value,
                    "cached": row.cached,
                },
            }
        )

    return outcome


__all__ = ["CombinationOutcome", "grid_size", "run_combinations"]
