"""Hard bounds, versions and vocabulary for the hybrid investigation agent (Part 8).

The agent is the *only* place in SafeFlux where a model is consulted, and the
model is never trusted with a number, a limit or a permission. This module pins
the budget vocabulary the whole package enforces:

- ``max_steps`` — investigation cycles (one decision + one tool call each),
- ``max_model_calls`` — every provider round trip counts, including the final
  explanation,
- ``max_simulations`` — charged by the *tool layer* before any scenario runs, so
  the bound holds no matter what the model asks for,
- ``max_tokens`` — cumulative provider-reported tokens (when the provider reports
  them), a soft ceiling that stops the loop cleanly,
- ``timeout_s`` — wall-clock ceiling for one investigation.

Hitting a bound is a *reported outcome* (``AgentStopReason``), never an exception
a caller has to interpret, and never a silent truncation: a partial
investigation that says it is partial is usable evidence, one that pretends to be
complete is a hazard.

AI never determines physical or threshold truth. In this package the model may
only choose *what deserves investigation* and explain the evidence that the
deterministic Part 4 simulator, the Part 5 safety engine and the Part 7 search
produced.
"""

from __future__ import annotations

from enum import Enum

#: Bump when the agent loop or its prompt contract changes. Recorded in every
#: investigation result so two runs with different agent versions are not
#: silently compared.
AGENT_VERSION = "0.1.0"
#: Bump when the decision schema changes shape (older decisions are not valid).
AGENT_SCHEMA_VERSION = "1"

# --- provider / model handling ------------------------------------------------
PROVIDER_NAME = "nebius-token-factory"

# --- hard bounds (module defaults; Settings may only tighten them) ------------
DEFAULT_MAX_STEPS = 6
MAX_STEPS_CEILING = 12
DEFAULT_MAX_MODEL_CALLS = 8
MAX_MODEL_CALLS_CEILING = 16
DEFAULT_MAX_SIMULATIONS = 40
MAX_SIMULATIONS_CEILING = 200
DEFAULT_MAX_TOKENS = 20000
MAX_TOKENS_CEILING = 200000
DEFAULT_TIMEOUT_S = 120.0
MIN_TIMEOUT_S = 5.0
MAX_TIMEOUT_S_CEILING = 600.0

# --- provider call shape ------------------------------------------------------
DEFAULT_MAX_OUTPUT_TOKENS = 700
MAX_OUTPUT_TOKENS_CEILING = 4000
DEFAULT_TEMPERATURE = 0.0
PROVIDER_TIMEOUT_S = 45.0
#: One bounded retry for transient categories only (timeout/connection/5xx).
PROVIDER_MAX_ATTEMPTS = 2

# --- untrusted text -----------------------------------------------------------
#: Longest engineering-change text accepted from a user (rule 6 / rule 25).
MAX_FOCUS_TEXT_CHARS = 2000
#: Longest free-text field the model may return.
MAX_MODEL_TEXT_CHARS = 600
#: Longest reason/explanation the model may return.
MAX_MODEL_REASON_CHARS = 1200

# --- evidence bounds (what a tool may hand back to the model) -----------------
MAX_EVIDENCE_ITEMS = 12
MAX_HISTORY_FRAMES = 120
MAX_FAILURES_REPORTED = 10
MAX_TRACE_ENTRIES = 200


class AgentState(str, Enum):
    """Explicit, finite states — there is no free-running agent here."""

    UNDERSTAND = "understand"
    IDENTIFY = "identify"
    CHOOSE = "choose"
    CALL_TOOL = "call_tool"
    OBSERVE = "observe"
    DECIDE = "decide"
    EXPLAIN = "explain"
    DONE = "done"


class AgentStopReason(str, Enum):
    """Why the loop stopped. ``COMPLETE`` is the only happy path."""

    COMPLETE = "complete"
    MAX_STEPS = "max_steps"
    MAX_MODEL_CALLS = "max_model_calls"
    MAX_SIMULATIONS = "max_simulations"
    MAX_TOKENS = "max_tokens"
    TIMEOUT = "timeout"
    INVALID_OUTPUT = "invalid_output"
    TOOL_REJECTED = "tool_rejected"
    PROVIDER_ERROR = "provider_error"
    NOT_CONFIGURED = "not_configured"


