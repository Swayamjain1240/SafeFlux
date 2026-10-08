import { useEffect, useMemo, useRef } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { StatePanel } from '../components/ui/StatePanel'
import { Panel } from '../components/ui/Panel'
import { revealSequence } from '../animation/failureSequence'
import { useReducedMotion } from '../animation/useReducedMotion'
import { useResultDocument } from '../hooks/useAnalyses'
import { safeguardsView } from '../analysis/safeguardsView'
import type { SafeguardTiming } from '../types/analysis'

/**
 * Safeguard verification (Part 9).
 *
 * The page states what the simulation measured — trigger, response, violation
 * times of the *modelled* safeguards — and uses the required language: a late
 * response is "Safeguard response occurred after the simulated violation", never
 * a claim that a real plant's safeguard is unsafe.
 *
 * Visual transformation: the recorded offsets are drawn on one shared time
 * axis per safeguard, so "after the violation" is visible as an ordering, and
 * the markers carry the only motion on the page.
 */

function fmt(value: number | null): string {
  return value === null ? '—' : `${value}s`
}

type VerdictTone = 'ok' | 'late' | 'idle'

function verdictFor(timing: SafeguardTiming): { text: string; tone: VerdictTone } {
  if (timing.prevented === null)
    return { text: 'Setpoint not reached in the tested scenario.', tone: 'idle' }
  if (timing.prevented)
    return { text: 'Averted the simulated violation in the tested scenario.', tone: 'ok' }
  return { text: 'Safeguard response occurred after the simulated violation.', tone: 'late' }
}

const TONE_CLASS: Record<VerdictTone, string> = {
  ok: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300',
  late: 'border-rose-500/50 bg-rose-500/10 text-rose-300',
  idle: 'border-edge bg-surface text-slate-400',
}

/** Shared axis end: the largest recorded offset, so every marker keeps its real ratio. */
function axisEnd(timings: readonly SafeguardTiming[]): number {
  let max = 0
  for (const timing of timings) {
    for (const value of [timing.trigger_time_s, timing.response_time_s, timing.violation_time_s]) {
      if (value !== null && value > max) max = value
    }
  }
  return max > 0 ? max : 1
}

function Timeline({
  timing,
  end,
}: {
  timing: SafeguardTiming
  end: number
}) {
  const markers: { at: number; label: string; kind: 'trigger' | 'response' | 'violation' }[] = []
  if (timing.trigger_time_s !== null)
    markers.push({ at: timing.trigger_time_s, label: 'trigger', kind: 'trigger' })
  if (timing.violation_time_s !== null)
    markers.push({ at: timing.violation_time_s, label: 'violation', kind: 'violation' })
  if (timing.response_time_s !== null)
    markers.push({ at: timing.response_time_s, label: 'response', kind: 'response' })

  const colour = (kind: 'trigger' | 'response' | 'violation') =>
    kind === 'violation' ? '#f43f5e' : kind === 'trigger' ? '#f59e0b' : '#00d9ff'

  return (
    <div className="flex flex-col gap-1">
      <div className="relative h-9">
        <div aria-hidden="true" className="absolute top-4 right-0 left-0 h-px bg-edge-strong/70" />
        {markers.map((marker) => (
          <div
            key={`${marker.kind}-${marker.at}`}
            data-sequence-step
            className="absolute top-0 flex -translate-x-1/2 flex-col items-center"
            style={{ left: `${Math.min(100, (marker.at / end) * 100)}%` }}
          >
            <span className="stat-num text-[10px] text-slate-400">{marker.at}s</span>
            <span
              aria-hidden="true"
              className="mt-0.5 h-2.5 w-2.5 rounded-full ring-2 ring-void"
              style={{ backgroundColor: colour(marker.kind) }}
            />
            <span className="text-[9px] tracking-wide text-slate-500 uppercase">{marker.label}</span>
          </div>
        ))}
      </div>
      <div className="stat-num flex justify-between text-[10px] text-slate-600">
        <span>0s</span>
        <span>{end}s</span>
      </div>
    </div>
  )
}

