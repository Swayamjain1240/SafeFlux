"""Deterministic safety engine coverage (Part 5, rule 23).

Asserts the classification status and physical direction — never invented exact
numbers — plus safeguards that act early (prevent) versus too late. Every case
runs the same deterministic simulator with no RNG.
"""

from __future__ import annotations

import pytest

from app.safety import (
    SafetyStatus,
    SafetyThresholds,
    assess_scenario,
    evaluate_simulation,
    worst_status,
)
from app.simulator import (
    FaultSpec,
    FaultType,
    LimitSet,
    ProcessParameters,
    SafeguardSettings,
    Scenario,
    SimulationInput,
    SimulationLimits,
    run_simulation,
)

LIMITS = SimulationLimits(max_duration_s=3600, min_time_step_s=0.05, max_samples=20000)
NO_GUARD = SafeguardSettings(auto_shutdown_enabled=False)


def _params(**overrides) -> ProcessParameters:
    base = {
        "feed_flow_lpm": 120.0,
        "heater_power_pct": 100.0,
        "cooling_pct": 32.0,
        "valve_position_pct": 45.0,
    }
    base.update(overrides)
    return ProcessParameters(**base)


def _run(
    scenario: Scenario,
    *,
    params: ProcessParameters | None = None,
    safety: LimitSet | None = None,
    safeguards: SafeguardSettings | None = None,
):
    return run_simulation(
        SimulationInput(
            params=params or _params(),
            initial_volume_l=45.0,
            initial_temperature_c=80.0,
            scenario=scenario,
            limits=LIMITS,
            safety_limits=safety or LimitSet(max_temperature_c=150.0, max_pressure_bar=50.0, max_level_pct=100.0),
            safeguards=safeguards or NO_GUARD,
            plant_id="plant-1",
        )
    )


def _scenario(faults=(), duration=400.0, label="scenario") -> Scenario:
    return Scenario(duration_s=duration, time_step_s=1.0, faults=tuple(faults), sensor_faults=(), label=label)


def _status_for(assessment, variable: str) -> SafetyStatus:
    return next(f.status for f in assessment.findings if f.variable == variable)


# --------------------------------------------------------------------------
# classification
# --------------------------------------------------------------------------


def test_safe_baseline_is_safe():
    scenario = _scenario(duration=120.0, label="baseline")
    params = _params(heater_power_pct=60.0, cooling_pct=90.0, valve_position_pct=55.0)
    result = _run(scenario, params=params)
    assessment = evaluate_simulation(
        result, SafetyThresholds(150.0, 50.0, 90.0), scenario_id="baseline"
    )
    assert assessment.status is SafetyStatus.SAFE
    assert all(f.status is SafetyStatus.SAFE for f in assessment.findings)
    assert assessment.summary["violations"] == []


def test_near_limit_temperature_is_flagged_but_safe():
    result = _run(_scenario())
    assessment = evaluate_simulation(result, SafetyThresholds(150.0, 50.0, 100.0))
    assert _status_for(assessment, "temperature_c") is SafetyStatus.NEAR_LIMIT
    assert assessment.status is SafetyStatus.NEAR_LIMIT
    assert assessment.summary["near_limit"] == ["temperature_c"]


def test_near_limit_fraction_is_configurable():
    result = _run(_scenario())
    strict = evaluate_simulation(
        result, SafetyThresholds(150.0, 50.0, 100.0, near_limit_fraction=0.99)
    )
    loose = evaluate_simulation(
        result, SafetyThresholds(150.0, 50.0, 100.0, near_limit_fraction=0.9)
    )
    assert _status_for(strict, "temperature_c") is SafetyStatus.SAFE
    assert _status_for(loose, "temperature_c") is SafetyStatus.NEAR_LIMIT


def test_temperature_violation():
    result = _run(_scenario(), params=_params(cooling_pct=20.0))
    assessment = evaluate_simulation(result, SafetyThresholds(150.0, 50.0, 100.0))
    assert _status_for(assessment, "temperature_c") is SafetyStatus.VIOLATION
    assert assessment.status is SafetyStatus.VIOLATION


def test_pressure_violation():
    safety = LimitSet(max_temperature_c=300.0, max_pressure_bar=5.0, max_level_pct=100.0)
    result = _run(
        _scenario(faults=[FaultSpec(FaultType.COOLING_LOSS, 0.0)], duration=600.0),
        safety=safety,
    )
    assessment = evaluate_simulation(result, SafetyThresholds(300.0, 5.0, 100.0))
    assert _status_for(assessment, "pressure_bar") is SafetyStatus.VIOLATION


def test_level_violation():
    safety = LimitSet(max_temperature_c=300.0, max_pressure_bar=50.0, max_level_pct=90.0)
    result = _run(
        _scenario(faults=[FaultSpec(FaultType.FEED_INCREASE, 0.0, factor=3.0)], duration=600.0),
        safety=safety,
    )
    assessment = evaluate_simulation(result, SafetyThresholds(300.0, 50.0, 90.0))
    assert _status_for(assessment, "level_pct") is SafetyStatus.VIOLATION


