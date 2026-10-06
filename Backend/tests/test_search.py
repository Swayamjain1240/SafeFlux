"""Deterministic scenario search engine coverage (Part 7, rule 23).

Engine-level tests: no HTTP. A fake runner stands in for the real simulator so
tests are fast and can drive the budget clock; the real model is exercised end
to end in ``test_search_api.py``.

Covers: coarse sweep, boundary refinement (safe and failing boundary, both risk
directions), bisection-only-when-monotonic, repeatability, combination search,
sensitivity, the hard scenario budget, the injectable-clock timeout, and the
value-no-echo guarantee.
"""

from __future__ import annotations

import pytest

from app.search import (
    METHOD_VERSION,
    SEARCH_DISCLAIMER,
    Monotonicity,
    PlantProfile,
    SearchBudget,
    SearchBudgetExceeded,
    SearchLimits,
    SearchMode,
    SearchSpec,
    SearchVariable,
    ScenarioPlan,
    classify_monotonic,
    default_axis,
    make_case,
    planned_scenarios,
    run_search,
    spec_for,
    supports_bisection,
)
from app.safety import SafetyAssessment, SafetyFinding, SafetyStatus
from app.simulator import (
    LimitSet,
    ProcessParameters,
    SafeguardSettings,
    SimulationInput,
    SimulationResult,
)


# ---------------------------------------------------------------------------
# Harness: a plant snapshot and deterministic fake simulations
# ---------------------------------------------------------------------------


def _profile() -> PlantProfile:
    """A plant snapshot with the API's baseline configuration."""
    return PlantProfile(
        plant_id="11111111-1111-1111-1111-111111111111",
        name="Reactor Train A",
        params=ProcessParameters(
            feed_flow_lpm=120.0,
            heater_power_pct=60.0,
            cooling_pct=90.0,
            valve_position_pct=55.0,
            pump_running=True,
        ),
        initial_volume_l=900.0,
        initial_temperature_c=80.0,
        safety_limits=LimitSet(max_temperature_c=150.0, max_pressure_bar=10.0, max_level_pct=90.0),
        safeguards=SafeguardSettings(
            auto_shutdown_enabled=True,
            high_temperature_trip=True,
            high_pressure_trip=True,
            high_level_trip=True,
            trip_delay_s=30.0,
        ),
        config={
            "feed_flow_lpm": 120.0,
            "heater_power_pct": 60.0,
            "cooling_pct": 90.0,
            "valve_position_pct": 55.0,
            "shutdown_delay_s": 5,
            "initial_level_pct": 45.0,
            "initial_temperature_c": 80.0,
            "initial_pressure_bar": 4.0,
            "pump_running": True,
        },
    )


def _limits(**overrides) -> SearchLimits:
    values = {
        "max_scenarios": 150,
        "max_combinations": 36,
        "max_refinement_depth": 6,
        "timeout_s": 90.0,
    }
    values.update(overrides)
    return SearchLimits(**values)


def _spec(**overrides) -> SearchSpec:
    values = {
        "mode": SearchMode.SWEEP,
        "plan": ScenarioPlan(duration_s=300.0, time_step_s=1.0),
        "axes": (default_axis(SearchVariable.COOLING_FACTOR, steps=9),),
        "refine": False,
    }
    values.update(overrides)
    return SearchSpec(**values)


def _classify(thresholds, peak: float) -> SafetyStatus:
    if peak >= thresholds.max_temperature_c:
        return SafetyStatus.VIOLATION
    if peak >= thresholds.near_limit_for("temperature_c"):
        return SafetyStatus.NEAR_LIMIT
    return SafetyStatus.SAFE


def _assessment(peak: float, thresholds) -> SafetyAssessment:
    """Status plus the temperature finding the real safety engine would emit.

    The search engine derives ``limit_exceeded`` from findings (keyed by the
    finding's variable), so a faithful fake must ship one once the limit is
    approached — and none while the plant stays safely below it.
    """
    status = _classify(thresholds, peak)
    near = thresholds.near_limit_for("temperature_c")
    findings = [
        SafetyFinding(
            variable="temperature_c",
            status=status,
            timestamp_s=None,
            measured_value=peak,
            limit=thresholds.max_temperature_c,
            near_limit=near,
            scenario_id=None,
            message=f"peak {peak:.1f} degC vs limit {thresholds.max_temperature_c:.1f} degC",
        )
    ] if peak >= near else []
    return SafetyAssessment(status=status, findings=findings)


