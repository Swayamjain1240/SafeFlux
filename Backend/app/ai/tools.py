"""The allowlisted tool layer (Part 8).

This is the *only* surface the model can act through, and it enforces security by
itself — independently of anything the model says or is told:

- **No shell, no Python, no SQL, no files, no secrets, no permissions.** A tool is
  a Python function in this file; the model cannot create one, and no argument it
  supplies is ever evaluated, imported or interpolated into a command.
- **Arguments are re-validated here.** Every tool has its own strict Pydantic model
  (``extra="forbid"``), so an argument the model invented — including
  ``owner_id``/``plant_id``/``role`` — is a rejected call, not a capability.
- **The plant comes from the caller, never from the model.** The context carries a
  plant that was already loaded with ``get_owned_or_404``; no tool accepts an
  owner or a plant id, so cross-user access is impossible by construction.
- **Costs are charged here.** Simulations and searches are charged against the
  investigation's simulation budget *before* they run, so "max simulations" holds
  no matter what the model asks for, and a budget refusal is an ordinary rejected
  tool call the model must work around.
- **Payloads are bounded and redacted** before the model or the client sees them.

Nothing in this module is reachable from user text: text can only influence which
tool the model *asks* for, and every ask is re-validated here.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from app.ai.constants import (
    MAX_EVIDENCE_ITEMS,
    MAX_FAILURES_REPORTED,
    MAX_HISTORY_FRAMES,
)
from app.ai.security import redact_secrets
from app.safety import SafetyStatus, SafetyThresholds, assess_scenario, status_rank
from app.schemas.simulation import FaultIn, SensorFaultIn
from app.search import (
    PlantProfile,
    SearchLimits,
    SearchMode,
    SearchSpec,
    ScenarioPlan,
    SearchVariable,
    default_axis,
    planned_scenarios,
    resolve_limits,
    run_search,
    spec_for,
)
from app.search.constants import DEFAULT_REFINEMENT_DEPTH, MAX_MULTI_STEPS, MAX_SWEEP_STEPS
from app.search.variables import effect_for
from app.simulator import (
    FaultSpec,
    LimitSet,
    ProcessParameters,
    SafeguardSettings,
    Scenario,
    SensorFault,
    SimulationInput,
    SimulationLimitError,
    SimulationLimits,
    volume_from_level,
)

logger = logging.getLogger("safeflux.ai.tools")

#: A tool payload larger than this is a bug, not a big result: reject rather than
#: truncate silently, so the model never reads a half-truth.
MAX_PAYLOAD_CHARS = 12000
MAX_PAYLOAD_KEYS = 40


class ToolRejected(Exception):
    """A rejected tool call: safe, value-free reason, recorded as evidence."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(reason)
        self.reason = reason
        self.detail = redact_secrets(" ".join(str(detail).split()))[:200]


@dataclass
class ToolBudget:
    """Simulation budget for one investigation, charged by the tool layer."""

    max_simulations: int
    used: int = 0

    @property
    def remaining(self) -> int:
        return max(0, self.max_simulations - self.used)

    def charge(self, count: int) -> None:
        if count < 0:
            raise ToolRejected("invalid_cost")
        if count > self.remaining:
            raise ToolRejected(
                "simulation_budget",
                f"requested {count} simulations, {self.remaining} remain",
            )
        self.used += count

    def refund(self, count: int) -> None:
        self.used = max(0, self.used - max(0, count))


@dataclass
class ToolContext:
    """Everything a tool may read. No secrets, no owner ids, no SQL handles."""

    db: Any
    user: Any
    plant: Any
    settings: Any
    telemetry: Any = None
    budget: ToolBudget = field(default_factory=lambda: ToolBudget(max_simulations=1))
    artifacts: dict[str, Any] = field(default_factory=dict)

    @property
    def profile(self) -> PlantProfile:
        profile = self.artifacts.get("profile")
        if profile is None:
            profile = PlantProfile.from_plant(self.plant)
            self.artifacts["profile"] = profile
        return profile


# ---------------------------------------------------------------------------
# Argument schemas — one per tool, all strict
# ---------------------------------------------------------------------------


class _StrictArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class NoArgs(_StrictArgs):
    """Tools that take nothing: passing anything at all is rejected."""


