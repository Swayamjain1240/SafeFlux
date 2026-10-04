"""Deterministic simulation engine.

Orchestrates the model and faults over a scenario:

1. validate the requested duration/time-step against the hard budgets,
2. integrate the ODE system with SciPy's ``solve_ivp`` — one call per smooth
   segment between scheduled fault changes (and an optional shutdown), so step
   changes are honoured without smearing them across an adaptive step,
3. sample on the requested uniform grid, derive observed sensor readings,
4. collect extrema, events, a summary and version metadata.

``solve_ivp`` is used where it is technically appropriate: inside each smooth
segment. It is not used across discontinuities, which is exactly why segments
exist. The integration is fully deterministic (fixed tolerances, no RNG), so
identical inputs always produce identical results.

Shutdown delay is resolved to the sample grid and evaluated against the
un-shutdown trajectory (a documented simplification): the first armed limit
crossing schedules a pump stop ``trip_delay_s`` later, then the run is
re-integrated once with that stop in place.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy.integrate import solve_ivp

from app.simulator.constants import (
    ASSUMPTIONS,
    LIMITATIONS,
    MODEL_NAME,
    MODEL_VERSION,
    SIMULATOR_VERSION,
)
from app.simulator.faults import FaultSchedule, apply_sensor_faults, sensor_events
from app.simulator.limits import SimulationLimits
from app.simulator.model import (
    ProcessParameters,
    derivatives,
    initial_vector,
    level_percent,
    pressure_bar,
)
from app.simulator.result import SimulationResult, build_extrema
from app.simulator.scenario import Scenario, SensorType

_RTOL = 1e-9
_ATOL = 1e-11


class SimulationLimitError(Exception):
    """Raised when a scenario violates the hard compute budgets."""

    def __init__(self, errors: list[tuple[str, str]]) -> None:
        super().__init__("simulation request exceeds allowed budgets")
        self.errors = errors


@dataclass(frozen=True)
class LimitSet:
    """Configured trip limits copied from the plant's SafetyLimits."""

    max_temperature_c: float
    max_pressure_bar: float
    max_level_pct: float


@dataclass(frozen=True)
class SafeguardSettings:
    """Armed safeguards copied from the plant's SafeguardConfig."""

    auto_shutdown_enabled: bool = False
    high_temperature_trip: bool = True
    high_pressure_trip: bool = True
    high_level_trip: bool = True
    trip_delay_s: float = 0.0


@dataclass(frozen=True)
class SimulationInput:
    """Everything the engine needs for one deterministic run."""

    params: ProcessParameters
    initial_volume_l: float
    initial_temperature_c: float
    scenario: Scenario
    limits: SimulationLimits
    safety_limits: LimitSet
    safeguards: SafeguardSettings = SafeguardSettings()
    plant_id: str | None = None


def build_sample_times(duration_s: float, time_step_s: float) -> list[float]:
    """Uniform sample grid inclusive of t=0, ending exactly at the duration."""
    count = int(math.floor(duration_s / time_step_s)) + 1
    times = [index * time_step_s for index in range(count)]
    if times and times[-1] > duration_s + 1e-9:
        times.pop()
    if not times or times[-1] < duration_s - 1e-9:
        times.append(duration_s)
    return times


def _segment_bounds(
    schedule: FaultSchedule, duration_s: float, stop_at: float | None
) -> list[float]:
    bounds = {0.0, duration_s}
    for point in schedule.breakpoints:
        if 0.0 < point < duration_s:
            bounds.add(float(point))
    if stop_at is not None and 0.0 < stop_at < duration_s:
        bounds.add(float(stop_at))
    return sorted(bounds)