def _fault_factor(sim_input: SimulationInput, fault_name: str) -> float:
    for fault in sim_input.scenario.faults:
        if fault.type.value == fault_name:
            return float(fault.factor)
    return 1.0


def _cooling_runner(risk: float = 100.0):
    """Peak temperature ``risk / cooling_factor`` degC.

    Risk rises as cooling falls: classic monotonic behaviour. The violation
    boundary sits at cooling_factor = risk / 150 (2/3 for the default risk=100).
    """

    def runner(sim_input: SimulationInput, thresholds, scenario_id: str):
        factor = _fault_factor(sim_input, "cooling_degradation")
        peak = risk / max(factor, 1e-9)
        assessment = _assessment(peak, thresholds)
        result = SimulationResult(
            # The evaluator reads evidence peaks from the series columns, so
            # even this fake must ship the real simulator's column names.
            series={
                "true_temperature_c": [peak],
                "true_pressure_bar": [4.0],
                "level_pct": [45.0],
            },
            summary={"peak_temperature_c": peak},
            metadata={"deterministic": True, "scenario_id": scenario_id},
        )
        return assessment, result

    return runner


def _feed_runner():
    """Peak temperature rises with the feed factor (risk direction: increasing)."""

    def runner(sim_input: SimulationInput, thresholds, scenario_id: str):
        feed = _fault_factor(sim_input, "feed_increase")
        peak = 40.0 + 30.0 * feed
        assessment = _assessment(peak, thresholds)
        return assessment, SimulationResult(
            series={
                "true_temperature_c": [peak],
                "true_pressure_bar": [4.0],
                "level_pct": [45.0],
            },
            metadata={"deterministic": True},
        )

    return runner


# ---------------------------------------------------------------------------
# coarse sweep
# ---------------------------------------------------------------------------


def test_coarse_sweep_classifies_every_point():
    # risk=100: the violation boundary sits at cooling_factor = 2/3, so the
    # coarse grid (step 0.125) yields three safe points and six violations.
    run = run_search(
        profile=_profile(), spec=_spec(refine=False), limits=_limits(), runner=_cooling_runner(100.0)
    )

    result = run.result
    assert result.status == "complete"
    assert result.mode == "sweep"
    assert result.counts["scenarios"] == 9
    assert result.counts["distinct_cases"] == 9
    assert result.counts["violation"] == 6
    assert result.counts["safe"] == 3
    assert result.counts["failing"] == 6
    assert len(result.cases) == 9
    assert {case["status"] for case in result.cases} == {"safe", "violation"}
    assert result.failures and result.failures[0]["values"]["cooling_factor"] == 0.0
    # Every case carries evidence, not just a label.
    failing = result.failures[0]
    assert failing["peaks"]["temperature_c"] > 150.0
    assert failing["limit_exceeded"]["temperature_c"] is True


def test_coarse_sweep_visits_safe_end_first():
    """The trace reads like the brief's example: 100 SAFE ... 40 VIOLATION."""
    run = run_search(
        profile=_profile(), spec=_spec(refine=False), limits=_limits(), runner=_cooling_runner(100.0)
    )

    sweep_entries = [
        entry
        for entry in run.result.trace
        if entry["kind"] == "case" and entry["detail"]["phase"] == "sweep"
    ]
    values = [entry["detail"]["value"] for entry in sweep_entries]
    assert values[0] == pytest.approx(1.0)
    assert values[-1] == pytest.approx(0.0)
    assert values == sorted(values, reverse=True)
    assert sweep_entries[0]["detail"]["status"] == "safe"
    assert sweep_entries[-1]["detail"]["status"] == "violation"


def test_sweep_values_are_a_deterministic_linspace():
    axis = default_axis(SearchVariable.COOLING_FACTOR, steps=5)
    # values() is the ascending canonical linspace (min -> max); the safe-end-
    # first traversal order is a separate concern (traverse_order, above).
    assert axis.values() == [0.0, 0.25, 0.5, 0.75, 1.0]
    assert axis.values() == default_axis(SearchVariable.COOLING_FACTOR, steps=5).values()


