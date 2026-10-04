"""Plant domain models (SAFEFLUX_MASTER.md §4, ARCHITECTURE §16).

The locked MVP process:

    Feed Tank → Pump P-101 → Heated Reactor R-101 → Outlet Valve V-101 → Product Tank

Five tables model one plant:

- ``Plant``          — identity + ownership (every plant belongs to one User),
- ``PlantConfig``    — static engineered configuration (setpoints/equipment),
- ``PlantState``     — dynamic initial process condition,
- ``SafetyLimits``   — configured trip limits,
- ``SafeguardConfig``— which safeguards are armed and their timing.

Config/state/limits/safeguards are one-to-one rows owned by the plant and
are deleted with it. Every numeric field is a *design input*: this is a
simulation model, never a live control system.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Plant(Base):
    __tablename__ = "plants"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # Owner FK — the ONLY source of truth for authorization (never client input).
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    location: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )

    config: Mapped["PlantConfig"] = relationship(
        back_populates="plant", cascade="all, delete-orphan", uselist=False
    )
    state: Mapped["PlantState"] = relationship(
        back_populates="plant", cascade="all, delete-orphan", uselist=False
    )
    safety_limits: Mapped["SafetyLimits"] = relationship(
        back_populates="plant", cascade="all, delete-orphan", uselist=False
    )
    safeguards: Mapped["SafeguardConfig"] = relationship(
        back_populates="plant", cascade="all, delete-orphan", uselist=False
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Plant {self.id} owner={self.owner_id}>"


class PlantConfig(Base):
    """Static engineered configuration — what the plant is set to run at."""

    __tablename__ = "plant_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    plant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plants.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    feed_flow_lpm: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    cooling_pct: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    valve_position_pct: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)
    heater_power_pct: Mapped[float] = mapped_column(Float, nullable=False, default=60.0)
    shutdown_delay_s: Mapped[int] = mapped_column(Integer, nullable=False, default=5)

    plant: Mapped[Plant] = relationship(back_populates="config")


class PlantState(Base):
    """Dynamic initial process condition the simulation starts from."""

    __tablename__ = "plant_states"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    plant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plants.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    pump_running: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    temperature_c: Mapped[float] = mapped_column(Float, nullable=False, default=25.0)
    pressure_bar: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    level_pct: Mapped[float] = mapped_column(Float, nullable=False, default=50.0)

    plant: Mapped[Plant] = relationship(back_populates="state")


class SafetyLimits(Base):
    """Configured trip limits used by the safety engine (Part 5)."""

    __tablename__ = "safety_limits"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    plant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plants.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    max_temperature_c: Mapped[float] = mapped_column(Float, nullable=False, default=150.0)
    max_pressure_bar: Mapped[float] = mapped_column(Float, nullable=False, default=10.0)
    max_level_pct: Mapped[float] = mapped_column(Float, nullable=False, default=90.0)

    plant: Mapped[Plant] = relationship(back_populates="safety_limits")


class SafeguardConfig(Base):
    """Which safeguards are armed and how fast they act."""

    __tablename__ = "safeguard_configs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    plant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plants.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    auto_shutdown_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    high_temperature_trip: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    high_pressure_trip: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    high_level_trip: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    trip_delay_s: Mapped[int] = mapped_column(Integer, nullable=False, default=2)

    plant: Mapped[Plant] = relationship(back_populates="safeguards")
