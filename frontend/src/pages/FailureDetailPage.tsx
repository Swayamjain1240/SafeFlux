import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { StatePanel } from '../components/ui/StatePanel'
import { useFailureDetail } from '../hooks/useAnalyses'
import type { FailureDetail, SafeguardTiming } from '../types/analysis'

/**
 * Failure detail (Part 9) — one failing scenario's full evidence.
 *
 * Every number here was produced by the Part 4 simulator through the Part 5
 * safety engine for this exact case; the page re-simulates server-side and
 * draws the returned trajectories as they came back. The page is tabbed so it
 * stays one viewport at any size: trajectories, limits/peaks and safeguard
 * timing are three panels, not one long scroll.
 */

type View = 'trajectories' | 'limits' | 'safeguards'

const VIEWS: { id: View; label: string }[] = [
  { id: 'trajectories', label: 'Trajectories' },
  { id: 'limits', label: 'Limits & peaks' },
  { id: 'safeguards', label: 'Safeguard events' },
]

interface SeriesSpec {
  key: string
  label: string
  unit: string
  limit: number | null
}

const SERIES_SPECS: SeriesSpec[] = [
  { key: 'true_temperature_c', label: 'Temperature', unit: '°C', limit: null },
  { key: 'true_pressure_bar', label: 'Pressure', unit: 'bar', limit: null },
  { key: 'level_pct', label: 'Level', unit: '%', limit: null },
]

/** A compact SVG line chart: one series, its configured limit, real points. */
function TrajectoryChart({
  times,
  values,
  limit,
  label,
  unit,
}: {
  times: number[]
  values: number[]
  limit: number | null
  label: string
  unit: string
}) {
  const width = 520
  const height = 130
  const pad = { left: 6, right: 6, top: 10, bottom: 16 }
  const all = limit !== null ? [...values, limit] : values
  const min = Math.min(...all)
  const max = Math.max(...all)
  const span = max - min || 1
  const x = (t: number) => {
    const tMin = times[0] ?? 0
    const tMax = times[times.length - 1] ?? 1
    return pad.left + ((t - tMin) / (tMax - tMin || 1)) * (width - pad.left - pad.right)
  }
  const y = (v: number) => pad.top + (1 - (v - min) / span) * (height - pad.top - pad.bottom)
  const path = values.map((value, index) => `${index === 0 ? 'M' : 'L'}${x(times[index]).toFixed(1)},${y(value).toFixed(1)}`).join(' ')
  const peak = values.length > 0 ? Math.max(...values) : null
  return (
    <figure className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
      <figcaption className="flex items-baseline justify-between text-xs">
        <span className="font-medium text-slate-200">{label}</span>
        <span className="text-slate-500">
          peak {peak === null ? '—' : `${peak.toFixed(1)} ${unit}`}
          {limit !== null ? ` · limit ${limit} ${unit}` : ''}
        </span>
      </figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} className="mt-2 w-full" role="img" aria-label={`${label} trajectory`}>
        {limit !== null && (
          <g>
            <line x1={pad.left} x2={width - pad.right} y1={y(limit)} y2={y(limit)} stroke="#f43f5e" strokeDasharray="4 3" strokeWidth={1} />
            <text x={width - pad.right} y={Math.max(9, y(limit) - 4)} textAnchor="end" fontSize={9} fill="#fb7185">
              configured limit {limit} {unit}
            </text>
          </g>
        )}
        <path d={path} fill="none" stroke="#22d3ee" strokeWidth={1.5} />
      </svg>
    </figure>
  )
}

function SafeguardRow({ timing }: { timing: SafeguardTiming }) {
  const fmt = (value: number | null) => (value === null ? '—' : `${value}s`)
  const late = timing.prevented === false
  return (
    <li className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium text-slate-200">{timing.safeguard}</span>
        <span className={late ? 'text-rose-300' : 'text-emerald-300'}>
          {timing.prevented === null ? 'not triggered' : late ? 'response after simulated violation' : 'prevented in simulation'}
        </span>
      </div>
      <dl className="mt-1 grid grid-cols-3 gap-2 text-slate-400">
        <div>trigger {fmt(timing.trigger_time_s)}</div>
        <div>response {fmt(timing.response_time_s)}</div>
        <div>violation {fmt(timing.violation_time_s)}</div>
      </dl>
      <p className="mt-1 text-[11px] text-slate-500">{timing.note}</p>
    </li>
  )
}

export default function FailureDetailPage() {
  const { id, failureId } = useParams<{ id: string; failureId: string }>()
  const detailQuery = useFailureDetail(id, failureId)
  const detail = detailQuery.data
  const [view, setView] = useState<View>('trajectories')

  const specs = useMemo<SeriesSpec[]>(() => {
    if (!detail) return SERIES_SPECS
    const limits = detail.configured_limits
    return SERIES_SPECS.map((spec) => ({
      ...spec,
      limit:
        spec.key === 'true_temperature_c'
          ? limits.max_temperature_c
          : spec.key === 'true_pressure_bar'
            ? limits.max_pressure_bar
            : limits.max_level_pct,
    }))
  }, [detail])

  if (detailQuery.isLoading) return <StatePanel title="Simulating this case…" hint="The backend re-runs the real scenario for this page." />
  if (detailQuery.isError || !detail) {
    return (
      <StatePanel
        tone="crit"
        title="Failure not found"
        hint="It may belong to another account or analysis."
        action={{ label: 'Back', onAct: () => window.history.back() }}
      />
    )
  }
  return <Loaded detail={detail} specs={specs} view={view} setView={setView} />
}

