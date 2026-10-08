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
import { Panel } from '../ui/Panel'

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

/* Chart palette mirrors the design tokens in index.css (Recharts needs
   literals): accent #00d9ff, warn #f59e0b, crit #f43f5e, edge #1e2a38. */
const CHART = {
  accent: '#00d9ff',
  warn: '#f59e0b',
  crit: '#f43f5e',
  grid: '#1e2a38',
  axis: '#64748b',
  tooltipBg: '#0b0f14',
} as const

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
 * Telemetry chart workspace (Part 6, restyled).
 *
 * Switchable series tabs keep four channels in one panel so the page stays
 * inside a single viewport. The configured limit and near-limit band are drawn
 * from the frame's own thresholds, and the first simulated violation is marked
 * from the streamed frames — never inferred client-side. Animation is disabled
 * because the series already replays frame by frame.
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

  const firstViolation = useMemo(() => {
    const hit = frames.find((frame) => frame.status === 'violation')
    return hit ? hit.time_s : null
  }, [frames])

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
    // Snap the padded domain to a shared step: axis ticks must never carry
    // floating-point noise (a padded raw float prints like 15.000000678509329
    // and the clipped axis then reads as meaningless digits).
    const magnitude = Math.max(Math.abs(min - pad), Math.abs(max + pad))
    const step = magnitude >= 100 ? 1 : magnitude >= 10 ? 0.5 : 0.05
    return [Math.floor((min - pad) / step) * step, Math.ceil((max + pad) / step) * step] as [
      number,
      number,
    ]
  }, [points, limit])

  /** Axis ticks: fixed, readable precision instead of the raw float. */
  function formatTick(value: number): string {
    const abs = Math.abs(value)
    const decimals = abs >= 100 ? 0 : abs >= 10 ? 1 : 2
    return value.toFixed(decimals)
  }

  return (
    <Panel
      title="Telemetry"
      hint="replay of the deterministic run"
      className="h-full"
      bodyClassName="p-0"
      actions={
        <span className="stat-num text-xs text-slate-300">
          {current === undefined ? '—' : `${current.toFixed(1)} ${tab.unit}`}
        </span>
      }
    >
      <div className="flex h-full min-h-0 flex-col">
        <div className="flex shrink-0 flex-wrap gap-1 border-b border-edge/70 px-2 py-1.5" role="tablist" aria-label="Chart series">
          {TABS.map((item) => (
            <button
              key={item.id}
              type="button"
              role="tab"
              aria-selected={item.id === active}
              onClick={() => setActive(item.id)}
              className={[
                'rounded px-2.5 py-1 text-xs font-medium transition',
                item.id === active
                  ? 'bg-accent/12 text-accent ring-1 ring-accent/25'
                  : 'text-slate-400 hover:text-slate-200',
              ].join(' ')}
            >
              {item.label}
            </button>
          ))}
          {firstViolation !== null && (
            <span className="ml-auto self-center pr-1 text-[10px] text-rose-300">
              first violation at t = {firstViolation.toFixed(0)}s
            </span>
          )}
        </div>

        <div className="min-h-0 flex-1 p-2">
          {bounds ? (
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={points} margin={{ top: 8, right: 10, bottom: 4, left: 0 }}>
                <CartesianGrid stroke={CHART.grid} strokeDasharray="3 3" />
                <XAxis
                  dataKey="t"
                  type="number"
                  domain={['dataMin', 'dataMax']}
                  tick={{ fill: CHART.axis, fontSize: 10 }}
                  tickLine={false}
                  axisLine={{ stroke: CHART.grid }}
                  minTickGap={40}
                />
                <YAxis
                  domain={bounds}
                  tick={{ fill: CHART.axis, fontSize: 10 }}
                  tickLine={false}
                  axisLine={false}
                  width={48}
                  tickFormatter={formatTick}
                />
                <Tooltip
                  contentStyle={{
                    background: CHART.tooltipBg,
                    border: `1px solid ${CHART.grid}`,
                    borderRadius: 6,
                    fontSize: 11,
                  }}
                  labelStyle={{ color: '#94a3b8' }}
                  formatter={(value) => [`${Number(value).toFixed(2)} ${tab.unit}`, tab.label]}
                  labelFormatter={(value) => `t = ${Number(value).toFixed(0)} s`}
                />
                {near !== undefined && (
                  <ReferenceLine
                    y={near}
                    stroke={CHART.warn}
                    strokeDasharray="4 3"
                    label={{ value: 'near', position: 'insideTopRight', fill: CHART.warn, fontSize: 9 }}
                  />
                )}
                {limit !== undefined && (
                  <ReferenceLine
                    y={limit}
                    stroke={CHART.crit}
                    strokeDasharray="5 3"
                    label={{ value: 'limit', position: 'insideTopRight', fill: CHART.crit, fontSize: 9 }}
                  />
                )}
                {firstViolation !== null && (
                  <ReferenceLine
                    x={firstViolation}
                    stroke={CHART.crit}
                    strokeDasharray="2 3"
                    label={{ value: 'violation', position: 'insideBottomLeft', fill: CHART.crit, fontSize: 9 }}
                  />
                )}
                <Line
                  type="monotone"
                  dataKey="v"
                  stroke={CHART.accent}
                  strokeWidth={1.6}
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
    </Panel>
  )
}
