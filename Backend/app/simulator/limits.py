"""Hard compute budgets that protect the simulator endpoint from abuse.

A simulation must never be able to request millions/billions of integration
steps. These limits are enforced server-side *before* any integration runs and
are configurable through Settings (SAFEFLUX_MASTER.md rule 8).
"""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class SimulationLimits:
    """Maximum duration, minimum time step and maximum sample count."""

    max_duration_s: float
    min_time_step_s: float
    max_samples: int

    def sample_count(self, duration_s: float, time_step_s: float) -> int:
        """Number of sample points inclusive of both endpoints."""
        return int(math.floor(duration_s / time_step_s)) + 1

    def validation_errors(
        self, duration_s: float, time_step_s: float
    ) -> list[tuple[str, str]]:
        """Return ``(field, message)`` pairs for any violated budget.

        Messages never echo the submitted values (rule 6 / safe API format).
        """
        errors: list[tuple[str, str]] = []
        if duration_s <= 0:
            errors.append(("duration_s", "Duration must be greater than zero."))
        elif duration_s > self.max_duration_s:
            errors.append(
                ("duration_s", "Duration exceeds the maximum allowed simulation duration.")
            )
        if time_step_s <= 0:
            errors.append(("time_step_s", "Time step must be greater than zero."))
        elif time_step_s < self.min_time_step_s:
            errors.append(("time_step_s", "Time step is below the minimum allowed value."))
        if duration_s > 0 and time_step_s > 0 and not errors:
            if self.sample_count(duration_s, time_step_s) > self.max_samples:
                errors.append(
                    ("time_step_s", "Requested simulation would exceed the maximum sample count.")
                )
        return errors
