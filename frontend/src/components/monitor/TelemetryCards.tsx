import type { StreamFrame } from '../../telemetry/streamState'

type Tone = 'safe' | 'near' | 'violation' | 'idle'

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

const TONE_CLASS: Record<Tone, string> = {
  safe: 'border-emerald-500/40 bg-emerald-500/5 text-emerald-300',
  near: 'border-amber-500/40 bg-amber-500/5 text-amber-300',
  violation: 'border-rose-500/50 bg-rose-500/10 text-rose-300',
  idle: 'border-slate-800 bg-slate-900/60 text-slate-400',
}

function toneFor(frame: StreamFrame | null, metric: Metric): Tone {
  if (!frame || !metric.limitKey) return 'idle'
  const value = frame.values[metric.key]
  if (value === undefined) return 'idle'
  const limit = frame.limits[metric.limitKey]
  const near = frame.near_limits[metric.limitKey]
  if (value > limit) return 'violation'
  if (value >= near) return 'near'
  return 'safe'
}

export function TelemetryCards({ frame }: { frame: StreamFrame | null }) {
  return (
    <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
      {METRICS.map((metric) => {
        const value = frame?.values[metric.key]
        const observed = frame?.observed[metric.key]
        const tone = toneFor(frame, metric)
        const limit = metric.limitKey ? frame?.limits[metric.limitKey] : undefined
        const ratio =
          limit && value !== undefined ? Math.min(100, Math.max(0, (value / limit) * 100)) : 0
        return (
          <div key={metric.key} className={`rounded-xl border px-3 py-2 ${TONE_CLASS[tone]}`}>
            <p className="text-[10px] tracking-wide text-slate-400 uppercase">{metric.label}</p>
            <p className="mt-0.5 font-mono text-lg font-semibold">
              {value === undefined ? '—' : value.toFixed(1)}
              <span className="ml-1 text-[10px] font-normal text-slate-500">{metric.unit}</span>
            </p>
            {limit !== undefined && (
              <div className="mt-1.5 h-1 w-full overflow-hidden rounded bg-slate-800">
                <div
                  className={
                    tone === 'violation'
                      ? 'h-full bg-rose-400'
                      : tone === 'near'
                        ? 'h-full bg-amber-400'
                        : 'h-full bg-emerald-400'
                  }
                  style={{ width: `${ratio.toFixed(1)}%` }}
                />
              </div>
            )}
            <p className="mt-1 text-[10px] text-slate-500">
              {limit !== undefined ? `limit ${limit}` : 'no configured limit'}
              {observed !== undefined && observed !== value
                ? ` · sensor ${observed.toFixed(1)}`
                : ''}
            </p>
          </div>
        )
      })}
    </div>
  )
}
