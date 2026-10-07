"""Request schemas for the analysis endpoints (Part 9, rule 6).

Every model is strict (unknown fields are rejected, not silently dropped), every
string is bounded, and every id is a plain string the route resolves through
ownership — a client never asserts *whose* object something is, only *which*.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

#: Mitigation keys re-verify accepts (allowlist; the route re-checks bounds).
MITIGATION_KEYS = (
    "shutdown_delay_s",
    "cooling_capacity_pct",
    "operating_target_pct",
    "feed_factor",
    "outlet_factor",
    "cooling_factor",
)

MAX_GOAL_CHARS = 2000


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class AnalysisRunRequest(_StrictModel):
    """POST /analyses/run — one autonomous analysis over one owned plant."""

    plant_id: str = Field(min_length=1, max_length=64)
    goal: str = Field(default="", max_length=MAX_GOAL_CHARS)


class ReverifyRequest(_StrictModel):
    """POST /analyses/{id}/reverify — one stored before/after comparison."""

    mitigations: dict[str, float] = Field(max_length=10)
    goal: str = Field(default="", max_length=MAX_GOAL_CHARS)

    model_config = ConfigDict(extra="forbid")


class PageParams(_StrictModel):
    """Shared pagination bounds (history; failure lists are bounded server-side)."""

    page: int = Field(default=1, ge=1, le=10_000)
    page_size: int = Field(default=10, ge=1, le=50)


__all__ = [
    "AnalysisRunRequest",
    "MITIGATION_KEYS",
    "PageParams",
    "ReverifyRequest",
]
