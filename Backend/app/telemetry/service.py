"""Telemetry service: ingestion, replay and bounded streaming (Part 5).

The service is the only place that turns deterministic simulator output into
telemetry. It ingests a run into the current-state store, then replays the
stored frames over an SSE-friendly async iterator. Every stream connection is
counted so a client can never open unbounded concurrent streams.

Counters live in-process (fine for the single-process MVP) and are released in
the stream's ``finally`` block, so a client disconnect always frees its slot.
"""

from __future__ import annotations

import asyncio
import contextlib
import threading
from collections.abc import AsyncIterator

from app.simulator.result import SimulationResult
from app.telemetry.constants import DEFAULT_REPLAY_INTERVAL_S
from app.telemetry.frames import TelemetryFrame, build_frames
from app.telemetry.store import CurrentStateStore


class ConnectionLimitError(Exception):
    """Raised when opening a telemetry stream would exceed a hard limit."""

    def __init__(self, scope: str, limit: int) -> None:
        super().__init__("telemetry stream connection limit reached")
        self.scope = scope
        self.limit = limit


class TelemetryService:
    """Owns the current-state store and the bounded stream registry."""

    def __init__(
        self,
        store: CurrentStateStore,
        *,
        max_streams_total: int = 64,
        max_streams_per_plant: int = 8,
        max_streams_per_user: int = 8,
        replay_interval_s: float = DEFAULT_REPLAY_INTERVAL_S,
    ) -> None:
        self._store = store
        self._max_total = max(1, max_streams_total)
        self._max_per_plant = max(1, max_streams_per_plant)
        self._max_per_user = max(1, max_streams_per_user)
        self._replay_interval = max(0.0, replay_interval_s)
        self._total = 0
        self._per_plant: dict[str, int] = {}
        self._per_user: dict[str, int] = {}
        self._lock = threading.Lock()

    # -------------------- ingestion --------------------

    @property
    def store(self) -> CurrentStateStore:
        return self._store

    def ingest_frames(self, plant_id: str, frames: list[TelemetryFrame]) -> int:
        return self._store.ingest(plant_id, frames)

    def ingest_result(
        self,
        plant_id: str,
        result: SimulationResult,
        limits: dict[str, float],
        near_limits: dict[str, float],
    ) -> int:
        frames = build_frames(result, plant_id, limits, near_limits)
        return self.ingest_frames(plant_id, frames)

    # -------------------- reads --------------------

    def current(self, plant_id: str) -> TelemetryFrame | None:
        return self._store.current(plant_id)

    def history(self, plant_id: str, limit: int | None = None) -> list[TelemetryFrame]:
        return self._store.history(plant_id, limit)

    def has_session(self, plant_id: str) -> bool:
        return self._store.current(plant_id) is not None

    def clear(self, plant_id: str) -> None:
        self._store.clear(plant_id)

    # -------------------- connection registry --------------------

    def active_streams(self, plant_id: str | None = None) -> int:
        with self._lock:
            if plant_id is None:
                return self._total
            return self._per_plant.get(plant_id, 0)

    def _register(self, plant_id: str, user_id: str) -> None:
        with self._lock:
            if self._total >= self._max_total:
                raise ConnectionLimitError("total", self._max_total)
            if self._per_plant.get(plant_id, 0) >= self._max_per_plant:
                raise ConnectionLimitError("plant", self._max_per_plant)
            if self._per_user.get(user_id, 0) >= self._max_per_user:
                raise ConnectionLimitError("user", self._max_per_user)
            self._total += 1
            self._per_plant[plant_id] = self._per_plant.get(plant_id, 0) + 1
            self._per_user[user_id] = self._per_user.get(user_id, 0) + 1

    def _release(self, plant_id: str, user_id: str) -> None:
        with self._lock:
            self._total = max(0, self._total - 1)
            if self._per_plant.get(plant_id):
                self._per_plant[plant_id] -= 1
                if self._per_plant[plant_id] == 0:
                    del self._per_plant[plant_id]
            if self._per_user.get(user_id):
                self._per_user[user_id] -= 1
                if self._per_user[user_id] == 0:
                    del self._per_user[user_id]

    # -------------------- streaming --------------------

    async def _replay(self, plant_id: str) -> AsyncIterator[TelemetryFrame]:
        frames = self._store.history(plant_id)
        for frame in frames:
            if self._replay_interval:
                await asyncio.sleep(self._replay_interval)
            yield frame

    @contextlib.asynccontextmanager
    async def open_stream(self, plant_id: str, user_id: str):
        """Register a bounded stream; yields an async frame iterator.

        Raises ``ConnectionLimitError`` before yielding when a hard connection
        limit would be exceeded, and always releases the slot on exit.
        """
        self._register(plant_id, user_id)
        try:
            yield self._replay(plant_id)
        finally:
            self._release(plant_id, user_id)


__all__ = ["ConnectionLimitError", "TelemetryService"]