class HistoryArgs(_StrictArgs):
    limit: int = Field(default=30, ge=5, le=MAX_HISTORY_FRAMES)


class SimulationArgs(_StrictArgs):
    duration_s: float = Field(default=300.0, gt=0, le=3600)
    time_step_s: float = Field(default=1.0, gt=0, le=60)
    label: str = Field(default="ai scenario", max_length=120)
    faults: list[FaultIn] = Field(default_factory=list, max_length=4)
    sensor_faults: list[SensorFaultIn] = Field(default_factory=list, max_length=2)


class SearchArgs(_StrictArgs):
    mode: SearchMode = SearchMode.SWEEP
    variable: SearchVariable
    steps: int = Field(default=9, ge=2, le=MAX_SWEEP_STEPS)
    second_variable: SearchVariable | None = None
    second_steps: int = Field(default=3, ge=2, le=MAX_MULTI_STEPS)
    refine: bool = True
    duration_s: float = Field(default=300.0, gt=0, le=3600)
    time_step_s: float = Field(default=1.0, gt=0, le=60)


class CompareArgs(_StrictArgs):
    variable: SearchVariable
    low: float
    high: float
    duration_s: float = Field(default=300.0, gt=0, le=3600)
    time_step_s: float = Field(default=1.0, gt=0, le=60)


class FailureDetailsArgs(_StrictArgs):
    limit: int = Field(default=5, ge=1, le=MAX_FAILURES_REPORTED)


class SafeguardArgs(_StrictArgs):
    delay_s: float | None = Field(default=None, ge=0, le=600)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _peaks(series: dict[str, list[Any]]) -> dict[str, float | None]:
    def peak(column: str) -> float | None:
        values = series.get(column) or []
        numeric = [float(value) for value in values if isinstance(value, (int, float))]
        return round(max(numeric), 4) if numeric else None

    return {
        "temperature_c": peak("true_temperature_c"),
        "pressure_bar": peak("true_pressure_bar"),
        "level_pct": peak("level_pct"),
    }


def _finding_summary(assessment: Any, limit: int = 3) -> list[dict[str, Any]]:
    findings = sorted(
        assessment.findings,
        key=lambda finding: status_rank(finding.status),
        reverse=True,
    )
    return [
        {
            "type": finding.variable,
            "status": finding.status.value if hasattr(finding.status, "value") else str(finding.status),
            "measured_value": round(float(finding.measured_value), 4)
            if finding.measured_value is not None
            else None,
            "limit": round(float(finding.limit), 4) if finding.limit is not None else None,
            "message": str(finding.message)[:160],
        }
        for finding in findings[:limit]
    ]


def _shutdown_at(result: Any) -> float | None:
    for event in result.events:
        if event.get("kind") == "shutdown":
            return float(event["time_s"])
    return None


def _thresholds(ctx: ToolContext) -> SafetyThresholds:
    profile = ctx.profile
    fraction = getattr(ctx.settings, "SAFETY_NEAR_LIMIT_FRACTION", 0.9)
    return SafetyThresholds(
        max_temperature_c=profile.safety_limits.max_temperature_c,
        max_pressure_bar=profile.safety_limits.max_pressure_bar,
        max_level_pct=profile.safety_limits.max_level_pct,
        near_limit_fraction=float(fraction),
    )


def _simulation_limits(ctx: ToolContext) -> SimulationLimits:
    return SimulationLimits(
        max_duration_s=float(getattr(ctx.settings, "SIM_MAX_DURATION_S", 3600.0)),
        min_time_step_s=float(getattr(ctx.settings, "SIM_MIN_TIME_STEP_S", 0.05)),
        max_samples=int(getattr(ctx.settings, "SIM_MAX_SAMPLES", 20000)),
    )


def _build_input(ctx: ToolContext, scenario: Scenario, safeguards: SafeguardSettings | None = None) -> SimulationInput:
    profile = ctx.profile
    return SimulationInput(
        params=profile.params,
        initial_volume_l=profile.initial_volume_l,
        initial_temperature_c=profile.initial_temperature_c,
        scenario=scenario,
        limits=_simulation_limits(ctx),
        safety_limits=profile.safety_limits,
        safeguards=safeguards or profile.safeguards,
        plant_id=profile.plant_id,
    )


