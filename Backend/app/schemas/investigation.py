"""Pydantic schema for the investigation endpoint (Part 8).

The request carries a plant the caller must own and an optional engineer-written
goal. The goal is *untrusted text*: it is sanitized, scanned for instruction-like
content and quarantined as data. It is never treated as a configuration, never
evaluated, and never logged.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.ai.constants import MAX_FOCUS_TEXT_CHARS


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class InvestigationRunRequest(_StrictModel):
    """POST /investigations/run — one bounded AI-assisted investigation."""

    plant_id: str = Field(min_length=1, max_length=64)
    #: Free text from the engineer. Bounded here; sanitized and scanned before use.
    goal: str | None = Field(default=None, max_length=MAX_FOCUS_TEXT_CHARS)


__all__ = ["InvestigationRunRequest"]
