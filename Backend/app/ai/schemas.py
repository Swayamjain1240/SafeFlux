"""Strict schemas for every programmatic model interaction (Part 8, rule 6).

Nothing the model produces is used before it passes through one of these models,
and every model is ``extra="forbid"`` with bounded strings and lists:

- ``AgentDecision`` — what deserves investigation next (the only "action" surface
  the model has). ``action`` is an enum that maps to exactly one allowlisted tool,
  ``variables`` may only name allowlisted search variables, and ``arguments`` is a
  small typed block the *tool layer* re-validates against that tool's own schema.
- ``AgentExplanation`` — the closing narrative: what was found and which evidence
  ids support it. No numbers are accepted from the model here; it references
  evidence ids and may restate values, but a value it invents is never treated as
  data by SafeFlux.
- ``ToolResultRecord`` / ``InvestigationResult`` — what the backend actually ran.

Invalid output is rejected safely: a failed parse stops the investigation with
``AgentStopReason.INVALID_OUTPUT`` and the raw text is never executed, logged or
returned.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.ai.constants import (
    AGENT_SCHEMA_VERSION,
    AGENT_VERSION,
    MAX_EVIDENCE_ITEMS,
    MAX_FAILURES_REPORTED,
    MAX_MODEL_REASON_CHARS,
    MAX_MODEL_TEXT_CHARS,
    MAX_TRACE_ENTRIES,
)
from app.search.variables import SearchVariable


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class AgentAction(str, Enum):
    """The only actions the model may choose.

    Each maps to exactly one allowlisted tool (``TOOL_FOR_ACTION``). The model
    cannot invent a tool name, and it cannot reach the simulator directly.
    """

    COLLECT_CONTEXT = "collect_context"
    GET_CURRENT_STATE = "get_current_state"
    GET_SAFETY_LIMITS = "get_safety_limits"
    GET_RECENT_HISTORY = "get_recent_history"
    RUN_SIMULATION = "run_simulation"
    RUN_SCENARIO_SEARCH = "run_scenario_search"
    COMPARE_SCENARIOS = "compare_scenarios"
    GET_FAILURE_DETAILS = "get_failure_details"
    CHECK_SAFEGUARDS = "check_safeguards"
    CONCLUDE = "conclude"


#: action -> tool name. Exhaustive by construction: an action with no tool is a
#: programming error, not a runtime surprise (asserted in tests).
TOOL_FOR_ACTION: dict[AgentAction, str] = {
    AgentAction.COLLECT_CONTEXT: "get_plant_configuration",
    AgentAction.GET_CURRENT_STATE: "get_current_state",
    AgentAction.GET_SAFETY_LIMITS: "get_safety_limits",
    AgentAction.GET_RECENT_HISTORY: "get_recent_history",
    AgentAction.RUN_SIMULATION: "run_simulation",
    AgentAction.RUN_SCENARIO_SEARCH: "run_scenario_search",
    AgentAction.COMPARE_SCENARIOS: "compare_scenarios",
    AgentAction.GET_FAILURE_DETAILS: "get_failure_details",
    AgentAction.CHECK_SAFEGUARDS: "check_safeguards",
}

#: Actions that may run a simulation and therefore charge the AI budget. The
#: authoritative counter lives in the tool layer (``ToolBudget``); this set is what
#: the machine accounts for on each evidence record. ``CHECK_SAFEGUARDS`` is here
#: because testing a shutdown delay runs a scenario.
EXPENSIVE_ACTIONS: frozenset[AgentAction] = frozenset(
    {
        AgentAction.RUN_SIMULATION,
        AgentAction.RUN_SCENARIO_SEARCH,
        AgentAction.COMPARE_SCENARIOS,
        AgentAction.CHECK_SAFEGUARDS,
    }
)


class AgentDecision(_StrictModel):
    """One step of the investigation, as chosen by the model."""

    schema_version: str = Field(default=AGENT_SCHEMA_VERSION, max_length=8)
    focus: str = Field(min_length=3, max_length=MAX_MODEL_TEXT_CHARS)
    reason: str = Field(min_length=3, max_length=MAX_MODEL_REASON_CHARS)
    action: AgentAction
    variables: list[SearchVariable] = Field(default_factory=list, max_length=3)
    arguments: dict[str, Any] = Field(default_factory=dict)

    @field_validator("arguments")
    @classmethod
    def _bounded_arguments(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Reject an argument block no tool could accept anyway.

        The tool layer still validates every argument against the tool's own
        strict schema; this only stops a model from shipping an unbounded object
        into the pipeline in the first place.
        """
        if len(value) > 8:
            raise ValueError("Too many tool arguments.")
        for key in value:
            if not isinstance(key, str) or not key.isascii() or len(key) > 40:
                raise ValueError("Invalid tool argument name.")
        return value

    @property
    def tool(self) -> str | None:
        """The single tool this action is allowed to call (``None`` to conclude)."""
        return TOOL_FOR_ACTION.get(self.action)


