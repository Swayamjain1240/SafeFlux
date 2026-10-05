"""Search budgets (Part 7).

Two layers, both mandatory:

1. ``SearchLimits`` — the *plan*: how many scenarios, combinations, refinement
   levels and seconds a single search may use. Request values above the
   configured ceiling are rejected (never silently clamped), so an oversized
   search is a clear 422 rather than a quiet surprise.
2. ``SearchBudget`` — the *runtime counter*: charged before every simulation, so
   the engine can stop gracefully when a limit is reached instead of running
   away. Hitting a limit is a normal, reported outcome (the result is marked
   truncated), not an exception the caller has to interpret.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field

from app.search.constants import (
    DEFAULT_MAX_COMBINATIONS,
    DEFAULT_MAX_SCENARIOS,
    DEFAULT_REFINEMENT_DEPTH,
    DEFAULT_TIMEOUT_S,
    MAX_COMBINATIONS_CEILING,
    MAX_COMBINATION_AXES,
    MAX_REFINEMENT_DEPTH_CEILING,
    MAX_SCENARIOS_CEILING,
    MAX_TIMEOUT_S_CEILING,
    MIN_TIMEOUT_S,
)


class SearchBudgetExceeded(Exception):
    """Raised internally when a hard budget stops the search."""

    def __init__(self, kind: str) -> None:
        super().__init__(f"search budget exceeded: {kind}")
        self.kind = kind


def _positive_int(value: object, fallback: int) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return fallback
    if not math.isfinite(float(value)):
        return fallback
    return int(value)


@dataclass(frozen=True)
class SearchLimits:
    """Resolved, non-negotiable limits for one search."""

    max_scenarios: int = DEFAULT_MAX_SCENARIOS
    max_combinations: int = DEFAULT_MAX_COMBINATIONS
    max_refinement_depth: int = DEFAULT_REFINEMENT_DEPTH
    timeout_s: float = DEFAULT_TIMEOUT_S
    max_duration_s: float = 3600.0
    min_time_step_s: float = 0.05
    max_samples: int = 20000

    @property
    def max_combination_axes(self) -> int:
        return MAX_COMBINATION_AXES

    def to_dict(self) -> dict:
        return {
            "max_scenarios": self.max_scenarios,
            "max_combinations": self.max_combinations,
            "max_refinement_depth": self.max_refinement_depth,
            "timeout_s": self.timeout_s,
            "max_duration_s": self.max_duration_s,
            "min_time_step_s": self.min_time_step_s,
            "max_samples": self.max_samples,
        }

    def validation_errors(
        self,
        *,
        duration_s: float,
        time_step_s: float,
        refinement_depth: int,
        axes: int,
        combinations: int,
        scenarios: int,
    ) -> list[tuple[str, str]]:
        """Return ``(field, message)`` pairs for any exceeded limit.

        Messages never echo the submitted values (rule 6 / safe API contract).
        """
        errors: list[tuple[str, str]] = []
        if duration_s <= 0:
            errors.append(("duration_s", "Duration must be greater than zero."))
        elif duration_s > self.max_duration_s:
            errors.append(("duration_s", "Duration exceeds the maximum allowed simulation duration."))
        if time_step_s <= 0:
            errors.append(("time_step_s", "Time step must be greater than zero."))
        elif time_step_s < self.min_time_step_s:
            errors.append(("time_step_s", "Time step is below the minimum allowed value."))
        if duration_s > 0 and time_step_s > 0 and duration_s <= self.max_duration_s:
            samples = int(math.floor(duration_s / time_step_s)) + 1
            if samples > self.max_samples:
                errors.append(
                    ("time_step_s", "Requested simulation would exceed the maximum sample count.")
                )
        if refinement_depth > self.max_refinement_depth:
            errors.append(
                ("refinement_depth", "Refinement depth exceeds the maximum allowed depth.")
            )
        if axes > self.max_combination_axes:
            errors.append(("axes", "Too many search axes for a bounded combination search."))
        if combinations > self.max_combinations:
            errors.append(
                ("axes", "The requested combination search would exceed the combination limit.")
            )
        if scenarios > self.max_scenarios:
            errors.append(
                ("steps", "The requested search would exceed the maximum scenario budget.")
            )
        return errors


def resolve_limits(settings: object | None = None) -> SearchLimits:
    """Build limits from Settings, falling back to the built-in defaults.

    Settings values are themselves clamped to the hard ceilings so a bad
    environment variable can never uncap the search.
    """
    get = (lambda name, fallback: getattr(settings, name, fallback)) if settings else (
        lambda name, fallback: fallback
    )
    max_scenarios = min(
        max(1, _positive_int(get("SEARCH_MAX_SCENARIOS", DEFAULT_MAX_SCENARIOS), DEFAULT_MAX_SCENARIOS)),
        MAX_SCENARIOS_CEILING,
    )
    max_combinations = min(
        max(
            1,
            _positive_int(
                get("SEARCH_MAX_COMBINATIONS", DEFAULT_MAX_COMBINATIONS), DEFAULT_MAX_COMBINATIONS
            ),
        ),
        MAX_COMBINATIONS_CEILING,
    )
    max_depth = min(
        max(
            0,
            _positive_int(
                get("SEARCH_MAX_REFINEMENT_DEPTH", DEFAULT_REFINEMENT_DEPTH),
                DEFAULT_REFINEMENT_DEPTH,
            ),
        ),
        MAX_REFINEMENT_DEPTH_CEILING,
    )
    timeout_s = float(get("SEARCH_TIMEOUT_SECONDS", DEFAULT_TIMEOUT_S))
    if not math.isfinite(timeout_s):
        timeout_s = DEFAULT_TIMEOUT_S
    timeout_s = min(max(timeout_s, MIN_TIMEOUT_S), MAX_TIMEOUT_S_CEILING)
    return SearchLimits(
        max_scenarios=max_scenarios,
        max_combinations=max_combinations,
        max_refinement_depth=max_depth,
        timeout_s=timeout_s,
        max_duration_s=float(get("SIM_MAX_DURATION_S", 3600.0)),
        min_time_step_s=float(get("SIM_MIN_TIME_STEP_S", 0.05)),
        max_samples=_positive_int(get("SIM_MAX_SAMPLES", 20000), 20000),
    )


@dataclass
class SearchBudget:
    """Runtime counter charged before every simulated scenario."""

    limits: SearchLimits
    started_at: float = field(default_factory=time.monotonic)
    scenarios: int = 0
    #: Set when a limit stopped the search (``scenarios`` or ``timeout``).
    exceeded: str | None = None

    def elapsed_s(self) -> float:
        return time.monotonic() - self.started_at

    def remaining_scenarios(self) -> int:
        return max(0, self.limits.max_scenarios - self.scenarios)

    def timed_out(self) -> bool:
        return self.elapsed_s() >= self.limits.timeout_s

    def charge(self) -> None:
        """Reserve one scenario, raising when a limit is already reached."""
        if self.scenarios >= self.limits.max_scenarios:
            self.exceeded = "scenarios"
            raise SearchBudgetExceeded("scenarios")
        if self.timed_out():
            self.exceeded = "timeout"
            raise SearchBudgetExceeded("timeout")
        self.scenarios += 1

    def to_dict(self) -> dict:
        return {
            "scenarios_used": self.scenarios,
            "max_scenarios": self.limits.max_scenarios,
            "scenarios_remaining": self.remaining_scenarios(),
            "timeout_s": self.limits.timeout_s,
            "elapsed_s": round(self.elapsed_s(), 3),
            "exceeded": self.exceeded,
        }


__all__ = [
    "SearchBudget",
    "SearchBudgetExceeded",
    "SearchLimits",
    "resolve_limits",
]