def _run_scenario(ctx: ToolContext, scenario: Scenario, safeguards: SafeguardSettings | None = None) -> dict[str, Any]:
    """Charge one simulation, run it, and return a bounded summary."""
    ctx.budget.charge(1)
    thresholds = _thresholds(ctx)
    sim_input = _build_input(ctx, scenario, safeguards=safeguards)
    try:
        assessment, result = assess_scenario(sim_input, thresholds, scenario_id=scenario.label)
    except SimulationLimitError as exc:
        ctx.budget.refund(1)
        raise ToolRejected("limits", "; ".join(message for _, message in exc.errors)) from exc

    ctx.artifacts["last_assessment"] = (assessment, result)
    return {
        "scenario": {"label": scenario.label, "duration_s": scenario.duration_s, "time_step_s": scenario.time_step_s},
        "status": assessment.status.value,
        "peaks": _peaks(result.series),
        "limit_exceeded": {
            finding.variable: finding.status is SafetyStatus.VIOLATION
            for finding in assessment.findings
        },
        "shutdown_at_s": _shutdown_at(result),
        "findings": _finding_summary(assessment),
        "samples": int(result.summary.get("sample_count", 0) or 0),
    }


def _search_axes(args: SearchArgs) -> tuple[Any, ...]:
    primary = default_axis(args.variable, steps=args.steps)
    if args.mode is SearchMode.COMBINATIONS:
        second = args.second_variable or _other_variable(args.variable)
        return (primary, default_axis(second, steps=args.second_steps, max_steps=MAX_MULTI_STEPS))
    if args.second_variable is not None and args.mode is SearchMode.SWEEP:
        # A sweep with two variables is a combination search in disguise; refuse
        # rather than quietly dropping one axis the model asked for.
        raise ToolRejected("mode_mismatch", "a sweep takes exactly one variable")
    return (primary,)


def _other_variable(variable: SearchVariable) -> SearchVariable:
    for candidate in SearchVariable:
        if candidate is not variable:
            return candidate
    return variable


# ---------------------------------------------------------------------------
# Handlers — one per allowlisted tool
# ---------------------------------------------------------------------------


def get_plant_configuration(ctx: ToolContext, args: NoArgs) -> dict[str, Any]:
    plant = ctx.plant
    config = plant.config
    return {
        "plant_id": str(plant.id),
        "name": str(getattr(plant, "name", "plant")),
        "description": str(getattr(plant, "description", "") or "")[:160],
        "location": str(getattr(plant, "location", "") or "")[:80],
        "config": {
            "feed_flow_lpm": float(config.feed_flow_lpm),
            "heater_power_pct": float(config.heater_power_pct),
            "cooling_pct": float(config.cooling_pct),
            "valve_position_pct": float(config.valve_position_pct),
            "shutdown_delay_s": float(config.shutdown_delay_s),
        },
        "unit": "simulated lumped model (never a real plant)",
    }


def get_current_state(ctx: ToolContext, args: NoArgs) -> dict[str, Any]:
    frame = None
    if ctx.telemetry is not None:
        try:
            frame = ctx.telemetry.current(str(ctx.plant.id))
        except Exception:  # noqa: BLE001 - telemetry is advisory, never fatal
            frame = None
    state = ctx.plant.state
    if frame is not None:
        return {
            "source": "live_telemetry",
            "time_s": float(frame.time_s),
            "status": frame.status.value if hasattr(frame.status, "value") else str(frame.status),
            "values": {name: round(float(value), 4) for name, value in frame.values.items()},
            "pump_running": bool(frame.pump_running),
        }
    return {
        "source": "configured_initial_state",
        "time_s": 0.0,
        "status": "unknown",
        "values": {
            "temperature_c": float(state.temperature_c),
            "pressure_bar": float(state.pressure_bar),
            "level_pct": float(state.level_pct),
        },
        "pump_running": bool(state.pump_running),
    }


def get_safety_limits(ctx: ToolContext, args: NoArgs) -> dict[str, Any]:
    thresholds = _thresholds(ctx)
    return {
        "limits": {
            "temperature_c": float(thresholds.max_temperature_c),
            "pressure_bar": float(thresholds.max_pressure_bar),
            "level_pct": float(thresholds.max_level_pct),
        },
        "near_limit": {
            "temperature_c": round(thresholds.near_limit_for("temperature_c"), 4),
            "pressure_bar": round(thresholds.near_limit_for("pressure_bar"), 4),
            "level_pct": round(thresholds.near_limit_for("level_pct"), 4),
        },
        "near_limit_fraction": float(thresholds.near_limit_fraction),
        "note": "Limits are the plant's configured values; the safety engine owns the verdict.",
    }


