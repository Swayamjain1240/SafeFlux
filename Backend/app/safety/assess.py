"""Safety assessment orchestration (Part 5).

The deterministic safety engine verifies the plant *with its emergency shutdown
driven by the high alarm setpoint* (``near_limit_fraction · limit``) plus the
configured ``trip_delay_s``. This is what lets the engine distinguish a
safeguard that stopped a rising condition in time from one that responded too
late: a pure trip-at-the-limit model can only ever be too late, because the
limit is already exceeded when the trip fires.

The guarded run is still produced by the Part 4 simulator — identical equations,
identical determinism — via the ``trip_fraction`` knob. When auto shutdown is
disabled, the plant's own (limit-trip) result is classified unchanged.
"""

from __future__ import annotations

from dataclasses import replace

from app.safety.findings import SafetyAssessment, SafetyThresholds
from app.simulator.engine import SimulationInput, run_simulation
from app.simulator.result import SimulationResult


def alarm_driven_input(
    sim_input: SimulationInput, near_limit_fraction: float
) -> SimulationInput:
    """Return a copy whose emergency shutdown trips at the alarm setpoint."""
    guarded_safeguards = replace(
        sim_input.safeguards, trip_fraction=near_limit_fraction
    )
    return replace(sim_input, safeguards=guarded_safeguards)


def assess_scenario(
    sim_input: SimulationInput,
    thresholds: SafetyThresholds,
    scenario_id: str | None = None,
) -> tuple[SafetyAssessment, SimulationResult]:
    """Assess one scenario and return (assessment, guarded simulator result).

    The returned result is the guarded run whose trajectory the assessment was
    derived from, so callers can show the exact evidence behind a verdict.
    """
    from app.safety import assess_simulation  # local import avoids a cycle

    if sim_input.safeguards.auto_shutdown_enabled:
        guarded_input = alarm_driven_input(sim_input, thresholds.near_limit_fraction)
    else:
        guarded_input = sim_input

    guarded_result = run_simulation(guarded_input)
    assessment = assess_simulation(
        guarded_result,
        thresholds,
        safeguards=sim_input.safeguards,
        scenario_id=scenario_id,
    )
    return assessment, guarded_result


__all__ = ["alarm_driven_input", "assess_scenario"]
