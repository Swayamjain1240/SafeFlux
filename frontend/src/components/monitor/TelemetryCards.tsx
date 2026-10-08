import type { StreamFrame } from '../../telemetry/streamState'
import { InstrumentTile } from '../ui/Instrument'
import type { Tone } from '../../dashboard/viewState'

type CardTone = 'safe' | 'near' | 'violation' | 'idle'

interface Metric {
  key: string
  label: string
  unit: string
  limitKey?: 'temperature_c' | 'pressure_bar' | 'level_pct'
}

const METRICS: Metric[] = [
  { key: 'temperature_c', label: 'Temperature', unit: '°C', limitKey: 'temperature_c' },
  { key: 'pressure_bar', label: 'Pressure', unit: 'bar', limitKey: 'pressure_bar' },
  { key: 'level_pct', label: 'Level', unit: '%', limitKey: 'level_pct' },
  { key: 'outlet_flow_lpm', label: 'Outlet flow', unit: 'L/min' },
]

const TONE: Record<CardTone, Tone> = {
  safe: 'ok',
  near: 'warn',
  violation: 'crit',
  idle: 'idle',
}

function toneFor(frame: StreamFrame | null, metric: Metric): CardTone {
  if (!frame || !metric.limitKey) return 'idle'
  const value = frame.values[metric.key]
  if (value === undefined) return 'idle'
  const limit = frame.limits[metric.limitKey]
  const near = frame.near_limits[metric.limitKey]
  if (value > limit) return 'violation'
  if (value >= near) return 'near'
  return 'safe'
}

/**
 * Live instrumentation (Part 5, restyled): the four streamed quantities with
 * their configured limits. When a sensor fault is active the observed reading
 * is shown next to the true simulated value — the model state is never
 * replaced by the sensor reading.
 */
export function TelemetryCards({ frame }: { frame: StreamFrame | null }) {
  return (
    <div className="grid shrink-0 grid-cols-2 gap-2 lg:grid-cols-4">
      {METRICS.map((metric) => {
        const value = frame?.values[metric.key]
        const observed = frame?.observed[metric.key]
        const cardTone = toneFor(frame, metric)
        const limit = metric.limitKey ? frame?.limits[metric.limitKey] : undefined
        const ratio =
          limit && value !== undefined ? Math.min(100, Math.max(0, (value / limit) * 100)) : 0

        const caption = [
          limit !== undefined ? `limit ${limit}` : 'no configured limit',
          observed !== undefined && value !== undefined && observed !== value
            ? `sensor ${observed.toFixed(1)}`
            : null,
        ]
          .filter(Boolean)
          .join(' · ')

        return (
          <InstrumentTile
            key={metric.key}
            label={metric.label}
            value={value === undefined ? '—' : value.toFixed(1)}
            unit={metric.unit}
            tone={TONE[cardTone]}
            caption={caption}
            rail={limit !== undefined ? ratio : undefined}
          />
        )
      })}
    </div>
  )
}
