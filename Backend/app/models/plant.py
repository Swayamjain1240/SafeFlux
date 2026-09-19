from pydantic import BaseModel, Field


class SafetyLimits(BaseModel):
    max_temperature_c: float = Field(
        default=120.0,
        gt=0
    )

    max_pressure_bar: float = Field(
        default=4.0,
        gt=0
    )

    max_level_pct: float = Field(
        default=90.0,
        ge=0,
        le=100
    )


class PlantState(BaseModel):
    time_s: float = Field(
        default=0.0,
        ge=0
    )

    feed_flow_lpm: float = Field(
        default=100.0,
        ge=0
    )

    temperature_c: float = 80.0

    pressure_bar: float = Field(
        default=2.0,
        ge=0
    )

    level_pct: float = Field(
        default=50.0,
        ge=0,
        le=100
    )

    cooling_pct: float = Field(
        default=100.0,
        ge=0,
        le=100
    )

    valve_position_pct: float = Field(
        default=100.0,
        ge=0,
        le=100
    )

    pump_running: bool = True

    heater_power_pct: float = Field(
        default=50.0,
        ge=0,
        le=100
    )


class PlantConfig(BaseModel):
    plant_name: str = "SafeFlux Demo Plant"

    limits: SafetyLimits = Field(
        default_factory=SafetyLimits
    )

    initial_state: PlantState = Field(
        default_factory=PlantState
    )