"""Constants for the live simulated telemetry layer (Part 5).

The telemetry layer only *serves* deterministic simulator output. It never
generates random values and never routes per-tick data through the LLM
(SAFEFLUX_MASTER.md §11).
"""

from __future__ import annotations

TELEMETRY_VERSION = "0.1.0"

# Requested-history default when a caller omits ``limit``.
DEFAULT_HISTORY_LIMIT = 120
# Absolute ceiling on how many frames can be requested in one history call.
MAX_HISTORY_LIMIT = 1000

# Default per-plant retained history (samples). Bounded so a long run can never
# grow memory without limit.
DEFAULT_MAX_HISTORY = 600
# Maximum number of plants whose telemetry is retained in one process.
DEFAULT_MAX_PLANTS = 200

# Default wall-clock pacing between streamed frames (seconds).
DEFAULT_REPLAY_INTERVAL_S = 0.25