export default function SafeguardsPage() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const resultQuery = useResultDocument(id)
  const reducedMotion = useReducedMotion()
  const containerRef = useRef<HTMLUListElement | null>(null)

  const timings = useMemo<SafeguardTiming[]>(() => {
    const result = resultQuery.data
    if (!result) return []
    const view = safeguardsView(result)
    return view.kind === 'evidence' ? view.evidence.timings : []
  }, [resultQuery.data])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return
    const nodes = Array.from(container.querySelectorAll<HTMLElement>('[data-sequence-step]'))
    return revealSequence(nodes, reducedMotion)
  }, [reducedMotion, timings])

  if (resultQuery.isLoading) return <StatePanel title="Loading safeguard evidence…" />
  if (resultQuery.isError || !resultQuery.data) {
    return (
      <StatePanel
        tone="crit"
        title="Evidence could not be loaded"
        hint="The stored result document is unavailable."
        action={{ label: 'Retry', onAct: () => void resultQuery.refetch() }}
      />
    )
  }
  const result = resultQuery.data
  const view = safeguardsView(result)
  if (view.kind === 'no-evidence') {
    // A re-verification record stores the before/after comparison, not the
    // safeguard timings — those belong to the parent analysis (BUG-02).
    const parentId = view.parentId
    return (
      <StatePanel
        title="No safeguard evidence on this record"
        hint="This record is a re-verification run. Its safeguard timings belong to the parent analysis it compares against."
        action={
          parentId
            ? {
                label: 'Open parent safeguards',
                onAct: () => navigate(`/analysis/${parentId}/safeguards`),
              }
            : undefined
        }
      />
    )
  }

  const { note, caseLabel } = view.evidence
  const end = axisEnd(timings)

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <header className="flex shrink-0 flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold tracking-[0.22em] text-accent/80 uppercase">
            Safeguard verification
          </p>
          <h1 className="truncate text-base font-semibold tracking-tight text-white sm:text-lg">
            Did the modelled safeguard react in time?
          </h1>
          <p className="truncate text-xs text-slate-500">{result.goal}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <Link
            to={`/analysis/${id}/investigation`}
            className="rounded-md border border-edge-strong px-3 py-1.5 text-slate-300 transition hover:border-accent/40 hover:text-slate-100"
          >
            Investigation
          </Link>
          <Link
            to={`/analysis/${id}/reverify`}
            className="rounded-md border border-accent/40 px-3 py-1.5 text-accent transition hover:bg-accent/10"
          >
            Re-verify
          </Link>
        </div>
      </header>

      <Panel
        className="min-h-0 flex-1"
        bodyClassName="flex min-h-0 flex-col gap-3"
        scroll
        title="Recorded safeguard timings"
        hint="measured offsets in the simulated scenario"
      >
        <p className="text-xs text-slate-500">{note ?? 'No note was recorded for this evidence.'}</p>
        {caseLabel && (
          <p className="text-xs text-slate-500">
            Simulated case: <span className="text-slate-300">{caseLabel}</span>
          </p>
        )}

        <ul ref={containerRef} className="flex flex-col gap-2">
          {timings.map((timing) => {
            const verdict = verdictFor(timing)
            return (
              <li key={timing.safeguard} data-sequence-step className="panel-inset p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 className="text-sm font-medium text-slate-100">{timing.safeguard}</h2>
                  <span
                    className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${TONE_CLASS[verdict.tone]}`}
                  >
                    {verdict.text}
                  </span>
                </div>
                <div className="stat-num mt-2 grid grid-cols-3 gap-2 text-center text-xs">
                  {(
                    [
                      ['trigger', timing.trigger_time_s],
                      ['response', timing.response_time_s],
                      ['violation', timing.violation_time_s],
                    ] as const
                  ).map(([label, value]) => (
                    <div key={label} className="rounded border border-edge/70 bg-void/50 px-2 py-1.5">
                      <p className="text-[10px] tracking-wide text-slate-500 uppercase">{label}</p>
                      <p className="text-slate-100">{fmt(value)}</p>
                    </div>
                  ))}
                </div>
                <div className="mt-2">
                  <Timeline timing={timing} end={end} />
                </div>
                <p className="mt-1 text-[11px] text-slate-500">{timing.note}</p>
              </li>
            )
          })}
          {timings.length === 0 && (
            <li className="text-sm text-slate-400">
              No safeguard timings were recorded for this analysis.
            </li>
          )}
        </ul>

        <p className="text-[11px] text-slate-500">
          Verdicts describe the modelled safeguards inside the tested simulation only. SafeFlux
          never actuates real equipment and never certifies a real plant.
        </p>
      </Panel>
    </div>
  )
}
