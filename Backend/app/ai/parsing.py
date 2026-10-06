"""Parsing model output into validated objects (Part 8, rule 6).

Providers are chatty: they wrap JSON in prose, in code fences, or emit two
objects. This module extracts the first *balanced* JSON object from the text and
validates it with the strict Pydantic schemas. Anything that does not validate is
a safe stop (``INVALID_OUTPUT``): the raw text is never executed, never logged and
never returned to the client.

Pure functions only — no provider, no network, no side effects — so the malformed
output paths are cheap to test exhaustively.
"""

from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from app.ai.schemas import AgentDecision, AgentExplanation
from app.ai.security import redact_secrets


def find_json_object(text: str) -> str | None:
    """Return the first balanced ``{...}`` slice of ``text``, or ``None``.

    Balance tracking is string-aware (escapes and quoted braces do not count), so
    a value containing ``}`` cannot close the object early. Depth is capped so a
    pathological input cannot cost unbounded work.
    """
    if not isinstance(text, str) or not text:
        return None
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escaped = False
    for index in range(start, min(len(text), start + 200_000)):
        char = text[index]
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def parse_json(text: str) -> dict[str, Any] | None:
    """Extract and decode the first JSON object, or ``None`` if there is none."""
    candidate = find_json_object(text)
    if candidate is None:
        return None
    try:
        payload = json.loads(candidate)
    except (ValueError, TypeError):
        return None
    return payload if isinstance(payload, dict) else None


def _summarize_error(exc: ValidationError) -> str:
    """A short, value-free reason: field paths and error types only."""
    parts: list[str] = []
    for error in exc.errors()[:4]:
        location = ".".join(str(part) for part in error.get("loc", ())) or "body"
        parts.append(f"{location}:{error.get('type', 'invalid')}")
    return ", ".join(parts)[:200]


def parse_decision(text: str) -> tuple[AgentDecision | None, str | None]:
    """Validate model text as an ``AgentDecision``.

    Returns ``(decision, None)`` on success and ``(None, reason)`` on failure,
    where ``reason`` is a curated, value-free string safe to log and return.
    """
    payload = parse_json(text)
    if payload is None:
        return None, "no_json_object"
    try:
        return AgentDecision.model_validate(payload), None
    except ValidationError as exc:
        return None, f"invalid_decision:{_summarize_error(exc)}"


def parse_explanation(text: str) -> tuple[AgentExplanation | None, str | None]:
    """Validate model text as an ``AgentExplanation`` (same contract)."""
    payload = parse_json(text)
    if payload is None:
        return None, "no_json_object"
    try:
        return AgentExplanation.model_validate(payload), None
    except ValidationError as exc:
        return None, f"invalid_explanation:{_summarize_error(exc)}"


def safe_excerpt(text: str, limit: int = 200) -> str:
    """A redacted, single-line excerpt — for diagnostics that must not leak."""
    if not isinstance(text, str):
        return ""
    return redact_secrets(" ".join(text.split()))[:limit]


__all__ = [
    "find_json_object",
    "parse_decision",
    "parse_explanation",
    "parse_json",
    "safe_excerpt",
]
