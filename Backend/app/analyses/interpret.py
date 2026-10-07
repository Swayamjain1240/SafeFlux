"""Deterministic goal interpretation (Part 9).

The engineer types an engineering change like ``Increase production throughput
by 30%.``. Deriving the *interpreted change* is deliberately mechanical:
numbers, percentages, direction words and allowlisted variable names are read
out of the sanitized text; everything else is treated as data. Nothing here
asks a model, and nothing here decides anything about safety — interpretation
only draws the search boundary, the simulator still proves it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.search.variables import VARIABLE_NAMES, SearchVariable

#: Direction words a goal may use (English; the MVP language).
_INCREASE_WORDS = ("increase", "raise", "boost", "more", "higher", "ramp up", "step up")
_DECREASE_WORDS = ("decrease", "reduce", "less", "lower", "cut", "shut down", "turn down")

#: A number optionally followed by a percent sign, e.g. ``30%``, ``0.5``, ``1.5x``.
_NUMBER_RE = re.compile(r"(?<![\w.])(\d+(?:\.\d+)?)\s*(%|x)?(?![\w])")

#: Nouns that plausibly name an allowlisted variable (multi-word first).
_VARIABLE_NOUNS: tuple[tuple[tuple[str, ...], SearchVariable], ...] = (
    (("throughput", "production", "output", "product"), SearchVariable.FEED_FACTOR),
    (("cooling", "coolant", "chiller"), SearchVariable.COOLING_FACTOR),
    (("outlet", "drain", "discharge"), SearchVariable.OUTLET_FACTOR),
    (("valve",), SearchVariable.VALVE_TARGET_PCT),
    (("pump",), SearchVariable.PUMP_FACTOR),
    (("shutdown", "trip"), SearchVariable.SHUTDOWN_DELAY_S),
    (("sensor", "sensor bias", "measurement"), SearchVariable.TEMPERATURE_SENSOR_BIAS_C),
)

MAX_GOAL_CHARS = 2000


@dataclass(frozen=True)
class InterpretedChange:
    """What the goal text asked for, read mechanically from the words used."""

    #: The sanitized text (the only form that travels further).
    text: str
    #: Increase/decrease/None as read from direction words.
    direction: str | None
    #: The magnitude with a percent sign, when one was stated.
    magnitude: str | None
    #: Numeric magnitude for the plan (None unless a number was present).
    magnitude_value: float | None
    #: Whether the number read as a percentage (vs a plain factor).
    is_percent: bool
    #: Allowlisted variables the nouns in the text plausibly target.
    variables: list[str] = field(default_factory=list)
    #: Nouns found but not resolvable to an allowlisted variable (kept as data).
    unrecognised: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "text": self.text,
            "direction": self.direction,
            "magnitude": self.magnitude,
            "magnitude_value": self.magnitude_value,
            "is_percent": self.is_percent,
            "variables": list(self.variables),
            "unrecognised": list(self.unrecognised),
        }


def _direction_of(text_lower: str) -> str | None:
    increase = any(word in text_lower for word in _INCREASE_WORDS)
    decrease = any(word in text_lower for word in _DECREASE_WORDS)
    if increase and not decrease:
        return "increase"
    if decrease and not increase:
        return "decrease"
    if increase and decrease:
        # Contradictory words: the text is data, not a plan; say so.
        return "conflicting"
    return None


def _magnitude_of(text: str) -> tuple[str | None, float | None, bool]:
    """First number with an optional % or x suffix, read left to right."""
    match = _NUMBER_RE.search(text)
    if match is None:
        return None, None, False
    number = float(match.group(1))
    suffix = match.group(2)
    if suffix == "%":
        return f"{number:g}%", number, True
    if suffix == "x":
        return f"{number:g}x", number, False
    # A bare number in a throughput-style goal is conventionally a percentage.
    return f"{number:g}%", number, True


def _variables_of(text_lower: str) -> list[str]:
    found: list[SearchVariable] = []
    seen: set[SearchVariable] = set()
    for nouns, variable in _VARIABLE_NOUNS:
        if variable in seen:
            continue
        if any(noun in text_lower for noun in nouns):
            found.append(variable)
            seen.add(variable)
    return [variable.value for variable in found]


def _has_known_variable_word(text_lower: str) -> bool:
    return any(
        noun in text_lower for nouns, _variable in _VARIABLE_NOUNS for noun in nouns
    )


def interpret_goal(raw: str | None) -> InterpretedChange:
    """Read the engineering change out of already-sanitized goal text."""
    text = (raw or "").strip()[:MAX_GOAL_CHARS]
    lowered = text.lower()

    direction = _direction_of(lowered)
    magnitude, magnitude_value, is_percent = _magnitude_of(text)
    variables = _variables_of(lowered)

    known_words = _has_known_variable_word(lowered)
    unrecognised: list[str] = []
    if direction and known_words is False and text:
        # Direction without any equipment noun: record the gap instead of guessing.
        unrecognised.append("request names no known equipment or variable")

    return InterpretedChange(
        text=text,
        direction=direction,
        magnitude=magnitude,
        magnitude_value=magnitude_value,
        is_percent=is_percent,
        variables=variables,
        unrecognised=unrecognised,
    )


def variables_in_allowlist(names: list[str]) -> list[str]:
    """Keep only real allowlist names (order preserved, duplicates dropped)."""
    allowlist = set(SearchVariable)
    seen: set[SearchVariable] = set()
    ordered: list[str] = []
    for name in names or []:
        try:
            variable = SearchVariable(name)
        except ValueError:
            continue
        if variable not in seen:
            seen.add(variable)
            ordered.append(variable.value)
    del allowlist
    return ordered


__all__ = [
    "InterpretedChange",
    "MAX_GOAL_CHARS",
    "interpret_goal",
    "variables_in_allowlist",
    "VARIABLE_NAMES",
]
