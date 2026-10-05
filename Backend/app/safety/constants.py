"""Constants for the deterministic safety engine (Part 5).

The safety engine is pure deterministic software: it classifies numeric
simulator evidence against configured limits. No LLM participates in deciding
whether a limit was exceeded (SAFEFLUX_MASTER.md §8).
"""

from __future__ import annotations

SAFETY_ENGINE_VERSION = "0.1.0"

# A value at or above ``near_limit_fraction · limit`` is NEAR_LIMIT: still
# inside the configured limit but close enough to warn about. The fraction is
# caller-configurable per assessment and clamped to this window.
DEFAULT_NEAR_LIMIT_FRACTION = 0.9
MIN_NEAR_LIMIT_FRACTION = 0.5
MAX_NEAR_LIMIT_FRACTION = 1.0

# The three monitored process variables, in evaluation order.
MONITORED_VARIABLES: tuple[str, ...] = ("temperature_c", "pressure_bar", "level_pct")

# Safety language (SAFEFLUX_MASTER.md §24): never claim a real plant is safe.
SAFETY_LANGUAGE_DISCLAIMER = (
    "Deterministic simulation evidence for the tested scenarios only. "
    "This is never a claim about a real plant and never a certified safety limit."
)
NO_UNSAFE_CONDITION = (
    "No unsafe condition was detected within the tested simulation scenarios."
)
NO_REAL_PLANT_CLAIM = (
    "Simulated safeguard timing only — never a claim about real plant response."
)
