"""Authenticated simulation endpoint.

Paths are `/api/v1/simulations/*` (the Part 4 brief's `/api/simulations/run`
maps onto the single canonical `/api/v1` prefix fixed in Part 1).

Security posture:
- requires a verified session (`get_current_user`),
- the plant is loaded with `get_owned_or_404`, so another user's plant returns
  404 and can never be simulated (rule 5),
- hard compute budgets (duration / time step / sample count) are enforced from
  Settings before any integration runs (rule 8),
- the endpoint has its own per-IP rate-limit bucket,
- the response follows the shared success envelope and never leaks internals.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.ownership import get_owned_or_404
from app.core.rate_limit import simulation_rate_limit
from app.core.responses import FieldError, error_response, success_response
from app.database import get_db
from app.models import Plant, User
from app.schemas import SimulationRunRequest
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
    run_simulation,
)

logger = logging.getLogger("safeflux.simulations")

router = APIRouter(prefix="/simulations")


def _to_scenario(payload: SimulationRunRequest) -> Scenario:
    scenario = payload.scenario
    faults = tuple(
        FaultSpec(
            type=fault.type,
            start_s=fault.start_s,
            factor=fault.factor,
            target_pct=fault.target_pct,
        )
        for fault in scenario.faults
    )
    sensor_faults = tuple(
        SensorFault(
            sensor=fault.sensor,
            start_s=fault.start_s,
            mode=fault.mode,
            magnitude=fault.magnitude,
        )
        for fault in scenario.sensor_faults
    )
    return Scenario(
        duration_s=scenario.duration_s,
        time_step_s=scenario.time_step_s,
        faults=faults,
        sensor_faults=sensor_faults,
        label=scenario.label,
    )


def _to_input(plant: Plant, payload: SimulationRunRequest, limits: SimulationLimits) -> SimulationInput:
    config = plant.config
    state = plant.state
    safeguards = plant.safeguards
    return SimulationInput(
        params=ProcessParameters(
            feed_flow_lpm=config.feed_flow_lpm,
            heater_power_pct=config.heater_power_pct,
            cooling_pct=config.cooling_pct,
            valve_position_pct=config.valve_position_pct,
            pump_running=state.pump_running,
        ),
        initial_volume_l=volume_from_level(state.level_pct),
        initial_temperature_c=state.temperature_c,
        scenario=_to_scenario(payload),
        limits=limits,
        safety_limits=LimitSet(
            max_temperature_c=plant.safety_limits.max_temperature_c,
            max_pressure_bar=plant.safety_limits.max_pressure_bar,
            max_level_pct=plant.safety_limits.max_level_pct,
        ),
        safeguards=SafeguardSettings(
            auto_shutdown_enabled=safeguards.auto_shutdown_enabled,
            high_temperature_trip=safeguards.high_temperature_trip,
            high_pressure_trip=safeguards.high_pressure_trip,
            high_level_trip=safeguards.high_level_trip,
            trip_delay_s=float(safeguards.trip_delay_s),
        ),
        plant_id=plant.id,
    )


@router.post(
    "/run",
    dependencies=[Depends(simulation_rate_limit)],
    summary="Run one deterministic simulation scenario",
)
def run_scenario(
    payload: SimulationRunRequest,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    # Ownership is enforced before any compute happens (404 on cross-user).
    plant = get_owned_or_404(db, Plant, payload.plant_id, user)

    settings = request.app.state.settings
    limits = SimulationLimits(
        max_duration_s=settings.SIM_MAX_DURATION_S,
        min_time_step_s=settings.SIM_MIN_TIME_STEP_S,
        max_samples=settings.SIM_MAX_SAMPLES,
    )
    sim_input = _to_input(plant, payload, limits)

    try:
        result = run_simulation(sim_input)
    except SimulationLimitError as exc:
        return error_response(
            422,
            "VALIDATION_ERROR",
            "One or more input fields are invalid.",
            [FieldError(field=field, message=message) for field, message in exc.errors],
        )

    logger.info(
        "Simulation run: plant=%s user=%s samples=%s",
        plant.id,
        user.id,
        result.summary.get("sample_count"),
    )
    return success_response({"result": result.to_dict()})
