"""Deterministic simulator engine coverage (Part 4, rule 23).

Asserts physical *direction* (monotonicity) rather than invented exact numbers,
plus repeatability and the hard compute budgets. Every case runs the same
deterministic engine with no RNG.
"""

from __future__ import annotations

import math

import pytest

from app.simulator import (
    FaultSpec,
    FaultType,
    LimitSet,
    ProcessParameters,
    SafeguardSettings,
    Scenario,
    SensorFailureMode,
    SensorFault,
    SensorType,
    SimulationInput,
    SimulationLimitError,
    SimulationLimits,
    run_simulation,
)

LIMITS = SimulationLimits(max_duration_s=3600, min_time_step_s=0.05, max_samples=20000)
SAFETY = LimitSet(max_temperature_c=150.0, max_pressure_bar=10.0, max_level_pct=90.0)


def _params(**overrides) -> ProcessParameters:
    base = {
        "feed_flow_lpm": 120.0,
        "heater_power_pct": 60.0,
        "cooling_pct": 90.0,
        "valve_position_pct": 55.0,
    }
    base.update(overrides)
    return ProcessParameters(**base)


def _run(
    scenario: Scenario,
    *,
    params: ProcessParameters | None = None,
    safeguards: SafeguardSettings | None = None,
):
    return run_simulation(
        SimulationInput(
            params=params or _params(),
            initial_volume_l=45.0,
            initial_temperature_c=80.0,
            scenario=scenario,
            limits=LIMITS,
            safety_limits=SAFETY,
            safeguards=safeguards or SafeguardSettings(),
            plant_id="plant-1",
        )
    )


def _scenario(duration=600.0, time_step=1.0, faults=(), sensor_faults=(), label="baseline"):
    return Scenario(
        duration_s=duration,
        time_step_s=time_step,
        faults=tuple(faults),
        sensor_faults=tuple(sensor_faults),
        label=label,
    )


def _final_temperature(result) -> float:
    return result.summary["final_temperature_c"]


def _max_temperature(result) -> float:
    return result.extrema["true_temperature_c"]["max"]["value"]


def _max_level(result) -> float:
    return result.extrema["level_pct"]["max"]["value"]


def _max_outlet(result) -> float:
    return result.extrema["outlet_flow_lpm"]["max"]["value"]


# --------------------------------------------------------------------------
# baseline + repeatability
# --------------------------------------------------------------------------


def test_safe_baseline_stays_within_limits():
    result = _run(_scenario())
    assert result.summary["sample_count"] == 601
    assert result.summary["limit_exceeded"] == {
        "temperature_c": False,
        "pressure_bar": False,
        "level_pct": False,
    }
    assert _max_temperature(result) < SAFETY.max_temperature_c
    assert _max_level(result) < SAFETY.max_level_pct
    assert result.summary["pump_stopped"] is False
    assert all(result.series["pump_running"])


def test_same_input_produces_identical_output():
    first = _run(_scenario())
    second = _run(_scenario())
    assert first.to_dict() == second.to_dict()


def test_result_contains_series_extrema_events_and_metadata():
    result = _run(_scenario())
    summary = result.summary
    assert summary["duration_s"] == 600.0
    assert summary["time_step_s"] == 1.0
    for key in ("true_temperature_c", "observed_temperature_c", "level_pct", "true_pressure_bar"):
        assert key in result.series
        assert key in result.extrema
    metadata = result.metadata
    assert metadata["simulator_version"]
    assert metadata["model_version"]
    assert metadata["deterministic"] is True
    assert metadata["assumptions"]
    assert metadata["limitations"]


# --------------------------------------------------------------------------
# physical direction
# --------------------------------------------------------------------------


def test_higher_heating_does_not_produce_cooler_trajectory():
    hot = _run(_scenario(), params=_params(heater_power_pct=100.0))
    base = _run(_scenario(), params=_params(heater_power_pct=40.0))
    assert _final_temperature(hot) > _final_temperature(base)
    assert _max_temperature(hot) > _max_temperature(base)


def test_reduced_cooling_does_not_produce_lower_temperature():
    weak = _run(_scenario(), params=_params(cooling_pct=20.0))
    strong = _run(_scenario(), params=_params(cooling_pct=100.0))
    assert _final_temperature(weak) > _final_temperature(strong)


def test_cooling_degradation_raises_temperature_above_baseline():
    degraded = _run(
        _scenario(faults=[FaultSpec(FaultType.COOLING_DEGRADATION, 0.0, factor=0.2)])
    )
    baseline = _run(_scenario())
    assert _max_temperature(degraded) > _max_temperature(baseline)


def test_complete_cooling_loss_violates_temperature_limit():
    result = _run(_scenario(faults=[FaultSpec(FaultType.COOLING_LOSS, 0.0)]))
    assert result.summary["limit_exceeded"]["temperature_c"] is True
    assert _max_temperature(result) > SAFETY.max_temperature_c
    assert any(event["kind"] == "limit_exceeded" for event in result.events)


def test_greater_outlet_restriction_does_not_increase_outlet_flow():
    restricted = _run(
        _scenario(faults=[FaultSpec(FaultType.OUTLET_RESTRICTION, 0.0, factor=0.3)])
    )
    baseline = _run(_scenario())
    assert _max_outlet(restricted) <= _max_outlet(baseline)
    assert _max_level(restricted) >= _max_level(baseline)


