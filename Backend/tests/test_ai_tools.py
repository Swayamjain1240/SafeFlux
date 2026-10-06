"""Allowlisted tool layer coverage (Part 8, rules 5/6/8/23).

These are the tests that prove the AI layer's security is *not* delegated to the
model:

- every action maps to exactly one allowlisted tool, and no tool takes an owner or
  plant id, so a cross-user investigation is impossible by construction,
- invented arguments (``owner_id``, ``shell``, …) are rejected, not ignored,
- the simulation budget is charged by the tool layer, so "max simulations" holds
  even if the model asks for more,
- the tools really do run the Part 4 simulator and the Part 7 search: the seeded
  unsafe region is discovered through this path too,
- payloads are bounded and redacted before the model ever reads them.
"""

from __future__ import annotations

import types

import pytest
from pydantic import BaseModel, ConfigDict

from app.ai import schemas as ai_schemas
from app.ai import tools as tools_module
from app.ai.schemas import AgentAction, TOOL_FOR_ACTION
from app.ai.tools import (
    TOOL_NAMES,
    TOOLS,
    ToolBudget,
    ToolContext,
    call_tool,
)
from tests.ai_fakes import fake_plant, fake_settings, make_ctx

EXPECTED_TOOLS = (
    "get_plant_configuration",
    "get_current_state",
    "get_safety_limits",
    "get_recent_history",
    "run_simulation",
    "run_scenario_search",
    "compare_scenarios",
    "get_failure_details",
    "check_safeguards",
)


# ---------------------------------------------------------------------------
# harness: a plant snapshot and settings, no ORM and no HTTP
# ---------------------------------------------------------------------------


def ctx(budget: int = 40, **setting_overrides) -> ToolContext:
    """A tool context with overridable search limits (shared fakes)."""
    return make_ctx(budget=budget, settings=fake_settings(**setting_overrides))


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------


def test_registry_exposes_exactly_the_documented_tools():
    assert TOOL_NAMES == EXPECTED_TOOLS
    assert set(TOOLS) == set(EXPECTED_TOOLS)


def test_every_action_maps_to_exactly_one_allowlisted_tool():
    mapped = [tool for tool in TOOL_FOR_ACTION.values()]
    assert len(mapped) == len(set(mapped)), "two actions share a tool"
    assert set(mapped).issubset(set(TOOLS))
    for action in AgentAction:
        if action is AgentAction.CONCLUDE:
            assert action not in TOOL_FOR_ACTION
        else:
            assert action in TOOL_FOR_ACTION


def test_no_tool_accepts_an_owner_plant_or_user_argument():
    forbidden = {"owner_id", "plant_id", "user_id", "email", "role", "is_admin"}
    for spec in TOOLS.values():
        assert forbidden.isdisjoint(set(spec.args_model.model_fields)), spec.name


def test_expensive_tools_are_flagged_and_actions_agree():
    for name in ("run_simulation", "run_scenario_search", "compare_scenarios", "check_safeguards"):
        assert TOOLS[name].charges_simulations is True
    for name in ("get_plant_configuration", "get_current_state", "get_safety_limits", "get_recent_history"):
        assert TOOLS[name].charges_simulations is False
    # The schema's notion of "expensive" is the same set the machine accounts for.
    assert {
        action.value
        for action in ai_schemas.EXPENSIVE_ACTIONS
    } == {"run_simulation", "run_scenario_search", "compare_scenarios", "check_safeguards"}


# ---------------------------------------------------------------------------
# refusals
# ---------------------------------------------------------------------------


def test_unknown_tool_is_refused_without_executing_anything():
    ok, payload, error, _latency = call_tool("run_shell", {"command": "rm -rf /"}, ctx())
    assert ok is False
    assert error == "unknown_tool"
    assert payload == {}


def test_invented_arguments_are_refused():
    for tool, args in (
        ("get_plant_configuration", {"owner_id": "someone-else"}),
        ("get_current_state", {"plant_id": "another-plant"}),
        ("run_simulation", {"command": "rm -rf /"}),
        ("run_simulation", {"duration_s": 300, "faults": [{"type": "cooling_loss", "start_s": 0}], "shell": "x"}),
    ):
        ok, _payload, error, _latency = call_tool(tool, args, ctx())
        assert ok is False, (tool, args)
        assert error is not None and error.startswith("invalid_arguments")