def get_recent_history(ctx: ToolContext, args: HistoryArgs) -> dict[str, Any]:
    frames = []
    if ctx.telemetry is not None:
        try:
            frames = ctx.telemetry.history(str(ctx.plant.id), limit=args.limit)
        except Exception:  # noqa: BLE001 - history is advisory
            frames = []
    if not frames:
        return {"source": "none", "frame_count": 0, "window_s": 0.0, "series": {}}

    series: dict[str, dict[str, float]] = {}
    for name in ("temperature_c", "pressure_bar", "level_pct"):
        values = [float(frame.values[name]) for frame in frames if name in frame.values]
        if values:
            series[name] = {
                "min": round(min(values), 4),
                "max": round(max(values), 4),
                "last": round(values[-1], 4),
            }
    statuses = [frame.status.value if hasattr(frame.status, "value") else str(frame.status) for frame in frames]
    return {
        "source": "live_telemetry",
        "frame_count": len(frames),
        "window_s": round(float(frames[-1].time_s) - float(frames[0].time_s), 3),
        "worst_status": _worst_status(statuses),
        "series": series,
    }


def _worst_status(statuses: list[str]) -> str:
    order = {"safe": 0, "near_limit": 1, "safeguard_activated": 2, "violation": 3}
    worst = "unknown"
    for status in statuses:
        if order.get(status, -1) > order.get(worst, -1):
            worst = status
    return worst


def run_simulation(ctx: ToolContext, args: SimulationArgs) -> dict[str, Any]:
    scenario = Scenario(
        duration_s=args.duration_s,
        time_step_s=args.time_step_s,
        faults=tuple(
            FaultSpec(type=fault.type, start_s=fault.start_s, factor=fault.factor, target_pct=fault.target_pct)
            for fault in args.faults
        ),
        sensor_faults=tuple(
            SensorFault(
                sensor=fault.sensor,
                start_s=fault.start_s,
                mode=fault.mode,
                magnitude=fault.magnitude,
            )
            for fault in args.sensor_faults
        ),
        label=args.label,
    )
    return _run_scenario(ctx, scenario)


def run_scenario_search(ctx: ToolContext, args: SearchArgs) -> dict[str, Any]:
    limits: SearchLimits = resolve_limits(ctx.settings)
    axes = _search_axes(args)
    if args.mode is SearchMode.SENSITIVITY:
        axes = ()
    spec = SearchSpec(
        mode=args.mode,
        plan=ScenarioPlan(duration_s=args.duration_s, time_step_s=args.time_step_s, label="ai search"),
        axes=axes if args.mode is not SearchMode.SENSITIVITY else (default_axis(args.variable),),
        refine=args.refine and args.mode is SearchMode.SWEEP,
        refinement_depth=min(DEFAULT_REFINEMENT_DEPTH, limits.max_refinement_depth),
    )

    planned = planned_scenarios(spec)
    combinations = 1
    if args.mode is SearchMode.COMBINATIONS and len(spec.axes_for_mode()) == 2:
        combinations = spec.axes_for_mode()[0].steps * spec.axes_for_mode()[1].steps

    errors = limits.validation_errors(
        duration_s=args.duration_s,
        time_step_s=args.time_step_s,
        refinement_depth=spec.refinement_depth if spec.refine else 0,
        axes=len(spec.axes_for_mode()),
        combinations=combinations,
        scenarios=planned,
    )
    if errors:
        raise ToolRejected("out_of_bounds", "; ".join(message for _, message in errors))

    ctx.budget.charge(planned)
    try:
        run = run_search(
            profile=ctx.profile,
            spec=spec,
            limits=limits,
            settings=ctx.settings,
        )
    except SimulationLimitError as exc:
        ctx.budget.refund(planned)
        raise ToolRejected("limits", "; ".join(message for _, message in exc.errors)) from exc
    except Exception:  # noqa: BLE001 - a failed search is a rejected call, not a crash
        ctx.budget.refund(planned)
        raise

    used = int(run.result.counts.get("evaluations", planned))
    ctx.budget.refund(max(0, planned - used))
    ctx.artifacts["last_search"] = run.result

    boundary = run.result.boundaries[0] if run.result.boundaries else None
    return {
        "mode": run.result.mode,
        "status": run.result.status,
        "truncated": run.result.truncated,
        "counts": {
            key: int(value)
            for key, value in run.result.counts.items()
            if key
            in {
                "scenarios",
                "safe",
                "near_limit",
                "violation",
                "safeguard_activated",
                "failing",
                "evaluations",
                "boundary_candidates",
            }
        },
        "boundary": _boundary_summary(boundary),
        "failures": [_case_summary(case) for case in run.result.failures[:3]],
        "notes": [str(note)[:200] for note in run.result.notes[:3]],
    }


