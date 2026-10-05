import type { ProcessSnapshot } from '../plant/ProcessGraph'
import type { PlantDetail } from '../../types/plant'

export type Tone = 'ok' | 'warn' | 'crit' | 'idle'

const ACCENT: Record<Tone, string> = {
  ok: 'text-emerald-300',
  warn: 'text-amber-300',
  crit: 'text-rose-300',
  idle: 'text-slate-400',
}

const RAIL: Record<Tone, string> = {
  ok: 'bg-emerald-400/70',
  warn: 'bg-amber-400',
  crit: 'bg-rose-500',
  idle: 'bg-slate-600',
}

interface Metric {
  key: string
  label: string
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
 * page never invents numbers. Every card is the same height so the grid never
 * clips or overlaps at any tested viewport.
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
      display: values.temperature_c.toFixed(1),
      sub: `limit ${limits.max_temperature_c.toFixed(0)} °C · ${source}`,
      tone: toneAgainstLimit(values.temperature_c, limits.max_temperature_c),
      fraction: fractionOf(values.temperature_c, limits.max_temperature_c),
    },
    {
      key: 'pressure',
      label: 'Pressure',
      display: values.pressure_bar.toFixed(2),
      sub: `limit ${limits.max_pressure_bar.toFixed(1)} bar · ${source}`,
      tone: toneAgainstLimit(values.pressure_bar, limits.max_pressure_bar),
      fraction: fractionOf(values.pressure_bar, limits.max_pressure_bar),
    },
    {
      key: 'feed',
      label: 'Feed flow',
      display: values.feed_flow_lpm.toFixed(0),
      sub: `L/min · ${source}`,
      tone: values.pump_running ? 'ok' : 'idle',
      fraction: null,
    },
    {
      key: 'level',
      label: 'Level',
      display: values.level_pct.toFixed(1),
      sub: `limit ${limits.max_level_pct.toFixed(0)} % · ${source}`,
      tone: toneAgainstLimit(values.level_pct, limits.max_level_pct),
      fraction: fractionOf(values.level_pct, limits.max_level_pct),
    },
    {
      key: 'cooling',
      label: 'Cooling',
      display: plant.config.cooling_pct.toFixed(0),
      sub: 'jacket duty % · configured',
      tone: plant.config.cooling_pct <= 0 ? 'crit' : plant.config.cooling_pct < 50 ? 'warn' : 'ok',
      fraction: plant.config.cooling_pct,
    },
    {
      key: 'valve',
      label: 'Valve',
      display: plant.config.valve_position_pct.toFixed(0),
      sub: `outlet ${values.outlet_flow_lpm.toFixed(0)} L/min · ${source}`,
      tone: 'ok',
      fraction: plant.config.valve_position_pct,
    },
    {
      key: 'pump',
      label: 'Pump',
      display: values.pump_running ? 'Running' : 'Stopped',
      sub: values.pump_running ? 'P-101 · live' : 'P-101 · stopped',
      tone: values.pump_running ? 'ok' : 'idle',
      fraction: values.pump_running ? 100 : 0,
    },
  ]

  const gridColumns =
    columns === 4 ? 'grid-cols-2 sm:grid-cols-4' : columns === 3 ? 'grid-cols-2 sm:grid-cols-3' : 'grid-cols-2'

  return (
    <div className={`grid gap-2 ${gridColumns}`}>
      {metrics.map((metric) => (
        <div
          key={metric.key}
          className="min-w-0 rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2"
        >
          <p className="truncate text-[10px] tracking-wide text-slate-500 uppercase">{metric.label}</p>
          <p className={`mt-0.5 truncate font-mono text-lg font-semibold ${ACCENT[metric.tone]}`}>
            {metric.display}
          </p>
          <div className="mt-1 h-1 w-full overflow-hidden rounded bg-slate-800">
            <div
              className={`h-full transition-[width] duration-500 ${RAIL[metric.tone]}`}
              style={{ width: `${metric.fraction ?? 0}%` }}
            />
          </div>
          <p className={`mt-1 truncate font-mono ${compact ? 'text-[10px]' : 'text-[11px]'} text-slate-500`}>
            {metric.sub}
          </p>
        </div>
      ))}
    </div>
  )
}
