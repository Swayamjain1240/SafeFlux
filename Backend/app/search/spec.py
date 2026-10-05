"""Search specification: modes, axes, scenario plan and cases (Part 7).

A ``SearchSpec`` is the whole plan for one search, resolved from the request
*before* anything runs. That is what makes an oversized search rejectable: the
number of scenarios a plan implies is computable up front, so it can be checked
against the budget instead of discovered halfway through.

Everything here is data. ``SweepAxis.values()`` is a deterministic linspace —
same axis, same points, forever — and ``SearchCase.key()`` is a canonical string
so results and caches are stable and comparable between runs.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Mapping, Sequence

from app.search.constants import (
    DEFAULT_FAULT_START_S,
    DEFAULT_REFINEMENT_DEPTH,
    DEFAULT_SCENARIO_DURATION_S,
    DEFAULT_SCENARIO_TIME_STEP_S,
    DEFAULT_SWEEP_STEPS,
    MAX_REFINEMENT_EVALUATIONS,
    MAX_SWEEP_STEPS,
    MIN_SWEEP_STEPS,
    VALUE_TOLERANCE,
)
from app.search.variables import (
    SPECS,
    SearchVariable,
    canonical_value,
    spec_for,
)


class SearchMode(str, Enum):
    """Deterministic search strategies. No AI participates in any of them."""

    SWEEP = "sweep"
    SENSITIVITY = "sensitivity"
    COMBINATIONS = "combinations"


@dataclass(frozen=True)
class ScenarioPlan:
    """The scenario shape every searched case is built on."""

    duration_s: float = DEFAULT_SCENARIO_DURATION_S
    time_step_s: float = DEFAULT_SCENARIO_TIME_STEP_S
    start_s: float = DEFAULT_FAULT_START_S
    label: str = "search"

    def to_dict(self) -> dict:
        return {
            "duration_s": self.duration_s,
            "time_step_s": self.time_step_s,
            "start_s": self.start_s,
            "label": self.label,
        }


@dataclass(frozen=True)
class SweepAxis:
    """One variable and the range of values to try along it."""

    variable: SearchVariable
    minimum: float
    maximum: float
    steps: int

    def values(self) -> list[float]:
        """Deterministic inclusive linspace, deduplicated.

        ``steps=1`` (or a collapsed range) yields a single point rather than
        dividing by zero; consecutive duplicates at float resolution are dropped
        so a tiny range cannot waste scenario budget on the same case.
        """
        count = max(1, int(self.steps))
        if count == 1 or abs(self.maximum - self.minimum) <= VALUE_TOLERANCE:
            return [canonical_value(self.minimum)]
        span = self.maximum - self.minimum
        raw = [self.minimum + span * index / (count - 1) for index in range(count)]
        out: list[float] = []
        for value in raw:
            point = canonical_value(value)
            if not out or abs(point - out[-1]) > VALUE_TOLERANCE:
                out.append(point)
        return out

    @property
    def step_size(self) -> float:
        values = self.values()
        return 0.0 if len(values) < 2 else values[1] - values[0]

    def to_dict(self) -> dict:
        return {
            "variable": self.variable.value,
            "minimum": self.minimum,
            "maximum": self.maximum,
            "steps": self.steps,
            "step_size": round(self.step_size, 6),
            "direction": SPECS[self.variable].direction.value,
        }


def default_axis(
    variable: SearchVariable | str,
    steps: int | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
    max_steps: int = MAX_SWEEP_STEPS,
) -> SweepAxis:
    """Build an axis from the variable's allowlisted bounds.

    A ``None`` bound falls back to the spec's own bound, so a request can narrow
    an axis but never invent a range outside the allowlist. ``max_steps`` lets a
    combination search clamp harder than a single-axis sweep (per-axis points
    multiply, so a modest grid can still be a large search).
    """
    spec = spec_for(variable)
    requested = DEFAULT_SWEEP_STEPS if steps is None else int(steps)
    ceiling = max(MIN_SWEEP_STEPS, min(int(max_steps), MAX_SWEEP_STEPS))
    count = min(max(requested, MIN_SWEEP_STEPS), ceiling)
    return SweepAxis(
        variable=spec.variable,
        minimum=spec.minimum if minimum is None else float(minimum),
        maximum=spec.maximum if maximum is None else float(maximum),
        steps=count,
    )


@dataclass(frozen=True)
class SearchCase:
    """One fully-specified point in the search space."""

    values: tuple[tuple[SearchVariable, float], ...]
    label: str

    def as_dict(self) -> dict[str, float]:
        return {variable.value: value for variable, value in self.values}

    def value_for(self, variable: SearchVariable) -> float | None:
        return next((value for name, value in self.values if name is variable), None)

    def key(self) -> str:
        """Canonical, order-independent identifier used for de-duplication."""
        ordered = sorted((name.value, value) for name, value in self.values)
        return ";".join(f"{name}={value!r}" for name, value in ordered)


def make_case(values: Mapping[SearchVariable, float], label: str = "search") -> SearchCase:
    """Build a case from a mapping, canonicalising every value."""
    ordered = tuple(
        (variable, canonical_value(float(values[variable])))
        for variable in sorted(values, key=lambda item: item.value)
    )
    return SearchCase(values=ordered, label=label)


@dataclass(frozen=True)
class SearchSpec:
    """The resolved plan for one deterministic search."""

    mode: SearchMode
    plan: ScenarioPlan
    axes: tuple[SweepAxis, ...] = ()
    refine: bool = True
    refinement_depth: int = DEFAULT_REFINEMENT_DEPTH
    near_limit_fraction: float | None = None

    def to_dict(self) -> dict:
        return {
            "mode": self.mode.value,
            "plan": self.plan.to_dict(),
            "axes": [axis.to_dict() for axis in self.axes],
            "refine": self.refine,
            "refinement_depth": self.refinement_depth,
            "near_limit_fraction": self.near_limit_fraction,
        }

    def axes_for_mode(self) -> tuple[SweepAxis, ...]:
        """Axes the mode actually uses (sensitivity ignores them by design)."""
        if self.mode is SearchMode.SENSITIVITY:
            return ()
        return self.axes


def planned_scenarios(spec: SearchSpec) -> int:
    """Upper bound on the scenarios this plan may run.

    Used to reject an oversized search *before* any compute happens. Refinement
    is budgeted from its depth plus the per-pass cap, so the estimate is a real
    ceiling rather than a guess.
    """
    mode = spec.mode
    if mode is SearchMode.SENSITIVITY:
        # Baseline plus a low/high perturbation for every allowlisted variable.
        return 1 + 2 * len(SPECS)

    axes = spec.axes_for_mode()
    if mode is SearchMode.COMBINATIONS:
        total = 1
        for axis in axes:
            total *= max(1, len(axis.values()))
        return total

    # SWEEP: the coarse grid, plus a bounded refinement allowance.
    steps = max(1, len(axes[0].values())) if axes else 1
    if not spec.refine:
        return steps
    allowance = min(
        MAX_REFINEMENT_EVALUATIONS,
        max(0, spec.refinement_depth) * 2,
    )
    return steps + allowance


def coarse_values(values: Sequence[float]) -> list[float]:
    """Sort/deduplicate sampled values, keeping ascending argument order."""
    out: list[float] = []
    for value in sorted(values):
        if not out or abs(value - out[-1]) > VALUE_TOLERANCE:
            out.append(value)
    return out


__all__ = [
    "ScenarioPlan",
    "SearchCase",
    "SearchMode",
    "SearchSpec",
    "SweepAxis",
    "coarse_values",
    "default_axis",
    "make_case",
    "planned_scenarios",
]
