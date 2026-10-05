"""Bounded, thread-safe current-state store for telemetry (Part 5).

Architecture (SAFEFLUX_MASTER.md §11 / ARCHITECTURE §19):

    Simulator -> TelemetryService -> CurrentStateStore -> SSE/API -> Frontend

The store keeps only the most recent frame per plant plus a bounded per-plant
history, so receiving a long simulation can never grow memory without limit.
It holds no secrets: frames contain simulated process values and configured
limits only.
"""

from __future__ import annotations

import threading
from collections import OrderedDict, deque

from app.telemetry.constants import DEFAULT_MAX_HISTORY, DEFAULT_MAX_PLANTS
from app.telemetry.frames import TelemetryFrame


class CurrentStateStore:
    """Latest frame + bounded history per plant, with a bounded plant count."""

    def __init__(
        self,
        max_history: int = DEFAULT_MAX_HISTORY,
        max_plants: int = DEFAULT_MAX_PLANTS,
    ) -> None:
        self._max_history = max(1, max_history)
        self._max_plants = max(1, max_plants)
        self._current: OrderedDict[str, TelemetryFrame] = OrderedDict()
        self._history: OrderedDict[str, deque[TelemetryFrame]] = OrderedDict()
        self._lock = threading.Lock()

    def _touch(self, plant_id: str) -> None:
        # Move to the end (most recently used) for LRU eviction.
        self._current.pop(plant_id, None)
        self._history.pop(plant_id, None)

    def _evict_if_needed(self) -> None:
        while len(self._current) > self._max_plants:
            oldest, _ = self._current.popitem(last=False)
            self._history.pop(oldest, None)

    def ingest(self, plant_id: str, frames: list[TelemetryFrame]) -> int:
        """Store a batch of frames; keep only the most recent ``max_history``."""
        if not frames:
            return 0
        with self._lock:
            self._touch(plant_id)
            history: deque[TelemetryFrame] = deque(maxlen=self._max_history)
            for frame in frames:
                history.append(frame)
            self._current[plant_id] = history[-1]
            self._history[plant_id] = history
            self._evict_if_needed()
            return len(history)

    def set_current(self, frame: TelemetryFrame) -> None:
        with self._lock:
            self._current[frame.plant_id] = frame
            self._current.move_to_end(frame.plant_id)
            history = self._history.get(frame.plant_id)
            if history is None:
                history = deque(maxlen=self._max_history)
                self._history[frame.plant_id] = history
            if not history or history[-1].sequence != frame.sequence:
                history.append(frame)
            self._evict_if_needed()

    def current(self, plant_id: str) -> TelemetryFrame | None:
        with self._lock:
            return self._current.get(plant_id)

    def history(self, plant_id: str, limit: int | None = None) -> list[TelemetryFrame]:
        with self._lock:
            frames = list(self._history.get(plant_id, ()))
        if limit is not None and limit < len(frames):
            frames = frames[-limit:]
        return frames

    def clear(self, plant_id: str) -> None:
        with self._lock:
            self._current.pop(plant_id, None)
            self._history.pop(plant_id, None)

    def plant_count(self) -> int:
        with self._lock:
            return len(self._current)

    def history_size(self, plant_id: str) -> int:
        with self._lock:
            return len(self._history.get(plant_id, ()))


__all__ = ["CurrentStateStore"]
