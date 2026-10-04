"""Simulator constants, units and documented assumptions.

This is a **deliberately simplified, lumped, well-mixed** model of the locked MVP
process. It is a decision-support tool for exploring *simulated* behaviour — it is
not an industrially certified model, not a first-principles chemical-engineering
simulation, and never a controller for real equipment.

Units used throughout the simulator:

- time: seconds (``s``)
- volume: litres (``L``)
- flow: litres per minute (``lpm``) — matches ``PlantConfig.feed_flow_lpm``
- temperature: degrees Celsius (``°C``)
- pressure: bar (``bar``)
- level: percent of nominal reactor volume (``%``)
- power / heat rate: kilowatts (``kW`` == kJ/s)
- thermal capacity: kJ per litre per kelvin (``kJ/(L·K)``)

The liquid is treated as water-like (density 1 kg/L, cp 4.18 kJ/(kg·K)), so a
thermal capacity of ``cp · V`` in kJ/K follows directly from the volume in litres.
"""

from __future__ import annotations

SIMULATOR_VERSION = "0.1.0"
MODEL_NAME = "safeflux-lumped-mvp"
MODEL_VERSION = "1"

# --- geometry ---------------------------------------------------------------
REACTOR_NOMINAL_VOLUME_L = 100.0

# --- thermal ----------------------------------------------------------------
CP_KJ_PER_L_K = 4.18  # water-like: rho 1 kg/L x cp 4.18 kJ/(kg·K)
FEED_TEMPERATURE_C = 25.0
COOLANT_INLET_C = 25.0
HEATER_MAX_KW = 2000.0  # 2 MW industrial process heater at 100 % power
COOLING_UA_MAX_KW_PER_K = 30.0  # jacket conductance at 100 % cooling effectiveness

# --- hydraulics -------------------------------------------------------------
OUTLET_K_LPM = 400.0  # outlet flow at 100 % valve opening and full level

# --- pressure proxy ---------------------------------------------------------
PRESSURE_ATMOSPHERIC_BAR = 1.0
PRESSURE_PER_KELVIN_BAR = 0.05  # proxy for vapour-pressure growth with T
PRESSURE_PER_LEVEL_BAR = 2.0  # static head contribution at full level
PRESSURE_REFERENCE_C = 25.0

# --- numerical guards -------------------------------------------------------
MIN_THERMAL_VOLUME_L = 1.0  # avoids divide-by-zero in the energy balance

# Documented modelling assumptions surfaced in every result's metadata.
ASSUMPTIONS: tuple[str, ...] = (
    "Single perfectly-mixed reactor volume; no spatial gradients.",
    "Water-like liquid: density 1 kg/L, cp 4.18 kJ/(kg·K), constant.",
    "Feed enters at a fixed temperature and leaves at the reactor temperature.",
    "Heater delivers power proportional to heater_power_pct (0-100 %).",
    "Cooling removes heat linearly in (T - coolant_inlet) scaled by cooling_pct.",
    "Outlet flow is gravity-driven: proportional to valve opening and sqrt(level).",
    "Overflow (level 100 %) and dry-out (level 0 %) clamp the level; excess spills.",
    "Pressure is a documented proxy (atmospheric + temperature + static head), "
    "NOT a real vapour-pressure or phase-equilibrium calculation.",
    "Faults are deterministic step changes at scheduled times; there is no RNG.",
    "Sensor faults affect OBSERVED readings only, never the true process state.",
    "Shutdown-delay timing is resolved to the simulation time_step.",
    "Emergency shutdown stops the feed pump and cuts the heater; valve closure and "
    "depressurisation are NOT modelled.",
    "A dry vessel (no liquid) has nothing for the heater or jacket to act on, so its "
    "temperature is held rather than heating an empty shell.",
)

LIMITATIONS: tuple[str, ...] = (
    "Not a certified or first-principles model; no reaction kinetics or thermodynamics.",
    "No heat-exchanger dynamics, no pump curve, no pipe hydraulics or two-phase flow.",
    "Pressure is a proxy, so pressure findings are indicative only.",
    "Valid only for the single locked MVP process topology.",
)