def _integrate(
    sim: SimulationInput,
    schedule: FaultSchedule,
    sample_times: list[float],
    stop_at: float | None,
) -> tuple[list[ProcessParameters], np.ndarray]:
    """Integrate the scenario and return the parameter and state at each sample."""
    duration = sim.scenario.duration_s
    time_step = sim.scenario.time_step_s
    max_step = max(time_step, 1e-3)
    bounds = _segment_bounds(schedule, duration, stop_at)

    y = initial_vector(sim.initial_volume_l, sim.initial_temperature_c)
    params_out: list[ProcessParameters] = []
    state_out: list[np.ndarray] = []

    def _params_for(t: float) -> ProcessParameters:
        # t is a sample time; the state at t was produced by the parameters
        # active on the interval ending at t (so use the left limit).
        reference = t if t <= 1e-12 else t - 1e-12
        params = schedule.params_at(reference)
        if stop_at is not None and t >= stop_at - 1e-9:
            # Emergency shutdown removes the heat source and stops the feed.
            params = params.with_(pump_running=False, heater_power_pct=0.0)
        return params

    # Sample at t=0 belongs to the first segment's left edge.
    if sample_times[0] <= 1e-9:
        params_out.append(_params_for(0.0))
        state_out.append(y.copy())

    pointer = 1
    for index in range(len(bounds) - 1):
        seg_start, seg_end = bounds[index], bounds[index + 1]
        if seg_end <= seg_start + 1e-12:
            continue
        seg_samples: list[float] = []
        while pointer < len(sample_times) and sample_times[pointer] <= seg_end + 1e-9:
            seg_samples.append(sample_times[pointer])
            pointer += 1

        segment_params = schedule.params_at(seg_start + 1e-12)
        if stop_at is not None and seg_start + 1e-12 >= stop_at:
            segment_params = segment_params.with_(pump_running=False, heater_power_pct=0.0)

        solution = solve_ivp(
            lambda t, state: derivatives(t, state, segment_params),
            (seg_start, seg_end),
            y,
            t_eval=seg_samples if seg_samples else None,
            rtol=_RTOL,
            atol=_ATOL,
            max_step=max_step,
        )
        if seg_samples:
            for column, sample_time in enumerate(seg_samples):
                params_out.append(_params_for(sample_time))
                state_out.append(solution.y[:, column].copy())
        y = solution.y[:, -1].copy()

    return params_out, np.asarray(state_out, dtype=float)


@dataclass
class _Crossing:
    variable: str
    time_s: float
    value: float
    limit: float


def _detect_crossings(
    sim: SimulationInput,
    times: list[float],
    temperatures: list[float],
    pressures: list[float],
    levels: list[float],
) -> list[_Crossing]:
    """First sample where each armed trip limit is exceeded."""
    rules = []
    if sim.safeguards.high_temperature_trip:
        rules.append(("temperature_c", temperatures, sim.safety_limits.max_temperature_c))
    if sim.safeguards.high_pressure_trip:
        rules.append(("pressure_bar", pressures, sim.safety_limits.max_pressure_bar))
    if sim.safeguards.high_level_trip:
        rules.append(("level_pct", levels, sim.safety_limits.max_level_pct))

    crossings: list[_Crossing] = []
    for variable, values, limit in rules:
        for index, value in enumerate(values):
            if value > limit:
                crossings.append(_Crossing(variable, times[index], value, limit))
                break
    return crossings