def test_out_of_range_arguments_are_refused_by_the_schema():
    ok, _payload, error, _latency = call_tool(
        "run_scenario_search", {"variable": "cooling_factor", "steps": 999}, ctx()
    )
    assert ok is False
    assert error is not None and error.startswith("invalid_arguments")

    ok, _payload, error, _latency = call_tool(
        "compare_scenarios", {"variable": "cooling_factor", "low": -5, "high": 1}, ctx()
    )
    assert ok is False
    assert error == "out_of_bounds"


def test_the_tool_layer_enforces_the_simulation_budget_itself():
    empty = ctx(budget=0)
    for tool, args in (
        ("run_simulation", {"duration_s": 60, "time_step_s": 1}),
        ("run_scenario_search", {"variable": "cooling_factor", "steps": 9}),
        ("compare_scenarios", {"variable": "cooling_factor", "low": 0.0, "high": 1.0}),
    ):
        ok, payload, error, _latency = call_tool(tool, args, empty)
        assert ok is False, tool
        assert error == "simulation_budget"
        assert payload == {}
    assert empty.budget.used == 0


def test_search_limits_are_enforced_before_any_compute():
    controller = ctx(budget=40, SEARCH_MAX_SCENARIOS=3)
    ok, _payload, error, _latency = call_tool(
        "run_scenario_search", {"variable": "cooling_factor", "steps": 9}, controller
    )
    assert ok is False
    assert error == "out_of_bounds"
    assert controller.budget.used == 0


def test_a_sweep_with_two_variables_is_refused_rather_than_silently_reduced():
    ok, _payload, error, _latency = call_tool(
        "run_scenario_search",
        {"mode": "sweep", "variable": "cooling_factor", "second_variable": "feed_factor"},
        ctx(),
    )
    assert ok is False
    assert error == "mode_mismatch"


# ---------------------------------------------------------------------------
# real execution
# ---------------------------------------------------------------------------


def test_get_plant_configuration_returns_no_owner_or_contact_details():
    ok, payload, error, _latency = call_tool("get_plant_configuration", {}, ctx())
    assert ok is True and error is None
    assert payload["config"]["feed_flow_lpm"] == 120.0
    flat = str(payload)
    assert "user-1" not in flat
    assert "owner" not in flat
    assert "@" not in flat


def test_get_safety_limits_reports_limits_and_near_bands():
    ok, payload, _error, _latency = call_tool("get_safety_limits", {}, ctx())
    assert ok is True
    assert payload["limits"]["temperature_c"] == 150.0
    assert payload["near_limit"]["temperature_c"] == pytest.approx(135.0)


def test_get_current_state_falls_back_to_the_configured_state():
    ok, payload, _error, _latency = call_tool("get_current_state", {}, ctx())
    assert ok is True
    assert payload["source"] == "configured_initial_state"
    assert payload["values"]["temperature_c"] == 80.0


def test_get_recent_history_without_telemetry_is_honest():
    ok, payload, _error, _latency = call_tool("get_recent_history", {"limit": 30}, ctx())
    assert ok is True
    assert payload["frame_count"] == 0
    assert payload["source"] == "none"


def test_run_simulation_assesses_a_cooling_loss_and_charges_one_simulation():
    context = ctx()
    ok, payload, error, _latency = call_tool(
        "run_simulation",
        {"duration_s": 600, "time_step_s": 1, "label": "ai cooling loss", "faults": [{"type": "cooling_loss", "start_s": 0}]},
        context,
    )
    assert ok is True, error
    assert payload["status"] in {"safeguard_activated", "violation", "near_limit", "safe"}
    assert payload["peaks"]["temperature_c"] is not None
    assert len(payload["findings"]) <= 3
    assert context.budget.used == 1


def test_run_scenario_search_discovers_the_seeded_region_through_the_tool_layer():
    context = ctx()
    ok, payload, error, _latency = call_tool(
        "run_scenario_search",
        {"variable": "cooling_factor", "steps": 9, "refine": True, "duration_s": 600, "time_step_s": 1},
        context,
    )
    assert ok is True, error
    assert payload["mode"] == "sweep"
    assert payload["counts"]["scenarios"] >= 9
    assert payload["counts"]["violation"] + payload["counts"]["safeguard_activated"] >= 1
    assert payload["counts"]["safe"] >= 1
    assert payload["boundary"] is not None
    assert payload["boundary"]["variable"] == "cooling_factor"
    assert payload["boundary"]["method"] in {"bisection", "dense"}
    assert context.budget.used > 0
    assert context.budget.used <= context.budget.max_simulations


