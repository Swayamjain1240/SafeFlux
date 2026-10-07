"""The autonomous analysis runner (Part 9).

One run walks the exact pipeline the task names — understanding change →
mapping equipment → planning → running scenario → observing result → refining
boundary → finding violation → running counterfactuals → checking safeguards —
and every stage is recorded by the code that actually did the work.

Truth discipline (the reason this module exists):
- every *value* comes from the Part 7 search over the Part 4 simulator with the
  Part 5 safety engine; the runner invents no number,
- every *event* is written when the work happened, with the measured elapsed
  time; nothing is replayed, faked or animated,
- the AI (if configured) may only summarize evidence *after* it exists; its
  text is stored separately and can never become a verdict or a value,
- the run is bounded: one bounded sweep search plus a small counterfactual set
  and one safeguard re-computation — never an open loop.
"""

from __future__ import annotations

import logging

from app.analyses.constants import (
    AI_NOT_CONFIGURED_NOTE,
    ANALYSIS_DISCLAIMER,
    MAX_COUNTERFACTUALS,
    NO_UNSAFE_DETECTED_NOTE,
    SERIES_KEYS,
    UNSAFE_DETECTED_NOTE,
)
from app.analyses.events import EventRecorder, stage_index
from app.analyses.interpret import InterpretedChange
from app.ai.constants import MAX_FOCUS_TEXT_CHARS
from app.safety import SafetyThresholds, assess_scenario
from app.safety.safeguards import evaluate_safeguards
from app.search import (
    PlantProfile,
    SearchMode,
    SearchVariable,
    make_case,
    resolve_limits,
    run_search,
    versions as search_versions,
)
from app.search.constants import SEARCH_DISCLAIMER
from app.search.spec import SearchSpec, SweepAxis
from app.search.variables import spec_for

logger = logging.getLogger("safeflux.analysis.runner")

#: Sweep resolution per variable: 9 steps brackets the whole range, matching
#: the Part 7 default, and refinement narrows from there when it applies.
SWEEP_STEPS = 9
#: The run's scenario duration; Part 9 fixes a plan rather than taking input.
RUN_DURATION_S = 600.0
RUN_TIME_STEP_S = 1.0

_TIMELINE_ORDER = (
    "understanding_change",
    "mapping_equipment",
    "planning",
    "running_scenario",
    "observing_result",
    "refining_boundary",
    "finding_violation",
    "running_counterfactual",
    "checking_safeguard",
    "ai_summary",
    "complete",
    "failed",
)

_DEFAULT_VARIABLES = (
    SearchVariable.COOLING_FACTOR.value,
    SearchVariable.FEED_FACTOR.value,
    SearchVariable.OUTLET_FACTOR.value,
    SearchVariable.VALVE_TARGET_PCT.value,
)


def _series_by_key(result) -> dict:
    """The simulator's own series, restricted to what a page may draw."""
    series = getattr(result, "series", {}) or {}
    return {key: list(series[key]) for key in SERIES_KEYS if key in series}