class AgentExplanation(_StrictModel):
    """The closing narrative. Evidence-referencing only — never a computation."""

    headline: str = Field(min_length=3, max_length=MAX_MODEL_TEXT_CHARS)
    explanation: str = Field(min_length=3, max_length=MAX_MODEL_REASON_CHARS)
    evidence_ids: list[str] = Field(default_factory=list, max_length=MAX_EVIDENCE_ITEMS)
    next_variables: list[SearchVariable] = Field(default_factory=list, max_length=3)

    @field_validator("evidence_ids")
    @classmethod
    def _bounded_ids(cls, value: list[str]) -> list[str]:
        for item in value:
            if not item or len(item) > 40 or not item.replace("-", "").replace("_", "").isalnum():
                raise ValueError("Invalid evidence id.")
        return value


class ToolResultRecord(_StrictModel):
    """What one allowlisted tool returned, bounded and already sanitized."""

    id: str = Field(max_length=40)
    tool: str = Field(max_length=60)
    step: int = Field(ge=0)
    ok: bool
    #: Safe, curated failure reason when ``ok`` is False (never a traceback).
    error: str | None = Field(default=None, max_length=200)
    #: Bounded, JSON-safe payload for the model to read.
    payload: dict[str, Any] = Field(default_factory=dict)
    latency_ms: int = Field(ge=0)
    simulations: int = Field(default=0, ge=0)

    @field_validator("payload")
    @classmethod
    def _bounded_payload(cls, value: dict[str, Any]) -> dict[str, Any]:
        if len(value) > 40:
            raise ValueError("Tool payload has too many keys.")
        return value


class InvestigationBudgetState(_StrictModel):
    """The budget counters as reported to the client (and to the model, trimmed)."""

    max_steps: int = Field(ge=1)
    steps_used: int = Field(ge=0)
    max_model_calls: int = Field(ge=1)
    model_calls_used: int = Field(ge=0)
    max_simulations: int = Field(ge=1)
    simulations_used: int = Field(ge=0)
    max_tokens: int = Field(ge=1)
    tokens_used: int = Field(ge=0)
    timeout_s: float = Field(gt=0)
    elapsed_s: float = Field(ge=0)
    stop_reason: str | None = None


class InvestigationResult(_StrictModel):
    """The complete, reproducible investigation document."""

    analysis_id: str = Field(max_length=64)
    plant_id: str = Field(max_length=64)
    status: str = Field(max_length=32)
    focus: str = Field(default="", max_length=MAX_MODEL_TEXT_CHARS)
    provider: str = Field(max_length=60)
    model_id: str = Field(max_length=120)
    agent_version: str = Field(default=AGENT_VERSION, max_length=16)
    schema_version: str = Field(default=AGENT_SCHEMA_VERSION, max_length=8)
    budget: InvestigationBudgetState
    evidence: list[ToolResultRecord] = Field(default_factory=list, max_length=MAX_EVIDENCE_ITEMS)
    failures: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_FAILURES_REPORTED)
    boundaries: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_EVIDENCE_ITEMS)
    explanation: AgentExplanation | None = None
    trace: list[dict[str, Any]] = Field(default_factory=list, max_length=MAX_TRACE_ENTRIES)
    notes: list[str] = Field(default_factory=list, max_length=12)
    flagged_input: bool = False
    ai_involved: bool = True
    #: The AI never owns truth: this states it in the document itself.
    ai_limits: str = ""
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds"),
        max_length=40,
    )


__all__ = [
    "EXPENSIVE_ACTIONS",
    "TOOL_FOR_ACTION",
    "AgentAction",
    "AgentDecision",
    "AgentExplanation",
    "InvestigationBudgetState",
    "InvestigationResult",
    "ToolResultRecord",
]
