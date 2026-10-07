import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { StatePanel } from '../components/ui/StatePanel'
import { useAnalysesHistory } from '../hooks/useAnalyses'
import type { AnalysisOut } from '../types/analysis'

/**
 * Analysis history (Part 9) — server-paginated.
 *
 * The table shows one bounded page at a time: explicit Previous/Next controls
 * and a page-size selector, never an endless list. Each row links the record's
 * own destination (live view for running rows, report for completed ones).
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

function formatWhen(iso: string): string {
  try {
    return new Date(iso).toLocaleString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    })
  } catch {
    return iso
  }
}

const STATUS_TONE: Record<string, string> = {
  running: 'text-cyan-300',
  complete: 'text-emerald-300',
  failed: 'text-rose-300',
  interrupted: 'text-amber-300',
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
      <header className="flex shrink-0 flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold text-slate-100">Analysis history</h1>
          <p className="text-xs text-slate-400">
            {data?.total ?? 0} analyses · page {data?.page ?? 1} of {pages}
          </p>
        </div>
        <label className="flex items-center gap-2 text-xs text-slate-400">
          Rows per page
          <select
            value={pageSize}
            onChange={(event) => {
              setPageSize(Number.parseInt(event.target.value, 10))
              setPage(1)
            }}
            className="rounded border border-slate-700 bg-slate-950 px-2 py-1 text-slate-200"
          >
            {PAGE_SIZES.map((size) => (
              <option key={size} value={size}>
                {size}
              </option>
            ))}
          </select>
        </label>
      </header>

      <section className="flex min-h-0 flex-1 flex-col overflow-hidden rounded-xl border border-slate-800 bg-slate-900/50">
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
              <thead className="sticky top-0 bg-slate-950/90 text-xs text-slate-500 backdrop-blur">
                <tr>
                  <th className="px-3 py-2 font-medium">Goal</th>
                  <th className="px-3 py-2 font-medium">Kind</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Failing</th>
                  <th className="px-3 py-2 font-medium">When</th>
                  <th className="px-3 py-2 font-medium">Open</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/70">
                {items.map((item) => (
                  <tr key={item.id} className="hover:bg-slate-900/60">
                    <td className="max-w-[28ch] truncate px-3 py-2 text-slate-200">{item.goal || '(no goal text)'}</td>
                    <td className="px-3 py-2 text-xs text-slate-400">{kindLabel(item.kind)}</td>
                    <td className={`px-3 py-2 text-xs font-medium ${STATUS_TONE[item.status] ?? 'text-slate-300'}`}>
                      {item.status}
                    </td>
                    <td className="px-3 py-2 text-xs text-slate-300">{item.counts?.failures_stored ?? 0}</td>
                    <td className="px-3 py-2 text-xs text-slate-500">{formatWhen(item.created_at)}</td>
                    <td className="px-3 py-2">
                      <Link
                        to={destination(item)}
                        className="rounded border border-slate-700 px-2 py-1 text-xs text-slate-200 transition hover:bg-slate-800"
                      >
                        {item.status === 'running' ? 'Live' : item.kind === 'reverify' ? 'Reverify' : 'Report'}
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <footer className="flex shrink-0 items-center justify-between gap-2 text-xs text-slate-400">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => setPage((value) => Math.max(1, value - 1))}
          className="rounded-lg border border-slate-700 px-3 py-1.5 transition enabled:text-slate-200 enabled:hover:bg-slate-800 disabled:opacity-40"
        >
          ← Previous
        </button>
        <span>
          Page {data?.page ?? 1} / {pages}
        </span>
        <button
          type="button"
          disabled={page >= pages}
          onClick={() => setPage((value) => Math.min(pages, value + 1))}
          className="rounded-lg border border-slate-700 px-3 py-1.5 transition enabled:text-slate-200 enabled:hover:bg-slate-800 disabled:opacity-40"
        >
          Next →
        </button>
      </footer>
    </div>
  )
}
