"""Constants for the deterministic scenario search (Part 7).

The search is bounded by construction: every knob has a hard ceiling here and a
per-request ceiling in ``budgets.py``. Nothing in this package may run an
unbounded number of simulations (SAFEFLUX_MASTER.md rule 8).

``METHOD_VERSION`` is part of every result document: changing the search
algorithm must bump it, because two searches with identical inputs and
different method versions are not comparable evidence.
"""

from __future__ import annotations

# Bump when the search algorithm changes; recorded in every result.
METHOD_VERSION = "1"
SEARCH_ENGINE_VERSION = "0.1.0"

# --- coarse sweep ---
DEFAULT_SWEEP_STEPS = 9
MIN_SWEEP_STEPS = 2
MAX_SWEEP_STEPS = 25

# --- combination search (per-axis points) ---
DEFAULT_MULTI_STEPS = 5
MIN_MULTI_STEPS = 2
MAX_MULTI_STEPS = 7
MAX_COMBINATION_AXES = 2

# --- refinement ---
DEFAULT_REFINEMENT_DEPTH = 6
MAX_REFINEMENT_DEPTH_CEILING = 12
# Upper bound on extra evaluations one refinement pass may add, independent of
# depth, so a wide range can never explode the budget.
MAX_REFINEMENT_EVALUATIONS = 64

# --- budgets (hard ceilings; request values are clamped to these) ---
DEFAULT_MAX_SCENARIOS = 150
MAX_SCENARIOS_CEILING = 2000
DEFAULT_MAX_COMBINATIONS = 36
MAX_COMBINATIONS_CEILING = 200
DEFAULT_TIMEOUT_S = 90.0
MIN_TIMEOUT_S = 1.0
MAX_TIMEOUT_S_CEILING = 900.0

# --- default scenario shape for searched cases ---
DEFAULT_SCENARIO_DURATION_S = 300.0
DEFAULT_SCENARIO_TIME_STEP_S = 1.0
DEFAULT_FAULT_START_S = 0.0

# Tolerance used when deciding whether two sampled values are the same point
# (grid rounding) and when classifying monotonic behaviour.
VALUE_TOLERANCE = 1e-9
# Values are rounded to this many decimals so a case key is stable in JSON.
VALUE_DECIMALS = 6

SEARCH_DISCLAIMER = (
    "Deterministic search over the tested simulation scenarios only. "
    "A boundary found here is a property of this model, never of a real plant."
)

# Bound on how many failure scenarios a single result document may carry.
MAX_REPORTED_FAILURES = 100
MAX_TRACE_ENTRIES = 500
