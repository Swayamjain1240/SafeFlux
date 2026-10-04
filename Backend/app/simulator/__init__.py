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
from app.simulator.engine import (
    LimitSet,
    SafeguardSettings,
    SimulationInput,
    SimulationLimitError,
    run_simulation,
)
from app.simulator.limits import SimulationLimits
from app.simulator.model import ProcessParameters
from app.simulator.result import SimulationResult
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
    "LimitSet",
    "MODEL_NAME",
    "MODEL_VERSION",
    "ProcessParameters",
    "SIMULATOR_VERSION",
    "SafeguardSettings",
    "Scenario",
    "SensorFailureMode",
    "SensorFault",
    "SensorType",
    "SimulationInput",
    "SimulationLimitError",
    "SimulationLimits",
    "SimulationResult",
    "run_simulation",
]
