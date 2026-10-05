import { useMemo, useState } from 'react'
import {
  CartesianGrid,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
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

/** Cap the rendered points so a long run stays readable and cheap. */
const MAX_POINTS = 240

interface Point {
  t: number
  v: number
}

function downsample<T>(items: T[]): T[] {
  if (items.length <= MAX_POINTS) return items
  const step = items.length / MAX_POINTS
  const out: T[] = []
  for (let i = 0; i < MAX_POINTS; i += 1) out.push(items[Math.floor(i * step)])
  return out
}

/**
 * Telemetry chart workspace (Part 6).
 *
 * Switchable chart tabs (Temperature / Pressure / Level / Flow) keep four
 * series in one panel so the page stays inside a single viewport. Built on
 * Recharts as the stack specifies; animation is disabled because the series
 * already replays frame by frame and `prefers-reduced-motion` must be honoured
 * without extra configuration.
 */
export function TelemetryChart({ frames }: { frames: StreamFrame[] }) {
  const [active, setActive] = useState(TABS[0].id)
  const tab = TABS.find((item) => item.id === active) ?? TABS[0]

  const points: Point[] = useMemo(() => {
    const rows: Point[] = []
    for (const frame of frames) {
      const value = frame.values[tab.key]
      if (value === undefined) continue
      rows.push({ t: frame.time_s, v: value })
    }
    return downsample(rows)
  }, [frames, tab.key])

  const latest = frames.length ? frames[frames.length - 1] : null
  const limit = tab.limitKey && latest ? latest.limits[tab.limitKey] : undefined
  const near = tab.limitKey && latest ? latest.near_limits[tab.limitKey] : undefined
  const current = points.length ? points[points.length - 1].v : undefined

  const bounds = useMemo(() => {
    if (points.length === 0) return null
    const candidates = points.map((point) => point.v)
    let min = Math.min(...candidates)
    let max = Math.max(...candidates)
    if (limit !== undefined) {
      min = Math.min(min, limit)
      max = Math.max(max, limit)
    }
    if (min === max) {
      min -= 1
      max += 1
    }
    const pad = (max - min) * 0.08
    return [min - pad, max + pad] as [number, number]
  }, [points, limit])

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60">
      <div className="flex shrink-0 flex-wrap items-center justify-between gap-2 border-b border-slate-800 px-3 py-2">
        <div className="flex flex-wrap gap-1" role="tablist" aria-label="Chart series">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={item.id === active}
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
        <span className="font-mono text-xs text-slate-400">
          {current === undefined ? '—' : `${current.toFixed(1)} ${tab.unit}`}
        </span>
      </div>

      <div className="min-h-0 flex-1 p-2">
        {bounds ? (
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={points} margin={{ top: 8, right: 10, bottom: 4, left: 0 }}>
              <CartesianGrid stroke="#1e293b" strokeDasharray="3 3" />
              <XAxis
                dataKey="t"
                type="number"
                domain={['dataMin', 'dataMax']}
                tick={{ fill: '#64748b', fontSize: 10 }}
                tickLine={false}
                axisLine={{ stroke: '#1e293b' }}
                minTickGap={40}
              />
              <YAxis
                domain={bounds}
                tick={{ fill: '#64748b', fontSize: 10 }}
                tickLine={false}
                axisLine={false}
                width={44}
              />
              <Tooltip
                contentStyle={{
                  background: '#0f172a',
                  border: '1px solid #1e293b',
                  borderRadius: 8,
                  fontSize: 11,
                }}
                labelStyle={{ color: '#94a3b8' }}
                formatter={(value) => [`${Number(value).toFixed(2)} ${tab.unit}`, tab.label]}
                labelFormatter={(value) => `t = ${Number(value).toFixed(0)} s`}
              />
              {near !== undefined && (
                <ReferenceLine
                  y={near}
                  stroke="#f59e0b"
                  strokeDasharray="4 3"
                  label={{ value: 'near', position: 'insideTopRight', fill: '#f59e0b', fontSize: 9 }}
                />
              )}
              {limit !== undefined && (
                <ReferenceLine
                  y={limit}
                  stroke="#f43f5e"
                  strokeDasharray="5 3"
                  label={{ value: 'limit', position: 'insideTopRight', fill: '#f43f5e', fontSize: 9 }}
                />
              )}
              <Line
                type="monotone"
                dataKey="v"
                stroke="#22d3ee"
                strokeWidth={1.5}
                dot={false}
                isAnimationActive={false}
              />
            </LineChart>
          </ResponsiveContainer>
        ) : (
          <div className="flex h-full items-center justify-center px-3 text-center text-xs text-slate-500">
            No telemetry yet — run a scenario to populate this chart.
          </div>
        )}
      </div>
    </div>
  )
}
