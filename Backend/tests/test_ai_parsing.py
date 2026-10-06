"""Model-output parsing coverage (Part 8, rule 6/23).

The model is not trusted to produce clean JSON, and it is not trusted to produce
*schema-shaped* JSON either. These tests pin both halves: extraction from
realistic provider noise, and a safe rejection for everything that does not
validate (which the loop reports as ``invalid_output``).
"""

from __future__ import annotations

from app.ai.parsing import (
    find_json_object,
    parse_decision,
    parse_explanation,
    parse_json,
    safe_excerpt,
)
from app.ai.schemas import AgentAction


# ---------------------------------------------------------------------------
# extraction
# ---------------------------------------------------------------------------


def test_extracts_a_bare_object():
    assert find_json_object('{"a": 1}') == '{"a": 1}'


def test_extracts_from_prose_and_code_fences():
    text = 'Sure! Here is the plan:\n```json\n{"focus": "cooling", "action": "conclude"}\n```\nDone.'
    assert parse_json(text) == {"focus": "cooling", "action": "conclude"}


def test_braces_inside_strings_do_not_close_the_object_early():
    assert find_json_object('{"reason": "the {valve} stuck", "n": 1}') == '{"reason": "the {valve} stuck", "n": 1}'
    assert find_json_object('{"reason": "quote \\" then { brace", "n": 1}') == (
        '{"reason": "quote \\" then { brace", "n": 1}'
    )


def test_nested_objects_are_kept_whole():
    text = 'noise {"outer": {"inner": 1}, "list": [{"x": 2}]} tail'
    assert find_json_object(text) == '{"outer": {"inner": 1}, "list": [{"x": 2}]}'


def test_non_json_and_unbalanced_input_return_none():
    assert find_json_object("no object here") is None
    assert find_json_object("") is None
    assert parse_json('{"unterminated": ') is None
    assert parse_json("[]") is None  # a list is not a decision document


# ---------------------------------------------------------------------------
# decisions
# ---------------------------------------------------------------------------


def test_valid_decision_parses_with_allowlisted_variables():
    text = (
        '{"schema_version": "1", "focus": "cooling_outlet_interaction", '
        '"reason": "Pressure approached its configured limit in ev-1.", '
        '"action": "run_scenario_search", "variables": ["cooling_factor", "outlet_factor"], '
        '"arguments": {"variable": "cooling_factor", "steps": 9}}'
    )
    decision, error = parse_decision(text)
    assert error is None
    assert decision is not None
    assert decision.action is AgentAction.RUN_SCENARIO_SEARCH
    assert decision.tool == "run_scenario_search"
    assert [variable.value for variable in decision.variables] == ["cooling_factor", "outlet_factor"]
    assert decision.arguments == {"variable": "cooling_factor", "steps": 9}


def test_malformed_json_is_rejected_with_a_safe_reason():
    decision, error = parse_decision('{"focus": "cooling", "action":')
    assert decision is None
    assert error == "no_json_object"


def test_unknown_action_is_rejected():
    decision, error = parse_decision('{"focus": "x", "reason": "y", "action": "rm_rf"}')
    assert decision is None
    assert error is not None and error.startswith("invalid_decision:")
    assert "rm_rf" not in error


def test_variable_outside_the_allowlist_is_rejected():
    text = (
        '{"focus": "x", "reason": "y", "action": "run_scenario_search", '
        '"variables": ["__import__"], "arguments": {}}'
    )
    decision, error = parse_decision(text)
    assert decision is None
    assert error is not None and "variables" in error


def test_extra_fields_are_rejected():
    text = '{"focus": "x", "reason": "y", "action": "conclude", "shell": "rm -rf /"}'
    decision, error = parse_decision(text)
    assert decision is None
    assert error is not None and "shell" in error


def test_argument_block_is_bounded():
    big = {f"k{index}": index for index in range(20)}
    text = (
        '{"focus": "x", "reason": "y", "action": "get_recent_history", "arguments": '
        + str(big).replace("'", '"')
        + "}"
    )
    decision, error = parse_decision(text)
    assert decision is None
    assert error is not None


def test_empty_required_text_is_rejected():
    decision, error = parse_decision('{"focus": "", "reason": "why", "action": "conclude"}')
    assert decision is None
    assert error is not None and "focus" in error


# ---------------------------------------------------------------------------
# explanations
# ---------------------------------------------------------------------------


def test_valid_explanation_parses_and_bounds_evidence_ids():
    text = (
        '{"headline": "Boundary near 0.09 cooling", '
        '"explanation": "ev-1 found one violation and one boundary candidate.", '
        '"evidence_ids": ["ev-1", "ev-2"], "next_variables": ["cooling_factor"]}'
    )
    explanation, error = parse_explanation(text)
    assert error is None
    assert explanation is not None
    assert explanation.evidence_ids == ["ev-1", "ev-2"]
    assert explanation.next_variables[0].value == "cooling_factor"


def test_invented_evidence_id_is_rejected():
    text = '{"headline": "h", "explanation": "e", "evidence_ids": ["ev-1; DROP TABLE users"]}'
    explanation, error = parse_explanation(text)
    assert explanation is None
    assert error is not None and error.startswith("invalid_explanation:")


def test_explanation_without_evidence_is_still_valid():
    explanation, error = parse_explanation('{"headline": "no boundary found", "explanation": "all sampled points stayed acceptable"}')
    assert error is None
    assert explanation is not None
    assert explanation.evidence_ids == []


# ---------------------------------------------------------------------------
# diagnostics
# ---------------------------------------------------------------------------


def test_safe_excerpt_collapses_and_redacts():
    excerpt = safe_excerpt("line one\n\nline two  Authorization: Bearer sk-live-1234567890abcdefghijklmnop")
    assert "\n" not in excerpt
    assert "sk-live-1234567890abcdefghijklmnop" not in excerpt
    long_text = " ".join(["cooling loss near the outlet"] * 30)
    assert len(safe_excerpt(long_text)) == 200
    # A 40+ character alphanumeric blob is treated as a credential-shaped token.
    assert safe_excerpt("x" * 500) == "[redacted]"
