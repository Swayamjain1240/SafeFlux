"""Shared fakes for the Part 8 tests.

No ORM, no HTTP, no network: a plant *snapshot* (attribute access only, which is
all ``PlantProfile.from_plant`` needs), a settings stub and a scripted provider
whose replies are queued in advance. That keeps the agent tests fully
deterministic — the same script always produces the same investigation.
"""

from __future__ import annotations

import json
import types

from app.ai.provider import ProviderError, ProviderResponse
from app.ai.tools import ToolBudget, ToolContext


def fake_plant(**overrides):
    """A plant snapshot with the baseline configuration used across the suite."""
    plant = types.SimpleNamespace(
        id="11111111-1111-1111-1111-111111111111",
        name="Reactor Train A",
        description="Baseline MVP process",
        location="Line 1",
        owner_id="user-1",
        config=types.SimpleNamespace(
            feed_flow_lpm=120.0,
            heater_power_pct=60.0,
            cooling_pct=90.0,
            valve_position_pct=55.0,
            shutdown_delay_s=5.0,
        ),
        state=types.SimpleNamespace(
            pump_running=True, temperature_c=80.0, pressure_bar=4.0, level_pct=45.0
        ),
        safety_limits=types.SimpleNamespace(
            max_temperature_c=150.0, max_pressure_bar=10.0, max_level_pct=90.0
        ),
        safeguards=types.SimpleNamespace(
            auto_shutdown_enabled=True,
            high_temperature_trip=True,
            high_pressure_trip=True,
            high_level_trip=True,
            trip_delay_s=30.0,
        ),
    )
    for key, value in overrides.items():
        setattr(plant, key, value)
    return plant


def fake_settings(**overrides):
    """Settings stub with every field the AI layer and its tools read."""
    settings = types.SimpleNamespace(
        SIM_MAX_DURATION_S=3600.0,
        SIM_MIN_TIME_STEP_S=0.05,
        SIM_MAX_SAMPLES=20000,
        SAFETY_NEAR_LIMIT_FRACTION=0.9,
        SEARCH_MAX_SCENARIOS=150,
        SEARCH_MAX_COMBINATIONS=36,
        SEARCH_MAX_REFINEMENT_DEPTH=6,
        SEARCH_TIMEOUT_SECONDS=90.0,
        # Provider variables: present here so a test can prove no secret ever
        # reaches a prompt (the AI layer never reads them itself).
        NEBIUS_API_KEY=None,
        NEBIUS_BASE_URL=None,
        NEBIUS_MODEL=None,
    )
    for key, value in overrides.items():
        setattr(settings, key, value)
    return settings


def make_ctx(budget: int = 40, settings=None, plant=None, telemetry=None) -> ToolContext:
    return ToolContext(
        db=None,
        user=types.SimpleNamespace(id="user-1"),
        plant=plant or fake_plant(),
        settings=settings or fake_settings(),
        telemetry=telemetry,
        budget=ToolBudget(max_simulations=budget),
    )


def decision(action: str, *, arguments: dict | None = None, variables: list[str] | None = None,
             focus: str = "cooling degradation", reason: str = "ev-1 shows a limit was approached") -> str:
    """One valid ``AgentDecision`` as the model would emit it (JSON text)."""
    return json.dumps(
        {
            "schema_version": "1",
            "focus": focus,
            "reason": reason,
            "action": action,
            "variables": variables or [],
            "arguments": arguments or {},
        }
    )


def conclusion(headline: str = "Cooling boundary found", explanation: str = "ev-1 found one violation.",
               evidence_ids: list[str] | None = None) -> str:
    return json.dumps(
        {
            "headline": headline,
            "explanation": explanation,
            "evidence_ids": evidence_ids if evidence_ids is not None else ["ev-1"],
            "next_variables": [],
        }
    )


class ScriptedProvider:
    """An ``AiProvider`` that replays a script and records every prompt."""

    name = "scripted-provider"

    def __init__(
        self,
        replies: list[str],
        *,
        model_id: str = "test/nemotron-3-nano",
        tokens: int = 100,
        error: ProviderError | None = None,
    ) -> None:
        self._replies = list(replies)
        self._error = error
        self.model_id = model_id
        self._tokens = tokens
        self.calls: list[dict] = []

    def complete(self, *, system: str, messages: list[dict[str, str]], max_output_tokens=None):
        self.calls.append({"system": system, "messages": messages, "max_output_tokens": max_output_tokens})
        if self._error is not None:
            raise self._error
        text = (
            self._replies.pop(0)
            if self._replies
            else conclusion(headline="No further actions", explanation="the script ended")
        )
        return ProviderResponse(
            text=text,
            model=self.model_id,
            latency_ms=4,
            attempts=1,
            prompt_tokens=self._tokens // 2,
            completion_tokens=self._tokens - self._tokens // 2,
            finish_reason="stop",
        )

    @property
    def prompts(self) -> str:
        """Every prompt text this provider was given, concatenated."""
        return "\n".join(
            message["content"] for call in self.calls for message in call["messages"]
        )

    @property
    def system_prompts(self) -> str:
        return "\n".join(call["system"] for call in self.calls)
