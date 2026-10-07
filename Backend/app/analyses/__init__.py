"""Autonomous analysis package (Part 9).

One analysis is one bounded, autonomous run that follows the pipeline the
task and the docs define:

    Understanding change → Mapping affected equipment → Planning investigation
    → Running scenario → Observing result → Refining boundary
    → Finding violation → Running counterfactual → Checking safeguard

Every stage is recorded by the code that did the work (analysis/events.py),
every verdict comes from the Part 4 simulator through the Part 5 safety engine,
the root-cause and re-verify comparisons run the Part 7 search machinery, and
the optional AI summary is rendered separately from the evidence it stems from.
"""

from __future__ import annotations

from app.analyses.constants import (
    ANALYSIS_DISCLAIMER,
    AnalysisEventKind,
    AnalysisKind,
    AnalysisStatus,
    EVENT_LABELS,
    MAX_COUNTERFACTUALS,
    MAX_MITIGATION_KEY_CHARS,
    MAX_STORED_CASES,
    MAX_STORED_EVENTS,
    MAX_STORED_FAILURES,
    MAX_STORED_SERIES_PER_CASE,
    MAX_STORED_TIMELINE,
    MAX_VARIANTS_PER_VARIABLE,
    NO_UNSAFE_DETECTED_NOTE,
    SERIES_KEYS,
)

__all__ = [
    "ANALYSIS_DISCLAIMER",
    "AnalysisEventKind",
    "AnalysisKind",
    "AnalysisStatus",
    "EVENT_LABELS",
    "MAX_COUNTERFACTUALS",
    "MAX_MITIGATION_KEY_CHARS",
    "MAX_STORED_CASES",
    "MAX_STORED_EVENTS",
    "MAX_STORED_FAILURES",
    "MAX_STORED_SERIES_PER_CASE",
    "MAX_STORED_TIMELINE",
    "MAX_VARIANTS_PER_VARIABLE",
    "NO_UNSAFE_DETECTED_NOTE",
    "SERIES_KEYS",
]