def test_reduced_cooling_is_never_less_severe():
    """Direction: weaker cooling must not classify as safer."""
    strong = evaluate_simulation(_run(_scenario(), params=_params(cooling_pct=45.0)), SafetyThresholds(150.0, 50.0, 100.0))
    weak = evaluate_simulation(_run(_scenario(), params=_params(cooling_pct=20.0)), SafetyThresholds(150.0, 50.0, 100.0))
    rank = {
        SafetyStatus.SAFE: 0,
        SafetyStatus.NEAR_LIMIT: 1,
        SafetyStatus.SAFEGUARD_ACTIVATED: 2,
        SafetyStatus.VIOLATION: 3,
    }
    assert rank[_status_for(weak, "temperature_c")] >= rank[_status_for(strong, "temperature_c")]


def test_finding_records_evidence():
    result = _run(_scenario(), params=_params(cooling_pct=20.0))
    assessment = evaluate_simulation(result, SafetyThresholds(150.0, 50.0, 100.0), scenario_id="hot")
    finding = next(f for f in assessment.findings if f.variable == "temperature_c")
    assert finding.scenario_id == "hot"
    assert finding.limit == 150.0
    assert finding.measured_value is not None and finding.measured_value > finding.limit
    assert finding.timestamp_s is not None
    assert finding.severity == "critical"
    payload = finding.to_dict()
    assert payload["type"] == "temperature_c"
    assert payload["status"] == "violation"


def test_assessment_carries_disclaimer_and_thresholds():
    assessment = evaluate_simulation(_run(_scenario()), SafetyThresholds(150.0, 50.0, 100.0))
    assert assessment.metadata["deterministic"] is True
    assert "never a claim about a real plant" in assessment.metadata["disclaimer"]
    assert assessment.metadata["thresholds"]["near_limit_fraction"] == 0.9


def test_worst_status_rollup():
    assert worst_status([]) is SafetyStatus.SAFE
    assert (
        worst_status([SafetyStatus.SAFE, SafetyStatus.NEAR_LIMIT, SafetyStatus.VIOLATION])
        is SafetyStatus.VIOLATION
    )


def test_invalid_near_limit_fraction_is_rejected():
    with pytest.raises(ValueError):
        SafetyThresholds(150.0, 50.0, 100.0, near_limit_fraction=0.2)


# --------------------------------------------------------------------------
# safeguard timing
# --------------------------------------------------------------------------


def _assess(delay: float):
    sim_input = SimulationInput(
        params=_params(heater_power_pct=60.0, cooling_pct=90.0, valve_position_pct=55.0),
        initial_volume_l=45.0,
        initial_temperature_c=80.0,
        scenario=_scenario(faults=[FaultSpec(FaultType.COOLING_LOSS, 0.0)], duration=600.0, label="cooling loss"),
        limits=LIMITS,
        safety_limits=LimitSet(max_temperature_c=150.0, max_pressure_bar=50.0, max_level_pct=100.0),
        safeguards=SafeguardSettings(auto_shutdown_enabled=True, trip_delay_s=delay),
        plant_id="plant-1",
    )
    return assess_scenario(sim_input, SafetyThresholds(150.0, 50.0, 100.0), scenario_id="cooling loss")


def test_early_safeguard_prevents_violation():
    assessment, guarded = _assess(delay=5.0)
    assert assessment.status is SafetyStatus.SAFEGUARD_ACTIVATED
    assert _status_for(assessment, "temperature_c") is SafetyStatus.SAFEGUARD_ACTIVATED
    assert guarded.extrema["true_temperature_c"]["max"]["value"] < 150.0
    shutdown = next(s for s in assessment.safeguards if s.safeguard == "emergency_shutdown")
    assert shutdown.trigger_time_s is not None
    assert shutdown.response_time_s is not None
    assert shutdown.trigger_time_s <= shutdown.response_time_s
    assert shutdown.violation_time_s is None
    assert shutdown.prevented is True


def test_late_safeguard_reports_violation():
    assessment, _ = _assess(delay=30.0)
    assert assessment.status is SafetyStatus.VIOLATION
    shutdown = next(s for s in assessment.safeguards if s.safeguard == "emergency_shutdown")
    assert shutdown.prevented is False
    assert shutdown.response_time_s is not None
    assert shutdown.violation_time_s is not None
    assert "too late" in shutdown.note


def test_alarm_timing_recorded_before_esd():
    assessment, _ = _assess(delay=5.0)
    alarm = next(s for s in assessment.safeguards if s.safeguard == "high_temperature_alarm")
    assert alarm.trigger_time_s is not None
    assert alarm.prevented is True


def test_emergency_shutdown_disabled_has_no_response():
    sim_input = SimulationInput(
        params=_params(heater_power_pct=60.0, cooling_pct=90.0, valve_position_pct=55.0),
        initial_volume_l=45.0,
        initial_temperature_c=80.0,
        scenario=_scenario(faults=[FaultSpec(FaultType.COOLING_LOSS, 0.0)], duration=600.0),
        limits=LIMITS,
        safety_limits=LimitSet(max_temperature_c=150.0, max_pressure_bar=50.0, max_level_pct=100.0),
        safeguards=SafeguardSettings(auto_shutdown_enabled=False),
        plant_id="plant-1",
    )
    assessment, _ = assess_scenario(sim_input, SafetyThresholds(150.0, 50.0, 100.0))
    # An unarmed emergency shutdown is not reported as a safeguard record.
    assert all(s.safeguard != "emergency_shutdown" for s in assessment.safeguards)
    assert assessment.status is SafetyStatus.VIOLATION


def test_safeguard_verdicts_never_claim_a_real_plant():
    assessment, _ = _assess(delay=5.0)
    shutdown = next(s for s in assessment.safeguards if s.safeguard == "emergency_shutdown")
    assert "never a claim about real plant response" in shutdown.note
