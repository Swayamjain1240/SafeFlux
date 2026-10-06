"""The explicit agent state machine (Part 8).

No framework, no free-running loop: a small finite machine whose every transition
is visible in the result's ``trace``. LangGraph was considered and deliberately
not used — the graph here is six states with hard bounds, so a hand-written
machine is simpler, easier to test, and adds no dependency.

    UNDERSTAND → IDENTIFY → CHOOSE → CALL_TOOL → OBSERVE → DECIDE → … → EXPLAIN → DONE

What the model may do: choose the next ``AgentDecision`` (an allowlisted action)
and, at the end, produce an ``AgentExplanation``. That is all.

What the machine does independently:

- **bounds every loop**: steps, model calls, tokens, wall-clock timeout, and the
  simulation budget the *tool layer* charges,
- **validates every model output** before use (a parse failure stops the run with
  ``INVALID_OUTPUT`` instead of being retried forever),
- **records every tool call** (including rejected ones) as evidence, so a refusal
  is visible rather than silent,
- **stops cleanly**: hitting a bound is a reported ``AgentStopReason``, never an
  exception and never a silent truncation.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from app.ai.constants import (
    AGENT_VERSION,
    DEFAULT_MAX_MODEL_CALLS,
    DEFAULT_MAX_OUTPUT_TOKENS,
    DEFAULT_MAX_SIMULATIONS,
    DEFAULT_MAX_STEPS,
    DEFAULT_MAX_TOKENS,
    DEFAULT_TIMEOUT_S,
    MAX_MODEL_CALLS_CEILING,
    MAX_OUTPUT_TOKENS_CEILING,
    MAX_SIMULATIONS_CEILING,
    MAX_STEPS_CEILING,
    MAX_TIMEOUT_S_CEILING,
    MAX_TOKENS_CEILING,
    MAX_TRACE_ENTRIES,
    MIN_TIMEOUT_S,
    PROVIDER_NAME,
    AgentState,
    AgentStopReason,
    ProviderErrorCategory,
)
from app.ai.parsing import parse_decision, parse_explanation
from app.ai.prompts import decision_prompt, explanation_prompt, system_prompt
from app.ai.provider import AiProvider, ProviderError
from app.ai.schemas import (
    EXPENSIVE_ACTIONS,
    AgentAction,
    InvestigationBudgetState,
    InvestigationResult,
    ToolResultRecord,
)
from app.ai.security import ai_limits_statement, detect_injection, log_event
from app.ai.tools import ToolContext, call_tool

logger = logging.getLogger("safeflux.ai.agent")

#: Two rejected calls in a row means the model is not adapting: stop rather than
#: let it burn the remaining budget on the same mistake.
MAX_CONSECUTIVE_REJECTIONS = 2

#: Tools whose payload is worth opening up in the evidence summary.
_SUMMARY_KEYS = ("status", "counts", "boundary", "worst_status", "failure_count")


def _int_setting(settings: Any, name: str, default: int, ceiling: int) -> int:
    try:
        value = int(getattr(settings, name, default))
    except (TypeError, ValueError):
        return default
    return max(1, min(value, ceiling))


def _float_setting(settings: Any, name: str, default: float, low: float, high: float) -> float:
    try:
        value = float(getattr(settings, name, default))
    except (TypeError, ValueError):
        return default
    if value != value:  # NaN
        return default
    return min(max(value, low), high)


@dataclass(frozen=True)
class AgentLimits:
    """Resolved hard bounds for one investigation (Settings may only tighten)."""

    max_steps: int = DEFAULT_MAX_STEPS
    max_model_calls: int = DEFAULT_MAX_MODEL_CALLS
    max_simulations: int = DEFAULT_MAX_SIMULATIONS
    max_tokens: int = DEFAULT_MAX_TOKENS
    timeout_s: float = DEFAULT_TIMEOUT_S
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS

    @classmethod
    def from_settings(cls, settings: Any) -> "AgentLimits":
        return cls(
            max_steps=_int_setting(settings, "AI_MAX_STEPS", DEFAULT_MAX_STEPS, MAX_STEPS_CEILING),
            max_model_calls=_int_setting(
                settings, "AI_MAX_MODEL_CALLS", DEFAULT_MAX_MODEL_CALLS, MAX_MODEL_CALLS_CEILING
            ),
            max_simulations=_int_setting(
                settings, "AI_MAX_SIMULATIONS", DEFAULT_MAX_SIMULATIONS, MAX_SIMULATIONS_CEILING
            ),
            max_tokens=_int_setting(settings, "AI_MAX_TOKENS", DEFAULT_MAX_TOKENS, MAX_TOKENS_CEILING),
            timeout_s=_float_setting(
                settings, "AI_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_S, MIN_TIMEOUT_S, MAX_TIMEOUT_S_CEILING
            ),
            max_output_tokens=_int_setting(
                settings,
                "AI_MAX_OUTPUT_TOKENS",
                DEFAULT_MAX_OUTPUT_TOKENS,
                MAX_OUTPUT_TOKENS_CEILING,
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_steps": self.max_steps,
            "max_model_calls": self.max_model_calls,
            "max_simulations": self.max_simulations,
            "max_tokens": self.max_tokens,
            "timeout_s": self.timeout_s,
            "max_output_tokens": self.max_output_tokens,
        }


def _evidence_row(record: ToolResultRecord) -> dict[str, Any]:
    """The bounded view of one tool result that the model is allowed to read."""
    summary: dict[str, Any] = {}
    for key in _SUMMARY_KEYS:
        if key in record.payload:
            summary[key] = record.payload[key]
    if not summary:
        summary = {"payload": json.dumps(record.payload, default=str)[:300]}
    return {
        "id": record.id,
        "tool": record.tool,
        "status": "ok" if record.ok else f"rejected({record.error})",
        "summary": json.dumps(summary, default=str)[:400],
    }


@dataclass
class AgentRun:
    """Everything one investigation produced."""

    result: InvestigationResult
    trace: list[dict[str, Any]] = field(default_factory=list)


class InvestigationAgent:
    """Runs one bounded investigation. Deterministic given a deterministic provider."""

    def __init__(
        self,
        provider: AiProvider,
        limits: AgentLimits,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._provider = provider
        self._limits = limits
        self._clock = clock

    # ------------------------------------------------------------------ utils

    def _remaining(self, *, steps: int, model_calls: int, budget_simulations: int) -> dict[str, int]:
        return {
            "steps": max(0, self._limits.max_steps - steps),
            "model_calls": max(0, self._limits.max_model_calls - model_calls),
            "simulations": budget_simulations,
        }

    def _model_call(
        self,
        *,
        system: str,
        messages: list[dict[str, str]],
        model_calls: int,
        started: float,
    ) -> tuple[str | None, int, int, AgentStopReason | None]:
        """One provider round trip, with the budget checked *before* it happens."""
        if model_calls >= self._limits.max_model_calls:
            return None, model_calls, 0, AgentStopReason.MAX_MODEL_CALLS
        if (self._clock() - started) >= self._limits.timeout_s:
            return None, model_calls, 0, AgentStopReason.TIMEOUT

        call_started = self._clock()
        try:
            response = self._provider.complete(
                system=system,
                messages=messages,
                max_output_tokens=self._limits.max_output_tokens,
            )
        except ProviderError as exc:
            category = exc.category.value
            if exc.category is ProviderErrorCategory.NOT_CONFIGURED:
                log_event(logger, "ai.provider_not_configured", provider=PROVIDER_NAME)
                return None, model_calls + 1, 0, AgentStopReason.NOT_CONFIGURED
            log_event(
                logger,
                "ai.provider_error",
                model_id=getattr(self._provider, "model_id", ""),
                error_category=category,
            )
            return None, model_calls + 1, 0, AgentStopReason.PROVIDER_ERROR
        except Exception:  # noqa: BLE001 - an unexpected provider bug must not crash the request
            logger.exception("AI provider raised unexpectedly")
            return None, model_calls + 1, 0, AgentStopReason.PROVIDER_ERROR

        log_event(
            logger,
            "ai.model_call",
            model_id=response.model,
            latency_ms=int((self._clock() - call_started) * 1000),
            tokens=response.tokens,
            attempts=response.attempts,
        )
        return response.text, model_calls + 1, response.tokens, None

    # -------------------------------------------------------------------- run

    def run(
        self,
        *,
        goal: str,
        plant_summary: str,
        ctx: ToolContext,
        analysis_id: str,
        plant_id: str,
        flagged_input: bool = False,
    ) -> AgentRun:
        """Run the loop until the model concludes or a hard bound stops it."""
        limits = self._limits
        system = system_prompt()
        started = self._clock()
        state = AgentState.UNDERSTAND

        # Defence in depth: the machine scans the goal itself rather than trusting
        # the caller to have done it. Detected ids are recorded; the text is never
        # echoed back and is only ever interpolated inside the data block.
        injection_patterns = detect_injection(goal)
        flagged = bool(flagged_input or injection_patterns)

        trace: list[dict[str, Any]] = []
        evidence: list[ToolResultRecord] = []
        notes: list[str] = []

        steps = 0
        model_calls = 0
        tokens = 0
        consecutive_rejections = 0
        stop_reason: AgentStopReason | None = None
        focus = ""
        decision_history: list[str] = []

        def trace_state(next_state: AgentState, **detail: Any) -> None:
            nonlocal state
            state = next_state
            if len(trace) < MAX_TRACE_ENTRIES:
                trace.append({"state": next_state.value, "step": steps, **detail})

        trace_state(AgentState.UNDERSTAND, flag=flagged)
        if injection_patterns:
            notes.append(
                "Instruction-like text was found in the request and treated as data only: "
                + ", ".join(injection_patterns)
            )

        while True:
            remaining = self._remaining(
                steps=steps, model_calls=model_calls, budget_simulations=ctx.budget.remaining
            )

            if steps >= limits.max_steps:
                stop_reason = AgentStopReason.MAX_STEPS
                break
            if model_calls >= limits.max_model_calls:
                stop_reason = AgentStopReason.MAX_MODEL_CALLS
                break
            if tokens >= limits.max_tokens:
                stop_reason = AgentStopReason.MAX_TOKENS
                break
            if ctx.budget.remaining <= 0:
                stop_reason = AgentStopReason.MAX_SIMULATIONS
                break
            if (self._clock() - started) >= limits.timeout_s:
                stop_reason = AgentStopReason.TIMEOUT
                break

            # IDENTIFY → CHOOSE: ask the model what deserves attention, with the
            # remaining budget and the evidence so far in front of it.
            trace_state(AgentState.IDENTIFY)
            trace_state(AgentState.CHOOSE)
            text, model_calls, used_tokens, stop = self._model_call(
                system=system,
                messages=[
                    {
                        "role": "user",
                        "content": decision_prompt(
                            goal=goal,
                            plant_summary=plant_summary,
                            evidence=[_evidence_row(record) for record in evidence],
                            remaining=remaining,
                            previous_actions=decision_history[-8:],
                        ),
                    }
                ],
                model_calls=model_calls,
                started=started,
            )
            tokens += used_tokens
            if stop is not None:
                stop_reason = stop
                break
            if text is None:
                stop_reason = AgentStopReason.PROVIDER_ERROR
                break

            decision, error = parse_decision(text)
            if decision is None:
                notes.append(
                    "The model's answer was not a valid decision object, so the investigation stopped "
                    "instead of guessing."
                )
                log_event(
                    logger,
                    "ai.invalid_output",
                    model_id=getattr(self._provider, "model_id", ""),
                    error_category=str(error)[:80],
                )
                stop_reason = AgentStopReason.INVALID_OUTPUT
                break

            focus = decision.focus
            trace_state(
                AgentState.DECIDE,
                action=decision.action.value,
                tool=decision.tool,
                variables=[variable.value for variable in decision.variables],
            )
            decision_history.append(f"{decision.action.value}({decision.tool or 'none'})")

            if decision.action is AgentAction.CONCLUDE:
                trace_state(AgentState.EXPLAIN)
                stop_reason = AgentStopReason.COMPLETE
                break

            if decision.tool is None:  # pragma: no cover - enum mapping is exhaustive
                stop_reason = AgentStopReason.INVALID_OUTPUT
                break

            # CALL_TOOL: the tool layer re-validates everything the model asked for.
            trace_state(AgentState.CALL_TOOL, tool=decision.tool, step=steps + 1)
            ok, payload, error, latency_ms = call_tool(decision.tool, decision.arguments, ctx)
            steps += 1
            record = ToolResultRecord(
                id=f"ev-{steps}",
                tool=decision.tool,
                step=steps,
                ok=ok,
                error=error,
                payload=payload if ok else {},
                latency_ms=latency_ms,
                simulations=1 if decision.action in EXPENSIVE_ACTIONS else 0,
            )
            evidence.append(record)

            if ok:
                consecutive_rejections = 0
                log_event(
                    logger,
                    "ai.tool_call",
                    tool=decision.tool,
                    step=steps,
                    latency_ms=latency_ms,
                    items=len(payload),
                    scenario_id=str(analysis_id),
                )
            else:
                consecutive_rejections += 1
                notes.append(f"Tool call refused by the safety layer: {decision.tool} ({error}).")
                log_event(
                    logger,
                    "ai.tool_rejected",
                    tool=decision.tool,
                    step=steps,
                    error_category=str(error)[:60],
                    scenario_id=str(analysis_id),
                )
                if consecutive_rejections >= MAX_CONSECUTIVE_REJECTIONS:
                    stop_reason = AgentStopReason.TOOL_REJECTED
                    break

            trace_state(AgentState.OBSERVE, tool=decision.tool, ok=ok)

        # EXPLAIN: one final call for the narrative, only if it fits the budget.
        explanation = None
        if stop_reason in (AgentStopReason.COMPLETE, AgentStopReason.MAX_STEPS) or stop_reason is None:
            trace_state(AgentState.EXPLAIN)
            text, model_calls, used_tokens, stop = self._model_call(
                system=system,
                messages=[
                    {
                        "role": "user",
                        "content": explanation_prompt(
                            goal=goal,
                            evidence=[_evidence_row(record) for record in evidence],
                            stop_reason=(stop_reason or AgentStopReason.COMPLETE).value,
                        ),
                    }
                ],
                model_calls=model_calls,
                started=started,
            )
            tokens += used_tokens
            if text is not None:
                parsed, error = parse_explanation(text)
                if parsed is None:
                    notes.append("The closing explanation did not validate; the evidence stands on its own.")
                    log_event(
                        logger,
                        "ai.invalid_output",
                        model_id=getattr(self._provider, "model_id", ""),
                        error_category=str(error)[:80],
                    )
                else:
                    explanation = parsed
            elif stop is not None and stop_reason is None:
                stop_reason = stop

        if stop_reason is None:
            stop_reason = AgentStopReason.COMPLETE

        elapsed = round(self._clock() - started, 3)
        last_search = ctx.artifacts.get("last_search")
        # The terminal state is recorded *before* the document is built: Pydantic
        # validates list fields into new lists, so a later append would never appear
        # in the result's trace.
        trace_state(AgentState.DONE, stop_reason=stop_reason.value)
        result = InvestigationResult(
            analysis_id=analysis_id,
            plant_id=plant_id,
            status="complete" if stop_reason is AgentStopReason.COMPLETE else stop_reason.value,
            focus=focus,
            provider=PROVIDER_NAME,
            model_id=getattr(self._provider, "model_id", ""),
            agent_version=AGENT_VERSION,
            budget=InvestigationBudgetState(
                max_steps=limits.max_steps,
                steps_used=steps,
                max_model_calls=limits.max_model_calls,
                model_calls_used=model_calls,
                max_simulations=limits.max_simulations,
                simulations_used=ctx.budget.used,
                max_tokens=limits.max_tokens,
                tokens_used=tokens,
                timeout_s=limits.timeout_s,
                elapsed_s=elapsed,
                stop_reason=stop_reason.value,
            ),
            evidence=evidence,
            failures=[_bounded_case(case) for case in (last_search.failures[:10] if last_search else [])],
            boundaries=[_bounded_boundary(row) for row in (last_search.boundaries[:6] if last_search else [])],
            explanation=explanation,
            trace=trace,
            notes=notes[:12],
            flagged_input=flagged,
            ai_involved=True,
            ai_limits=ai_limits_statement(),
        )
        log_event(
            logger,
            "ai.investigation",
            status=result.status,
            stop_reason=stop_reason.value,
            steps=steps,
            model_calls=model_calls,
            simulations=ctx.budget.used,
            tokens=tokens,
            duration_s=elapsed,
            scenario_id=str(analysis_id),
        )
        return AgentRun(result=result, trace=trace)


def _bounded_case(case: dict[str, Any]) -> dict[str, Any]:
    finding = case.get("worst_finding") or {}
    return {
        "key": str(case.get("key", ""))[:120],
        "status": str(case.get("status", "")),
        "values": {str(name): float(value) for name, value in (case.get("values") or {}).items()},
        "peaks": case.get("peaks") or {},
        "shutdown_at_s": case.get("shutdown_at_s"),
        "message": str(finding.get("message", ""))[:200],
    }


def _bounded_boundary(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "variable": row.get("variable"),
        "last_safe": row.get("last_safe"),
        "first_unsafe": row.get("first_unsafe"),
        "boundary_estimate": row.get("boundary_estimate"),
        "uncertainty": row.get("uncertainty"),
        "monotonicity": row.get("monotonicity"),
        "method": row.get("method"),
        "refined": row.get("refined"),
    }


__all__ = ["AgentLimits", "AgentRun", "InvestigationAgent", "MAX_CONSECUTIVE_REJECTIONS"]
