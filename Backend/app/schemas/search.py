"""Pydantic schemas for the deterministic search endpoint (Part 7).

Strict (``extra="forbid"``) request models. The important property is that the
request can only ever name an **allowlisted variable**: ``SearchVariable`` is an
enum, so a value like ``__import__`` or ``os.system`` fails validation before any
code path could look at it. Axis bounds are re-checked against the allowlist
server-side, and budget fields carry hard ceilings, so an oversized search is
rejected by the schema itself.

Validation errors never echo submitted values (rule 6 / safe API contract).
"""

from __future__ import annotations

from dataclasses import replace

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.search import (
    SearchLimits,
    SearchMode,
    SearchSpec,
    SearchVariable,
    ScenarioPlan,
    SweepAxis,
    planned_scenarios,
    resolve_limits,
    spec_for,
)
from app.search.combinations import grid_size
from app.search.constants import (
    DEFAULT_MULTI_STEPS,
    DEFAULT_REFINEMENT_DEPTH,
    DEFAULT_SCENARIO_DURATION_S,
    DEFAULT_SCENARIO_TIME_STEP_S,
    DEFAULT_SWEEP_STEPS,
    MAX_COMBINATIONS_CEILING,
    MAX_COMBINATION_AXES,
    MAX_MULTI_STEPS,
    MAX_REFINEMENT_DEPTH_CEILING,
    MAX_SCENARIOS_CEILING,
    MAX_SWEEP_STEPS,
    MAX_TIMEOUT_S_CEILING,
    MIN_MULTI_STEPS,
    MIN_SWEEP_STEPS,
    MIN_TIMEOUT_S,
)

MAX_AXES = MAX_COMBINATION_AXES


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SearchAxisIn(_StrictModel):
    """One variable and (optionally) the range to sweep."""

    variable: SearchVariable
    minimum: float | None = None
    maximum: float | None = None
    steps: int | None = Field(default=None, ge=MIN_MULTI_STEPS, le=MAX_SWEEP_STEPS)

    @model_validator(mode="after")
    def _bounded_range(self) -> "SearchAxisIn":
        spec = spec_for(self.variable)
        low = spec.minimum if self.minimum is None else self.minimum
        high = spec.maximum if self.maximum is None else self.maximum
        if low < spec.minimum or high > spec.maximum:
            raise ValueError("Axis range must stay inside the allowlisted bounds.")
        if low > high:
            raise ValueError("Axis minimum must not exceed its maximum.")
        if (high - low) <= 0 and (self.steps or DEFAULT_SWEEP_STEPS) > 1:
            raise ValueError("Axis range must span more than one point.")
        return self

    def to_axis(self, max_steps: int = MAX_SWEEP_STEPS) -> SweepAxis:
        spec = spec_for(self.variable)
        default_steps = DEFAULT_SWEEP_STEPS if max_steps > MAX_MULTI_STEPS else DEFAULT_MULTI_STEPS
        return SweepAxis(
            variable=spec.variable,
            minimum=spec.minimum if self.minimum is None else self.minimum,
            maximum=spec.maximum if self.maximum is None else self.maximum,
            steps=self.steps or default_steps,
        )


class SearchPlanIn(_StrictModel):
    """Shape of every scenario the search will run."""

    duration_s: float = Field(default=DEFAULT_SCENARIO_DURATION_S, gt=0)
    time_step_s: float = Field(default=DEFAULT_SCENARIO_TIME_STEP_S, gt=0)
    start_s: float = Field(default=0.0, ge=0, le=1_000_000)
    label: str = Field(default="search", max_length=120)

    def to_plan(self) -> ScenarioPlan:
        return ScenarioPlan(
            duration_s=self.duration_s,
            time_step_s=self.time_step_s,
            start_s=self.start_s,
            label=self.label,
        )


