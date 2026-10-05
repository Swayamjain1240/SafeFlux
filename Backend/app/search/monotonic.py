"""Monotonicity classification for sampled search series (Part 7).

Bisection is only a valid way to find a boundary when the *risk* moves in one
direction along the axis. Applying it to a non-monotonic series silently
converges on the wrong point — the classic misuse of binary search the Part 7
brief warns about.

So refinement asks this module first: given the severities seen so far, is the
series monotonic? If it is not, the boundary is refined by densifying the
interval instead, which is slower but never claims a false boundary.
"""

from __future__ import annotations

from enum import Enum
from typing import Sequence

from app.search.constants import VALUE_TOLERANCE


class Monotonicity(str, Enum):
    INCREASING = "increasing"
    DECREASING = "decreasing"
    NON_MONOTONIC = "non_monotonic"
    INSUFFICIENT = "insufficient"


def classify_monotonic(
    values: Sequence[float], tolerance: float = VALUE_TOLERANCE
) -> Monotonicity:
    """Classify a series sampled in ascending argument order.

    Requires at least two usable points, otherwise the answer is
    ``INSUFFICIENT`` rather than a guess. Flats are allowed: a step function like
    ``SAFE, SAFE, NEAR, VIOLATION`` is still monotonic.
    """
    usable = [float(value) for value in values if value is not None]
    if len(usable) < 2:
        return Monotonicity.INSUFFICIENT

    unknown_direction = True
    direction = 0
    for previous, current in zip(usable, usable[1:]):
        delta = current - previous
        if abs(delta) <= tolerance:
            continue
        step = 1 if delta > 0 else -1
        if unknown_direction:
            direction = step
            unknown_direction = False
        elif step != direction:
            return Monotonicity.NON_MONOTONIC

    if unknown_direction:
        # Every sample is equal: no direction to exploit, so treat it as
        # unsupported rather than claiming a boundary that cannot exist.
        return Monotonicity.INSUFFICIENT
    return Monotonicity.INCREASING if direction > 0 else Monotonicity.DECREASING


def supports_bisection(monotonicity: Monotonicity) -> bool:
    """Bisection is only sound for a strictly-directed, non-flat series."""
    return monotonicity in (Monotonicity.INCREASING, Monotonicity.DECREASING)


__all__ = ["Monotonicity", "classify_monotonic", "supports_bisection"]
