"""Deterministic lumped process model for the locked MVP process.

State vector (integrated by the engine):

    y = [volume_l, temperature_c]

Everything else (level, pressure, flows) is algebraic and derived from the
state plus the current parameters:

    level_pct        = 100 · V / V_nominal                     (clamped 0–100)
    feed_lpm         = feed_flow_lpm · fault_feed · pump_factor   (0 if pump off)
    valve_fraction   = (valve_position_pct / 100) · fault_outlet
    outlet_lpm       = K_out · valve_fraction · sqrt(level/100)
    heater_kw        = HEATER_MAX_KW · heater_power_pct / 100
    cooling_kw       = UA_max · cooling_pct/100 · fault_cooling · max(T − T_coolant, 0)
    pressure_bar     = P_atm + k_T · max(T − T_ref, 0) + k_L · (level/100)

Differential equations (SI-consistent, see ``constants`` for units):

    dV/dt = feed_lpm/60 − outlet_lpm/60                       [L/s]
    dT/dt = (heater_kw − cooling_kw
             + CP·feed_l/s·(T_feed − T)) / (CP·max(V, V_min))   [K/s]

The energy balance mixes the sensible heat of the feed stream with the heater and
jacket cooling. Expanding d(V·T)/dt with dV/dt = feed − outlet cancels the
outlet enthalpy term, so only the *feed* advection appears: draining a well-mixed
vessel does not by itself change its temperature. Cooling never adds heat (the
driving force is clamped at zero), and a dry vessel holds its temperature. At the
level bounds (100 % overflow / 0 % dry-out) the volume derivative is zeroed so
excess feed spills instead of leaving the physical range.

This is a documented simplification, not certified engineering software. See
``constants.ASSUMPTIONS`` and ``constants.LIMITATIONS``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import numpy as np

from app.simulator.constants import (
    COOLANT_INLET_C,
    COOLING_UA_MAX_KW_PER_K,
    CP_KJ_PER_L_K,
    FEED_TEMPERATURE_C,
    HEATER_MAX_KW,
    MIN_THERMAL_VOLUME_L,
    OUTLET_K_LPM,
    PRESSURE_ATMOSPHERIC_BAR,
    PRESSURE_PER_KELVIN_BAR,
    PRESSURE_PER_LEVEL_BAR,
    PRESSURE_REFERENCE_C,
    REACTOR_NOMINAL_VOLUME_L,
)


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


@dataclass(frozen=True)
class ProcessParameters:
    """Current (possibly faulted) operating parameters of the process."""

    feed_flow_lpm: float
    heater_power_pct: float
    cooling_pct: float
    valve_position_pct: float
    pump_running: bool = True
    # dynamic multipliers applied by fault injection (all neutral by default)
    cooling_factor: float = 1.0
    outlet_factor: float = 1.0
    feed_factor: float = 1.0
    pump_factor: float = 1.0
    coolant_inlet_c: float = COOLANT_INLET_C
    feed_temperature_c: float = FEED_TEMPERATURE_C

    def with_(self, **changes: object) -> "ProcessParameters":
        return replace(self, **changes)  # type: ignore[arg-type]

    @property
    def heater_kw(self) -> float:
        return HEATER_MAX_KW * clamp(self.heater_power_pct, 0.0, 100.0) / 100.0

    @property
    def cooling_ua_kw_per_k(self) -> float:
        effectiveness = clamp(self.cooling_pct, 0.0, 100.0) / 100.0 * self.cooling_factor
        return COOLING_UA_MAX_KW_PER_K * max(effectiveness, 0.0)

    @property
    def effective_feed_lpm(self) -> float:
        if not self.pump_running:
            return 0.0
        return max(self.feed_flow_lpm, 0.0) * self.feed_factor * max(self.pump_factor, 0.0)

    @property
    def valve_fraction(self) -> float:
        return clamp(self.valve_position_pct, 0.0, 100.0) / 100.0 * self.outlet_factor

    def outlet_lpm(self, level_pct: float) -> float:
        return OUTLET_K_LPM * self.valve_fraction * np.sqrt(max(level_pct, 0.0) / 100.0)


def level_percent(volume_l: float) -> float:
    return clamp(volume_l / REACTOR_NOMINAL_VOLUME_L * 100.0, 0.0, 100.0)


def pressure_bar(temperature_c: float, level_pct: float) -> float:
    """Simplified pressure proxy — NOT vapour pressure (see assumptions)."""
    thermal_term = PRESSURE_PER_KELVIN_BAR * max(temperature_c - PRESSURE_REFERENCE_C, 0.0)
    head_term = PRESSURE_PER_LEVEL_BAR * level_pct / 100.0
    return PRESSURE_ATMOSPHERIC_BAR + thermal_term + head_term


def initial_vector(volume_l: float, temperature_c: float) -> np.ndarray:
    return np.array([max(volume_l, 0.0), temperature_c], dtype=float)


def volume_from_level(level_pct: float) -> float:
    return clamp(level_pct, 0.0, 100.0) / 100.0 * REACTOR_NOMINAL_VOLUME_L


def derivatives(t: float, y: np.ndarray, params: ProcessParameters) -> np.ndarray:  # noqa: ARG001
    """Right-hand side of the ODE system (``t`` unused: the model is autonomous)."""
    volume = max(float(y[0]), 0.0)
    temperature = float(y[1])
    level = level_percent(volume)

    feed_lps = params.effective_feed_lpm / 60.0
    outlet_lps = params.outlet_lpm(level) / 60.0

    d_volume = feed_lps - outlet_lps
    if volume >= REACTOR_NOMINAL_VOLUME_L and d_volume > 0.0:
        d_volume = 0.0  # overflow: excess feed spills
    elif volume <= 0.0 and d_volume < 0.0:
        d_volume = 0.0  # dry-out: no liquid left to drain

    if volume <= MIN_THERMAL_VOLUME_L:
        # Dry vessel: there is no liquid to carry sensible heat, so the heater
        # and jacket have nothing to act on. Holding the temperature avoids a
        # meaningless divide-by-tiny-mass blow-up (documented simplification).
        return np.array([d_volume, 0.0], dtype=float)

    heater_kw = params.heater_kw
    cooling_kw = params.cooling_ua_kw_per_k * max(temperature - params.coolant_inlet_c, 0.0)
    # Feed advection: expanding d(V·T)/dt = Q/(rho·cp) + feed·T_feed − outlet·T with
    # dV/dt = feed − outlet cancels the outlet term, leaving feed·(T_feed − T).
    advection_kw = CP_KJ_PER_L_K * feed_lps * (params.feed_temperature_c - temperature)
    thermal_capacity = CP_KJ_PER_L_K * max(volume, MIN_THERMAL_VOLUME_L)
    d_temperature = (heater_kw - cooling_kw + advection_kw) / thermal_capacity

    return np.array([d_volume, d_temperature], dtype=float)


def sample(t: float, y: np.ndarray, params: ProcessParameters) -> dict[str, float | bool]:
    """Derive one observable snapshot from the state vector."""
    volume = max(float(y[0]), 0.0)
    temperature = float(y[1])
    level = level_percent(volume)
    return {
        "time_s": float(t),
        "volume_l": volume,
        "level_pct": level,
        "true_temperature_c": temperature,
        "true_pressure_bar": pressure_bar(temperature, level),
        "feed_flow_lpm": params.effective_feed_lpm,
        "outlet_flow_lpm": float(params.outlet_lpm(level)),
        "heater_power_pct": params.heater_power_pct,
        "cooling_pct": params.cooling_pct * params.cooling_factor,
        "valve_position_pct": params.valve_position_pct * params.outlet_factor,
        "pump_running": params.pump_running,
    }