def _boundary_summary(boundary: dict[str, Any] | None) -> dict[str, Any] | None:
    if not boundary:
        return None
    return {
        "variable": boundary.get("variable"),
        "last_safe": boundary.get("last_safe"),
        "first_unsafe": boundary.get("first_unsafe"),
        "estimate": boundary.get("boundary_estimate"),
        "uncertainty": boundary.get("uncertainty"),
        "monotonicity": boundary.get("monotonicity"),
        "method": boundary.get("method"),
        "refined": boundary.get("refined"),
    }


def _case_summary(case: dict[str, Any]) -> dict[str, Any]:
    finding = case.get("worst_finding") or {}
    return {
        "key": str(case.get("key", ""))[:120],
        "status": str(case.get("status", "")),
        "values": {str(name): float(value) for name, value in (case.get("values") or {}).items()},
        "peaks": case.get("peaks") or {},
        "shutdown_at_s": case.get("shutdown_at_s"),
        "message": str(finding.get("message", ""))[:200],
    }


def compare_scenarios(ctx: ToolContext, args: CompareArgs) -> dict[str, Any]:
    """Compare the same variable at two values, sorted into ``lower`` and ``upper``.

    The two points are returned by their *numeric* order (not the order the model
    wrote them), so ``temperature_delta_c`` always means ``upper − lower`` — a
    model cannot flip the sign of a comparison by swapping its arguments.
    """
    spec = spec_for(args.variable)
    lower = min(args.low, args.high)
    upper = max(args.low, args.high)
    for value in (lower, upper):
        if not spec.contains(value):
            raise ToolRejected("out_of_bounds", f"{spec.variable.value} outside its allowlisted range")

    results: dict[str, dict[str, Any]] = {}
    for label, value in (("lower", lower), ("upper", upper)):
        effect = effect_for(spec, value, 0.0)
        safeguards = ctx.profile.safeguards
        if effect.shutdown_delay_s is not None:
            from dataclasses import replace

            safeguards = replace(safeguards, trip_delay_s=float(effect.shutdown_delay_s))
        scenario = Scenario(
            duration_s=args.duration_s,
            time_step_s=args.time_step_s,
            faults=(effect.fault,) if effect.fault is not None else (),
            sensor_faults=(effect.sensor_fault,) if effect.sensor_fault is not None else (),
            label=f"compare {spec.variable.value}={value}",
        )
        results[label] = {"value": value, **_run_scenario(ctx, scenario, safeguards=safeguards)}

    lower_peak = (results["lower"].get("peaks") or {}).get("temperature_c")
    upper_peak = (results["upper"].get("peaks") or {}).get("temperature_c")
    delta = (
        round(float(upper_peak) - float(lower_peak), 4)
        if isinstance(lower_peak, (int, float)) and isinstance(upper_peak, (int, float))
        else None
    )
    return {
        "variable": spec.variable.value,
        "unit": spec.unit,
        #: Ordered by value, so the delta below always means upper − lower.
        "lower": results["lower"],
        "upper": results["upper"],
        "temperature_delta_c": delta,
        "worse_side": (
            "upper" if (delta or 0) > 0 else "lower" if (delta or 0) < 0 else "neither"
        ),
        "note": "Both points are simulator output; the comparison is arithmetic on that output.",
    }


