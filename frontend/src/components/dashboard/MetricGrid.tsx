import type { ProcessSnapshot } from '../plant/ProcessGraph'
import type { PlantDetail } from '../../types/plant'
import type { Tone } from '../../dashboard/viewState'
import { InstrumentTile } from '../ui/Instrument'

interface Metric {
  key: string
  label: string
  unit: string
  display: string
  sub: string
  tone: Tone
  fraction: number | null
}

function toneAgainstLimit(value: number, limit: number): Tone {
  if (value > limit) return 'crit'
  if (value >= limit * 0.9) return 'warn'
  return 'ok'
}

function fractionOf(value: number, limit: number): number {
  return Math.max(0, Math.min(100, (value / limit) * 100))
}

/**
 * The seven operating metrics the brief requires (Part 6): temperature,
 * pressure, feed flow, level, cooling, valve and pump.
 *
 * Live values come from the telemetry frame when one exists; otherwise the
 * configured/initial plant values are shown and labelled as configured — the
 * page never invents numbers. Every tile is the same height so the grid never
 * clips or overlaps at any tested viewport.
 *
 * Visual transformation: rendered through the instrument primitives (uppercase
 * label, mono numeral with unit, limit rail coloured by actual thresholds).
 */
export function MetricGrid({
  plant,
  values,
  live,
  columns,
  compact,
}: {
  plant: PlantDetail
  values: ProcessSnapshot
  live: boolean
  columns: 2 | 3 | 4
  compact: boolean
}) {
  const limits = plant.safety_limits
  const source = live ? 'telemetry' : 'configured'

  const metrics: Metric[] = [
    {
      key: 'temperature',
      label: 'Temperature',
      unit: '°C',
      display: values.temperature_c.toFixed(1),
      sub: `limit ${limits.max_temperature_c.toFixed(0)} °C · ${source}`,
      tone: toneAgainstLimit(values.temperature_c, limits.max_temperature_c),
      fraction: fractionOf(values.temperature_c, limits.max_temperature_c),
    },
    {
      key: 'pressure',
      label: 'Pressure',
      unit: 'bar',
      display: values.pressure_bar.toFixed(2),
      sub: `limit ${limits.max_pressure_bar.toFixed(1)} bar · ${source}`,
      tone: toneAgainstLimit(values.pressure_bar, limits.max_pressure_bar),
      fraction: fractionOf(values.pressure_bar, limits.max_pressure_bar),
    },
    {
      key: 'feed',
      label: 'Feed flow',
      unit: 'L/min',
      display: values.feed_flow_lpm.toFixed(0),
      sub: `${source} · pump ${values.pump_running ? 'running' : 'stopped'}`,
      tone: values.pump_running ? 'ok' : 'idle',
      fraction: null,
    },
    {
      key: 'level',
      label: 'Level',
      unit: '%',
      display: values.level_pct.toFixed(1),
      sub: `limit ${limits.max_level_pct.toFixed(0)} % · ${source}`,
      tone: toneAgainstLimit(values.level_pct, limits.max_level_pct),
      fraction: fractionOf(values.level_pct, limits.max_level_pct),
    },
    {
      key: 'cooling',
      label: 'Cooling',
      unit: '%',
      display: plant.config.cooling_pct.toFixed(0),
      sub: 'jacket duty · configured',
      tone: plant.config.cooling_pct <= 0 ? 'crit' : plant.config.cooling_pct < 50 ? 'warn' : 'ok',
      fraction: plant.config.cooling_pct,
    },
    {
      key: 'valve',
      label: 'Valve',
      unit: '%',
      display: plant.config.valve_position_pct.toFixed(0),
      sub: `outlet ${values.outlet_flow_lpm.toFixed(0)} L/min · ${source}`,
      tone: 'ok',
      fraction: plant.config.valve_position_pct,
    },
    {
      key: 'pump',
      label: 'Pump',
      unit: '',
      display: values.pump_running ? 'RUN' : 'STOP',
      sub: 'P-101 · drive',
      tone: values.pump_running ? 'ok' : 'idle',
      fraction: values.pump_running ? 100 : 0,
    },
  ]

  const gridColumns =
    columns === 4
      ? 'grid-cols-2 sm:grid-cols-4'
      : columns === 3
        ? 'grid-cols-2 sm:grid-cols-3'
        : 'grid-cols-2'

  return (
    <div className={`grid gap-2 ${gridColumns}`}>
      {metrics.map((metric) => (
        <InstrumentTile
          key={metric.key}
          label={metric.label}
          value={metric.display}
          unit={metric.unit || undefined}
          tone={metric.tone}
          caption={metric.sub}
          rail={metric.fraction ?? undefined}
          className={compact ? 'px-2 py-1.5' : ''}
        />
      ))}
    </div>
  )
}
