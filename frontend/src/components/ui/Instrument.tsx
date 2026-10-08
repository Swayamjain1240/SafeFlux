/**
 * Instrumentation primitives (visual transformation).
 *
 * `InstrumentTile` renders one measured quantity the way a control-room panel
 * does: uppercase label, mono numeral with unit, optional limit line and
 * trend. `Gauge` renders the same quantity as a restrained radial arc with the
 * configured limit marked. Both are presentation only — every number comes from
 * the caller, which gets it from the deterministic backend.
 */

import type { Tone } from '../../dashboard/viewState'

const TONE_TEXT: Record<Tone, string> = {
  ok: 'text-safe',
  warn: 'text-warn',
  crit: 'text-crit',
  idle: 'text-slate-300',
}

const TONE_STROKE: Record<Tone, string> = {
  ok: '#34d399',
  warn: '#f59e0b',
  crit: '#f43f5e',
  idle: '#00d9ff',
}

export function InstrumentTile({
  label,
  value,
  unit,
  tone = 'idle',
  caption,
  delta,
  sparkline,
  rail,
  className = '',
}: {
  label: string
  value: string
  unit?: string
  tone?: Tone
  caption?: string
  /** Signed change text, e.g. "+1.2". */
  delta?: string
  /** Recent values for the trend line (oldest → newest). */
  sparkline?: number[]
  /** 0-100 fill against a configured limit (percentage of the limit). */
  rail?: number
  className?: string
}) {
  return (
    <div className={`panel-inset flex min-h-0 flex-col justify-between px-2.5 py-2 ${className}`}>
      <div className="flex items-baseline justify-between gap-2">
        <p className="truncate text-[10px] font-semibold tracking-[0.16em] text-slate-500 uppercase">
          {label}
        </p>
        {delta && <span className={`stat-num text-[10px] ${TONE_TEXT[tone]}`}>{delta}</span>}
      </div>

      <div className="mt-1 flex items-end justify-between gap-2">
        <p className={`stat-num text-xl leading-none font-medium ${TONE_TEXT[tone]}`}>{value}</p>
        {unit && <span className="pb-0.5 text-[10px] text-slate-500">{unit}</span>}
      </div>

      {sparkline && sparkline.length > 1 && (
        <Sparkline values={sparkline} stroke={TONE_STROKE[tone]} className="mt-1.5 h-5 w-full" />
      )}

      {rail !== undefined && (
        <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-edge/70">
          <div
            className="h-full transition-[width] duration-500"
            style={{
              width: `${Math.max(0, Math.min(100, rail))}%`,
              backgroundColor: TONE_STROKE[tone],
            }}
          />
        </div>
      )}

      {caption && <p className="mt-1 truncate text-[10px] text-slate-500">{caption}</p>}
    </div>
  )
}

/** Minimal trend line — no axes, no tooltip; it exists to show direction. */
function Sparkline({
  values,
  stroke,
  className = '',
}: {
  values: number[]
  stroke: string
  className?: string
}) {
  const min = Math.min(...values)
  const max = Math.max(...values)
  const span = max - min || 1
  const points = values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * 100
      const y = 100 - ((value - min) / span) * 100
      return `${x.toFixed(2)},${y.toFixed(2)}`
    })
    .join(' ')

  return (
    <svg
      viewBox="0 0 100 100"
      preserveAspectRatio="none"
      className={className}
      aria-hidden="true"
      focusable="false"
    >
      <polyline
        points={points}
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
        opacity={0.85}
      />
    </svg>
  )
}

/**
 * Radial gauge: value against a known maximum, with the configured limit drawn
 * as a tick. Colour follows the safety tone supplied by the caller.
 */
export function Gauge({
  label,
  value,
  max,
  unit,
  limit,
  tone = 'idle',
  size = 132,
  className = '',
}: {
  label: string
  value: number
  max: number
  unit: string
  limit?: number
  tone?: Tone
  size?: number
  className?: string
}) {
  const clamped = Math.max(0, Math.min(max, value))
  const fraction = max > 0 ? clamped / max : 0
  const limitFraction = limit !== undefined && max > 0 ? Math.max(0, Math.min(1, limit / max)) : null

  const radius = 46
  const circumference = Math.PI * radius // half circle
  const stroke = 6
  const arc = `${fraction * circumference} ${circumference}`

  const angleFor = (f: number) => Math.PI - f * Math.PI
  const limitPoint = limitFraction === null ? null : angleFor(limitFraction)

  return (
    <div className={`panel-inset flex flex-col items-center px-2 py-2.5 ${className}`}>
      <svg viewBox="0 0 120 72" width={size} height={size * 0.6} aria-hidden="true" focusable="false">
        <path
          d={`M 14 60 A ${radius} ${radius} 0 0 1 106 60`}
          fill="none"
          stroke="rgba(30,42,56,0.9)"
          strokeWidth={stroke}
          strokeLinecap="round"
        />
        <path
          d={`M 14 60 A ${radius} ${radius} 0 0 1 106 60`}
          fill="none"
          stroke={TONE_STROKE[tone]}
          strokeWidth={stroke}
          strokeLinecap="round"
          strokeDasharray={arc}
          opacity={0.95}
        />
        {limitPoint !== null && (
          <line
            x1={60 + Math.cos(limitPoint) * (radius - stroke)}
            y1={60 - Math.sin(limitPoint) * (radius - stroke)}
            x2={60 + Math.cos(limitPoint) * (radius + stroke)}
            y2={60 - Math.sin(limitPoint) * (radius + stroke)}
            stroke="#f59e0b"
            strokeWidth={1.6}
          />
        )}
      </svg>

      <p className="stat-num -mt-3 text-lg leading-none font-medium text-slate-100">
        {value.toFixed(2)}
        <span className="ml-1 text-[10px] font-normal text-slate-500">{unit}</span>
      </p>
      <p className="mt-1 text-[10px] font-semibold tracking-[0.16em] text-slate-500 uppercase">
        {label}
      </p>
      {limit !== undefined && (
        <p className="mt-0.5 text-[10px] text-slate-500">
          limit <span className="stat-num text-slate-400">{limit.toFixed(2)}</span> {unit}
        </p>
      )}
    </div>
  )
}
