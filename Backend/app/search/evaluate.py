"""Bounded evaluation of search cases (Part 7).

This is the only place a search touches the simulator. It exists to guarantee
three things the brief requires:

- **Bounded** — every real simulation is charged to a ``SearchBudget`` first, so
  no search can run away.
- **De-duplicated** — identical cases are simulated once and replayed from the
  cache, which is what makes a refined search affordable and keeps repeat runs
  honest (the same case key is the same simulation).
- **Traceable** — each outcome carries the evidence the verdict came from (peaks,
  limit crossings, shutdown time, findings), never a bare label.

The simulated trajectory is the *true* process state. A sensor variable therefore
cannot change a verdict here — and the outcome says so explicitly instead of
implying a bias made the plant safer or more dangerous.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Callable

from app.safety import SafetyStatus, SafetyThresholds, assess_scenario, status_rank
from app.simulator import (
    LimitSet,
    ProcessParameters,
    SafeguardSettings,
    Scenario,
    SimulationInput,
    SimulationLimits,
    volume_from_level,
)
from app.simulator.result import SimulationResult

from app.search.budgets import SearchBudget
from app.search.spec import SearchCase, SearchSpec
from app.search.variables import SPECS, effect_for


def _series_peak(series: dict, key: str) -> float | None:
    values = series.get(key)
    if not values:
        return None
    return float(max(values))


@dataclass(frozen=True)
class PlantProfile:
    """Immutable snapshot of everything a searched case needs from one plant.

    Deliberately built from attribute access only, so the search package never
    depends on the ORM or the request layer. It carries no owner id: the profile
    feeds simulation and result metadata, never authorization.
    """

    plant_id: str
    name: str
    params: ProcessParameters
    initial_volume_l: float
    initial_temperature_c: float
    safety_limits: LimitSet
    safeguards: SafeguardSettings
    config: dict = field(default_factory=dict)

    @classmethod
    def from_plant(cls, plant: object) -> "PlantProfile":
        config = plant.config  # type: ignore[attr-defined]
        state = plant.state  # type: ignore[attr-defined]
        limits = plant.safety_limits  # type: ignore[attr-defined]
        guards = plant.safeguards  # type: ignore[attr-defined]
        return cls(
            plant_id=str(plant.id),  # type: ignore[attr-defined]
            name=str(getattr(plant, "name", "plant")),
            params=ProcessParameters(
                feed_flow_lpm=config.feed_flow_lpm,
                heater_power_pct=config.heater_power_pct,
                cooling_pct=config.cooling_pct,
                valve_position_pct=config.valve_position_pct,
                pump_running=state.pump_running,
            ),
            initial_volume_l=volume_from_level(state.level_pct),
            initial_temperature_c=state.temperature_c,
            safety_limits=LimitSet(
                max_temperature_c=limits.max_temperature_c,
                max_pressure_bar=limits.max_pressure_bar,
                max_level_pct=limits.max_level_pct,
            ),
            safeguards=SafeguardSettings(
                auto_shutdown_enabled=guards.auto_shutdown_enabled,
                high_temperature_trip=guards.high_temperature_trip,
                high_pressure_trip=guards.high_pressure_trip,
                high_level_trip=guards.high_level_trip,
                trip_delay_s=float(guards.trip_delay_s),
            ),
            config={
                "feed_flow_lpm": config.feed_flow_lpm,
                "heater_power_pct": config.heater_power_pct,
                "cooling_pct": config.cooling_pct,
                "valve_position_pct": config.valve_position_pct,
                "shutdown_delay_s": config.shutdown_delay_s,
                "initial_level_pct": state.level_pct,
                "initial_temperature_c": state.temperature_c,
                "initial_pressure_bar": state.pressure_bar,
                "pump_running": state.pump_running,
            },
        )

    def to_dict(self) -> dict:
        return {
            "plant_id": self.plant_id,
            "plant_name": self.name,
            "config": dict(self.config),
            "safety_limits": {
                "max_temperature_c": self.safety_limits.max_temperature_c,
                "max_pressure_bar": self.safety_limits.max_pressure_bar,
                "max_level_pct": self.safety_limits.max_level_pct,
            },
            "safeguards": {
                "auto_shutdown_enabled": self.safeguards.auto_shutdown_enabled,
                "trip_delay_s": self.safeguards.trip_delay_s,
                "trip_fraction": self.safeguards.trip_fraction,
            },
        }


@dataclass
class CaseOutcome:
    """The evidence for one evaluated case."""

    key: str
    label: str
    values: dict[str, float]
    status: SafetyStatus
    rank: int
    observation_only: bool
    peaks: dict[str, float | None]
    limit_exceeded: dict[str, bool]
    shutdown_at_s: float | None
    findings: list[dict]
    worst_finding: dict | None
    cached: bool = False

    @property
    def failing(self) -> bool:
        """A case the engineer must look at: a violation or a tripped safeguard."""
        return self.status in (SafetyStatus.VIOLATION, SafetyStatus.SAFEGUARD_ACTIVATED)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "label": self.label,
            "values": dict(self.values),
            "status": self.status.value,
            "rank": self.rank,
            "observation_only": self.observation_only,
            "peaks": dict(self.peaks),
            "limit_exceeded": dict(self.limit_exceeded),
            "shutdown_at_s": self.shutdown_at_s,
            "worst_finding": self.worst_finding,
            "findings": list(self.findings),
            "cached": self.cached,
        }


Runner = Callable[[SimulationInput, SafetyThresholds, str], tuple[object, SimulationResult]]


class ScenarioEvaluator:
    """Runs (or replays) one search case at a time under a hard budget."""

    def __init__(
        self,
        *,
        profile: PlantProfile,
        spec: SearchSpec,
        thresholds: SafetyThresholds,
        limits: SimulationLimits,
        budget: SearchBudget,
        runner: Runner | None = None,
    ) -> None:
        self.profile = profile
        self.spec = spec
        self.thresholds = thresholds
        self.limits = limits
        self.budget = budget
        self._runner = runner
        self._cache: dict[str, CaseOutcome] = {}
        self.cache_hits = 0
        self.simulations = 0

    # ------------------------- input construction -------------------------

    def build_input(self, case: SearchCase) -> SimulationInput:
        """Translate a case into a deterministic simulator input."""
        plan = self.spec.plan
        faults = []
        sensor_faults = []
        delay: float | None = None
        for variable, value in case.values:
            effect = effect_for(SPECS[variable], value, plan.start_s)
            if effect.fault is not None:
                faults.append(effect.fault)
            if effect.sensor_fault is not None:
                sensor_faults.append(effect.sensor_fault)
            if effect.shutdown_delay_s is not None:
                delay = effect.shutdown_delay_s

        safeguards = self.profile.safeguards
        if delay is not None:
            safeguards = replace(safeguards, trip_delay_s=delay)
        scenario = Scenario(
            duration_s=plan.duration_s,
            time_step_s=plan.time_step_s,
            faults=tuple(faults),
            sensor_faults=tuple(sensor_faults),
            label=case.label,
        )
        return SimulationInput(
            params=self.profile.params,
            initial_volume_l=self.profile.initial_volume_l,
            initial_temperature_c=self.profile.initial_temperature_c,
            scenario=scenario,
            limits=self.limits,
            safety_limits=self.profile.safety_limits,
            safeguards=safeguards,
            plant_id=self.profile.plant_id,
        )

    # ----------------------------- evaluation -----------------------------

    def evaluate(self, case: SearchCase) -> CaseOutcome:
        """Return the outcome for ``case``, simulating it at most once."""
        key = case.key()
        cached = self._cache.get(key)
        if cached is not None:
            self.cache_hits += 1
            return replace(cached, cached=True)

        # Charged before the simulation so an exhausted budget stops the search
        # rather than being discovered after the work is already done.
        self.budget.charge()
        sim_input = self.build_input(case)
        assessment, result = self._execute(sim_input, case)
        self.simulations += 1

        outcome = self._to_outcome(case, key, assessment, result)
        self._cache[key] = outcome
        return outcome

    def _execute(self, sim_input: SimulationInput, case: SearchCase):
        if self._runner is not None:
            return self._runner(sim_input, self.thresholds, case.label)
        return assess_scenario(sim_input, self.thresholds, scenario_id=case.label)

    def _to_outcome(self, case: SearchCase, key: str, assessment, result: SimulationResult) -> CaseOutcome:
        findings = [finding.to_dict() for finding in assessment.findings]
        worst = max(
            findings,
            key=lambda item: status_rank(SafetyStatus(item["status"])),
            default=None,
        )
        shutdown: float | None = None
        for event in result.events:
            if event.get("kind") == "shutdown":
                shutdown = float(event["time_s"])
                break
        exceeded = {
            item["type"]: item["status"] == SafetyStatus.VIOLATION.value for item in findings
        }
        # Only a variable that is actually doing something counts: a sensor bias
        # of 0 is the plant as configured, not a sensor-affected case.
        observation_only = any(
            SPECS[variable].is_observation_only and SPECS[variable].is_active(value)
            for variable, value in case.values
        )
        return CaseOutcome(
            key=key,
            label=case.label,
            values=case.as_dict(),
            status=assessment.status,
            rank=status_rank(assessment.status),
            observation_only=observation_only,
            peaks={
                "temperature_c": _series_peak(result.series, "true_temperature_c"),
                "pressure_bar": _series_peak(result.series, "true_pressure_bar"),
                "level_pct": _series_peak(result.series, "level_pct"),
            },
            limit_exceeded=exceeded,
            shutdown_at_s=shutdown,
            findings=findings,
            worst_finding=worst,
        )

    # ------------------------------- helpers -------------------------------

    def is_observation_only(self, case: SearchCase) -> bool:
        return any(
            SPECS[variable].is_observation_only and SPECS[variable].is_active(value)
            for variable, value in case.values
        )

    def cache_size(self) -> int:
        return len(self._cache)


__all__ = ["CaseOutcome", "PlantProfile", "ScenarioEvaluator"]
