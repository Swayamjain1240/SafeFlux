"""Live simulated telemetry (Part 5).

Deterministic simulator output is turned into bounded telemetry frames and
served to the frontend through the current-state store and SSE. No random
values, no LLM per tick.
"""

from app.telemetry.constants import (
    DEFAULT_HISTORY_LIMIT,
    DEFAULT_MAX_HISTORY,
    DEFAULT_MAX_PLANTS,
    MAX_HISTORY_LIMIT,
    TELEMETRY_VERSION,
)
from app.telemetry.frames import TelemetryFrame, build_frames, telemetry_metadata
from app.telemetry.service import ConnectionLimitError, TelemetryService
from app.telemetry.store import CurrentStateStore

__all__ = [
    "ConnectionLimitError",
    "CurrentStateStore",
    "DEFAULT_HISTORY_LIMIT",
    "DEFAULT_MAX_HISTORY",
    "DEFAULT_MAX_PLANTS",
    "MAX_HISTORY_LIMIT",
    "TELEMETRY_VERSION",
    "TelemetryFrame",
    "TelemetryService",
    "build_frames",
    "telemetry_metadata",
]