def run_simulation(sim: SimulationInput) -> SimulationResult:
    """Run one deterministic scenario and assemble a ``SimulationResult``."""
    scenario = sim.scenario
    budget_errors = sim.limits.validation_errors(scenario.duration_s, scenario.time_step_s)
    if budget_errors:
        raise SimulationLimitError(budget_errors)

    sample_times = build_sample_times(scenario.duration_s, scenario.time_step_s)
    schedule = FaultSchedule(sim.params, scenario.faults)

    # Pass 1 — no shutdown, used to locate the first armed limit crossing.
    params_1, states_1 = _integrate(sim, schedule, sample_times, stop_at=None)
    times = [float(p) for p in sample_times[: len(params_1)]]
    temps_1 = [float(s[1]) for s in states_1]
    levels_1 = [level_percent(float(s[0])) for s in states_1]
    pressures_1 = [pressure_bar(t, l) for t, l in zip(temps_1, levels_1)]
    crossings = _detect_crossings(sim, times, temps_1, pressures_1, levels_1)

    # Pass 2 — if armed, stop the pump trip_delay_s after the first crossing.
    stop_at: float | None = None
    if crossings and sim.safeguards.auto_shutdown_enabled:
        stop_at = round((crossings[0].time_s + sim.safeguards.trip_delay_s) / scenario.time_step_s) * scenario.time_step_s
        stop_at = min(stop_at, scenario.duration_s)
        params_out, states_out = _integrate(sim, schedule, sample_times, stop_at=stop_at)
    else:
        params_out, states_out = params_1, states_1

    sample_count = len(params_out)
    times = [float(t) for t in sample_times[:sample_count]]
    temperatures = [float(s[1]) for s in states_out]
    volumes = [float(s[0]) for s in states_out]
    levels = [level_percent(v) for v in volumes]
    pressures = [pressure_bar(t, l) for t, l in zip(temperatures, levels)]

    series: dict[str, list] = {
        "time_s": times,
        "volume_l": volumes,
        "level_pct": levels,
        "true_temperature_c": temperatures,
        "true_pressure_bar": pressures,
        "feed_flow_lpm": [p.effective_feed_lpm for p in params_out],
        "outlet_flow_lpm": [float(p.outlet_lpm(l)) for p, l in zip(params_out, levels)],
        "valve_position_pct": [p.valve_position_pct * p.outlet_factor for p in params_out],
        "cooling_pct": [p.cooling_pct * p.cooling_factor for p in params_out],
        "pump_running": [bool(p.pump_running) for p in params_out],
    }
    time_array = np.asarray(times, dtype=float)
    series["observed_temperature_c"] = apply_sensor_faults(
        np.asarray(temperatures), time_array, scenario.sensor_faults, sensor=SensorType.TEMPERATURE
    ).tolist()
    series["observed_pressure_bar"] = apply_sensor_faults(
        np.asarray(pressures), time_array, scenario.sensor_faults, sensor=SensorType.PRESSURE
    ).tolist()

    events = schedule.events(scenario.duration_s) + sensor_events(
        scenario.sensor_faults, scenario.duration_s
    )
    for crossing in crossings:
        events.append(
            {
                "time_s": crossing.time_s,
                "kind": "limit_exceeded",
                "detail": {
                    "variable": crossing.variable,
                    "measured": crossing.value,
                    "limit": crossing.limit,
                },
            }
        )
    pump_stopped = bool(stop_at is not None)
    if pump_stopped:
        events.append(
            {
                "time_s": float(stop_at),
                "kind": "shutdown",
                "detail": {
                    "reason": "armed trip crossing + configured shutdown delay",
                    "delay_s": sim.safeguards.trip_delay_s,
                    "actions": ["stop feed pump", "cut heater power"],
                },
            }
        )
    events.sort(key=lambda item: (float(item["time_s"]), str(item["kind"])))

    summary = {
        "duration_s": scenario.duration_s,
        "time_step_s": scenario.time_step_s,
        "sample_count": sample_count,
        "final_temperature_c": temperatures[-1],
        "final_level_pct": levels[-1],
        "final_pressure_bar": pressures[-1],
        "final_observed_temperature_c": series["observed_temperature_c"][-1],
        "final_observed_pressure_bar": series["observed_pressure_bar"][-1],
        "pump_stopped": pump_stopped,
        "limit_exceeded": {
            "temperature_c": any(c.variable == "temperature_c" for c in crossings),
            "pressure_bar": any(c.variable == "pressure_bar" for c in crossings),
            "level_pct": any(c.variable == "level_pct" for c in crossings),
        },
        "safety_limits": {
            "max_temperature_c": sim.safety_limits.max_temperature_c,
            "max_pressure_bar": sim.safety_limits.max_pressure_bar,
            "max_level_pct": sim.safety_limits.max_level_pct,
        },
    }

    metadata = {
        "simulator_version": SIMULATOR_VERSION,
        "model_name": MODEL_NAME,
        "model_version": MODEL_VERSION,
        "plant_id": sim.plant_id,
        "scenario_label": scenario.label,
        "fault_count": len(scenario.faults),
        "sensor_fault_count": len(scenario.sensor_faults),
        "deterministic": True,
        "determinism_note": "No RNG; identical inputs produce identical results.",
        "assumptions": list(ASSUMPTIONS),
        "limitations": list(LIMITATIONS),
    }

    return SimulationResult(
        series=series,
        extrema=build_extrema(series),
        summary=summary,
        events=events,
        metadata=metadata,
    )
