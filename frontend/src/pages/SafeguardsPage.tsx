import { useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'
import { StatePanel } from '../components/ui/StatePanel'
import { useResultDocument } from '../hooks/useAnalyses'
import type { SafeguardTiming } from '../types/analysis'

/**
 * Safeguard verification (Part 9).
 *
 * The page states what the simulation measured — trigger, response, violation
 * times of the *modelled* safeguards — and uses the required language: a late
 * response is "Safeguard response occurred after the simulated violation", never
 * a claim that a real plant's safeguard is unsafe.
 */

function fmt(value: number | null): string {
  return value === null ? '—' : `${value}s`
}

function verdictFor(timing: SafeguardTiming): { text: string; tone: 'ok' | 'late' | 'idle' } {
  if (timing.prevented === null) return { text: 'Setpoint not reached in the tested scenario.', tone: 'idle' }
  if (timing.prevented) return { text: 'Averted the simulated violation in the tested scenario.', tone: 'ok' }
  return { text: 'Safeguard response occurred after the simulated violation.', tone: 'late' }
}

const TONE_CLASS: Record<'ok' | 'late' | 'idle', string> = {
  ok: 'text-emerald-300',
  late: 'text-rose-300',
  idle: 'text-slate-400',
}

export default function SafeguardsPage() {
  const { id } = useParams<{ id: string }>()
  const resultQuery = useResultDocument(id)

  const timings = useMemo<SafeguardTiming[]>(
    () => resultQuery.data?.safeguards?.timings ?? [],
    [resultQuery.data],
  )

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

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <header className="shrink-0">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <h1 className="text-lg font-semibold text-slate-100">Safeguard verification</h1>
            <p className="truncate text-xs text-slate-400">{result.goal}</p>
          </div>
          <div className="flex gap-2 text-xs">
            <Link
              to={`/analysis/${id}/investigation`}
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-slate-300 transition hover:bg-slate-800"
            >
              Investigation
            </Link>
            <Link
              to={`/analysis/${id}/reverify`}
              className="rounded-lg border border-cyan-500/40 px-3 py-1.5 text-cyan-200 transition hover:bg-cyan-500/10"
            >
              Re-verify
            </Link>
          </div>
        </div>
      </header>

      <section className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-slate-800 bg-slate-900/50 p-4">
        <p className="text-xs text-slate-500">{result.safeguards.note}</p>
        <p className="mt-1 text-xs text-slate-500">
          Simulated case: {result.safeguards.case_label || result.safeguards.case_key}
        </p>
        <ul className="mt-3 flex flex-col gap-2">
          {timings.map((timing) => {
            const verdict = verdictFor(timing)
            return (
              <li key={timing.safeguard} className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h2 className="text-sm font-medium text-slate-100">{timing.safeguard}</h2>
                  <span className={`text-xs font-medium ${TONE_CLASS[verdict.tone]}`}>{verdict.text}</span>
                </div>
                <dl className="mt-2 grid grid-cols-3 gap-2 text-center text-xs">
                  <div className="rounded border border-slate-800 bg-slate-900/60 p-1.5">
                    <dt className="text-slate-500">trigger</dt>
                    <dd className="text-slate-100">{fmt(timing.trigger_time_s)}</dd>
                  </div>
                  <div className="rounded border border-slate-800 bg-slate-900/60 p-1.5">
                    <dt className="text-slate-500">response</dt>
                    <dd className="text-slate-100">{fmt(timing.response_time_s)}</dd>
                  </div>
                  <div className="rounded border border-slate-800 bg-slate-900/60 p-1.5">
                    <dt className="text-slate-500">violation</dt>
                    <dd className="text-slate-100">{fmt(timing.violation_time_s)}</dd>
                  </div>
                </dl>
                <p className="mt-2 text-[11px] text-slate-500">{timing.note}</p>
              </li>
            )
          })}
          {timings.length === 0 && (
            <li className="text-sm text-slate-400">No safeguard timings were recorded for this analysis.</li>
          )}
        </ul>
        <p className="mt-3 text-[11px] text-slate-500">
          Verdicts describe the modelled safeguards inside the tested simulation only. SafeFlux
          never actuates real equipment and never certifies a real plant.
        </p>
      </section>
    </div>
  )
}
