import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { StatePanel } from '../components/ui/StatePanel'
import { TabBar, type TabItem } from '../components/ui/TabBar'
import { useAnalysis, useResultDocument } from '../hooks/useAnalyses'
import type { CounterfactualRow } from '../types/analysis'

/**
 * Root-cause investigation (Part 9) — counterfactual evidence first, AI second.
 *
 * The two blocks are visibly separate: SIMULATION EVIDENCE lists the real
 * restore-one-change runs the backend executed, each with its simulated
 * verdict; AI EXPLANATION (when a provider is configured) is the model's
 * narration of that evidence and can never alter it. Without a provider the
 * AI block says so instead of pretending.
 */

type View = 'counterfactuals' | 'ai' | 'search'

const TABS: readonly TabItem<View>[] = [
  { id: 'counterfactuals', label: 'Counterfactuals' },
  { id: 'ai', label: 'AI explanation' },
  { id: 'search', label: 'Search context' },
]

const STATUS_TONE: Record<string, string> = {
  safe: 'text-emerald-300',
  near_limit: 'text-amber-300',
  safeguard_activated: 'text-amber-300',
  violation: 'text-rose-300',
}

function statusClass(status: string | null | undefined): string {
  return STATUS_TONE[status ?? ''] ?? 'text-slate-300'
}

