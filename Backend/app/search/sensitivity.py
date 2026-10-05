"""One-at-a-time sensitivity analysis (Part 7).

Before searching a space, it is worth knowing which variable steers the risk at
all. Sensitivity perturbs each allowlisted variable on its own to its low and
high bound, holding everything else at the plant's operating point, and reports
how much the verdict moved.

This is deliberately *not* a search for a boundary — it is a screening pass that
tells the engineer where the interesting axis is, and it is reported with the
same evidence as everything else rather than as a bare score.

The operating point leaves safeguard variables at the plant's configured value
rather than forcing them to an arbitrary default, so "no change" really means no
change to the plant as configured.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.search.budgets import SearchBudgetExceeded
from app.search.evaluate import CaseOutcome, ScenarioEvaluator
from app.search.result import SensitivityRow, influence_label, worst_rank
from app.search.spec import make_case
from app.search.variables import SPECS, SearchVariable

_OBSERVATION_NOTE = (
    "Sensor faults change what the plant observes, not the true simulated "
    "trajectory, so this variable cannot raise a true-state verdict in a "
    "non-actuating model."
)
_NO_EFFECT_NOTE = "No change in verdict across the tested range."
_SAFEGUARD_NOTE = (
    "Measured through the simulated emergency-shutdown delay; a late response "
    "shows up as a safeguard that fired but arrived too late."
)



def baseline_values() -> dict[SearchVariable, float]:
    """The plant's operating point: no variable perturbed at all.

    An empty case means "the plant exactly as configured" — no fault injected and
    the plant's own safeguard delay in force. Filling in each variable's nominal
    default instead would silently assert that those defaults match the plant,
    which is not something this code knows.
    """
    return {}


@dataclass
class SensitivityOutcome:
    """Baseline, one row per variable, and every case that was evaluated."""

    baseline: CaseOutcome | None = None
    rows: list[SensitivityRow] = field(default_factory=list)
    #: Distinct cases behind the rows, so callers count evidence the same way
    #: they do in every other mode instead of re-deriving it.
    outcomes: list[CaseOutcome] = field(default_factory=list)
    truncated: bool = False
    stop_reason: str | None = None

    def to_dict(self) -> dict:
        return {
            "baseline": self.baseline.to_dict() if self.baseline else None,
            "truncated": self.truncated,
            "stop_reason": self.stop_reason,
            "rows": [row.to_dict() for row in self.rows],
        }


def _evaluate(evaluator: ScenarioEvaluator, values: dict, label: str) -> CaseOutcome:
    return evaluator.evaluate(make_case(values, label=label))


def run_sensitivity(evaluator: ScenarioEvaluator, trace: list[dict]) -> SensitivityOutcome:
    """Perturb every allowlisted variable one at a time from the operating point."""
    outcome = SensitivityOutcome()
    base_values = baseline_values()

    try:
        baseline = _evaluate(evaluator, base_values, "sensitivity baseline")
    except SearchBudgetExceeded as exc:
        outcome.truncated = True
        outcome.stop_reason = exc.kind
        trace.append({"kind": "stop", "detail": {"reason": exc.kind, "phase": "sensitivity"}})
        return outcome
    outcome.baseline = baseline
    outcome.outcomes.append(baseline)
    trace.append(
        {
            "kind": "case",
            "detail": {
                "phase": "sensitivity",
                "variable": None,
                "status": baseline.status.value,
                "cached": baseline.cached,
            },
        }
    )

    for variable, spec in SPECS.items():
        # One variable at a time, away from the operating point and nothing else.
        low_case = {variable: spec.minimum}
        high_case = {variable: spec.maximum}
        try:
            low = _evaluate(evaluator, low_case, f"sensitivity {spec.variable.value}={spec.minimum}")
            high = _evaluate(evaluator, high_case, f"sensitivity {spec.variable.value}={spec.maximum}")
        except SearchBudgetExceeded as exc:
            outcome.truncated = True
            outcome.stop_reason = exc.kind
            trace.append(
                {
                    "kind": "stop",
                    "detail": {
                        "reason": exc.kind,
                        "phase": "sensitivity",
                        "variable": spec.variable.value,
                    },
                }
            )
            break
        delta = max(worst_rank([low, high]) - worst_rank([baseline]), 0)
        if spec.is_observation_only:
            note = _OBSERVATION_NOTE
        elif spec.is_safeguard:
            note = _SAFEGUARD_NOTE if delta else f"{_SAFEGUARD_NOTE} {_NO_EFFECT_NOTE}"
        else:
            note = (
                f"Varying this variable moves the verdict by up to {delta} level(s) "
                "across the tested range."
                if delta
                else _NO_EFFECT_NOTE
            )
        outcome.outcomes.extend([low, high])
        outcome.rows.append(
            SensitivityRow(
                variable=spec.variable.value,
                # None means "whatever the plant is configured with": the
                # baseline case perturbs nothing, so there is no number to show.
                baseline_value=baseline.values.get(spec.variable.value),
                baseline_status=baseline.status.value,
                low_value=spec.minimum,
                low_status=low.status.value,
                high_value=spec.maximum,
                high_status=high.status.value,
                worst_delta=delta,
                influence=influence_label(delta),
                note=note,
            )
        )
        for point, value in ((low, spec.minimum), (high, spec.maximum)):
            trace.append(
                {
                    "kind": "case",
                    "detail": {
                        "phase": "sensitivity",
                        "variable": spec.variable.value,
                        "value": value,
                        "status": point.status.value,
                        "cached": point.cached,
                    },
                }
            )

    outcome.rows.sort(key=lambda row: (-row.worst_delta, row.variable))
    return outcome


__all__ = ["SensitivityOutcome", "baseline_values", "run_sensitivity"]
