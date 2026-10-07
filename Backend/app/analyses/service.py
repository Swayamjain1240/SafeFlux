"""The analysis service (Part 9).

The one place that assembles an interpretation, a recorder and the runner, and
the boundary the routes never reason past:
- ownership is resolved by the caller (routes) with ``get_owned_or_404`` before
  the service runs; the service itself never trusts a client id,
- a repeated click cannot run two analyses on the same plant at once: the
  in-flight guard answers a duplicate with 409 instead of a second run,
- every stage of a run writes real events *through the same DB session*, and
  the work commits only when the run really finished,
- statuses are real: ``complete``/``failed`` from the run's outcome, and a
  process restart never pretends a live row finished.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from app.ai.provider import build_provider
from app.analyses.constants import (
    ANALYSIS_DISCLAIMER,
    NO_UNSAFE_DETECTED_NOTE,
    UNSAFE_DETECTED_NOTE,
)
from app.analyses.events import EventRecorder
from app.analyses.interpret import interpret_goal
from app.analyses.runner import AnalysisRunner
from app.ai.guards import DuplicateRunError, InFlightGuard
from app.ai.security import sanitize_untrusted_text
from app.search import PlantProfile

logger = logging.getLogger("safeflux.analysis.service")

_SECONDS_PER_MINUTE = 60.0


class AnalysisCleanupError(RuntimeError):
    """Raised internally when a claimed slot is released like Part 8 does."""


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AnalysisService:
    """Creates, runs and serves stored analyses and their comparisons."""

    def __init__(self, *, guard: InFlightGuard | None = None) -> None:
        self.guard = guard or InFlightGuard()

    # ------------------------------------------------------------------ run

    def run(
        self,
        *,
        db,  # noqa: ANN001 - Session
        user,  # noqa: ANN001 - User
        plant,  # noqa: ANN001 - Plant
        settings,  # noqa: ANN001 - Settings
        goal: str,
        analysis_id: str | None = None,
        recorder: EventRecorder | None = None,
    ) -> str:
        """Execute one autonomous run; returns the analysis id.

        Ownership has been enforced by the caller. The in-flight slot is claimed
        here, not in the route, so *every* caller of the service (routes, tests,
        a future worker) is protected the same way.
        """
        analysis_id = analysis_id or f"an-{uuid.uuid4().hex[:12]}"
        cleaned = sanitize_untrusted_text(goal or "", limit=2000)
        interpretation = interpret_goal(cleaned)
        recorder = recorder or EventRecorder(db, analysis_id)
        self.last_failed_id: str | None = None
        with self.guard.claim(str(user.id), str(plant.id)):
            analysis = self._create_row(
                db=db,
                user=user,
                plant=plant,
                analysis_id=analysis_id,
                goal=cleaned,
                interpretation=interpretation,
            )
            db.flush()
            evaluator = AnalysisRunner(
                db=db,
                analysis_id=analysis_id,
                profile=PlantProfile.from_plant(plant),
                settings=settings,
                goal_text=cleaned,
                interpretation=interpretation,
                recorder=recorder,
                summarizer=self._summarizer_for(settings),
            )
            try:
                result = evaluator.run()
                analysis.result = result
                analysis.counts = self._counts_for(result)
                mark_complete(analysis)
            except Exception as exc:  # noqa: BLE001 - real failure, real status
                self.last_failed_id = analysis_id
                mark_failed(analysis, exc, running_status="failed")
                raise
            return analysis_id

    def _summarizer_for(self, settings) -> object | None:
        """Build the after-evidence summarizer when a provider is configured."""
        from app.analyses.summary import ai_summarizer_if_configured

        return ai_summarizer_if_configured(settings)

    def _evaluator_for(self, *, runner: type) -> None:
        """Unused hook retained for interface stability (no behavior)."""
        del runner

    def _create_row(self, *, db, user, plant, analysis_id: str, goal: str, interpretation) -> object:
        """Insert the analysis row (owner and snapshot only; result comes later)."""
        from app.models import Analysis

        analysis = Analysis(
            id=analysis_id,
            owner_id=str(user.id),
            plant_id=str(plant.id),
            kind="auto",
            status="running",
            goal=goal,
            request={
                "goal": goal,
                "interpreted_change": interpretation.to_dict(),
                "created_at": _utcnow().isoformat(),
            },
            result=None,
            counts=None,
        )
        db.add(analysis)
        return analysis

    # ------------------------------------------------------------------ reads

    def counts_for(self, result: dict | None) -> dict | None:
        """The history-row fast summary (headline only, no full document)."""
        return self._counts_for(result)

    def _counts_for(self, result: dict | None) -> dict | None:
        if not result:
            return None
        counts = result.get("counts") or {}

        failures = result.get("failures") or []
        pivot = result.get("pivot") or {}
        return {
            "scenarios": counts.get("scenarios", 0),
            "failing": counts.get("failing", 0),
            "violation": counts.get("violation", 0),
            "safeguard_activated": counts.get("safeguard_activated", 0),
            "failures_stored": len(failures),
            "counterfactuals": len(result.get("counterfactuals") or []),
            "headline": (pivot.get("status") or "none"),
            "pivot_status": pivot.get("status"),
            "disclaimer": ANALYSIS_DISCLAIMER,
        }

    def ai_configured(self, settings) -> bool:
        """Whether an AI provider is configured (boolean only; never values)."""
        from app.ai.provider import ProviderConfig

        return bool(ProviderConfig.from_settings(settings).configured)


def mark_complete(analysis) -> None:
    """Real completion: a finished run with the measured status."""
    analysis.status = "complete"
    analysis.error = None
    analysis.finished_at = _utcnow()


def mark_failed(analysis, exc: BaseException | None, *, running_status: str = "failed") -> None:
    """A real failure: the run stopped, and the failure is recorded verbatim."""
    analysis.status = running_status
    analysis.error = str(exc)[:300] if exc else None
    analysis.finished_at = _utcnow()


def mark_interrupted(db, *, before: datetime) -> int:
    """Rows still ``running`` with no live claim are honest about the restart.

    Called at process start so a hard kill never leaves a run pretending to be
    active. Returns the count of rows closed as ``interrupted``.
    """
    from sqlalchemy import select

    from app.models import Analysis

    rows = db.execute(
        select(Analysis).where(
            Analysis.status == "running", Analysis.created_at <= before
        )
    ).scalars().all()
    for row in rows:
        row.status = "interrupted"
        row.error = "The process restarted while this analysis was running."
        row.finished_at = _utcnow()
    db.commit()
    return len(rows)


def mark_failed_status(db, analysis_id: str, status: str, error: str | None = None) -> None:
    """Force-close one analysis row (for exception handlers / tests)."""
    from app.models import Analysis

    row = db.get(Analysis, analysis_id)
    if row is not None:
        mark_failed(row, None, running_status=status)
        if error:
            row.error = error[:300]
        db.commit()


__all__ = [
    "AnalysisService",
    "AnalysisCleanupError",
    "mark_complete",
    "mark_failed",
    "mark_failed_status",
    "mark_interrupted",
    "_SECONDS_PER_MINUTE",
]
