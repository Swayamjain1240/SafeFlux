"""Deterministic SafeFlux process simulator (Part 4).

The simulator evolves the locked MVP process deterministically: identical
inputs always produce identical outputs. There is no RNG and no LLM here —
truth is numeric and reproducible (SAFEFLUX_MASTER.md §8).
"""

from app.simulator.constants import (
    MODEL_NAME,
    MODEL_VERSION,
    SIMULATOR_VERSION,
)
from app.simulator.limits import SimulationLimits
from app.simulator.scenario import (
    FaultSpec,
    FaultType,
    Scenario,
    SensorFailureMode,
    SensorFault,
    SensorType,
)

__all__ = [
    "FaultSpec",
    "FaultType",
    "MODEL_NAME",
    "MODEL_VERSION",
    "SIMULATOR_VERSION",
    "Scenario",
    "SensorFailureMode",
    "SensorFault",
    "SensorType",
    "SimulationLimits",
]