def test_valve_stuck_closed_accumulates_level():
    stuck = _run(_scenario(faults=[FaultSpec(FaultType.VALVE_STUCK, 0.0, target_pct=0.0)]))
    baseline = _run(_scenario())
    assert _max_level(stuck) > _max_level(baseline)
    assert _max_outlet(stuck) == pytest.approx(0.0, abs=1e-9)


def test_feed_increase_raises_level():
    increased = _run(_scenario(faults=[FaultSpec(FaultType.FEED_INCREASE, 0.0, factor=1.5)]))
    baseline = _run(_scenario())
    assert _max_level(increased) > _max_level(baseline)


def test_combined_feed_increase_and_cooling_degradation_is_worse_in_both_dimensions():
    combined = _run(
        _scenario(
            faults=[
                FaultSpec(FaultType.FEED_INCREASE, 0.0, factor=1.5),
                FaultSpec(FaultType.COOLING_DEGRADATION, 0.0, factor=0.2),
            ],
            label="combined",
        )
    )
    baseline = _run(_scenario())
    assert _max_level(combined) > _max_level(baseline)
    assert _max_temperature(combined) > _max_temperature(baseline)


def test_pump_variation_reduces_feed_flow():
    reduced = _run(_scenario(faults=[FaultSpec(FaultType.PUMP_VARIATION, 0.0, factor=0.5)]))
    baseline = _run(_scenario())
    assert reduced.series["feed_flow_lpm"][-1] < baseline.series["feed_flow_lpm"][-1]


# --------------------------------------------------------------------------
# sensors and shutdown
# --------------------------------------------------------------------------


def test_sensor_fault_changes_only_observed_readings():
    biased = _run(
        _scenario(
            sensor_faults=[
                SensorFault(SensorType.TEMPERATURE, 0.0, SensorFailureMode.BIAS, 9.0)
            ]
        )
    )
    assert biased.series["observed_temperature_c"][-1] == pytest.approx(
        biased.series["true_temperature_c"][-1] + 9.0
    )
    # The true trajectory must be identical to a run without the sensor fault.
    baseline = _run(_scenario())
    assert biased.series["true_temperature_c"] == pytest.approx(
        baseline.series["true_temperature_c"]
    )


def test_frozen_sensor_holds_reading_without_touching_true_state():
    frozen = _run(
        _scenario(
            faults=[FaultSpec(FaultType.COOLING_LOSS, 0.0)],
            sensor_faults=[
                SensorFault(SensorType.TEMPERATURE, 0.0, SensorFailureMode.FREEZE, 0.0)
            ],
        )
    )
    observed = frozen.series["observed_temperature_c"]
    assert observed[0] == pytest.approx(observed[-1])
    assert frozen.series["true_temperature_c"][-1] > observed[-1]


def test_delayed_shutdown_stops_the_pump_after_the_configured_delay():
    safeguards = SafeguardSettings(auto_shutdown_enabled=True, trip_delay_s=30.0)
    result = _run(
        _scenario(faults=[FaultSpec(FaultType.COOLING_LOSS, 0.0)]), safeguards=safeguards
    )
    assert result.summary["pump_stopped"] is True
    shutdown = [event for event in result.events if event["kind"] == "shutdown"]
    assert len(shutdown) == 1
    crossing = [event for event in result.events if event["kind"] == "limit_exceeded"][0]
    assert shutdown[0]["time_s"] == pytest.approx(crossing["time_s"] + 30.0, abs=1.0)


def test_disarmed_trip_does_not_cross():
    safeguards = SafeguardSettings(
        auto_shutdown_enabled=True, high_temperature_trip=False, trip_delay_s=10.0
    )
    result = _run(
        _scenario(faults=[FaultSpec(FaultType.COOLING_LOSS, 0.0)]), safeguards=safeguards
    )
    assert result.summary["pump_stopped"] is False
    assert result.summary["limit_exceeded"]["temperature_c"] is False


# --------------------------------------------------------------------------
# compute budgets
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("duration", "time_step", "field"),
    [
        (10_000.0, 1.0, "duration_s"),
        (600.0, 0.001, "time_step_s"),
    ],
)
def test_budget_violations_are_rejected(duration, time_step, field):
    with pytest.raises(SimulationLimitError) as excinfo:
        _run(_scenario(duration=duration, time_step=time_step))
    fields = [name for name, _ in excinfo.value.errors]
    assert field in fields


def test_max_duration_enforcement():
    with pytest.raises(SimulationLimitError) as excinfo:
        _run(_scenario(duration=LIMITS.max_duration_s * 2, time_step=1.0))
    assert excinfo.value.errors == [
        ("duration_s", "Duration exceeds the maximum allowed simulation duration.")
    ]


def test_max_sample_enforcement():
    duration = 1000.0
    time_step = 0.1  # 10_001 samples, well above the tighter sample budget below
    tight = SimulationLimits(max_duration_s=3600, min_time_step_s=0.0, max_samples=500)
    with pytest.raises(SimulationLimitError) as excinfo:
        run_simulation(
            SimulationInput(
                params=_params(),
                initial_volume_l=45.0,
                initial_temperature_c=80.0,
                scenario=_scenario(duration=duration, time_step=time_step),
                limits=tight,
                safety_limits=SAFETY,
            )
        )
    assert excinfo.value.errors == [
        (
            "time_step_s",
            "Requested simulation would exceed the maximum sample count.",
        )
    ]


def test_sample_count_matches_grid():
    result = _run(_scenario(duration=100.0, time_step=0.5))
    assert result.summary["sample_count"] == int(math.floor(100.0 / 0.5)) + 1
    assert result.series["time_s"][0] == 0.0
    assert result.series["time_s"][-1] == pytest.approx(100.0)