def get_failure_details(ctx: ToolContext, args: FailureDetailsArgs) -> dict[str, Any]:
    result = ctx.artifacts.get("last_search")
    if result is None:
        raise ToolRejected("no_search_yet", "run a scenario search before asking for its failures")
    if not result.failures:
        return {"failure_count": 0, "failures": [], "note": "No failing scenario in the last search."}
    return {
        "failure_count": len(result.failures),
        "returned": min(args.limit, len(result.failures)),
        "failures": [_case_summary(case) for case in result.failures[: args.limit]],
        "boundary": _boundary_summary(result.boundaries[0] if result.boundaries else None),
    }


def check_safeguards(ctx: ToolContext, args: SafeguardArgs) -> dict[str, Any]:
    safeguards = ctx.profile.safeguards
    payload: dict[str, Any] = {
        "settings": {
            "auto_shutdown_enabled": bool(safeguards.auto_shutdown_enabled),
            "high_temperature_trip": bool(safeguards.high_temperature_trip),
            "high_pressure_trip": bool(safeguards.high_pressure_trip),
            "high_level_trip": bool(safeguards.high_level_trip),
            "trip_delay_s": float(safeguards.trip_delay_s),
        }
    }
    if args.delay_s is not None:
        from dataclasses import replace

        delay = float(args.delay_s)
        scenario = Scenario(
            duration_s=600.0,
            time_step_s=1.0,
            faults=(FaultSpec(type=_cooling_loss_type(), start_s=0.0),),
            label=f"safeguard delay {delay}s",
        )
        payload["tested"] = _run_scenario(
            ctx, scenario, safeguards=replace(safeguards, trip_delay_s=delay)
        )
        payload["delay_s"] = delay
        payload["note"] = "A delay is a safeguard property: the modelled trip fires later, the plan does not."
        return payload

    last = ctx.artifacts.get("last_assessment")
    if last is not None:
        assessment, _result = last
        payload["last_assessment"] = {
            "status": assessment.status.value,
            "safeguards": [
                {
                    "safeguard": str(timing.safeguard),
                    "trigger_time_s": timing.trigger_time_s,
                    "response_time_s": timing.response_time_s,
                    "violation_time_s": timing.violation_time_s,
                    "prevented": timing.prevented,
                    "note": str(timing.note)[:160],
                }
                for timing in assessment.safeguards[:4]
            ],
        }
    return payload


def _cooling_loss_type():
    from app.simulator.scenario import FaultType

    return FaultType.COOLING_LOSS


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args_model: type[BaseModel]
    handler: Callable[[ToolContext, Any], dict[str, Any]]
    charges_simulations: bool = False


TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        "get_plant_configuration",
        "Read the plant's configured process values and safeguards.",
        NoArgs,
        get_plant_configuration,
    ),
    ToolSpec(
        "get_current_state",
        "Read the current simulated state (live telemetry if available, else configured).",
        NoArgs,
        get_current_state,
    ),
    ToolSpec("get_safety_limits", "Read the configured limits and near-limit bands.", NoArgs, get_safety_limits),
    ToolSpec(
        "get_recent_history",
        "Read a bounded summary of recent telemetry frames.",
        HistoryArgs,
        get_recent_history,
    ),
    ToolSpec(
        "run_simulation",
        "Run one deterministic scenario (allowlisted faults only) and assess it.",
        SimulationArgs,
        run_simulation,
        charges_simulations=True,
    ),
    ToolSpec(
        "run_scenario_search",
        "Run one bounded scenario search over allowlisted variables.",
        SearchArgs,
        run_scenario_search,
        charges_simulations=True,
    ),
    ToolSpec(
        "compare_scenarios",
        "Run the same variable at two allowlisted values and compare the outcomes.",
        CompareArgs,
        compare_scenarios,
        charges_simulations=True,
    ),
    ToolSpec(
        "get_failure_details",
        "Read the failure rows and boundary of the last scenario search.",
        FailureDetailsArgs,
        get_failure_details,
    ),
    ToolSpec(
        "check_safeguards",
        "Read safeguard settings and timing, optionally testing a shutdown delay.",
        SafeguardArgs,
        check_safeguards,
        charges_simulations=True,
    ),
)

TOOLS: dict[str, ToolSpec] = {spec.name: spec for spec in TOOL_SPECS}
TOOL_NAMES: tuple[str, ...] = tuple(spec.name for spec in TOOL_SPECS)


