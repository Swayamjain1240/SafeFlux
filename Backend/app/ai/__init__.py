"""Hybrid SafeFlux investigation agent (Part 8).

    AI decides what deserves investigation
    → deterministic search / simulator produces values
    → safety engine produces verdicts
    → the engineer decides what it means

This is the only package in SafeFlux that contacts an external provider. It is
built so that removing it would leave Parts 1–7 working exactly as they do now:
no other module imports from ``app.ai``, and the provider is optional
configuration rather than a startup requirement.

The three guarantees this package exists to uphold:

- **The model cannot act.** It names one allowlisted action; the tool layer
  re-validates every argument and enforces ownership, bounds and cost by itself.
  There is no shell, no ``eval``/``exec``, no file access, no SQL and no secrets.
- **The model cannot decide truth.** It never computes a value, a limit or a
  verdict; those come from the Part 4 simulator, the Part 5 safety engine and the
  Part 7 search. The result says so in ``ai_limits``.
- **The loop cannot run away.** Steps, model calls, simulations, tokens and time
  are hard-bounded, and hitting a bound is a reported stop reason.
"""

from __future__ import annotations

from app.ai.constants import (
    AGENT_SCHEMA_VERSION,
    AGENT_VERSION,
    AI_DISCLAIMER,
    PHYSICAL_TRUTH_NOTE,
    PROVIDER_NAME,
    AgentState,
    AgentStopReason,
    ProviderErrorCategory,
)
from app.ai.guards import DuplicateRunError, InFlightGuard
from app.ai.machine import AgentLimits, AgentRun, InvestigationAgent
from app.ai.provider import (
    AiProvider,
    NebiusProvider,
    ProviderConfig,
    ProviderError,
    ProviderResponse,
    build_provider,
    validate_base_url,
)
from app.ai.schemas import (
    EXPENSIVE_ACTIONS,
    TOOL_FOR_ACTION,
    AgentAction,
    AgentDecision,
    AgentExplanation,
    InvestigationBudgetState,
    InvestigationResult,
    ToolResultRecord,
)
from app.ai.service import (
    DEFAULT_GOAL,
    GoalPreparation,
    InvestigationService,
    new_analysis_id,
    plant_summary,
    prepare_goal,
)
from app.ai.tools import (
    TOOLS,
    TOOL_NAMES,
    ToolBudget,
    ToolContext,
    ToolRejected,
    call_tool,
    tool_catalog,
)

__all__ = [
    "AGENT_SCHEMA_VERSION",
    "AGENT_VERSION",
    "AI_DISCLAIMER",
    "DEFAULT_GOAL",
    "EXPENSIVE_ACTIONS",
    "PHYSICAL_TRUTH_NOTE",
    "PROVIDER_NAME",
    "TOOLS",
    "TOOL_FOR_ACTION",
    "TOOL_NAMES",
    "AgentAction",
    "AgentDecision",
    "AgentExplanation",
    "AgentLimits",
    "AgentRun",
    "AgentState",
    "AgentStopReason",
    "AiProvider",
    "DuplicateRunError",
    "GoalPreparation",
    "InFlightGuard",
    "InvestigationAgent",
    "InvestigationBudgetState",
    "InvestigationResult",
    "InvestigationService",
    "NebiusProvider",
    "ProviderConfig",
    "ProviderError",
    "ProviderErrorCategory",
    "ProviderResponse",
    "ToolBudget",
    "ToolContext",
    "ToolRejected",
    "ToolResultRecord",
    "build_provider",
    "call_tool",
    "new_analysis_id",
    "plant_summary",
    "prepare_goal",
    "tool_catalog",
    "validate_base_url",
]