def test_failure_details_need_a_previous_search_and_then_come_from_it():
    context = ctx()
    ok, _payload, error, _latency = call_tool("get_failure_details", {}, context)
    assert ok is False
    assert error == "no_search_yet"

    call_tool(
        "run_scenario_search",
        {"variable": "cooling_factor", "steps": 9, "refine": False, "duration_s": 600, "time_step_s": 1},
        context,
    )
    ok, payload, error, _latency = call_tool("get_failure_details", {"limit": 3}, context)
    assert ok is True, error
    assert payload["failure_count"] >= 1
    first = payload["failures"][0]
    assert set(first) >= {"key", "status", "values", "peaks"}
    assert first["status"] in {"violation", "safeguard_activated"}


def test_compare_scenarios_uses_the_allowlisted_mapping_and_reports_a_delta():
    context = ctx()
    ok, payload, error, _latency = call_tool(
        "compare_scenarios",
        {"variable": "cooling_factor", "low": 1.0, "high": 0.0, "duration_s": 600, "time_step_s": 1},
        context,
    )
    assert ok is True, error
    assert payload["variable"] == "cooling_factor"
    # Ordered by value, not by the order the caller wrote them.
    assert payload["lower"]["value"] == 0.0 and payload["upper"]["value"] == 1.0
    assert payload["temperature_delta_c"] is not None
    assert payload["temperature_delta_c"] < 0  # upper = full cooling is cooler
    assert payload["worse_side"] == "lower"
    assert context.budget.used == 2


def test_compare_scenarios_cannot_be_flipped_by_argument_order():
    first = ctx()
    second = ctx()
    _ok, a, _err, _latency = call_tool(
        "compare_scenarios", {"variable": "cooling_factor", "low": 0.0, "high": 1.0, "duration_s": 300}, first
    )
    _ok, b, _err, _latency = call_tool(
        "compare_scenarios", {"variable": "cooling_factor", "low": 1.0, "high": 0.0, "duration_s": 300}, second
    )
    assert a["temperature_delta_c"] == b["temperature_delta_c"]
    assert a["lower"]["value"] == b["lower"]["value"] == 0.0


def test_check_safeguards_reports_settings_and_can_test_a_delay():
    context = ctx()
    ok, payload, error, _latency = call_tool("check_safeguards", {}, context)
    assert ok is True, error
    assert payload["settings"]["trip_delay_s"] == 30.0
    assert "last_assessment" not in payload

    ok, payload, error, _latency = call_tool("check_safeguards", {"delay_s": 120}, context)
    assert ok is True, error
    assert payload["delay_s"] == 120
    assert payload["tested"]["status"] in {"safeguard_activated", "violation", "near_limit", "safe"}
    assert context.budget.used == 1


# ---------------------------------------------------------------------------
# payload bounds
# ---------------------------------------------------------------------------


class _TempArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


def test_an_oversized_payload_is_rejected_rather_than_truncated():
    def huge(_ctx, _args):
        return {"blob": "x" * (tools_module.MAX_PAYLOAD_CHARS + 1)}

    spec = tools_module.ToolSpec("temp_huge", "temp", _TempArgs, huge)
    tools_module.TOOLS["temp_huge"] = spec
    try:
        ok, payload, error, _latency = call_tool("temp_huge", {}, ctx())
    finally:
        tools_module.TOOLS.pop("temp_huge")

    assert ok is False
    assert error == "payload_too_large"
    assert payload == {}


def test_a_legitimate_payload_is_bounded_and_redacted():
    def leaky(_ctx, _args):
        return {"note": "Authorization: Bearer sk-live-1234567890abcdefghijklmnop"}

    spec = tools_module.ToolSpec("temp_leaky", "temp", _TempArgs, leaky)
    tools_module.TOOLS["temp_leaky"] = spec
    try:
        ok, payload, error, _latency = call_tool("temp_leaky", {}, ctx())
    finally:
        tools_module.TOOLS.pop("temp_leaky")

    assert ok is True, error
    assert "sk-live-1234567890abcdefghijklmnop" not in payload["note"]


def test_a_failing_handler_becomes_a_safe_rejection():
    def boom(_ctx, _args):
        raise RuntimeError("database password is hunter2")

    spec = tools_module.ToolSpec("temp_boom", "temp", _TempArgs, boom)
    tools_module.TOOLS["temp_boom"] = spec
    try:
        ok, payload, error, _latency = call_tool("temp_boom", {}, ctx())
    finally:
        tools_module.TOOLS.pop("temp_boom")

    assert ok is False
    assert error == "tool_error"
    assert payload == {}
    assert "hunter2" not in str(error)
