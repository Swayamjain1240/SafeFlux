import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { StatePanel } from '../components/ui/StatePanel'
import { Panel } from '../components/ui/Panel'
import { StatusBadge } from '../components/ui/StatusBadge'
import { useAnalysesHistory } from '../hooks/useAnalyses'
import type { AnalysisOut } from '../types/analysis'
import type { Tone } from '../dashboard/viewState'

/**
 * Analysis history (Part 9) — server-paginated.
 *
 * The table shows one bounded page at a time: explicit Previous/Next controls
 * and a page-size selector, never an endless list. Each row links the record's
 * own destination (live view for running rows, report for completed ones).
 *
 * Visual transformation: dense instrumentation table, semantic status chips and
 * a shortened date column, so the whole page still fits one viewport.
 */

const PAGE_SIZES = [10, 25, 50] as const

function kindLabel(kind: string): string {
  if (kind === 'auto') return 'autonomous'
  if (kind === 'reverify') return 're-verification'
  return kind
}

function destination(item: AnalysisOut): string {
  if (item.status === 'running') return `/analysis/${item.id}/live`
  if (item.kind === 'reverify') return `/analysis/${item.parent_id}/reverify`
  return `/reports/${item.id}`
}

function linkLabel(item: AnalysisOut): string {
  if (item.status === 'running') return 'Live'
  if (item.kind === 'reverify') return 'Reverify'
  return 'Report'
}

function statusTone(status: string): Tone {
  if (status === 'running') return 'warn'
  if (status === 'complete') return 'ok'
  if (status === 'failed') return 'crit'
  return 'idle'
}

/** Compact two-line timestamp: date, then time — no locale noise in the column. */
function whenParts(iso: string): { date: string; time: string } {
  try {
    const value = new Date(iso)
    return {
      date: value.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' }),
      time: value.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' }),
    }
  } catch {
    return { date: iso, time: '' }
  }
}

export default function HistoryPage() {
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState<number>(10)
  const historyQuery = useAnalysesHistory(page, pageSize)
  const data = historyQuery.data

  if (historyQuery.isLoading) return <StatePanel title="Loading history…" />
  if (historyQuery.isError) {
    return (
      <StatePanel
        tone="crit"
        title="History could not be loaded"
        hint="Check that the backend is reachable."
        action={{ label: 'Retry', onAct: () => void historyQuery.refetch() }}
      />
    )
  }

  const items = data?.items ?? []
  const pages = data?.pages ?? 1

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <header className="flex shrink-0 flex-wrap items-end justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold tracking-[0.22em] text-accent/80 uppercase">
            Runs &amp; reports
          </p>
          <h1 className="text-base font-semibold tracking-tight text-white sm:text-lg">
            Analysis history
          </h1>
          <p className="stat-num text-xs text-slate-500">
            {data?.total ?? 0} analyses · page {data?.page ?? 1} of {pages}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="flex items-center gap-2 text-xs text-slate-400">
            <span className="hidden sm:inline">Rows per page</span>
            <select
              value={pageSize}
              onChange={(event) => {
                setPageSize(Number.parseInt(event.target.value, 10))
                setPage(1)
              }}
              className="stat-num rounded-md border border-edge-strong bg-void/70 px-2 py-1 text-slate-200"
            >
              {PAGE_SIZES.map((size) => (
                <option key={size} value={size}>
                  {size}
                </option>
              ))}
            </select>
          </label>
          <Link
            to="/analysis/new"
            className="rounded-md bg-accent px-3 py-1.5 text-xs font-semibold text-void transition hover:bg-accent-soft"
          >
            New analysis
          </Link>
        </div>
      </header>

      <Panel
        className="min-h-0 flex-1"
        bodyClassName="flex min-h-0 flex-col p-0"
        title="Recorded runs"
        hint="each row opens its own record"
      >
        {items.length === 0 ? (
          <div className="flex flex-1 items-center justify-center p-4">
            <StatePanel
              title="No analyses yet"
              hint="Start one from the New analysis workspace."
              action={{ label: 'New analysis', onAct: () => void navigate('/analysis/new') }}
            />
          </div>
        ) : (
          <div className="min-h-0 flex-1 overflow-y-auto">
            <table className="w-full text-left text-sm">
              <thead className="sticky top-0 z-10 bg-void/95 text-[10px] tracking-[0.14em] text-slate-500 uppercase backdrop-blur">
                <tr>
                  <th className="px-3 py-2 font-medium">Change</th>
                  <th className="hidden px-3 py-2 font-medium sm:table-cell">Kind</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 text-right font-medium">Failing</th>
                  <th className="hidden px-3 py-2 font-medium md:table-cell">When</th>
                  <th className="px-3 py-2 font-medium">Open</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-edge/60">
                {items.map((item) => {
                  const when = whenParts(item.created_at)
                  return (
                    <tr key={item.id} className="transition hover:bg-surface/40">
                      <td className="max-w-[34ch] truncate px-3 py-2 text-slate-200">
                        {item.goal || '(no goal text)'}
                      </td>
                      <td className="hidden px-3 py-2 text-xs text-slate-400 sm:table-cell">
                        {kindLabel(item.kind)}
                      </td>
                      <td className="px-3 py-2">
                        <StatusBadge label={item.status} tone={statusTone(item.status)} />
                      </td>
                      <td className="stat-num px-3 py-2 text-right text-xs text-slate-300">
                        {item.counts?.failures_stored ?? 0}
                      </td>
                      <td className="hidden px-3 py-2 text-xs text-slate-500 md:table-cell">
                        <span className="stat-num block">{when.date}</span>
                        <span className="stat-num block text-slate-600">{when.time}</span>
                      </td>
                      <td className="px-3 py-2">
                        <Link
                          to={destination(item)}
                          className="rounded border border-edge-strong px-2 py-1 text-xs text-slate-200 transition hover:border-accent/40 hover:text-white"
                        >
                          {linkLabel(item)}
                        </Link>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </Panel>

      <footer className="flex shrink-0 items-center justify-between gap-2 text-xs text-slate-400">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => setPage((value) => Math.max(1, value - 1))}
          className="rounded-md border border-edge-strong px-3 py-1.5 transition enabled:hover:border-accent/40 enabled:hover:text-slate-100 disabled:opacity-40"
        >
          ← Previous
        </button>
        <span className="stat-num">
          Page {data?.page ?? 1} / {pages}
        </span>
        <button
          type="button"
          disabled={page >= pages}
          onClick={() => setPage((value) => Math.min(pages, value + 1))}
          className="rounded-md border border-edge-strong px-3 py-1.5 transition enabled:hover:border-accent/40 enabled:hover:text-slate-100 disabled:opacity-40"
        >
          Next →
        </button>
      </footer>
    </div>
  )
}
