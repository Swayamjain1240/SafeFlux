"""SimulationResult container: time series, extrema, events, summary, metadata.

The result is plain JSON-serialisable data so it can travel through the API
envelope and be persisted/replayed later. Series are columnar (one list per
variable) which keeps sample counts cheap to encode.

Limit *crossings* recorded here are raw simulator observations with the
configured limit attached — status classification (SAFE / NEAR_LIMIT /
SAFEGUARD_ACTIVATED / VIOLATION) belongs to the Part 5 safety engine, not to the
simulator.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Numeric series that receive a min/max extrema summary (time_s and the boolean
# pump_running are intentionally excluded).
EXTREMA_KEYS: tuple[str, ...] = (
    "level_pct",
    "true_temperature_c",
    "observed_temperature_c",
    "true_pressure_bar",
    "observed_pressure_bar",
    "outlet_flow_lpm",
    "feed_flow_lpm",
)


@dataclass
class SimulationResult:
    series: dict[str, list] = field(default_factory=dict)
    extrema: dict[str, dict] = field(default_factory=dict)
    summary: dict = field(default_factory=dict)
    events: list[dict] = field(default_factory=list)
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "series": self.series,
            "extrema": self.extrema,
            "summary": self.summary,
            "events": self.events,
            "metadata": self.metadata,
        }


def build_extrema(series: dict[str, list]) -> dict[str, dict]:
    """Min/max (value + time) for each tracked numeric series."""
    extrema: dict[str, dict] = {}
    times = series.get("time_s", [])
    for key in EXTREMA_KEYS:
        values = series.get(key)
        if not values:
            continue
        min_index = max_index = 0
        min_value = max_value = values[0]
        for index, value in enumerate(values):
            if value < min_value:
                min_value, min_index = value, index
            if value > max_value:
                max_value, max_index = value, index
        extrema[key] = {
            "min": {"value": min_value, "time_s": times[min_index] if times else None},
            "max": {"value": max_value, "time_s": times[max_index] if times else None},
            "final": values[-1],
        }
    return extrema