# ---------------------------------------------------------------------------
# boundary refinement
# ---------------------------------------------------------------------------


def test_boundary_refinement_bisects_a_safe_failing_boundary():
    # True boundary at 2/3: between the coarse 0.75 (safe) and 0.625 (violation).
    run = run_search(
        profile=_profile(), spec=_spec(refine=True), limits=_limits(), runner=_cooling_runner(100.0)
    )

    boundary = run.result.boundaries[0]
    assert boundary["variable"] == "cooling_factor"
    assert boundary["monotonicity"] == "decreasing"
    assert boundary["method"] == "bisection"
    assert boundary["refined"] is True
    assert boundary["last_safe"] is not None and boundary["first_unsafe"] is not None
    assert boundary["last_safe"] == pytest.approx(2 / 3, abs=0.05)
    assert boundary["first_unsafe"] == pytest.approx(2 / 3, abs=0.05)
    # Cooling is a decreasing-direction variable: the safe side is the HIGH
    # end, so the numerically last safe value sits just above the first unsafe
    # one. Never assert a fixed numeric order without knowing the direction.
    assert boundary["last_safe"] > boundary["first_unsafe"]
    assert 0.0 < boundary["uncertainty"] < 0.125  # tighter than the coarse step
    assert boundary["boundary_estimate"] is not None
    assert run.result.counts["boundary_candidates"] == 1
    # Refinement evaluations land in the counts and the trace.
    assert run.result.counts["evaluations"] > 9
    assert any(entry["kind"] == "refine" for entry in run.result.trace)


def test_boundary_refinement_also_works_when_risk_increases():
    """The same machinery on an increasing axis: feed increase vs the limit."""
    spec = _spec(axes=(default_axis(SearchVariable.FEED_FACTOR, steps=9),), refine=True)
    run = run_search(profile=_profile(), spec=spec, limits=_limits(), runner=_feed_runner())

    boundary = run.result.boundaries[0]
    assert boundary["monotonicity"] == "increasing"
    assert boundary["method"] == "bisection"
    assert boundary["refined"] is True
    # True boundary at 40 + 30f = 150 -> f = 11/3.
    assert boundary["last_safe"] == pytest.approx(11 / 3, abs=0.05)
    assert boundary["first_unsafe"] == pytest.approx(11 / 3, abs=0.05)
    assert boundary["last_safe"] < boundary["first_unsafe"]


def test_bisection_not_used_when_non_monotonic():
    calls: list[float] = []

    def runner(sim_input: SimulationInput, thresholds, scenario_id: str):
        factor = _fault_factor(sim_input, "cooling_degradation")
        calls.append(factor)
        # A deliberately non-monotonic world: safe everywhere except a spike at
        # exactly 0.25. Bisection on this would converge on the wrong point.
        # The spike must cross the limit, otherwise no bracket ever exists.
        peak = 200.0 if abs(factor - 0.25) < 0.01 else 50.0
        status = (
            SafetyStatus.SAFEGUARD_ACTIVATED
            if peak >= thresholds.max_temperature_c
            else SafetyStatus.SAFE
        )
        return SafetyAssessment(status=status), SimulationResult(
            series={
                "true_temperature_c": [peak],
                "true_pressure_bar": [4.0],
                "level_pct": [45.0],
            },
            metadata={"deterministic": True},
        )

    spec = _spec(axes=(default_axis(SearchVariable.COOLING_FACTOR, steps=9),), refine=True)
    run = run_search(profile=_profile(), spec=spec, limits=_limits(), runner=runner)

    boundary = run.result.boundaries[0]
    assert boundary["monotonicity"] == "non_monotonic"
    assert boundary["method"] == "densify"
    assert boundary["refined"] is True
    assert boundary["last_safe"] is not None and boundary["first_unsafe"] is not None
    assert any("densified" in note for note in run.result.notes)
    # Densify evaluates strictly inside the bracket it was given.
    coarse_values = {1.0, 0.875, 0.75, 0.625, 0.5, 0.375, 0.25, 0.125, 0.0}
    refined_values = [value for value in calls if value not in coarse_values]
    assert refined_values
    assert all(0.25 < value < 0.375 for value in refined_values)