function Loaded({
  detail,
  specs,
  view,
  setView,
}: {
  detail: FailureDetail
  specs: SeriesSpec[]
  view: View
  setView: (view: View) => void
}) {
  const times = detail.series.time_s ?? []
  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <header className="shrink-0">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <h1 className="truncate text-lg font-semibold text-slate-100">{detail.case_label}</h1>
            <p className="text-xs text-slate-400">
              status <span className="font-medium text-rose-300">{detail.status}</span>
              {detail.scenario.duration_s !== null ? ` · ${detail.scenario.duration_s}s simulated` : ''}
              {detail.scenario.time_step_s !== null ? ` at ${detail.scenario.time_step_s}s steps` : ''}
            </p>
          </div>
          <Link
            to={`/analysis/${detail.analysis_id}/investigation`}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-200 transition hover:bg-slate-800"
          >
            Root-cause investigation
          </Link>
        </div>
      </header>

      <nav className="flex shrink-0 gap-1 overflow-x-auto rounded-lg border border-slate-800 bg-slate-900/60 p-1" role="tablist" aria-label="Failure detail sections">
        {VIEWS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={view === tab.id}
            onClick={() => setView(tab.id)}
            className={[
              'flex-1 rounded-md px-3 py-1.5 text-xs font-medium whitespace-nowrap transition',
              view === tab.id
                ? 'bg-cyan-500/15 text-cyan-300 ring-1 ring-cyan-500/30'
                : 'text-slate-400 hover:text-slate-200',
            ].join(' ')}
          >
            {tab.label}
          </button>
        ))}
      </nav>

      <section className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-slate-800 bg-slate-900/50 p-4">
        {view === 'trajectories' && (
          <div className="flex flex-col gap-3">
            {times.length === 0 && <p className="text-sm text-slate-400">No series were returned for this case.</p>}
            {specs.map((spec) => {
              const values = detail.series[spec.key]
              if (!values || values.length === 0) return null
              return (
                <TrajectoryChart key={spec.key} times={times} values={values} limit={spec.limit} label={spec.label} unit={spec.unit} />
              )
            })}
            <p className="text-[11px] text-slate-500">{detail.note}</p>
          </div>
        )}

        {view === 'limits' && (
          <div className="flex flex-col gap-3">
            <div className="grid grid-cols-3 gap-2 text-xs">
              {(
                [
                  ['Temperature', detail.configured_limits.max_temperature_c, '°C', detail.peaks.temperature_c],
                  ['Pressure', detail.configured_limits.max_pressure_bar, 'bar', detail.peaks.pressure_bar],
                  ['Level', detail.configured_limits.max_level_pct, '%', detail.peaks.level_pct],
                ] as const
              ).map(([label, limit, unit, peak]) => (
                <div key={label} className="rounded-lg border border-slate-800 bg-slate-950/60 p-2 text-center">
                  <p className="text-slate-500">{label}</p>
                  <p className="mt-1 font-semibold text-slate-100">
                    {peak === null || peak === undefined ? '—' : peak.toFixed(1)} {unit}
                  </p>
                  <p className="text-[11px] text-rose-300">limit {limit} {unit}</p>
                </div>
              ))}
            </div>
            {detail.first_violation && (
              <div className="rounded-lg border border-rose-600/50 bg-rose-950/40 p-3 text-xs text-rose-100">
                <p className="font-semibold">First violation</p>
                <p className="mt-1">{detail.first_violation.message}</p>
                <p className="mt-1 text-rose-300/80">
                  at {detail.first_violation.timestamp_s}s · measured {detail.first_violation.measured_value?.toFixed(2)} · limit {detail.first_violation.limit}
                </p>
              </div>
            )}
            <ul className="flex flex-col gap-1.5">
              {detail.findings.map((finding, index) => (
                <li key={`${finding.type}-${index}`} className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2 text-xs text-slate-300">
                  <span className="font-medium text-slate-200">{finding.type}</span> · {finding.status} · {finding.message}
                </li>
              ))}
            </ul>
          </div>
        )}

        {view === 'safeguards' && (
          <div className="flex flex-col gap-3">
            <p className="text-xs text-slate-500">
              Trigger / response / violation times describe the simulated response of the modelled
              safeguards, not the behaviour of a real plant.
            </p>
            <ul className="flex flex-col gap-1.5">
              {detail.safeguard_events.map((timing) => (
                <SafeguardRow key={timing.safeguard} timing={timing} />
              ))}
              {detail.safeguard_events.length === 0 && (
                <li className="text-sm text-slate-400">No safeguard timings were recorded for this case.</li>
              )}
            </ul>
          </div>
        )}
      </section>
    </div>
  )
}
