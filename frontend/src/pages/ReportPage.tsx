import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { StatePanel } from '../components/ui/StatePanel'
import { TabBar, type TabItem } from '../components/ui/TabBar'
import { useDownloadReportPdf, useReport } from '../hooks/useAnalyses'
import type { ReportPayload, StoredFailure } from '../types/analysis'

/**
 * Engineering report (Part 9) — the stored evidence in six tabs, plus the
 * multi-page PDF download. The interactive screen stays one viewport (tabs);
 * the PDF is an export and may paginate freely.
 */

type TabId = 'overview' | 'scenarios' | 'failures' | 'counterfactuals' | 'safeguards' | 'evidence'

const TABS: readonly TabItem<TabId>[] = [
  { id: 'overview', label: 'Overview' },
  { id: 'scenarios', label: 'Scenarios' },
  { id: 'failures', label: 'Failures' },
  { id: 'counterfactuals', label: 'Counterfactuals' },
  { id: 'safeguards', label: 'Safeguards' },
  { id: 'evidence', label: 'Evidence' },
]

const STATUS_TONE: Record<string, string> = {
  safe: 'text-emerald-300',
  near_limit: 'text-amber-300',
  safeguard_activated: 'text-amber-300',
  violation: 'text-rose-300',
}

export default function ReportPage() {
  const { id } = useParams<{ id: string }>()
  const reportQuery = useReport(id)
  const download = useDownloadReportPdf()
  const [tab, setTab] = useState<TabId>('overview')
  const [downloadError, setDownloadError] = useState<string | null>(null)

  const report = reportQuery.data

  if (reportQuery.isLoading) return <StatePanel title="Loading report…" />
  if (reportQuery.isError || !report) {
    const error = reportQuery.error
    return (
      <StatePanel
        tone="crit"
        title="Report not available"
        hint={error instanceof ApiError ? error.message : 'The stored report could not be loaded.'}
        action={{ label: 'Back to history', onAct: () => window.history.back() }}
      />
    )
  }

  function handleDownload() {
    if (!id) return
    setDownloadError(null)
    download.mutate(id, {
      onError: () => setDownloadError('The PDF could not be downloaded. Please try again.'),
    })
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <header className="flex shrink-0 flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <h1 className="text-lg font-semibold text-slate-100">Engineering report</h1>
          <p className="truncate text-xs text-slate-400">{report.goal}</p>
        </div>
        <div className="flex items-center gap-2">
          <Link
            to={`/analysis/${report.analysis_id}/live`}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 transition hover:bg-slate-800"
          >
            Event record
          </Link>
          <button
            type="button"
            onClick={handleDownload}
            disabled={download.isPending}
            className="rounded-lg bg-cyan-500/20 px-4 py-1.5 text-xs font-semibold text-cyan-200 ring-1 ring-cyan-500/40 transition enabled:hover:bg-cyan-500/30 disabled:opacity-40"
          >
            {download.isPending ? 'Preparing PDF…' : 'Download PDF'}
          </button>
        </div>
      </header>

      <TabBar tabs={TABS} active={tab} onChange={setTab} label="Report tabs" />

      <section className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-slate-800 bg-slate-900/50 p-4">
        {downloadError && (
          <p role="alert" className="mb-3 rounded-lg border border-rose-600/50 bg-rose-950/40 px-3 py-2 text-xs text-rose-200">
            {downloadError}
          </p>
        )}
        <TabContent report={report} tab={tab} />
      </section>
    </div>
  )
}

function FailureList({ failures }: { failures: StoredFailure[] }) {
  if (failures.length === 0) {
    return (
      <p className="rounded-lg border border-emerald-500/40 bg-emerald-500/5 px-3 py-2 text-sm text-emerald-200">
        No unsafe condition was detected within the tested simulation scenarios.
      </p>
    )
  }
  return (
    <ul className="flex flex-col gap-1.5">
      {failures.map((failure) => (
        <li key={failure.key} className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <span className="break-all text-sm text-slate-200">{failure.label}</span>
            <span className={`text-xs font-medium ${STATUS_TONE[failure.status] ?? 'text-slate-300'}`}>
              {failure.status}
            </span>
          </div>
          {failure.worst_finding && (
            <p className="mt-1 text-[11px] text-slate-500">{failure.worst_finding.message}</p>
          )}
        </li>
      ))}
    </ul>
  )
}

