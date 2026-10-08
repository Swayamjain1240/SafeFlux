import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { StatePanel } from '../components/ui/StatePanel'
import { Panel } from '../components/ui/Panel'
import { StatusBadge } from '../components/ui/StatusBadge'
import { TabBar, type TabItem } from '../components/ui/TabBar'
import { IconChevronRight } from '../components/ui/Icons'
import { useAnalysis, useResultDocument } from '../hooks/useAnalyses'
import type { CounterfactualRow } from '../types/analysis'
import type { Tone } from '../dashboard/viewState'

/**
 * Root-cause investigation (Part 9) — counterfactual evidence first, AI second.
 *
 * The two blocks are visibly separate: SIMULATION EVIDENCE lists the real
 * restore-one-change runs the backend executed, each with its simulated
 * verdict; AI EXPLANATION (when a provider is configured) is the model's
 * narration of that evidence and can never alter it. Without a provider the
 * AI block says so instead of pretending.
 *
 * Visual transformation: each counterfactual is a before → after comparison
 * card (violation vs restored verdict) built from the recorded run only. No
 * driver ranking is invented — the list keeps the backend's own order.
 */

type View = 'counterfactuals' | 'ai' | 'search'

const TABS: readonly TabItem<View>[] = [
  { id: 'counterfactuals', label: 'Counterfactuals' },
  { id: 'ai', label: 'AI explanation' },
  { id: 'search', label: 'Search context' },
]

function toneForStatus(status: string | null | undefined): Tone {
  const normalised = (status ?? '').toLowerCase()
  if (normalised.includes('violation') || normalised.includes('shutdown')) return 'crit'
  if (normalised.includes('near') || normalised.includes('safeguard')) return 'warn'
  if (normalised.includes('safe')) return 'ok'
  return 'idle'
}