function CounterfactualCard({ row }: { row: CounterfactualRow }) {
  return (
    <li className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-slate-100">{row.label}</h3>
        <span className="text-xs">
          <span className="text-slate-500">was </span>
          <span className={statusClass(row.status_before)}>{row.status_before}</span>
          <span className="text-slate-500"> → now </span>
          <span className={statusClass(row.status)}>{row.status}</span>
        </span>
      </div>
      <dl className="mt-2 grid grid-cols-3 gap-2 text-[11px]">
        {row.changes.map((change) => (
          <div key={change.variable} className="rounded border border-slate-800 bg-slate-900/60 p-1.5">
            <dt className="text-slate-500">{change.variable}</dt>
            <dd className="text-slate-300">
              {change.before === null ? '—' : change.before.toFixed(1)} →{' '}
              {change.after === null ? '—' : change.after.toFixed(1)}
              {change.delta !== null && (
                <span className={change.delta < 0 ? ' text-emerald-300' : ' text-rose-300'}>
                  {' '}
                  ({change.delta > 0 ? '+' : ''}
                  {change.delta.toFixed(1)})
                </span>
              )}
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-[11px] text-slate-500">
        Simulated case {row.case_key}; every peak came from the same deterministic engine.
      </p>
    </li>
  )
}

export default function InvestigationPage() {
  const { id } = useParams<{ id: string }>()
  const analysisQuery = useAnalysis(id)
  const [view, setView] = useState<View>('counterfactuals')

  if (analysisQuery.isLoading) return <StatePanel title="Loading analysis…" />
  if (analysisQuery.isError || !analysisQuery.data) {
    return (
      <StatePanel
        tone="crit"
        title="Analysis not found"
        hint="It may belong to another account."
        action={{ label: 'Back to history', onAct: () => window.history.back() }}
      />
    )
  }
  const analysis = analysisQuery.data
  if (analysis.status !== 'complete') {
    return (
      <StatePanel
        tone="warn"
        title="This analysis has not completed"
        hint={`Current status: ${analysis.status}. Evidence appears only after the run completes.`}
        action={{ label: 'Open live view', onAct: () => window.history.back() }}
      />
    )
  }
  return <Loaded id={analysis.id} view={view} setView={setView} />
}

function Loaded({
  id,
  view,
  setView,
}: {
  id: string
  view: View
  setView: (view: View) => void
}) {
  const resultQuery = useResultDocument(id)
  const result = resultQuery.data

  if (resultQuery.isLoading && !result) return <StatePanel title="Loading stored evidence…" />
  if (resultQuery.isError || !result) {
    return (
      <StatePanel
        tone="crit"
        title="Evidence could not be loaded"
        hint="The stored result document is unavailable."
        action={{ label: 'Retry', onAct: () => void resultQuery.refetch() }}
      />
    )
  }

  const ai = result.ai_explanation
  const aiText = typeof ai?.text === 'string' ? ai.text : null
  const aiHeadline = typeof ai?.headline === 'string' ? ai.headline : null
  const counterfactuals = result.counterfactuals ?? []

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <header className="shrink-0">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <h1 className="text-lg font-semibold text-slate-100">Root-cause investigation</h1>
            <p className="truncate text-xs text-slate-400">{result.goal}</p>
          </div>
          <div className="flex gap-2 text-xs">
            {result.pivot && (
              <Link
                to={`/analysis/${id}/failures/${encodeURIComponent(result.pivot.key)}`}
                className="rounded-lg border border-slate-700 px-3 py-1.5 text-slate-200 transition hover:bg-slate-800"
              >
                Worst failure
              </Link>
            )}
            <Link
              to={`/analysis/${id}/safeguards`}
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-slate-300 transition hover:bg-slate-800"
            >
              Safeguards
            </Link>
          </div>
        </div>
      </header>

      <TabBar tabs={TABS} active={view} onChange={setView} label="Investigation sections" />

      <section className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-slate-800 bg-slate-900/50 p-4">
        {view === 'counterfactuals' && (
          <div className="flex flex-col gap-3">
            <h2 className="text-xs font-semibold tracking-widest text-slate-400 uppercase">
              Simulation evidence
            </h2>
            {result.pivot && (
              <p className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2 text-xs text-slate-300">
                Anchored on the worst failure{' '}
                <span className="font-medium text-slate-100">{result.pivot.label}</span>{' '}
                (<span className={statusClass(result.pivot.status)}>{result.pivot.status}</span>). Each
                counterfactual below restores one driver toward neutral and re-runs the real scenario.
              </p>
            )}
            {counterfactuals.length === 0 && (
              <p className="text-sm text-slate-400">
                No failing case was found, so no counterfactual comparisons were needed — the plant
                stayed within limits in the tested scenarios.
              </p>
            )}
            <ul className="flex flex-col gap-2">
              {counterfactuals.map((row) => (
                <CounterfactualCard key={row.case_key} row={row} />
              ))}
            </ul>
          </div>
        )}

        {view === 'ai' && (
          <div className="flex flex-col gap-3">
            <h2 className="text-xs font-semibold tracking-widest text-slate-400 uppercase">
              AI explanation
            </h2>
            {aiText ? (
              <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3">
                {aiHeadline && <p className="text-sm font-medium text-slate-100">{aiHeadline}</p>}
                <p className="mt-2 text-sm leading-relaxed whitespace-pre-line text-slate-300">{aiText}</p>
              </div>
            ) : (
              <p className="rounded-lg border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-sm text-amber-200">
                No AI provider is configured, so the explanation is empty. The simulation evidence
                stands on its own.
              </p>
            )}
            <p className="text-[11px] text-slate-500">
              The model narrates the recorded evidence; it cannot change a value, a verdict or a
              limit. The SIMULATION EVIDENCE tab is the authoritative record.
            </p>
          </div>
        )}

        {view === 'search' && (
          <div className="flex flex-col gap-3 text-xs">
            <h2 className="text-xs font-semibold tracking-widest text-slate-400 uppercase">Search context</h2>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {Object.entries(result.original.counts ?? {}).slice(0, 8).map(([key, value]) => (
                <div key={key} className="rounded-lg border border-slate-800 bg-slate-950/60 p-2">
                  <p className="text-slate-500">{key.replaceAll('_', ' ')}</p>
                  <p className="font-semibold text-slate-100">{String(value)}</p>
                </div>
              ))}
            </div>
            {(result.original.boundaries ?? []).length > 0 && (
              <div>
                <h3 className="font-semibold text-slate-200">Boundary candidates</h3>
                <ul className="mt-1 space-y-1 text-slate-400">
                  {(result.original.boundaries as Record<string, unknown>[]).map((boundary, index) => (
                    <li key={index} className="rounded border border-slate-800 bg-slate-950/60 px-2 py-1.5 font-mono">
                      {JSON.stringify(boundary)}
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <ul className="list-disc space-y-0.5 pl-4 text-slate-500">
              {(result.notes ?? []).map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </div>
        )}
      </section>
    </div>
  )
}
