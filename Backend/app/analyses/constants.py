"""Analysis domain constants (Part 9).

One analysis is one autonomous, evidence-producing run over an owned plant:

    auto           the end-user workflow: goal → plan → search → observe → refine
                   → counterfactuals → safeguard check → report-ready document
    counterfactual one stored what-if comparison against a parent's failure
    reverify       one stored before/after comparison under engineer mitigations

Everything the UI later shows is *recorded reality*: each event row is written by
the code that actually did the work, with the real elapsed time. Nothing is
replayed from timers, and no event exists that no code produced.
"""

from __future__ import annotations

from enum import Enum

#: Every document and page repeats what this product is.
ANALYSIS_DISCLAIMER = (
    "SafeFlux explores simulated scenarios only; it never actuates real equipment "
    "and never guarantees a real plant is safe."
)


class AnalysisKind(str, Enum):
    AUTO = "auto"
    COUNTERFACTUAL = "counterfactual"
    REVERIFY = "reverify"


class AnalysisStatus(str, Enum):
    RUNNING = "running"
    COMPLETE = "complete"
    FAILED = "failed"
    #: The process restarted while this run was in flight; the run's outcome is
    #: unknown, and the row says so instead of pretending it finished.
    INTERRUPTED = "interrupted"


class AnalysisEventKind(str, Enum):
    """The real pipeline stages, in the order they can occur."""

    UNDERSTANDING_CHANGE = "understanding_change"
    MAPPING_EQUIPMENT = "mapping_equipment"
    PLANNING = "planning"
    RUNNING_SCENARIO = "running_scenario"
    OBSERVING_RESULT = "observing_result"
    REFINING_BOUNDARY = "refining_boundary"
    FINDING_VIOLATION = "finding_violation"
    RUNNING_COUNTERFACTUAL = "running_counterfactual"
    CHECKING_SAFEGUARD = "checking_safeguard"
    AI_SUMMARY = "ai_summary"
    COMPLETE = "complete"
    FAILED = "failed"


#: Human labels for the live timeline. The frontend mirrors this map for its own
#: rendering, but the canonical wording lives beside the code that emits it.
EVENT_LABELS: dict[str, str] = {
    AnalysisEventKind.UNDERSTANDING_CHANGE.value: "Understanding change",
    AnalysisEventKind.MAPPING_EQUIPMENT.value: "Mapping affected equipment",
    AnalysisEventKind.PLANNING.value: "Planning investigation",
    AnalysisEventKind.RUNNING_SCENARIO.value: "Running scenario",
    AnalysisEventKind.OBSERVING_RESULT.value: "Observing result",
    AnalysisEventKind.REFINING_BOUNDARY.value: "Refining boundary",
    AnalysisEventKind.FINDING_VIOLATION.value: "Finding violation",
    AnalysisEventKind.RUNNING_COUNTERFACTUAL.value: "Running counterfactual",
    AnalysisEventKind.CHECKING_SAFEGUARD.value: "Checking safeguard",
    AnalysisEventKind.AI_SUMMARY.value: "AI explanation",
    AnalysisEventKind.COMPLETE.value: "Analysis complete",
    AnalysisEventKind.FAILED.value: "Analysis failed",
}

#: Bounded sizes for stored documents (a result is evidence, not a dump).
MAX_STORED_CASES = 400
MAX_STORED_EVENTS = 600
MAX_STORED_FAILURES = 25

#: Required language. A simulation can only speak about what it simulated.
NO_UNSAFE_DETECTED_NOTE = (
    "No unsafe condition was detected within the tested simulation scenarios."
)
UNSAFE_DETECTED_NOTE = (
    "Unsafe conditions were detected within the tested simulation scenarios; the "
    "listed failures are the evidence."
)
AI_NOT_CONFIGURED_NOTE = (
    "No AI provider is configured, so the explanation below is empty. The "
    "simulation evidence stands on its own."
)
SAFEGUARD_LANGUAGE_NOTE = (
    "Times describe the simulated response of the modelled safeguard, not the "
    "behaviour of a real plant."
)

__all__ = [
    "AI_NOT_CONFIGURED_NOTE",
    "ANALYSIS_DISCLAIMER",
    "AnalysisEventKind",
    "AnalysisKind",
    "AnalysisStatus",
    "EVENT_LABELS",
    "MAX_STORED_CASES",
    "MAX_STORED_EVENTS",
    "MAX_STORED_FAILURES",
    "NO_UNSAFE_DETECTED_NOTE",
    "SAFEGUARD_LANGUAGE_NOTE",
    "UNSAFE_DETECTED_NOTE",
]