function CounterfactualCard({ row }: { row: CounterfactualRow }) {
  const beforeTone = toneForStatus(row.status_before)
  const afterTone = toneForStatus(row.status)
  const improved = afterTone === 'ok' && beforeTone !== 'ok'

  return (
    <li
      className={`panel flex flex-col gap-2 p-3 ${
        improved ? 'border-safe/40' : afterTone === 'crit' ? 'border-crit/50/40' : ''
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="text-sm font-medium text-slate-100">{row.label}</h3>
        <StatusBadge
          label={improved ? 'restores safety in simulation' : 'still unsafe in simulation'}
          tone={improved ? 'ok' : afterTone === 'crit' ? 'crit' : afterTone}
        />
      </div>

      {/* Before → after, from the recorded runs only */}
      <div className="grid grid-cols-[1fr_auto_1fr] items-center gap-2">
        <div className="panel-inset px-2.5 py-2">
          <p className="text-[10px] font-semibold tracking-[0.16em] text-slate-500 uppercase">
            original
          </p>
          <p className="stat-num mt-0.5 text-sm text-crit">{row.status_before ?? '—'}</p>
        </div>
        <IconChevronRight className="h-4 w-4 text-slate-600" />
        <div className="panel-inset px-2.5 py-2">
          <p className="text-[10px] font-semibold tracking-[0.16em] text-slate-500 uppercase">
            after restoring
          </p>
          <p
            className={`stat-num mt-0.5 text-sm ${
              afterTone === 'ok' ? 'text-safe' : afterTone === 'crit' ? 'text-crit' : 'text-warn'
            }`}
          >
            {row.status}
          </p>
        </div>
      </div>

      {row.changes.length > 0 && (
        <dl className="grid grid-cols-2 gap-1.5 sm:grid-cols-3">
          {row.changes.map((change) => (
            <div key={change.variable} className="panel-inset px-2 py-1.5">
              <dt className="truncate text-[10px] text-slate-500">{change.variable}</dt>
              <dd className="stat-num text-xs text-slate-300">
                {change.before === null ? '—' : change.before.toFixed(1)}
                <span className="text-slate-600"> → </span>
                {change.after === null ? '—' : change.after.toFixed(1)}
                {change.delta !== null && (
                  <span className={change.delta < 0 ? ' text-safe' : ' text-crit'}>
                    {' '}
                    ({change.delta > 0 ? '+' : ''}
                    {change.delta.toFixed(1)})
                  </span>
                )}
              </dd>
            </div>
          ))}
        </dl>
      )}

      <p className="text-[11px] text-slate-500">
        Simulated case <span className="stat-num">{row.case_key}</span>; every peak came from the
        same deterministic engine.
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
      <header className="flex shrink-0 flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold tracking-[0.22em] text-accent/80 uppercase">
            Root-cause investigation
          </p>
          <h1 className="truncate text-base font-semibold tracking-tight text-white sm:text-lg">
            What would have prevented it?
          </h1>
          <p className="truncate text-xs text-slate-500">{result.goal}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {result.pivot && (
            <Link
              to={`/analysis/${id}/failures/${encodeURIComponent(result.pivot.key)}`}
              className="rounded-md border border-crit/50 px-3 py-1.5 text-crit transition hover:bg-crit/10"
            >
              Worst failure
            </Link>
          )}
          <Link
            to={`/analysis/${id}/safeguards`}
            className="rounded-md border border-edge-strong px-3 py-1.5 text-slate-300 transition hover:border-accent/40 hover:text-slate-100"
          >
            Safeguards
          </Link>
          <Link
            to={`/analysis/${id}/reverify`}
            className="rounded-md border border-edge-strong px-3 py-1.5 text-slate-300 transition hover:border-accent/40 hover:text-slate-100"
          >
            Re-verify
          </Link>
        </div>
      </header>

      <TabBar tabs={TABS} active={view} onChange={setView} label="Investigation sections" />

      <Panel
        className="min-h-0 flex-1"
        bodyClassName="flex min-h-0 flex-col gap-3"
        scroll
        title={
          view === 'counterfactuals'
            ? 'Simulation evidence'
            : view === 'ai'
              ? 'AI explanation'
              : 'Search context'
        }
        hint={
          view === 'counterfactuals'
            ? 'real re-runs by the deterministic engine'
            : view === 'ai'
              ? 'narration of the evidence · cannot change a value'
              : 'what the search actually explored'
        }
      >
        {view === 'counterfactuals' && (
          <>
            {result.pivot && (
              <p className="panel-inset px-3 py-2 text-xs text-slate-300">
                Anchored on the worst failure{' '}
                <span className="font-medium text-slate-100">{result.pivot.label}</span>{' '}
                <StatusBadge label={result.pivot.status} tone={toneForStatus(result.pivot.status)} />{' '}
                Each card restores one driver toward neutral and re-runs the real scenario.
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
            {counterfactuals.length > 0 && (
              <p className="text-[11px] text-slate-500">
                Cards are listed in the order the backend recorded them. SafeFlux does not rank
                drivers: each card is one comparison, and the simulator decides every verdict.
              </p>
            )}
          </>
        )}

        {view === 'ai' && (
          <>
            {aiText ? (
              <div className="panel-inset p-3">
                {aiHeadline && <p className="text-sm font-medium text-slate-100">{aiHeadline}</p>}
                <p className="mt-2 text-sm leading-relaxed whitespace-pre-line text-slate-300">
                  {aiText}
                </p>
              </div>
            ) : (
              <p className="rounded-md border border-warn/40 bg-warn/5 px-3 py-2 text-sm text-warn">
                No AI provider is configured, so the explanation is empty. The simulation evidence
                stands on its own.
              </p>
            )}
            <p className="text-[11px] text-slate-500">
              The model narrates the recorded evidence; it cannot change a value, a verdict or a
              limit. The SIMULATION EVIDENCE tab is the authoritative record.
            </p>
          </>
        )}

        {view === 'search' && (
          <>
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
              {Object.entries(result.original.counts ?? {})
                .slice(0, 8)
                .map(([key, value]) => (
                  <div key={key} className="panel-inset px-2.5 py-2">
                    <p className="truncate text-[10px] tracking-wide text-slate-500 uppercase">
                      {key.replaceAll('_', ' ')}
                    </p>
                    <p className="stat-num mt-0.5 text-sm font-medium text-slate-100">
                      {String(value)}
                    </p>
                  </div>
                ))}
            </div>
            {(result.original.boundaries ?? []).length > 0 && (
              <div>
                <h3 className="text-xs font-semibold tracking-widest text-slate-400 uppercase">
                  Boundary candidates
                </h3>
                <ul className="mt-1.5 space-y-1">
                  {(result.original.boundaries as Record<string, unknown>[]).map(
                    (boundary, index) => (
                      <li
                        key={index}
                        className="stat-num panel-inset px-2.5 py-1.5 text-[11px] break-all text-slate-400"
                      >
                        {JSON.stringify(boundary)}
                      </li>
                    ),
                  )}
                </ul>
              </div>
            )}
            <ul className="list-disc space-y-0.5 pl-4 text-xs text-slate-500">
              {(result.notes ?? []).map((note) => (
                <li key={note}>{note}</li>
              ))}
            </ul>
          </>
        )}
      </Panel>
    </div>
  )
}