class AnalysisRunner:
    """Executes one autonomous analysis and produces its evidence document."""

    def __init__(
        self,
        db,  # noqa: ANN001 - Session (kept for symmetry with the service layer)
        analysis_id: str,
        profile: PlantProfile,
        settings,  # noqa: ANN001 - Settings / stub
        goal_text: str,
        interpretation: InterpretedChange,
        recorder: EventRecorder,
        *,
        summarizer=None,
    ) -> None:
        self._db = db
        self._analysis_id = analysis_id
        self._profile = profile
        self._settings = settings
        self._goal_text = goal_text
        self._interpretation = interpretation
        self._recorder = recorder
        self._summarizer = summarizer
        self._evaluator = None

    # ------------------------------------------------------------- helpers

    def _emit(self, kind: str, *, label: str | None = None, payload: dict | None = None) -> None:
        self._recorder.emit(kind, label=label, payload=payload)

    @property
    def _variables(self) -> list[str]:
        """Variables worth searching: those the goal names, else the defaults."""
        named = list(self._interpretation.variables) or list(_DEFAULT_VARIABLES)
        return named

    # ------------------------------------------------------------- pipeline

    def run(self) -> dict:
        """Execute the whole pipeline and return the result document."""
        variables = self._variables

        # -- Stage 1: understanding change (real text, read mechanically) ----
        self._emit("understanding_change", payload=self._interpretation.to_dict())

        # -- Stage 2: mapping affected equipment ------------------------------
        self._emit(
            "mapping_equipment",
            payload={
                "variables": variables,
                "safety_limits": {
                    "max_temperature_c": self._profile.safety_limits.max_temperature_c,
                    "max_pressure_bar": self._profile.safety_limits.max_pressure_bar,
                    "max_level_pct": self._profile.safety_limits.max_level_pct,
                },
                "safeguards": {
                    "auto_shutdown_enabled": self._profile.safeguards.auto_shutdown_enabled,
                    "trip_delay_s": self._profile.safeguards.trip_delay_s,
                },
            },
        )

        # -- Stage 3: planning investigation ----------------------------------
        plan = self._build_plan(variables)
        self._emit("planning", payload=plan)

        # -- Stage 4: running the bounded scenario search ---------------------
        document = self._run_search(plan)
        self._emit(
            "running_scenario",
            payload={
                "mode": document.get("mode"),
                "status": document.get("status"),
                "scenarios": self._count_scenarios(document),
            },
        )

        # -- Stage 5: observing result ----------------------------------------
        counts = dict(document.get("counts", {}))
        self._emit("observing_result", payload={"counts": counts, "notes": document.get("notes", [])})

        # -- Stage 6: refining the boundary ------------------------------------
        boundaries = list(document.get("boundaries", []))
        if boundaries:
            self._emit("refining_boundary", payload={"boundaries": boundaries})

        # -- Stage 7: finding the limiting violation ---------------------------
        failures = list(document.get("failures", []))
        pivot = max(failures, key=lambda item: int(item.get("rank", 0))) if failures else None
        if pivot is not None:
            self._emit(
                "finding_violation",
                payload={
                    "case_key": pivot.get("key"),
                    "case_label": pivot.get("label"),
                    "status": pivot.get("status"),
                    "peaks": pivot.get("peaks", {}),
                    "values": pivot.get("values", {}),
                },
            )
        else:
            self._emit("finding_violation", payload={"found": False})

        # -- Stage 8: counterfactual comparisons --------------------------------
        counterfactuals = self._run_counterfactuals(pivot)

        # -- Stage 9: safeguard check (trigger/response/violation timing) --------
        safeguards = self._run_safeguard_check(pivot)

        # -- Optional AI summary: AFTER the evidence, never instead of it --------
        ai_summary, ai_note = self._run_ai_summary(pivot, counterfactuals, safeguards)

        return self._build_document(
            plan=plan,
            original=document,
            pivot=pivot,
            counterfactuals=counterfactuals,
            safeguards=safeguards,
            ai_summary=ai_summary,
            ai_note=ai_note,
        )

    # ------------------------------------------------------------ components

    def _build_plan(self, variables: list[str]) -> dict:
        """The deterministic plan derived from the interpreted change."""
        axes: list[dict] = []
        for variable in variables:
            spec = spec_for(SearchVariable(variable))
            axes.append(
                {
                    "variable": variable,
                    "minimum": spec.minimum,
                    "maximum": spec.maximum,
                    "steps": SWEEP_STEPS,
                }
            )
        return {
            "goal": self._goal_text[:MAX_FOCUS_TEXT_CHARS],
            "interpreted_change": self._interpretation.to_dict(),
            "variables": variables,
            "axes": axes,
            "modes": [SearchMode.SWEEP.value],
            "duration_s": RUN_DURATION_S,
            "time_step_s": RUN_TIME_STEP_S,
        }

    def _run_search(self, plan: dict) -> dict:
        """The real Part 7 search — bounded, deterministic, no AI anywhere."""
        axes = tuple(
            SweepAxis(
                variable=SearchVariable(axis["variable"]),
                minimum=float(axis["minimum"]),
                maximum=float(axis["maximum"]),
                steps=int(axis["steps"]),
            )
            for axis in plan["axes"]
        )
        spec = SearchSpec(
            mode=SearchMode.SWEEP,
            plan=self._scenario_plan("seeded search"),
            axes=axes,
            refine=True,
        )
        run = run_search(
            profile=self._profile,
            spec=spec,
            limits=resolve_limits(self._settings),
            settings=self._settings,
        )
        return run.result.to_dict()

    def _run_counterfactuals(self, pivot: dict | None) -> list[dict]:
        """Restore-one-change comparisons anchored on the pivot failure."""
        if pivot is None:
            return []
        values = dict(pivot.get("values") or {})
        evaluator = self._evaluator
        assert evaluator is not None
        counterfactuals: list[dict] = []
        for variable, value, label in self._candidates(values):
            if len(counterfactuals) >= MAX_COUNTERFACTUALS:
                break
            case = make_case({**values, variable: value}, label=label)
            self._emit("running_counterfactual", payload={**case.as_dict(), "label": label})
            evaluation = evaluator.evaluate(case).to_dict()
            peaks_before = dict(pivot.get("peaks") or {})
            peaks_after = dict(evaluation.get("peaks") or {})
            status_before = pivot.get("status")
            status_after = evaluation.get("status")
            changes = []
            for key in ("temperature_c", "pressure_bar", "level_pct"):
                before_value = peaks_before.get(key)
                after_value = peaks_after.get(key)
                changes.append(
                    {
                        "variable": key,
                        "before": before_value,
                        "after": after_value,
                        "delta": None
                        if before_value is None or after_value is None
                        else round(after_value - before_value, 6),
                    }
                )
            counterfactuals.append(
                {
                    "variable": variable,
                    "value": value,
                    "label": label,
                    "status_before": status_before,
                    "status": status_after,
                    "improved": (
                        None
                        if status_before is None or status_after is None
                        else int(evaluation.get("rank", 0)) < int(pivot.get("rank", 0))
                    ),
                    "peaks": peaks_after,
                    "changes": changes,
                    "case_key": evaluation.get("key") or case.key(),
                    "ai_explanation": None,
                }
            )
        return counterfactuals

    def _candidates(self, values: dict) -> list[tuple[str, float, str]]:
        """Restore-to-neutral targets, disambiguated by direction of the goal."""
        candidates: list[tuple[str, float, str]] = []
        direction = self._interpretation.direction
        requested = {name: value for name, value in values.items()}
        for name in sorted(requested):
            try:
                spec = spec_for(SearchVariable(name))
            except ValueError:
                continue
            target = spec.neutral if spec.neutral is not None else requested[name]
            if target is None or abs(target - requested[name]) <= 1e-12:
                continue
            label = f"restore {spec.label}"
            if direction == "increase" and target > requested[name]:
                label = f"reduce {spec.label} to neutral"
            candidates.append((name, target, label))
        return candidates

    def _run_safeguard_check(self, pivot: dict | None) -> dict:
        """Trigger/response/violation timing from a real bounded re-simulation."""
        evaluator = self._evaluator
        assert evaluator is not None
        if pivot is not None:
            case = make_case(dict(pivot.get("values") or {}), label="plant under change")
        else:
            case = make_case({}, label="plant as configured")
        self._emit("checking_safeguard", payload={"case_key": case.key()})
        _assessment, result = assess_scenario(
            evaluator.build_input(case),
            evaluator.thresholds,
            scenario_id=f"{self._analysis_id}:safeguard",
        )
        timings = [
            timing.to_dict()
            for timing in evaluate_safeguards(
                result,
                evaluator.thresholds,
                self._profile.safeguards,
            )
        ]
        return {
            "case_key": case.key(),
            "case_label": case.label,
            "timings": timings,
            "note": (
                "Times describe the simulated response of the modelled safeguard, "
                "not the behaviour of a real plant."
            ),
        }

    def _run_ai_summary(self, pivot, counterfactuals, safeguards):
        """Optional AI summary AFTER all evidence exists."""
        if self._summarizer is None:
            return None, AI_NOT_CONFIGURED_NOTE
        if pivot is None and not counterfactuals:
            return None, AI_NOT_CONFIGURED_NOTE
        self._emit("ai_summary", payload={"started": True})
        try:
            summary = self._summarizer(
                evidence={
                    "pivot": pivot,
                    "counterfactuals": counterfactuals,
                    "safeguards": safeguards,
                }
            )
        except Exception as exc:  # noqa: BLE001 - provider failure is never fatal to the run
            logger.warning("AI summary failed: %s", exc)
            self._emit(
                "ai_summary",
                payload={"configured": True, "ok": False, "error_category": "provider_error"},
            )
            return (
                None,
                "The AI explanation could not be produced; the simulation evidence "
                "stands on its own.",
            )
        text = (summary or {}).get("text")
        self._emit("ai_summary", payload={"configured": True, "ok": bool(text)})
        return summary, None

    # ------------------------------------------------------------- evaluator

    def _evaluator_for(self):
        """One shared evaluator so counterfactuals reuse the simulation cache."""
        if self._evaluator is None:
            from app.search.evaluate import ScenarioEvaluator
            from app.search.budgets import SearchBudget

            spec = SearchSpec(
                mode=SearchMode.SWEEP,
                plan=self._scenario_plan("analysis cases"),
                axes=(),
                refine=False,
            )
            self._evaluator = ScenarioEvaluator(
                profile=self._profile,
                spec=spec,
                thresholds=self._thresholds(),
                limits=self._sim_limits(),
                budget=SearchBudget(limits=resolve_limits(self._settings)),
            )
        return self._evaluator

    def _scenario_plan(self, label: str):
        from app.search.spec import ScenarioPlan

        return ScenarioPlan(
            duration_s=RUN_DURATION_S,
            time_step_s=RUN_TIME_STEP_S,
            start_s=0.0,
            label=f"{label}:{self._analysis_id}",
        )

    def _sim_limits(self):
        from app.simulator import SimulationLimits

        return SimulationLimits(
            max_duration_s=getattr(self._settings, "SIM_MAX_DURATION_S", 3600.0),
            min_time_step_s=getattr(self._settings, "SIM_MIN_TIME_STEP_S", 0.05),
            max_samples=getattr(self._settings, "SIM_MAX_SAMPLES", 20000),
        )

    def _thresholds(self) -> SafetyThresholds:
        return SafetyThresholds(
            max_temperature_c=self._profile.safety_limits.max_temperature_c,
            max_pressure_bar=self._profile.safety_limits.max_pressure_bar,
            max_level_pct=self._profile.safety_limits.max_level_pct,
            near_limit_fraction=getattr(self._settings, "SAFETY_NEAR_LIMIT_FRACTION", 0.9),
        )

    # ------------------------------------------------------------- document

    @staticmethod
    def _count_scenarios(document: dict) -> int:
        return int((document.get("counts") or {}).get("scenarios", 0))

    def _build_document(
        self,
        *,
        plan: dict,
        original: dict,
        pivot: dict | None,
        counterfactuals: list[dict],
        safeguards: dict,
        ai_summary: dict | None,
        ai_note: str | None,
    ) -> dict:
        """Assemble the result document (the evidence the UI and report read)."""
        notes: list[str] = [SEARCH_DISCLAIMER, ANALYSIS_DISCLAIMER]
        failures = list(original.get("failures", []))
        notes.append(NO_UNSAFE_DETECTED_NOTE if not failures else UNSAFE_DETECTED_NOTE)
        if ai_note:
            notes.append(ai_note)
        return {
            "analysis_id": self._analysis_id,
            "kind": "auto",
            "goal": self._goal_text[:MAX_FOCUS_TEXT_CHARS],
            "interpreted_change": self._interpretation.to_dict(),
            "plan": plan,
            "original": original,
            "failures": failures,
            "pivot": pivot,
            "counterfactuals": counterfactuals,
            "safeguards": safeguards,
            "ai_explanation": ai_summary,
            "notes": notes,
            "versions": search_versions(),
            "series_keys": list(SERIES_KEYS),
            "timeline_order": list(_TIMELINE_ORDER),
            "stage_index": {kind: stage_index(kind) for kind in _TIMELINE_ORDER},
        }


__all__ = ["AnalysisRunner", "RUN_DURATION_S", "RUN_TIME_STEP_S", "SWEEP_STEPS", "_series_by_key"]