function TabContent({ report, tab }: { report: ReportPayload; tab: TabId }) {
  const tabs = report.tabs
  if (tab === 'overview') {
    const interpreted = tabs.overview.interpreted_change
    return (
      <div className="flex flex-col gap-3 text-sm">
        <div>
          <h2 className="text-xs font-semibold tracking-widest text-slate-400 uppercase">Interpreted change</h2>
          <ul className="mt-1 space-y-0.5 text-xs text-slate-300">
            <li>direction: {interpreted?.direction ?? '—'}</li>
            <li>magnitude: {interpreted?.magnitude ?? '—'}</li>
            <li>variables: {interpreted?.variables?.join(', ') || 'default bounded set'}</li>
          </ul>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {Object.entries(tabs.overview.counts ?? {})
            .filter(([, value]) => typeof value === 'number')
            .slice(0, 8)
            .map(([key, value]) => (
              <div key={key} className="rounded-lg border border-slate-800 bg-slate-950/60 p-2 text-center">
                <p className="text-[11px] text-slate-500">{key.replaceAll('_', ' ')}</p>
                <p className="font-semibold text-slate-100">{String(value)}</p>
              </div>
            ))}
        </div>
        <ul className="list-disc space-y-0.5 pl-4 text-xs text-slate-500">
          {(tabs.overview.notes ?? []).map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </div>
    )
  }
  if (tab === 'scenarios') {
    return <FailureList failures={tabs.scenarios.cases ?? []} />
  }
  if (tab === 'failures') {
    return (
      <div className="flex flex-col gap-2">
        <FailureListWithLinks analysisId={report.analysis_id} failures={tabs.failures.failures ?? []} />
      </div>
    )
  }
  if (tab === 'counterfactuals') {
    const rows = tabs.counterfactuals.rows ?? []
    if (rows.length === 0) return <p className="text-sm text-slate-400">No counterfactual comparisons were recorded.</p>
    return (
      <ul className="flex flex-col gap-1.5 text-xs">
        {rows.map((row) => (
          <li key={row.case_key} className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2 text-slate-300">
            <span className="font-medium text-slate-100">{row.label}</span> · was {row.status_before}, then{' '}
            <span className={STATUS_TONE[row.status] ?? ''}>{row.status}</span>
          </li>
        ))}
      </ul>
    )
  }
  if (tab === 'safeguards') {
    const timings = tabs.safeguards.timings ?? []
    if (timings.length === 0) return <p className="text-sm text-slate-400">No safeguard timings were recorded.</p>
    return (
      <ul className="flex flex-col gap-1.5 text-xs">
        {timings.map((timing) => (
          <li key={timing.safeguard} className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2 text-slate-300">
            <span className="font-medium text-slate-100">{timing.safeguard}</span> · trigger{' '}
            {timing.trigger_time_s ?? '—'}s · response {timing.response_time_s ?? '—'}s · violation{' '}
            {timing.violation_time_s ?? '—'}s ·{' '}
            <span className={timing.prevented === false ? 'text-rose-300' : 'text-emerald-300'}>
              {timing.prevented === false
                ? 'Safeguard response occurred after the simulated violation.'
                : timing.prevented === true
                  ? 'averted the simulated violation in the tested scenario'
                  : 'not triggered'}
            </span>
          </li>
        ))}
      </ul>
    )
  }
  const evidence = tabs.evidence
  const ai = evidence.ai_explanation
  const aiText = typeof ai?.text === 'string' ? ai.text : null
  return (
    <div className="flex flex-col gap-3 text-xs">
      <div>
        <h2 className="text-xs font-semibold tracking-widest text-slate-400 uppercase">Version evidence</h2>
        <dl className="mt-1 space-y-0.5 font-mono text-slate-400">
          {Object.entries(evidence.versions ?? {}).map(([key, value]) => (
            <div key={key}>
              {key}: {String(value)}
            </div>
          ))}
        </dl>
      </div>
      <div>
        <h2 className="text-xs font-semibold tracking-widest text-slate-400 uppercase">AI explanation</h2>
        {aiText ? (
          <p className="mt-1 rounded-lg border border-slate-800 bg-slate-950/60 p-2 text-slate-300 whitespace-pre-line">{aiText}</p>
        ) : (
          <p className="mt-1 text-slate-500">
            No AI provider is configured, so the explanation is empty. The simulation evidence stands
            on its own.
          </p>
        )}
      </div>
      <p className="text-[11px] text-slate-500">{evidence.disclaimer}</p>
    </div>
  )
}

function FailureListWithLinks({ analysisId, failures }: { analysisId: string; failures: StoredFailure[] }) {
  if (failures.length === 0) {
    return (
      <p className="rounded-lg border border-emerald-500/40 bg-emerald-500/5 px-3 py-2 text-sm text-emerald-200">
        No unsafe condition was detected within the tested simulation scenarios.
      </p>
    )
  }
  return (
    <ul className="flex flex-col gap-1.5">
      {failures.map((failure) => (
        <li key={failure.key} className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <Link
              to={`/analysis/${analysisId}/failures/${encodeURIComponent(failure.key)}`}
              className="break-all text-sm text-cyan-200 underline-offset-2 hover:underline"
            >
              {failure.label}
            </Link>
            <span className={`text-xs font-medium ${STATUS_TONE[failure.status] ?? 'text-slate-300'}`}>
              {failure.status}
            </span>
          </div>
        </li>
      ))}
    </ul>
  )
}
