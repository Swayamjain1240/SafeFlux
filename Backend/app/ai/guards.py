"""Duplicate-run protection (Part 8, RATE LIMITING section).

A repeated click must not create a second expensive investigation. The guard is a
tiny in-process registry keyed by ``(user, plant)``: the first request wins, and a
concurrent duplicate is told ``409`` instead of starting another agent loop.

It is deliberately *not* a queue and not a cache: an entry exists only while a
run is executing, is removed on every exit path (success, refusal, exception),
and holds no user data beyond the keys.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from typing import Iterator


class DuplicateRunError(RuntimeError):
    """Raised when the same user already has an investigation in flight."""

    def __init__(self, key: str) -> None:
        super().__init__("an investigation is already running for this plant")
        self.key = key


class InFlightGuard:
    """Thread-safe set of active ``(user_id, plant_id)`` runs.

    ``threading.Lock`` is used because FastAPI runs sync endpoints in a worker
    pool; the critical sections are dict operations only, so contention is
    irrelevant next to a simulation.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._active: set[str] = set()

    @staticmethod
    def key(user_id: str, plant_id: str) -> str:
        return f"{user_id}:{plant_id}"

    def acquire(self, user_id: str, plant_id: str) -> str:
        """Claim the slot or raise ``DuplicateRunError``."""
        key = self.key(user_id, plant_id)
        with self._lock:
            if key in self._active:
                raise DuplicateRunError(key)
            self._active.add(key)
        return key

    def release(self, key: str) -> None:
        with self._lock:
            self._active.discard(key)

    def active_count(self) -> int:
        with self._lock:
            return len(self._active)

    @contextmanager
    def claim(self, user_id: str, plant_id: str) -> Iterator[str]:
        """Context manager form: ``with guard.claim(u, p): …``."""
        key = self.acquire(user_id, plant_id)
        try:
            yield key
        finally:
            self.release(key)


__all__ = ["DuplicateRunError", "InFlightGuard"]
