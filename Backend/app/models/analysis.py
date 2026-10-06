"""Analysis persistence (Part 9).

Two tables:

- ``Analysis``        — one autonomous run (or stored comparison) with its request
                        snapshot and the result document it produced,
- ``AnalysisEvent``   — the real pipeline events, written by the code that did the
                        work as it did it, each with its real elapsed time.

The result document is the evidence the UI pages and the report read; nothing in
the UI is reconstructed, estimated or animated into existence. Ownership follows
the plant rule: an analysis belongs to its owner, and every endpoint resolves it
through ``get_owned_or_404`` (cross-user access is a 404, never a 403).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class Analysis(Base):
    """One autonomous analysis run, or one stored comparison against a parent."""

    __tablename__ = "analyses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    # Owner FK — the ONLY source of truth for authorization (never client input).
    owner_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=False, index=True
    )
    plant_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("plants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # "auto" | "counterfactual" | "reverify" (app-level enum; validated in schemas).
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="auto")
    # "running" | "complete" | "failed" | "interrupted".
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running")
    # The engineer's engineering-change text, sanitized before storage.
    goal: Mapped[str] = mapped_column(String(2000), nullable=False, default="")
    # For stored comparisons: the analysis whose failure is being examined.
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # What was asked for (plan snapshot / mitigations / variants) — reproducibility.
    request: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    # The evidence document produced by the run (schema per kind).
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Fast summary for history rows (counts + headline), so listing never opens
    # the full result document.
    counts: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error: Mapped[str | None] = mapped_column(String(300), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow, onupdate=_utcnow
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    events: Mapped[list["AnalysisEvent"]] = relationship(
        back_populates="analysis", cascade="all, delete-orphan", order_by="AnalysisEvent.seq"
    )

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<Analysis {self.id} kind={self.kind} status={self.status}>"


class AnalysisEvent(Base):
    """One real pipeline event, written when the work happened, not replayed."""

    __tablename__ = "analysis_events"
    __table_args__ = (UniqueConstraint("analysis_id", "seq", name="uq_analysis_event_seq"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    analysis_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # 1-based, gapless per analysis; the polling cursor (?after_seq=) relies on it.
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Real wall-clock offset from run start — measured, never invented.
    elapsed_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_utcnow
    )

    analysis: Mapped[Analysis] = relationship(back_populates="events")

    def to_dict(self) -> dict:
        return {
            "seq": self.seq,
            "kind": self.kind,
            "label": self.label,
            "payload": self.payload,
            "elapsed_ms": self.elapsed_ms,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return f"<AnalysisEvent {self.analysis_id}#{self.seq} {self.kind}>"