class SearchRunRequest(_StrictModel):
    """POST /searches/run — a bounded, deterministic search over one plant."""

    plant_id: str = Field(min_length=1, max_length=64)
    mode: SearchMode = SearchMode.SWEEP
    plan: SearchPlanIn = Field(default_factory=SearchPlanIn)
    axes: list[SearchAxisIn] = Field(default_factory=list, max_length=MAX_AXES)
    refine: bool = True
    refinement_depth: int | None = Field(
        default=None, ge=0, le=MAX_REFINEMENT_DEPTH_CEILING
    )
    near_limit_fraction: float | None = Field(default=None, ge=0.5, le=1.0)
    # Per-request budgets may only tighten the configured limits (never loosen).
    max_scenarios: int | None = Field(default=None, ge=1, le=MAX_SCENARIOS_CEILING)
    max_combinations: int | None = Field(default=None, ge=1, le=MAX_COMBINATIONS_CEILING)
    timeout_s: float | None = Field(
        default=None, ge=MIN_TIMEOUT_S, le=MAX_TIMEOUT_S_CEILING
    )

    @model_validator(mode="after")
    def _axes_match_mode(self) -> "SearchRunRequest":
        count = len(self.axes)
        if self.mode is SearchMode.SWEEP and count != 1:
            raise ValueError("A sweep search requires exactly one axis.")
        if self.mode is SearchMode.COMBINATIONS and not 1 <= count <= MAX_AXES:
            raise ValueError("A combination search requires one or two axes.")
        if self.mode is SearchMode.SENSITIVITY and count:
            raise ValueError("A sensitivity search takes no axes.")
        seen = [axis.variable for axis in self.axes]
        if len(set(seen)) != len(seen):
            raise ValueError("Each axis must name a different variable.")
        return self

    def to_spec(self) -> SearchSpec:
        mode = self.mode
        if mode is SearchMode.COMBINATIONS:
            max_steps = MAX_MULTI_STEPS
        else:
            max_steps = MAX_SWEEP_STEPS
        depth = (
            self.refinement_depth
            if self.refinement_depth is not None
            else DEFAULT_REFINEMENT_DEPTH
        )
        return SearchSpec(
            mode=mode,
            plan=self.plan.to_plan(),
            axes=tuple(axis.to_axis(max_steps) for axis in self.axes),
            refine=self.refine,
            refinement_depth=depth,
            near_limit_fraction=self.near_limit_fraction,
        )

    def planned_combinations(self, spec: SearchSpec) -> int:
        if spec.mode is not SearchMode.COMBINATIONS:
            return 0
        return grid_size(spec.axes_for_mode())


def resolve_request_limits(
    settings: object | None, payload: SearchRunRequest, spec: SearchSpec
) -> tuple[SearchLimits, list[tuple[str, str]]]:
    """Merge per-request budgets with the configured ones and validate the plan.

    Per-request values may only *tighten* a limit. Asking for more than the
    operator configured is a rejection, not a silent clamp: silently running less
    than asked is how a "complete" search ends up covering nothing.
    """
    base = resolve_limits(settings)
    errors: list[tuple[str, str]] = []

    if payload.max_scenarios is not None and payload.max_scenarios > base.max_scenarios:
        errors.append(
            ("max_scenarios", "Requested scenario budget exceeds the configured maximum.")
        )
    if payload.max_combinations is not None and payload.max_combinations > base.max_combinations:
        errors.append(
            ("max_combinations", "Requested combination budget exceeds the configured maximum.")
        )
    if payload.timeout_s is not None and payload.timeout_s > base.timeout_s:
        errors.append(("timeout_s", "Requested timeout exceeds the configured maximum."))

    limits = replace(
        base,
        max_scenarios=payload.max_scenarios or base.max_scenarios,
        max_combinations=payload.max_combinations or base.max_combinations,
        timeout_s=payload.timeout_s or base.timeout_s,
    )
    if errors:
        return limits, errors

    depth = spec.refinement_depth if spec.mode is SearchMode.SWEEP and spec.refine else 0
    errors.extend(
        limits.validation_errors(
            duration_s=spec.plan.duration_s,
            time_step_s=spec.plan.time_step_s,
            refinement_depth=depth,
            axes=len(spec.axes_for_mode()),
            combinations=payload.planned_combinations(spec),
            scenarios=planned_scenarios(spec),
        )
    )
    return limits, errors


__all__ = [
    "SearchAxisIn",
    "SearchPlanIn",
    "SearchRunRequest",
    "resolve_request_limits",
]