def test_monotonic_classifier_gates_bisection():
    assert classify_monotonic([0.0, 0.0, 1.0, 1.0]) is Monotonicity.INCREASING
    assert classify_monotonic([3.0, 2.0, 2.0, 0.0]) is Monotonicity.DECREASING
    assert classify_monotonic([0.0, 3.0, 0.0]) is Monotonicity.NON_MONOTONIC
    assert classify_monotonic([2.0]) is Monotonicity.INSUFFICIENT
    assert classify_monotonic([1.0, 1.0, 1.0]) is Monotonicity.INSUFFICIENT
    assert supports_bisection(Monotonicity.NON_MONOTONIC) is False
    assert supports_bisection(Monotonicity.INSUFFICIENT) is False
    assert supports_bisection(Monotonicity.DECREASING) is True


def test_no_boundary_note_when_everything_stays_safe():
    spec = _spec(
        axes=(default_axis(SearchVariable.COOLING_FACTOR, minimum=0.2, maximum=1.0, steps=9),),
        refine=True,
    )
    run = run_search(profile=_profile(), spec=spec, limits=_limits(), runner=_cooling_runner(10.0))

    assert run.result.status == "complete"
    assert run.result.counts["violation"] == 0
    assert run.result.boundaries[0]["refined"] is False
    assert run.result.boundaries[0]["last_safe"] is None
    assert any("No failing boundary" in note for note in run.result.notes)


def test_observation_only_axis_is_labelled():
    spec = _spec(axes=(default_axis(SearchVariable.TEMPERATURE_SENSOR_BIAS_C, steps=5),), refine=False)
    run = run_search(profile=_profile(), spec=spec, limits=_limits(), runner=_cooling_runner(10.0))

    # Four of the five biases are active (0.0 is the neutral no-op).
    assert run.result.counts["observation_only"] == 4
    assert any("sensor" in note.lower() for note in run.result.notes)


# ---------------------------------------------------------------------------
# repeatability
# ---------------------------------------------------------------------------


def test_identical_runs_produce_identical_documents():
    spec = _spec(refine=True)

    def once() -> dict:
        # A fixed injected clock keeps the elapsed-time field comparable.
        budget = SearchBudget(limits=_limits(), clock=lambda: 0.0)
        return run_search(
            profile=_profile(), spec=spec, limits=_limits(), runner=_cooling_runner(), budget=budget
        ).result.to_dict()

    assert once() == once()


def test_result_document_is_reproducible():
    run = run_search(
        profile=_profile(), spec=_spec(refine=True), limits=_limits(), runner=_cooling_runner()
    )
    doc = run.result.to_dict()

    config = doc["config"]
    assert config["versions"]["deterministic"] is True
    assert config["versions"]["ai_involved"] is False
    assert config["versions"]["search_method_version"] == METHOD_VERSION
    assert config["spec"]["mode"] == "sweep"
    assert config["limits"]["max_scenarios"] == 150
    assert config["thresholds"]["max_temperature_c"] == 150.0
    assert doc["budget"]["max_scenarios"] == 150
    assert doc["plant"]["plant_id"] == "11111111-1111-1111-1111-111111111111"
    assert doc["notes"][0] == SEARCH_DISCLAIMER


# ---------------------------------------------------------------------------
# sensitivity + combinations
# ---------------------------------------------------------------------------


def test_sensitivity_perturbs_each_variable_once():
    spec = _spec(mode=SearchMode.SENSITIVITY, axes=())
    run = run_search(profile=_profile(), spec=spec, limits=_limits(), runner=_cooling_runner(100.0))

    rows = run.result.sensitivity
    assert len(rows) == len(list(SearchVariable))
    # Only cooling degradation moves the fake verdict; it sorts worst-first.
    assert rows[0]["variable"] == "cooling_factor"
    assert rows[0]["influence"] == "critical"
    assert rows[0]["low_status"] == "violation"
    # The baseline is the plant as configured: no perturbed value to report.
    assert rows[0]["baseline_value"] is None
    assert run.result.counts["scenarios"] == 1 + 2 * len(list(SearchVariable))
    assert run.result.counts["distinct_cases"] == 1 + 2 * len(list(SearchVariable))


