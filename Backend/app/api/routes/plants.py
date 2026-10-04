"""Authenticated plant configuration endpoints.

Paths are `/api/v1/plants/*` (the Part 3 brief's `/api/plants/*` maps onto the
single canonical `/api/v1` prefix from Part 1).

Authorization rules (SAFEFLUX_MASTER.md §12, ARCHITECTURE §10):
- every endpoint requires a verified session (`get_current_user`),
- the owner is always the session user — never a client-supplied id,
- all reads/writes/deletes go through `get_owned_or_404`, which returns 404
  for both missing and cross-user resources so existence is never leaked.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_user
from app.auth.ownership import get_owned_or_404
from app.core.responses import FieldError, error_response, success_response
from app.database import get_db
from app.models import Plant, PlantConfig, PlantState, SafeguardConfig, SafetyLimits, User
from app.schemas import (
    PlantConfigOut,
    PlantCreate,
    PlantDetailEnvelope,
    PlantListEnvelope,
    PlantStateEnvelope,
    PlantStateOut,
    PlantSummary,
    PlantUpdate,
    SafeguardConfigOut,
    SafetyLimitsOut,
)

logger = logging.getLogger("safeflux.plants")

router = APIRouter(prefix="/plants", tags=["plants"])

_NOT_FOUND_DESC = {"description": "Not found or not owned by the caller"}


def _config_out(config: PlantConfig) -> PlantConfigOut:
    return PlantConfigOut(
        feed_flow_lpm=config.feed_flow_lpm,
        cooling_pct=config.cooling_pct,
        valve_position_pct=config.valve_position_pct,
        heater_power_pct=config.heater_power_pct,
        shutdown_delay_s=config.shutdown_delay_s,
    )


def _state_out(state: PlantState) -> PlantStateOut:
    return PlantStateOut(
        pump_running=state.pump_running,
        temperature_c=state.temperature_c,
        pressure_bar=state.pressure_bar,
        level_pct=state.level_pct,
    )


def _limits_out(limits: SafetyLimits) -> SafetyLimitsOut:
    return SafetyLimitsOut(
        max_temperature_c=limits.max_temperature_c,
        max_pressure_bar=limits.max_pressure_bar,
        max_level_pct=limits.max_level_pct,
    )


def _safeguards_out(safeguards: SafeguardConfig) -> SafeguardConfigOut:
    return SafeguardConfigOut(
        auto_shutdown_enabled=safeguards.auto_shutdown_enabled,
        high_temperature_trip=safeguards.high_temperature_trip,
        high_pressure_trip=safeguards.high_pressure_trip,
        high_level_trip=safeguards.high_level_trip,
        trip_delay_s=safeguards.trip_delay_s,
    )


def _consistency_errors(plant: Plant) -> list[FieldError]:
    """Re-check that initial state stays below configured trip limits.

    Applied after a partial update so a PATCH can never leave the plant in
    a state the create path would have rejected.
    """
    errors: list[FieldError] = []
    if plant.state.temperature_c > plant.safety_limits.max_temperature_c:
        errors.append(
            FieldError(
                field="state.temperature_c",
                message="Initial temperature exceeds the configured maximum temperature limit.",
            )
        )
    if plant.state.pressure_bar > plant.safety_limits.max_pressure_bar:
        errors.append(
            FieldError(
                field="state.pressure_bar",
                message="Initial pressure exceeds the configured maximum pressure limit.",
            )
        )
    if plant.state.level_pct > plant.safety_limits.max_level_pct:
        errors.append(
            FieldError(
                field="state.level_pct",
                message="Initial level exceeds the configured maximum level limit.",
            )
        )
    return errors


def _detail(plant: Plant) -> dict:
    """Full plant payload for the detail/review view. Never includes owner_id."""
    return {
        "id": plant.id,
        "name": plant.name,
        "description": plant.description,
        "location": plant.location,
        "config": _config_out(plant.config).model_dump(),
        "state": _state_out(plant.state).model_dump(),
        "safety_limits": _limits_out(plant.safety_limits).model_dump(),
        "safeguards": _safeguards_out(plant.safeguards).model_dump(),
        "created_at": plant.created_at,
        "updated_at": plant.updated_at,
    }


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=PlantDetailEnvelope,
    summary="Create a plant configuration",
)
def create_plant(
    payload: PlantCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    plant = Plant(
        owner_id=user.id,
        name=payload.name,
        description=payload.description,
        location=payload.location,
        config=PlantConfig(**payload.config.model_dump()),
        state=PlantState(**payload.state.model_dump()),
        safety_limits=SafetyLimits(**payload.safety_limits.model_dump()),
        safeguards=SafeguardConfig(**payload.safeguards.model_dump()),
    )
    db.add(plant)
    db.commit()
    db.refresh(plant)
    logger.info("Plant created: %s by user %s", plant.id, user.id)
    return success_response({"plant": _detail(plant)})


@router.get("", response_model=PlantListEnvelope, summary="List your plants")
def list_plants(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    rows = db.scalars(
        select(Plant).where(Plant.owner_id == user.id).order_by(Plant.created_at.desc())
    ).all()
    plants = [
        PlantSummary(
            id=row.id,
            name=row.name,
            description=row.description,
            location=row.location,
            created_at=row.created_at,
            updated_at=row.updated_at,
        ).model_dump()
        for row in rows
    ]
    return success_response({"plants": plants})


@router.get(
    "/{plant_id}",
    response_model=PlantDetailEnvelope,
    responses={404: _NOT_FOUND_DESC},
    summary="Get one of your plants",
)
def get_plant(
    plant_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    plant = get_owned_or_404(db, Plant, plant_id, user)
    return success_response({"plant": _detail(plant)})


@router.patch(
    "/{plant_id}",
    response_model=PlantDetailEnvelope,
    responses={404: _NOT_FOUND_DESC},
    summary="Update one of your plants",
)
def update_plant(
    plant_id: str,
    payload: PlantUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    plant = get_owned_or_404(db, Plant, plant_id, user)

    if payload.name is not None:
        plant.name = payload.name
    if payload.description is not None:
        plant.description = payload.description
    if payload.location is not None:
        plant.location = payload.location
    if payload.config is not None:
        for field, value in payload.config.model_dump().items():
            setattr(plant.config, field, value)
    if payload.state is not None:
        for field, value in payload.state.model_dump().items():
            setattr(plant.state, field, value)
    if payload.safety_limits is not None:
        for field, value in payload.safety_limits.model_dump().items():
            setattr(plant.safety_limits, field, value)
    if payload.safeguards is not None:
        for field, value in payload.safeguards.model_dump().items():
            setattr(plant.safeguards, field, value)

    errors = _consistency_errors(plant)
    if errors:
        db.rollback()
        return error_response(
            422,
            "VALIDATION_ERROR",
            "One or more input fields are invalid.",
            errors,
        )

    db.commit()
    db.refresh(plant)
    logger.info("Plant updated: %s by user %s", plant.id, user.id)
    return success_response({"plant": _detail(plant)})


@router.delete(
    "/{plant_id}",
    response_model=None,
    status_code=status.HTTP_204_NO_CONTENT,
    responses={404: _NOT_FOUND_DESC},
    summary="Delete one of your plants",
)
def delete_plant(
    plant_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    plant = get_owned_or_404(db, Plant, plant_id, user)
    db.delete(plant)
    db.commit()
    logger.info("Plant deleted: %s by user %s", plant_id, user.id)


@router.get(
    "/{plant_id}/state",
    response_model=PlantStateEnvelope,
    responses={404: _NOT_FOUND_DESC},
    summary="Get a plant's initial process state",
)
def get_plant_state(
    plant_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    plant = get_owned_or_404(db, Plant, plant_id, user)
    return success_response(
        {"plantId": plant.id, "state": _state_out(plant.state).model_dump()}
    )
