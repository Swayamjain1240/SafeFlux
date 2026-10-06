"""One investigation, end to end (Part 8).

The service is the only place that assembles a provider, the agent machine and the
tool layer, and it is deliberately thin so tests can replace *just* the provider
(``build_provider``) and keep every other guarantee real.

What it does with the engineer's text: sanitize it, scan it for instruction-like
content, quarantine it as data, and hand the sanitized copy to the prompt builder.
The flagged pattern ids travel with the result so a reviewer can see that an
attempt happened — the text itself is never echoed back.

What it does *not* do: decide anything. The model chooses an action, the tool layer
enforces the bounds, the simulator produces values, the safety engine produces
verdicts, and the Part 7 search produces boundaries.
"""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

from app.ai.constants import MAX_FOCUS_TEXT_CHARS, PROVIDER_NAME, AgentStopReason
from app.ai.guards import InFlightGuard
from app.ai.machine import AgentLimits, InvestigationAgent
from app.ai.provider import AiProvider, ProviderConfig, build_provider
from app.ai.security import detect_injection, log_event, sanitize_untrusted_text
from app.ai.tools import TOOL_NAMES, ToolBudget, ToolContext
from app.search import PlantProfile

logger = logging.getLogger("safeflux.ai.service")

DEFAULT_GOAL = (
    "Find the conditions under which this plant approaches or crosses its configured safety limits, "
    "and identify which variables deserve a boundary search."
)


@dataclass(frozen=True)
class GoalPreparation:
    """The engineer's text after sanitizing and scanning."""

    text: str
    flagged: bool
    patterns: tuple[str, ...]


def prepare_goal(raw: str | None) -> GoalPreparation:
    """Sanitize and scan untrusted text without ever obeying it."""
    cleaned = sanitize_untrusted_text(raw or "", limit=MAX_FOCUS_TEXT_CHARS)
    if not cleaned:
        return GoalPreparation(text=DEFAULT_GOAL, flagged=False, patterns=())
    patterns = tuple(detect_injection(cleaned))
    return GoalPreparation(text=cleaned, flagged=bool(patterns), patterns=patterns)


def plant_summary(profile: PlantProfile) -> str:
    """A short deterministic description of the plant (the only facts in the prompt)."""
    limits = profile.safety_limits
    return (
        f"plant={profile.name} ({profile.plant_id}); "
        f"feed={profile.params.feed_flow_lpm} L/min, heater={profile.params.heater_power_pct}%, "
        f"cooling={profile.params.cooling_pct}%, valve={profile.params.valve_position_pct}%, "
        f"pump_running={profile.params.pump_running}; "
        f"start temperature={profile.initial_temperature_c} C; "
        f"limits: temperature<={limits.max_temperature_c} C, pressure<={limits.max_pressure_bar} bar, "
        f"level<={limits.max_level_pct}%; "
        f"auto_shutdown={profile.safeguards.auto_shutdown_enabled}, trip_delay={profile.safeguards.trip_delay_s}s"
    )


def new_analysis_id() -> str:
    return f"an-{uuid.uuid4().hex[:12]}"


class InvestigationService:
    """Runs one bounded investigation for an owned plant."""

    def __init__(
        self,
        *,
        provider_factory=build_provider,
        guard: InFlightGuard | None = None,
        gate_on_settings: bool = True,
    ) -> None:
        """Wire one investigation service.

        ``gate_on_settings`` (default) makes the service refuse to build a provider
        unless ``NEBIUS_API_KEY``/``_BASE_URL``/``_MODEL`` are all set, which is what
        keeps Parts 1–7 working with no AI configuration at all. An injected factory
        (tests, or a future second provider) owns its own configuration decision and
        turns the gate off, so the very same code path is exercised without a key.
        """
        self._provider_factory = provider_factory
        self._gate_on_settings = gate_on_settings
        self.guard = guard or InFlightGuard()

    def provider_for(self, settings: Any) -> AiProvider:
        """The provider for these settings (tests replace the factory)."""
        return self._provider_factory(ProviderConfig.from_settings(settings))

    @property
    def provider_name(self) -> str:
        return PROVIDER_NAME

    def run(
        self,
        *,
        db: Any,
        user: Any,
        plant: Any,
        settings: Any,
        goal: GoalPreparation,
        telemetry: Any = None,
        analysis_id: str | None = None,
    ) -> dict[str, Any]:
        """Execute the investigation and return the result document as a dict.

        Ownership has already been enforced by the caller: ``plant`` is a plant the
        session user owns, and no tool can reach any other plant.
        """
        analysis = analysis_id or new_analysis_id()
        profile = PlantProfile.from_plant(plant)
        limits = AgentLimits.from_settings(settings)

        if self._gate_on_settings and not ProviderConfig.from_settings(settings).configured:
            log_event(logger, "ai.not_configured", provider=PROVIDER_NAME, scenario_id=analysis)
            return _not_configured_result(analysis, str(plant.id), limits, goal)

        ctx = ToolContext(
            db=db,
            user=user,
            plant=plant,
            settings=settings,
            telemetry=telemetry,
            budget=ToolBudget(max_simulations=limits.max_simulations),
        )
        agent = InvestigationAgent(self.provider_for(settings), limits)
        run = agent.run(
            goal=goal.text,
            plant_summary=plant_summary(profile),
            ctx=ctx,
            analysis_id=analysis,
            plant_id=str(plant.id),
            flagged_input=goal.flagged,
        )
        result = run.result.model_dump()
        result["tools_available"] = list(TOOL_NAMES)
        # Pattern ids are safe to report (they name the *kind* of attempt, never its
        # text); the machine already records them, so this only covers the case where
        # the caller's own scan found something the machine's did not.
        reported = [note for note in result.get("notes", []) if "treated as data only" in note]
        if goal.patterns and not reported:
            result["notes"] = [
                *result.get("notes", []),
                "Instruction-like text was found in the request and treated as data only: "
                + ", ".join(goal.patterns),
            ][:12]
        return result


def _not_configured_result(
    analysis_id: str,
    plant_id: str,
    limits: AgentLimits,
    goal: GoalPreparation,
) -> dict[str, Any]:
    """A safe, explicit answer when no provider is configured (Parts 1–7 keep working)."""
    return {
        "analysis_id": analysis_id,
        "plant_id": plant_id,
        "status": AgentStopReason.NOT_CONFIGURED.value,
        "focus": "",
        "provider": PROVIDER_NAME,
        "model_id": "",
        "budget": {
            "max_steps": limits.max_steps,
            "steps_used": 0,
            "max_model_calls": limits.max_model_calls,
            "model_calls_used": 0,
            "max_simulations": limits.max_simulations,
            "simulations_used": 0,
            "max_tokens": limits.max_tokens,
            "tokens_used": 0,
            "timeout_s": limits.timeout_s,
            "elapsed_s": 0.0,
            "stop_reason": AgentStopReason.NOT_CONFIGURED.value,
        },
        "evidence": [],
        "failures": [],
        "boundaries": [],
        "explanation": None,
        "trace": [{"state": "understand", "step": 0, "configured": False}],
        "notes": [
            "No AI provider is configured, so no model was contacted. The deterministic search "
            "and the simulator work without it."
        ],
        "flagged_input": goal.flagged,
        "ai_involved": False,
        "ai_limits": "",
        "tools_available": list(TOOL_NAMES),
    }


__all__ = [
    "DEFAULT_GOAL",
    "GoalPreparation",
    "InvestigationService",
    "new_analysis_id",
    "plant_summary",
    "prepare_goal",
]