def test_planned_scenarios_upper_bounds_every_mode():
    assert planned_scenarios(_spec(mode=SearchMode.SENSITIVITY, axes=())) == 15
    assert planned_scenarios(_spec(refine=False)) == 9
    assert planned_scenarios(_spec(refine=True, refinement_depth=4)) == 9 + min(64, 8)
    combo = _spec(
        mode=SearchMode.COMBINATIONS,
        axes=(
            default_axis(SearchVariable.COOLING_FACTOR, steps=3, max_steps=7),
            default_axis(SearchVariable.FEED_FACTOR, steps=3, max_steps=7),
        ),
    )
    assert planned_scenarios(combo) == 9


def test_combination_search_finds_a_dangerous_pair():
    """Neither fault alone violates; the pair does (the hidden interaction)."""

    def runner(sim_input: SimulationInput, thresholds, scenario_id: str):
        cooling = _fault_factor(sim_input, "cooling_degradation")
        feed = _fault_factor(sim_input, "feed_increase")
        # Each alone: mild. Together: the peak adds up past the limit.
        peak = 60.0 + 40.0 * (2.0 - cooling) + 20.0 * (feed - 1.0)
        assessment = _assessment(peak, thresholds)
        return assessment, SimulationResult(
            series={
                "true_temperature_c": [peak],
                "true_pressure_bar": [4.0],
                "level_pct": [45.0],
            },
            metadata={"deterministic": True},
        )

    spec = _spec(
        mode=SearchMode.COMBINATIONS,
        axes=(
            default_axis(SearchVariable.COOLING_FACTOR, steps=3, max_steps=7),
            default_axis(SearchVariable.FEED_FACTOR, minimum=1.0, maximum=3.0, steps=3, max_steps=7),
        ),
    )
    run = run_search(profile=_profile(), spec=spec, limits=_limits(), runner=runner)

    meta = run.result.config["combination"]
    assert meta["grid_size"] == 9
    assert meta["evaluated"] == 9
    assert meta["skipped"] == 0
    assert meta["worst"]["status"] == "violation"
    assert run.result.counts["violation"] >= 1
    # All three violations share rank 3, so "worst" is the deterministic key
    # tie-break ("cooling_factor=0.5;..." > "cooling_factor=0.0;..."), NOT the
    # physically hottest corner. Assert the documented tie-break, not physics.
    assert meta["worst"]["values"]["cooling_factor"] == pytest.approx(0.5)
    assert meta["worst"]["values"]["feed_factor"] == pytest.approx(3.0)
    # The physically hottest corner (low cooling + max feed) is still reported.
    failing_pairs = {
        (row["values"]["cooling_factor"], row["values"]["feed_factor"])
        for row in meta["rows"]
        if row["status"] == "violation"
    }
    assert (0.0, 3.0) in failing_pairs
    # Neither single fault violates on its own — only the pair crosses.
    for row in meta["rows"]:
        values = row["values"]
        single_fault = values["cooling_factor"] == 1.0 or values["feed_factor"] == 1.0
        if single_fault:
            assert row["status"] != "violation"


def test_combination_grid_is_capped_and_reports_skips():
    spec = _spec(
        mode=SearchMode.COMBINATIONS,
        axes=(
            default_axis(SearchVariable.COOLING_FACTOR, steps=7, max_steps=7),
            default_axis(SearchVariable.FEED_FACTOR, steps=7, max_steps=7),
        ),
    )
    # A 49-point grid against a cap of 36.
    run = run_search(profile=_profile(), spec=spec, limits=_limits(), runner=_cooling_runner())

    meta = run.result.config["combination"]
    assert meta["grid_size"] == 49
    assert meta["evaluated"] == 36
    assert meta["skipped"] == 13
    assert run.result.status == "complete"  # a structural cap, not a truncation
    assert any("skipped" in note for note in run.result.notes)


# ---------------------------------------------------------------------------
# budgets: max scenarios + timeout
# ---------------------------------------------------------------------------


