import { useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { StatePanel } from '../components/ui/StatePanel'
import { Panel } from '../components/ui/Panel'
import { StatusBadge } from '../components/ui/StatusBadge'
import { TabBar, type TabItem } from '../components/ui/TabBar'
import { IconDownload } from '../components/ui/Icons'
import { useDownloadReportPdf, useReport } from '../hooks/useAnalyses'
import type { ReportPayload, StoredFailure } from '../types/analysis'
import type { Tone } from '../dashboard/viewState'

/**
 * Engineering report (Part 9) — the stored evidence in six tabs, plus the
 * multi-page PDF download. The interactive screen stays one viewport (tabs);
 * the PDF is an export and may paginate freely.
 *
 * Visual transformation: the report reads as a document index — quiet surfaces,
 * instrument numerals, and one accent action (the export).
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

function statusTone(status: string): Tone {
  if (status === 'violation') return 'crit'
  if (status === 'near_limit' || status === 'safeguard_activated') return 'warn'
  if (status === 'safe') return 'ok'
  return 'idle'
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
      <header className="flex shrink-0 flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold tracking-[0.22em] text-accent/80 uppercase">
            Engineering report
          </p>
          <h1 className="truncate text-base font-semibold tracking-tight text-white sm:text-lg">
            Stored evidence document
          </h1>
          <p className="truncate text-xs text-slate-500">{report.goal}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            to={`/analysis/${report.analysis_id}/live`}
            className="rounded-md border border-edge-strong px-3 py-1.5 text-xs text-slate-300 transition hover:border-accent/40 hover:text-slate-100"
          >
            Event record
          </Link>
          <Link
            to={`/analysis/${report.analysis_id}/investigation`}
            className="rounded-md border border-edge-strong px-3 py-1.5 text-xs text-slate-300 transition hover:border-accent/40 hover:text-slate-100"
          >
            Root cause
          </Link>
          <button
            type="button"
            onClick={handleDownload}
            disabled={download.isPending}
            className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-1.5 text-xs font-semibold text-void transition enabled:hover:bg-accent-soft disabled:opacity-40"
          >
            <IconDownload className="h-3.5 w-3.5" />
            {download.isPending ? 'Preparing PDF…' : 'Download PDF'}
          </button>
        </div>
      </header>

      <TabBar tabs={TABS} active={tab} onChange={setTab} label="Report tabs" />

      <Panel className="min-h-0 flex-1" bodyClassName="flex min-h-0 flex-col gap-3" scroll>
        {downloadError && (
          <p
            role="alert"
            className="rounded-md border border-crit/50 bg-crit/10 px-3 py-2 text-xs text-crit"
          >
            {downloadError}
          </p>
        )}
        <TabContent report={report} tab={tab} />
      </Panel>
    </div>
  )
}

function FailureList({
  failures,
  analysisId,
}: {
  failures: StoredFailure[]
  analysisId?: string
}) {
  if (failures.length === 0) {
    return (
      <p className="rounded-md border border-safe/40 bg-safe/5 px-3 py-2 text-sm text-safe">
        No unsafe condition was detected within the tested simulation scenarios.
      </p>
    )
  }
  return (
    <ul className="flex flex-col gap-1.5">
      {failures.map((failure) => (
        <li key={failure.key} className="panel-inset px-3 py-2">
          <div className="flex flex-wrap items-center justify-between gap-2">
            {analysisId ? (
              <Link
                to={`/analysis/${analysisId}/failures/${encodeURIComponent(failure.key)}`}
                className="break-all text-sm text-accent hover:underline"
              >
                {failure.label}
              </Link>
            ) : (
              <span className="break-all text-sm text-slate-200">{failure.label}</span>
            )}
            <StatusBadge label={failure.status} tone={statusTone(failure.status)} />
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
      <>
        <div>
          <h2 className="text-[11px] font-semibold tracking-[0.16em] text-slate-400 uppercase">
            Interpreted change
          </h2>
          <dl className="mt-1.5 grid grid-cols-2 gap-2 sm:grid-cols-3">
            {(
              [
                ['direction', interpreted?.direction ?? '—'],
                ['magnitude', interpreted?.magnitude ?? '—'],
                ['variables', interpreted?.variables?.join(', ') || 'default bounded set'],
              ] as const
            ).map(([label, value]) => (
              <div key={label} className="panel-inset px-2.5 py-2">
                <dt className="text-[10px] tracking-wide text-slate-500 uppercase">{label}</dt>
                <dd className="mt-0.5 text-xs break-words text-slate-200">{value}</dd>
              </div>
            ))}
          </dl>
        </div>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {Object.entries(tabs.overview.counts ?? {})
            .filter(([, value]) => typeof value === 'number')
            .slice(0, 8)
            .map(([key, value]) => (
              <div key={key} className="panel-inset px-2.5 py-2 text-center">
                <p className="truncate text-[10px] tracking-wide text-slate-500 uppercase">
                  {key.replaceAll('_', ' ')}
                </p>
                <p className="stat-num mt-0.5 text-base font-medium text-slate-100">
                  {String(value)}
                </p>
              </div>
            ))}
        </div>
        <ul className="list-disc space-y-0.5 pl-4 text-xs text-slate-500">
          {(tabs.overview.notes ?? []).map((note) => (
            <li key={note}>{note}</li>
          ))}
        </ul>
      </>
    )
  }

  if (tab === 'scenarios') {
    return <FailureList failures={tabs.scenarios.cases ?? []} />
  }

  if (tab === 'failures') {
    return (
      <FailureList
        analysisId={report.analysis_id}
        failures={tabs.failures.failures ?? []}
      />
    )
  }

  if (tab === 'counterfactuals') {
    const rows = tabs.counterfactuals.rows ?? []
    if (rows.length === 0) {
      return <p className="text-sm text-slate-400">No counterfactual comparisons were recorded.</p>
    }
    return (
      <ul className="flex flex-col gap-1.5 text-xs">
        {rows.map((row) => (
          <li key={row.case_key} className="panel-inset flex flex-wrap items-center gap-2 px-3 py-2">
            <span className="font-medium text-slate-100">{row.label}</span>
            <span className="text-slate-500">was</span>
            <StatusBadge label={row.status_before ?? '—'} tone="crit" />
            <span className="text-slate-500">then</span>
            <StatusBadge label={row.status} tone={statusTone(row.status)} />
          </li>
        ))}
      </ul>
    )
  }

  if (tab === 'safeguards') {
    const timings = tabs.safeguards.timings ?? []
    if (timings.length === 0) {
      return <p className="text-sm text-slate-400">No safeguard timings were recorded.</p>
    }
    return (
      <ul className="flex flex-col gap-1.5 text-xs">
        {timings.map((timing) => (
          <li
            key={timing.safeguard}
            className="panel-inset flex flex-wrap items-center justify-between gap-2 px-3 py-2"
          >
            <span className="font-medium text-slate-100">{timing.safeguard}</span>
            <span className="stat-num text-slate-500">
              trigger {timing.trigger_time_s ?? '—'}s · response {timing.response_time_s ?? '—'}s ·
              violation {timing.violation_time_s ?? '—'}s
            </span>
            <span
              className={
                timing.prevented === false
                  ? 'text-crit'
                  : timing.prevented === true
                    ? 'text-safe'
                    : 'text-slate-400'
              }
            >
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
    <>
      <div>
        <h2 className="text-[11px] font-semibold tracking-[0.16em] text-slate-400 uppercase">
          Version evidence
        </h2>
        <dl className="stat-num mt-1.5 flex flex-col gap-0.5 text-xs text-slate-400">
          {Object.entries(evidence.versions ?? {}).map(([key, value]) => (
            <div key={key}>
              {key}: {String(value)}
            </div>
          ))}
        </dl>
      </div>
      <div>
        <h2 className="text-[11px] font-semibold tracking-[0.16em] text-slate-400 uppercase">
          AI explanation
        </h2>
        {aiText ? (
          <p className="panel-inset mt-1.5 p-2.5 text-xs text-slate-300 whitespace-pre-line">
            {aiText}
          </p>
        ) : (
          <p className="mt-1.5 text-xs text-slate-500">
            No AI provider is configured, so the explanation is empty. The simulation evidence
            stands on its own.
          </p>
        )}
      </div>
      <p className="text-[11px] text-slate-500">{evidence.disclaimer}</p>
    </>
  )
}
