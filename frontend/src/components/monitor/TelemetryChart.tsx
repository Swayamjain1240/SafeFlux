import { useMemo, useState } from 'react'
import type { StreamFrame } from '../../telemetry/streamState'

interface TabDef {
  id: string
  label: string
  key: string
  limitKey?: 'temperature_c' | 'pressure_bar' | 'level_pct'
  unit: string
}

const TABS: TabDef[] = [
  { id: 'temperature', label: 'Temperature', key: 'temperature_c', limitKey: 'temperature_c', unit: '°C' },
  { id: 'pressure', label: 'Pressure', key: 'pressure_bar', limitKey: 'pressure_bar', unit: 'bar' },
  { id: 'level', label: 'Level', key: 'level_pct', limitKey: 'level_pct', unit: '%' },
  { id: 'flow', label: 'Flow', key: 'outlet_flow_lpm', unit: 'L/min' },
]

const MAX_POINTS = 220

const STATUS_DOT: Record<string, string> = {
  safe: 'bg-emerald-400',
  near_limit: 'bg-amber-400',
  violation: 'bg-rose-500',
  safeguard_activated: 'bg-cyan-400',
}

function downsample(values: number[]): number[] {
  if (values.length <= MAX_POINTS) return values
  const step = values.length / MAX_POINTS
  const out: number[] = []
  for (let i = 0; i < MAX_POINTS; i += 1) {
    out.push(values[Math.floor(i * step)])
  }
  return out
}

/** Minimal dependency-free SVG line chart — no chart library needed. */
export function TelemetryChart({ frames }: { frames: StreamFrame[] }) {
  const [active, setActive] = useState(TABS[0].id)
  const tab = TABS.find((item) => item.id === active) ?? TABS[0]
  const latest = frames.length ? frames[frames.length - 1] : null

  const geometry = useMemo(() => {
    const raw = frames.map((frame) => frame.values[tab.key]).filter((v) => v !== undefined)
    const series = downsample(raw)
    if (series.length < 2) return null
    const limit = tab.limitKey ? frames[frames.length - 1]?.limits[tab.limitKey] : undefined
    const near = tab.limitKey ? frames[frames.length - 1]?.near_limits[tab.limitKey] : undefined
    const candidates = [...series]
    if (limit !== undefined) candidates.push(limit)
    if (near !== undefined) candidates.push(near)
    let min = Math.min(...candidates)
    let max = Math.max(...candidates)
    if (min === max) {
      min -= 1
      max += 1
    }
    const pad = (max - min) * 0.08
    min -= pad
    max += pad
    const y = (value: number) => 100 - ((value - min) / (max - min)) * 100
    const points = series
      .map((value, index) => `${((index / (series.length - 1)) * 100).toFixed(2)},${y(value).toFixed(2)}`)
      .join(' ')
    return { points, min, max, limit, near, y }
  }, [frames, tab])

  const current = latest?.values[tab.key]

  return (
    <div className="flex min-h-0 flex-1 flex-col rounded-xl border border-slate-800 bg-slate-900/60">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 px-3 py-2">
        <div className="flex gap-1">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setActive(item.id)}
              className={[
                'rounded-md px-2.5 py-1 text-xs transition',
                item.id === active
                  ? 'bg-cyan-500/15 text-cyan-300 ring-1 ring-cyan-500/30'
                  : 'text-slate-400 hover:text-slate-200',
              ].join(' ')}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="flex items-center gap-2 text-xs text-slate-400">
          <span
            aria-hidden="true"
            className={`h-2 w-2 rounded-full ${STATUS_DOT[latest?.status ?? 'safe'] ?? 'bg-slate-500'}`}
          />
          <span className="font-mono">
            {current === undefined ? '—' : `${current.toFixed(1)} ${tab.unit}`}
          </span>
        </div>
      </div>

      <div className="relative min-h-0 flex-1 p-3">
        {geometry ? (
          <svg
            viewBox="0 0 100 100"
            preserveAspectRatio="none"
            className="h-full w-full"
            role="img"
            aria-label={`${tab.label} telemetry chart`}
          >
            {geometry.near !== undefined && (
              <line
                x1="0"
                x2="100"
                y1={geometry.y(geometry.near)}
                y2={geometry.y(geometry.near)}
                stroke="#f59e0b"
                strokeWidth="0.4"
                strokeDasharray="2 2"
                vectorEffect="non-scaling-stroke"
              />
            )}
            {geometry.limit !== undefined && (
              <line
                x1="0"
                x2="100"
                y1={geometry.y(geometry.limit)}
                y2={geometry.y(geometry.limit)}
                stroke="#f43f5e"
                strokeWidth="0.4"
                strokeDasharray="3 2"
                vectorEffect="non-scaling-stroke"
              />
            )}
            <polyline
              points={geometry.points}
              fill="none"
              stroke="#22d3ee"
              strokeWidth="0.8"
              vectorEffect="non-scaling-stroke"
            />
          </svg>
        ) : (
          <div className="flex h-full items-center justify-center text-xs text-slate-500">
            No telemetry yet — run a scenario to populate the stream.
          </div>
        )}
      </div>

      {geometry && (
        <div className="flex justify-between border-t border-slate-800 px-3 py-1.5 font-mono text-[10px] text-slate-500">
          <span>{geometry.min.toFixed(1)}</span>
          {geometry.limit !== undefined && <span className="text-rose-400">limit {geometry.limit}</span>}
          <span>{geometry.max.toFixed(1)}</span>
        </div>
      )}
    </div>
  )
}
