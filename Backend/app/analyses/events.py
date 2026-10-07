"""Recording the real pipeline events (Part 9).

Every event row is written by the code that did the work *while it did it*, so
the live timeline is a record, not an animation:
- ``seq`` is 1-based and gapless per analysis (the frontend's ``?after_seq=``
  cursor relies on it),
- ``elapsed_ms`` is the measured wall-clock offset from run start — nothing is
  invented and nothing is replayed from timers,
- ``payload`` is bounded JSON shaped by whoever did the work; the tail of an
  oversized list is dropped rather than the head, so the newest evidence wins.
"""

from __future__ import annotations

import time
from typing import Any

from sqlalchemy.orm import Session

from app.analyses.constants import MAX_STORED_TIMELINE
from app.models import Analysis, AnalysisEvent

#: Timeline stages, in pipeline order. ``COMPLETE`` and ``FAILED`` are terminal
#: records, not stages, and the optional ``AI_EXPLANATION`` may appear anywhere.
_STAGE_ORDER: tuple[str, ...] = (
    "understanding_change",
    "mapping_equipment",
    "planning",
    "running_scenario",
    "observing_result",
    "refining_boundary",
    "finding_violation",
    "running_counterfactual",
    "checking_safeguard",
)
_STAGE_INDEX = {kind: index for index, kind in enumerate(_STAGE_ORDER, start=1)}


def stage_index(kind: str) -> int | None:
    """The 1-based pipeline stage of a timeline event (None for others)."""
    return _STAGE_INDEX.get(kind)


def _bound_list(values: list | None) -> list | None:
    """Bounded list: keep the newest entries beyond the storage limit."""
    if not isinstance(values, list):
        return values
    if len(values) <= MAX_STORED_TIMELINE:
        return values
    return values[-MAX_STORED_TIMELINE:]


def _bound_payload(payload: dict | None) -> dict | None:
    if payload is None:
        return None
    bounded: dict[str, Any] = {}
    for key, value in payload.items():
        bounded[key] = _bound_list(value) if isinstance(value, list) else value
    return bounded


class EventRecorder:
    """Persists one analysis' events with real, monotonic elapsed offsets."""

    def __init__(self, db: Session, analysis_id: str, *, monotonic: Any = None) -> None:
        self._db = db
        self._analysis_id = analysis_id
        self._seq = 0
        self._started = time.monotonic()
        self._monotonic = monotonic or time.monotonic

    @property
    def count(self) -> int:
        return self._seq

    def _elapsed_ms(self) -> int:
        return int(max(0, (self._monotonic() - self._started) * 1000))

    def emit(
        self,
        kind: str,
        *,
        label: str | None = None,
        payload: dict | None = None,
    ) -> None:
        """Record one real event. Caller supplies only what actually exists."""
        self._seq += 1
        self._db.add(
            AnalysisEvent(
                id=f"aev-{self._analysis_id}-{self._seq}",
                analysis_id=self._analysis_id,
                seq=self._seq,
                kind=kind,
                label=label,
                payload=_bound_payload(payload),
                elapsed_ms=self._elapsed_ms(),
            )
        )

    @property
    def analysis_id(self) -> str:
        return self._analysis_id


def mark_running(analysis: Analysis, *, details: dict | None = None) -> None:
    """A run restarts without pretending the previous attempt had a result."""
    analysis.status = "running"
    analysis.request = {**analysis.request, "attempts": details or {}}


def mark_finished(analysis: Analysis, *, status: str, error: str | None = None) -> None:
    """Close the run with the real status and a bounded error string."""
    from datetime import datetime, timezone

    analysis.status = status
    analysis.finished_at = datetime.now(timezone.utc)
    analysis.error = None if error is None else str(error)[:300]