class ProviderErrorCategory(str, Enum):
    """Safe, loggable error vocabulary — never the provider's raw body."""

    NOT_CONFIGURED = "not_configured"
    AUTH = "auth"
    RATE_LIMIT = "rate_limit"
    TIMEOUT = "timeout"
    CONNECTION = "connection"
    SERVER = "server"
    INVALID_RESPONSE = "invalid_response"


class GuardVerdict(str, Enum):
    """What the untrusted-input guard decided about a user's text."""

    ACCEPTED = "accepted"
    #: Instruction-like content found: it is quarantined as *data*, never as
    #: instructions, and the attempt is recorded in the result.
    INJECTION_FLAGGED = "injection_flagged"
    REJECTED = "rejected"


#: Fields that may appear in an agent log line. Anything else is dropped before
#: logging, so a secret cannot reach a log file by accident (rule 1 / rule 18).
SAFE_LOG_FIELDS: frozenset[str] = frozenset(
    {
        "provider",
        "model_id",
        "analysis_id",
        "scenario_id",
        "plant_id",
        "user_id",
        "state",
        "action",
        "tool",
        "step",
        "model_calls",
        "simulations",
        "tokens",
        "latency_ms",
        "error_category",
        "stop_reason",
        "status",
        "attempts",
        "items",
        "count",
        "duration_s",
        "variables",
    }
)

#: Never logged, never returned to a client, never sent to the provider.
FORBIDDEN_LOG_FIELDS: frozenset[str] = frozenset(
    {
        "api_key",
        "authorization",
        "cookie",
        "password",
        "password_hash",
        "jwt",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "session",
        "prompt",
        "system_prompt",
        "raw_response",
        "body",
    }
)

AI_DISCLAIMER = (
    "The model chose what to investigate and explained the evidence; it did not "
    "compute any process value, limit or verdict. Every number here comes from the "
    "deterministic simulator, the safety engine and the scenario search."
)

PHYSICAL_TRUTH_NOTE = (
    "SafeFlux simulates a lumped model. Nothing in this result is a statement "
    "about a real plant, and nothing here is certified industrial safety software."
)

__all__ = [
    "AGENT_SCHEMA_VERSION",
    "AGENT_VERSION",
    "AI_DISCLAIMER",
    "DEFAULT_MAX_MODEL_CALLS",
    "DEFAULT_MAX_OUTPUT_TOKENS",
    "DEFAULT_MAX_SIMULATIONS",
    "DEFAULT_MAX_STEPS",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_TEMPERATURE",
    "DEFAULT_TIMEOUT_S",
    "FORBIDDEN_LOG_FIELDS",
    "MAX_EVIDENCE_ITEMS",
    "MAX_FAILURES_REPORTED",
    "MAX_FOCUS_TEXT_CHARS",
    "MAX_HISTORY_FRAMES",
    "MAX_MODEL_CALLS_CEILING",
    "MAX_MODEL_REASON_CHARS",
    "MAX_MODEL_TEXT_CHARS",
    "MAX_OUTPUT_TOKENS_CEILING",
    "MAX_SIMULATIONS_CEILING",
    "MAX_STEPS_CEILING",
    "MAX_TIMEOUT_S_CEILING",
    "MAX_TOKENS_CEILING",
    "MAX_TRACE_ENTRIES",
    "MIN_TIMEOUT_S",
    "PHYSICAL_TRUTH_NOTE",
    "PROVIDER_MAX_ATTEMPTS",
    "PROVIDER_NAME",
    "PROVIDER_TIMEOUT_S",
    "SAFE_LOG_FIELDS",
    "AgentState",
    "AgentStopReason",
    "GuardVerdict",
    "ProviderErrorCategory",
]
