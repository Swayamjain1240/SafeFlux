import { useEffect, useMemo, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { StatePanel } from '../components/ui/StatePanel'
import { Panel } from '../components/ui/Panel'
import { StatusBadge } from '../components/ui/StatusBadge'
import { TabBar, type TabItem } from '../components/ui/TabBar'
import { InstrumentTile } from '../components/ui/Instrument'
import { IconAlert, IconChevronRight } from '../components/ui/Icons'
import { useFailureDetail } from '../hooks/useAnalyses'
import { buildSequenceSteps, hasRecordedViolation, revealSequence } from '../animation/failureSequence'
import { useReducedMotion } from '../animation/useReducedMotion'
import type { FailureDetail, SafeguardTiming } from '../types/analysis'

/**
 * Failure detail (Part 9) — one failing scenario's full evidence.
 *
 * Every number here was produced by the Part 4 simulator through the Part 5
 * safety engine for this exact case; the page re-simulates server-side and
 * draws the returned trajectories as they came back. The page is tabbed so it
 * stays one viewport at any size: trajectories, limits/peaks, the recorded
 * finding sequence and safeguard timing are four panels, not one long scroll.
 *
 * Visual transformation: the violation leads — a critical banner, the recorded
 * sequence revealed step by step (GSAP, skipped entirely under reduced motion),
 * and traces drawn with the engineering palette.
 */

type View = 'trajectories' | 'limits' | 'sequence' | 'safeguards'

const VIEWS: readonly TabItem<View>[] = [
  { id: 'trajectories', label: 'Trajectories' },
  { id: 'limits', label: 'Limits & peaks' },
  { id: 'sequence', label: 'Recorded sequence' },
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

const TONE_STROKE: Record<string, string> = {
  crit: '#f43f5e',
  warn: '#f59e0b',
  ok: '#34d399',
  idle: '#00d9ff',
}

/** Compact SVG trace: one series, its configured limit and the real points. */
function TrajectoryChart({
  times,
  values,
  limit,
  label,
  unit,
  violationAt,
}: {
  times: number[]
  values: number[]
  limit: number | null
  label: string
  unit: string
  violationAt: number | null
}) {
  const width = 520
  const height = 128
  const pad = { left: 8, right: 8, top: 12, bottom: 18 }
  const all = limit !== null ? [...values, limit] : values
  const min = Math.min(...all)
  const max = Math.max(...all)
  const span = max - min || 1
  const tMin = times[0] ?? 0
  const tMax = times[times.length - 1] ?? 1
  const x = (t: number) => pad.left + ((t - tMin) / (tMax - tMin || 1)) * (width - pad.left - pad.right)
  const y = (v: number) => pad.top + (1 - (v - min) / span) * (height - pad.top - pad.bottom)
  const path = values
    .map((value, index) => `${index === 0 ? 'M' : 'L'}${x(times[index]).toFixed(1)},${y(value).toFixed(1)}`)
    .join(' ')
  const peak = values.length > 0 ? Math.max(...values) : null
  const exceeded = limit !== null && peak !== null && peak > limit

  return (
    <figure className="panel-inset p-2.5">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-2 text-xs">
        <span className="font-medium text-slate-200">{label}</span>
        <span className="stat-num text-slate-500">
          peak {peak === null ? '—' : `${peak.toFixed(1)} ${unit}`}
          {limit !== null ? ` · limit ${limit} ${unit}` : ''}
        </span>
      </figcaption>
      <svg viewBox={`0 0 ${width} ${height}`} className="mt-1.5 w-full" role="img" aria-label={`${label} trajectory`}>
        {[0.25, 0.5, 0.75].map((fraction) => (
          <line
            key={fraction}
            x1={pad.left}
            x2={width - pad.right}
            y1={pad.top + fraction * (height - pad.top - pad.bottom)}
            y2={pad.top + fraction * (height - pad.top - pad.bottom)}
            stroke="rgba(30,42,56,0.6)"
            strokeWidth={1}
          />
        ))}
        {limit !== null && (
          <g>
            <line
              x1={pad.left}
              x2={width - pad.right}
              y1={y(limit)}
              y2={y(limit)}
              stroke="#f43f5e"
              strokeDasharray="5 4"
              strokeWidth={1}
            />
            <text
              x={width - pad.right}
              y={Math.max(10, y(limit) - 4)}
              textAnchor="end"
              fontSize={9}
              fill="#fb7185"
            >
              limit {limit} {unit}
            </text>
          </g>
        )}
        {violationAt !== null && tMax > tMin && (
          <line
            x1={x(violationAt)}
            x2={x(violationAt)}
            y1={pad.top}
            y2={height - pad.bottom}
            stroke="#f43f5e"
            strokeWidth={1}
            strokeDasharray="2 3"
          />
        )}
        <path d={path} fill="none" stroke={exceeded ? '#f43f5e' : '#00d9ff'} strokeWidth={1.6} />
        <text x={pad.left} y={height - 4} fontSize={9} fill="#64748b">
          {tMin}s
        </text>
        <text x={width - pad.right} y={height - 4} textAnchor="end" fontSize={9} fill="#64748b">
          {tMax}s
        </text>
      </svg>
    </figure>
  )
}

function SafeguardRow({ timing }: { timing: SafeguardTiming }) {
  const fmt = (value: number | null) => (value === null ? '—' : `${value}s`)
  const late = timing.prevented === false
  const tone = timing.prevented === null ? 'idle' : late ? 'crit' : 'ok'
  return (
    <li className="panel-inset px-3 py-2 text-xs">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="font-medium text-slate-200">{timing.safeguard}</span>
        <StatusBadge
          label={
            timing.prevented === null
              ? 'not triggered'
              : late
                ? 'response after violation'
                : 'prevented in simulation'
          }
          tone={tone}
        />
      </div>
      <dl className="stat-num mt-1.5 grid grid-cols-3 gap-2 text-slate-400">
        <div>
          <dt className="text-[10px] tracking-wide text-slate-500 uppercase">trigger</dt>
          <dd>{fmt(timing.trigger_time_s)}</dd>
        </div>
        <div>
          <dt className="text-[10px] tracking-wide text-slate-500 uppercase">response</dt>
          <dd>{fmt(timing.response_time_s)}</dd>
        </div>
        <div>
          <dt className="text-[10px] tracking-wide text-slate-500 uppercase">violation</dt>
          <dd>{fmt(timing.violation_time_s)}</dd>
        </div>
      </dl>
      <p className="mt-1 text-[11px] text-slate-500">{timing.note}</p>
    </li>
  )
}

/**
 * The recorded finding sequence: what the safety engine produced for this case,
 * in its own timestamp order. The reveal is the only motion on the page.
 */
function SequenceReveal({ detail }: { detail: FailureDetail }) {
  const reducedMotion = useReducedMotion()
  const listRef = useRef<HTMLOListElement | null>(null)
  const steps = useMemo(() => buildSequenceSteps(detail.findings), [detail.findings])

  useEffect(() => {
    const list = listRef.current
    if (!list) return
    const nodes = Array.from(list.querySelectorAll<HTMLElement>('[data-sequence-step]'))
    return revealSequence(nodes, reducedMotion)
  }, [reducedMotion, steps])

  if (steps.length === 0) {
    return <p className="text-sm text-slate-400">The engine recorded no findings for this case.</p>
  }

  return (
    <ol ref={listRef} className="flex flex-col gap-1.5">
      {steps.map((step) => (
        <li key={`${step.index}-${step.type}`} data-sequence-step className="flex items-stretch gap-2.5">
          <div className="flex shrink-0 flex-col items-center pt-1">
            <span
              aria-hidden="true"
              className="mt-1 h-2 w-2 shrink-0 rounded-full"
              style={{ backgroundColor: TONE_STROKE[step.tone] }}
            />
            <span aria-hidden="true" className="w-px flex-1 bg-edge-strong/70" />
          </div>
          <div className="panel-inset min-w-0 flex-1 px-3 py-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-sm font-medium text-slate-100">
                <span className="stat-num mr-2 text-[11px] text-slate-500">
                  {String(step.index).padStart(2, '0')}
                </span>
                {step.label}
              </span>
              <span className="flex items-center gap-2">
                <StatusBadge label={step.status} tone={step.tone === 'ok' ? 'ok' : step.tone} />
                <span className="stat-num text-[11px] text-slate-500">
                  {step.timestamp === null ? 'time not recorded' : `t + ${step.timestamp}s`}
                </span>
              </span>
            </div>
            <p className="mt-1 text-xs leading-relaxed text-slate-400">{step.message}</p>
            {step.measured !== null && step.limit !== null && (
              <p className="stat-num mt-1 text-[11px] text-slate-500">
                measured {step.measured} · limit {step.limit}
              </p>
            )}
          </div>
        </li>
      ))}
    </ol>
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

  if (detailQuery.isLoading) {
    return (
      <StatePanel
        title="Simulating this case…"
        hint="The backend re-runs the real scenario for this page."
      />
    )
  }
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

  const times = detail.series.time_s ?? []
  const criticalFailure = hasRecordedViolation(detail.findings)

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <header className="flex shrink-0 flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p
            className={`text-[10px] font-semibold tracking-[0.22em] uppercase ${
              criticalFailure ? 'text-rose-300' : 'text-amber-300'
            }`}
          >
            {criticalFailure ? 'Critical failure' : 'Failure evidence'}
          </p>
          <h1 className="truncate text-base font-semibold tracking-tight text-white sm:text-lg">
            {detail.case_label}
          </h1>
          <p className="truncate text-xs text-slate-500">
            {detail.first_violation?.message ?? 'No violation was recorded for this case.'}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge label={`status: ${detail.status}`} tone={criticalFailure ? 'crit' : 'warn'} />
          {detail.scenario.duration_s !== null && (
            <StatusBadge
              label={`${detail.scenario.duration_s}s simulated`}
              tone="idle"
              title="Simulated horizon of this case"
            />
          )}
          {detail.scenario.time_step_s !== null && (
            <StatusBadge
              label={`${detail.scenario.time_step_s}s steps`}
              tone="idle"
              title="Deterministic integration step"
            />
          )}
          <Link
            to={`/analysis/${detail.analysis_id}/investigation`}
            className="inline-flex items-center gap-1.5 rounded-md border border-edge-strong px-3 py-1.5 text-xs text-slate-200 transition hover:border-accent/40 hover:text-white"
          >
            Root cause
            <IconChevronRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </header>

      <div className="grid shrink-0 grid-cols-3 gap-2">
        {(
          [
            ['Temperature', detail.configured_limits.max_temperature_c, '°C', detail.peaks.temperature_c],
            ['Pressure', detail.configured_limits.max_pressure_bar, 'bar', detail.peaks.pressure_bar],
            ['Level', detail.configured_limits.max_level_pct, '%', detail.peaks.level_pct],
          ] as const
        ).map(([label, limit, unit, peak]) => {
          const value = peak === null || peak === undefined ? null : peak
          const ratio = value === null || limit === 0 ? 0 : (value / limit) * 100
          const breakdown = value !== null && value > limit
          return (
            <InstrumentTile
              key={label}
              label={label}
              value={value === null ? '—' : value.toFixed(1)}
              unit={unit}
              tone={breakdown ? 'crit' : 'ok'}
              rail={Math.min(120, ratio)}
              caption={`limit ${limit} ${unit}${breakdown ? ' · exceeded' : ' · within limit'}`}
            />
          )
        })}
      </div>

      <TabBar tabs={VIEWS} active={view} onChange={setView} label="Failure detail sections" />

      <Panel
        className="min-h-0 flex-1"
        bodyClassName="flex min-h-0 flex-col gap-3"
        scroll
        title={
          view === 'trajectories'
            ? 'Simulated trajectories'
            : view === 'limits'
              ? 'Limits & peaks'
              : view === 'sequence'
                ? 'Recorded finding sequence'
                : 'Safeguard events'
        }
        hint="produced by the deterministic engine for this exact case"
      >
        {view === 'trajectories' && (
          <>
            {times.length === 0 && (
              <p className="text-sm text-slate-400">No series were returned for this case.</p>
            )}
            {specs.map((spec) => {
              const values = detail.series[spec.key]
              if (!values || values.length === 0) return null
              return (
                <TrajectoryChart
                  key={spec.key}
                  times={times}
                  values={values}
                  limit={spec.limit}
                  label={spec.label}
                  unit={spec.unit}
                  violationAt={detail.first_violation?.timestamp_s ?? null}
                />
              )
            })}
            <p className="text-[11px] text-slate-500">{detail.note}</p>
          </>
        )}

        {view === 'limits' && (
          <>
            {detail.first_violation && (
              <div className="flex gap-2 rounded-md border border-rose-600/50 bg-rose-950/40 p-3 text-xs text-rose-100 glow-crit">
                <IconAlert className="mt-0.5 h-4 w-4 shrink-0 text-rose-300" />
                <div className="min-w-0">
                  <p className="font-semibold">First violation</p>
                  <p className="mt-1">{detail.first_violation.message}</p>
                  <p className="stat-num mt-1 text-rose-300/80">
                    at {detail.first_violation.timestamp_s}s · measured{' '}
                    {detail.first_violation.measured_value?.toFixed(2)} · limit{' '}
                    {detail.first_violation.limit}
                  </p>
                </div>
              </div>
            )}
            <ul className="flex flex-col gap-1.5">
              {detail.findings.map((finding, index) => (
                <li
                  key={`${finding.type}-${index}`}
                  className="panel-inset px-3 py-2 text-xs text-slate-300"
                >
                  <span className="font-medium text-slate-200">{finding.type}</span> ·{' '}
                  <StatusBadge label={finding.status} tone="idle" /> · {finding.message}
                </li>
              ))}
              {detail.findings.length === 0 && (
                <li className="text-sm text-slate-400">
                  No findings were recorded for this case.
                </li>
              )}
            </ul>
          </>
        )}

        {view === 'sequence' && (
          <>
            <p className="text-xs text-slate-500">
              Every step below is a finding the safety engine recorded for this case, shown in its
              own timestamp order. SafeFlux does not draw causal arrows it cannot evidence — the
              order is the engine's, not an interpretation.
            </p>
            <SequenceReveal detail={detail} />
          </>
        )}

        {view === 'safeguards' && (
          <>
            <p className="text-xs text-slate-500">
              Trigger / response / violation times describe the simulated response of the modelled
              safeguards, not the behaviour of a real plant.
            </p>
            <ul className="flex flex-col gap-1.5">
              {detail.safeguard_events.map((timing) => (
                <SafeguardRow key={timing.safeguard} timing={timing} />
              ))}
              {detail.safeguard_events.length === 0 && (
                <li className="text-sm text-slate-400">
                  No safeguard timings were recorded for this case.
                </li>
              )}
            </ul>
          </>
        )}
      </Panel>
    </div>
  )
}