def test_max_scenario_budget_stops_and_reports_truncation():
    spec = _spec(axes=(default_axis(SearchVariable.COOLING_FACTOR, steps=25),), refine=False)
    run = run_search(
        profile=_profile(), spec=spec, limits=_limits(max_scenarios=10), runner=_cooling_runner()
    )

    assert run.result.status == "truncated"
    assert run.result.truncated is True
    assert run.result.counts["evaluations"] == 10
    assert run.evaluator.budget.exceeded == "scenarios"
    assert run.result.budget["exceeded"] == "scenarios"
    assert run.result.budget["scenarios_used"] == 10
    assert any("maximum scenario budget" in note for note in run.result.notes)


def test_refinement_stops_on_the_scenario_budget():
    spec = _spec(axes=(default_axis(SearchVariable.COOLING_FACTOR, steps=9),), refine=True)
    run = run_search(
        profile=_profile(), spec=spec, limits=_limits(max_scenarios=12), runner=_cooling_runner()
    )

    # 9 sweep points + at most 3 refinement evaluations before the cap bites.
    assert run.result.counts["evaluations"] == 12
    assert run.evaluator.budget.exceeded == "scenarios"
    assert run.result.boundaries[0]["stop_reason"] == "scenarios"


def test_timeout_uses_the_injected_clock():
    """The timeout path is testable without waiting for real seconds."""
    ticks = {"now": 0.0}

    def clock() -> float:
        return ticks["now"]

    inner = _cooling_runner()

    def runner(sim_input, thresholds, scenario_id):
        ticks["now"] += 10.0  # every simulated scenario burns 10 fake seconds
        return inner(sim_input, thresholds, scenario_id)

    spec = _spec(axes=(default_axis(SearchVariable.COOLING_FACTOR, steps=25),), refine=False)
    budget = SearchBudget(limits=_limits(timeout_s=25.0), clock=clock)
    run = run_search(
        profile=_profile(),
        spec=spec,
        limits=_limits(timeout_s=25.0),
        runner=runner,
        budget=budget,
    )

    assert run.evaluator.budget.exceeded == "timeout"
    assert run.result.status == "truncated"
    assert run.result.budget["exceeded"] == "timeout"
    assert run.result.budget["elapsed_s"] >= 25.0
    assert any("timeout" in note.lower() for note in run.result.notes)
    assert run.result.counts["evaluations"] < 25


def test_charging_an_exhausted_budget_raises():
    budget = SearchBudget(limits=_limits(max_scenarios=2))
    budget.charge()
    budget.charge()
    with pytest.raises(SearchBudgetExceeded) as excinfo:
        budget.charge()
    assert excinfo.value.kind == "scenarios"
    assert budget.remaining_scenarios() == 0


# ---------------------------------------------------------------------------
# allowlist hygiene
# ---------------------------------------------------------------------------


def test_case_keys_are_canonical_and_order_independent():
    first = make_case({SearchVariable.COOLING_FACTOR: 0.5, SearchVariable.FEED_FACTOR: 2.0})
    second = make_case({SearchVariable.FEED_FACTOR: 2.0, SearchVariable.COOLING_FACTOR: 0.5})
    assert first.key() == second.key()
    assert first.as_dict() == {"cooling_factor": 0.5, "feed_factor": 2.0}


def test_unknown_variable_cannot_reach_the_evaluator():
    """Anything outside the allowlist fails lookup before any simulation."""
    with pytest.raises(KeyError):
        spec_for("__import__")


def test_neutral_values_inject_no_fault():
    run = run_search(
        profile=_profile(), spec=_spec(refine=False), limits=_limits(), runner=_cooling_runner()
    )
    # pump_factor = 1.0 is the multiplicative identity: no fault is injected.
    neutral = run.evaluator.build_input(make_case({SearchVariable.PUMP_FACTOR: 1.0}))
    assert neutral.scenario.faults == ()
    # A value away from neutral is a real fault.
    active = run.evaluator.build_input(make_case({SearchVariable.PUMP_FACTOR: 0.5}))
    assert len(active.scenario.faults) == 1
    assert active.scenario.faults[0].type.value == "pump_variation"


def test_budget_error_messages_never_echo_submitted_values():
    errors = _limits().validation_errors(
        duration_s=987654.0,
        time_step_s=1.0,
        refinement_depth=0,
        axes=1,
        combinations=0,
        scenarios=0,
    )
    assert errors
    assert all("987654" not in message for _, message in errors)