def tool_catalog() -> list[dict[str, Any]]:
    """Public description of the tool layer (no internals, no secrets)."""
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "charges_simulations": spec.charges_simulations,
            "arguments": sorted(spec.args_model.model_fields.keys()),
        }
        for spec in TOOL_SPECS
    ]


def _bound_payload(value: Any, depth: int = 0) -> Any:
    """Recursively bound and redact anything handed back to the model."""
    if depth > 4:
        return "[depth]"
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        return redact_secrets(value)[:240]
    if isinstance(value, dict):
        bounded: dict[str, Any] = {}
        for key, item in list(value.items())[:MAX_PAYLOAD_KEYS]:
            bounded[str(key)[:40]] = _bound_payload(item, depth + 1)
        return bounded
    if isinstance(value, (list, tuple)):
        return [_bound_payload(item, depth + 1) for item in list(value)[:MAX_EVIDENCE_ITEMS]]
    return redact_secrets(str(value))[:120]


def call_tool(
    name: str,
    raw_arguments: dict[str, Any],
    ctx: ToolContext,
) -> tuple[bool, dict[str, Any], str | None, int]:
    """Validate and run one tool call.

    Returns ``(ok, payload, error, latency_ms)``. Every failure path is a *safe*
    rejection: an unknown tool, an invalid argument, a budget refusal, a
    simulator limit or an internal error all come back as a curated reason the
    model can react to. Nothing is executed on the model's behalf.
    """
    started = time.monotonic()
    spec = TOOLS.get(name)
    if spec is None:
        return False, {}, "unknown_tool", int((time.monotonic() - started) * 1000)

    if not isinstance(raw_arguments, dict):
        return False, {}, "arguments_not_object", int((time.monotonic() - started) * 1000)

    try:
        args = spec.args_model.model_validate(raw_arguments)
    except ValidationError as exc:
        fields = ", ".join(
            ".".join(str(part) for part in error.get("loc", ())) or "body" for error in exc.errors()[:3]
        )
        return False, {}, f"invalid_arguments:{fields}"[:200], int((time.monotonic() - started) * 1000)

    try:
        payload = spec.handler(ctx, args)
    except ToolRejected as exc:
        logger.info("AI tool rejected: tool=%s reason=%s", name, exc.reason)
        return False, {}, exc.reason, int((time.monotonic() - started) * 1000)
    except SimulationLimitError as exc:
        return False, {}, "limits", int((time.monotonic() - started) * 1000)
    except ValueError as exc:
        return False, {}, f"invalid_input:{redact_secrets(str(exc))[:80]}", int(
            (time.monotonic() - started) * 1000
        )
    except Exception:  # noqa: BLE001 - never leak a traceback to the model
        logger.exception("AI tool failed: tool=%s", name)
        return False, {}, "tool_error", int((time.monotonic() - started) * 1000)

    # A handler returning more than the cap is a bug, not a big result: reject it
    # rather than quietly handing the model a truncated half-truth.
    try:
        raw_size = len(json.dumps(payload, default=str))
    except (TypeError, ValueError):
        return False, {}, "payload_not_serializable", int((time.monotonic() - started) * 1000)
    if raw_size > MAX_PAYLOAD_CHARS or len(payload) > MAX_PAYLOAD_KEYS:
        logger.warning("AI tool payload too large: tool=%s chars=%s", name, raw_size)
        return False, {}, "payload_too_large", int((time.monotonic() - started) * 1000)

    bounded = _bound_payload(payload)
    try:
        serialized = json.dumps(bounded, default=str)
    except (TypeError, ValueError):
        return False, {}, "payload_not_serializable", int((time.monotonic() - started) * 1000)
    if len(serialized) > MAX_PAYLOAD_CHARS or len(bounded) > MAX_PAYLOAD_KEYS:
        return False, {}, "payload_too_large", int((time.monotonic() - started) * 1000)

    return True, bounded, None, int((time.monotonic() - started) * 1000)


__all__ = [
    "MAX_PAYLOAD_CHARS",
    "TOOLS",
    "TOOL_NAMES",
    "TOOL_SPECS",
    "CompareArgs",
    "FailureDetailsArgs",
    "HistoryArgs",
    "NoArgs",
    "SafeguardArgs",
    "SearchArgs",
    "SimulationArgs",
    "ToolBudget",
    "ToolContext",
    "ToolRejected",
    "ToolSpec",
    "call_tool",
    "tool_catalog",
]
