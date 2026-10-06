import { useState, type ReactNode } from 'react'
import { ErrorPanel } from '../components/ErrorPanel'
import { StatePanel } from '../components/ui/StatePanel'
import { StatusBadge } from '../components/ui/StatusBadge'
import { TabBar } from '../components/ui/TabBar'
import {
  countTiles,
  defaultFailureFilter,
  describeBoundary,
  describeTrace,
  describeValues,
  filterFailures,
  formatNumber,
  paginate,
  peakSummary,
  runTone,
  statusTone,
  type FailureFilter,
} from './plan'
import type { SearchResult } from '../types/search'

type ResultTab = 'summary' | 'failures' | 'boundaries' | 'ranking' | 'trace'

const RESULT_TABS: readonly { id: ResultTab; label: string }[] = [
  { id: 'summary', label: 'Summary' },
  { id: 'failures', label: 'Failures' },
  { id: 'boundaries', label: 'Boundaries' },
  { id: 'ranking', label: 'Ranking' },
  { id: 'trace', label: 'Trace' },
]

const ROWS_PER_PAGE = 8

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-slate-800 bg-slate-900/50 p-3">
      <h3 className="text-[10px] tracking-wide text-slate-500 uppercase">{title}</h3>
      <div className="mt-1.5 min-w-0">{children}</div>
    </section>
  )
}

function Pager({
  page,
  pageCount,
  total,
  onPage,
}: {
  page: number
  pageCount: number
  total: number
  onPage: (page: number) => void
}) {
  return (
    <div className="flex shrink-0 items-center justify-between gap-2 border-t border-slate-800 pt-2 text-xs text-slate-400">
      <span>
        {total} row{total === 1 ? '' : 's'} · page {page}/{pageCount}
      </span>
      <span className="flex gap-1">
        <button
          type="button"
          disabled={page <= 1}
          onClick={() => onPage(page - 1)}
          className="rounded-md border border-slate-700 px-2 py-1 transition enabled:hover:bg-slate-800 disabled:opacity-40"
        >
          Previous
        </button>
        <button
          type="button"
          disabled={page >= pageCount}
          onClick={() => onPage(page + 1)}
          className="rounded-md border border-slate-700 px-2 py-1 transition enabled:hover:bg-slate-800 disabled:opacity-40"
        >
          Next
        </button>
      </span>
    </div>
  )
}

/**
 * Result viewer (Part 7). Every panel is tabbed and paginated so a wide search
 * never becomes an endless page scroll: the bubbles are the four required
 * counts, and the lists are paged with explicit controls.
 */
export function SearchResults({
  result,
  running,
  error,
}: {
  result: SearchResult | null
  running: boolean
  error: unknown
}) {
  // A new result is a new document: stale filters must not hide its rows. The
  // caller remounts this component per result (key), so state starts clean
  // without an effect that would re-render on every arriving result.
  const [tab, setTab] = useState<ResultTab>('summary')
  const [filter, setFilter] = useState<FailureFilter>(defaultFailureFilter)
  const [page, setPage] = useState(1)

  if (running) {
    return <StatePanel tone="neutral" title="Running the search…" hint="Deterministic simulation only — no AI involved." />
  }
  if (error) {
    return (
      <div className="p-1">
        <ErrorPanel error={error} title="Search rejected" />
        <p className="mt-2 text-xs text-slate-500">
          Nothing was run. Adjust the plan and try again — the search never starts on an invalid request.
        </p>
      </div>
    )
  }
  if (!result) {
    return (
      <StatePanel
        tone="neutral"
        title="No search yet"
        hint="Pick a preset, choose a plant, and run. The search finds the safe/unsafe boundary by itself."
      />
    )
  }

  const counts = result.counts
  const failures = filterFailures(result.failures, filter)
  const failurePage = paginate(failures, page, ROWS_PER_PAGE)
  const tracePage = paginate(result.trace, page, ROWS_PER_PAGE)
  const failureOptions = Array.from(
    new Set(result.failures.flatMap((failure) => Object.keys(failure.values))),
  )
  const versions = (result.config?.versions ?? {}) as Record<string, unknown>

  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <div className="flex shrink-0 flex-wrap items-center gap-2">
        <StatusBadge label={`Search ${result.status}`} tone={runTone(result.status)} />
        <span className="text-xs text-slate-400">
          {counts.scenarios} scenario{counts.scenarios === 1 ? '' : 's'} · {counts.evaluations} simulation
          {counts.evaluations === 1 ? '' : 's'} · {result.budget.elapsed_s}s
        </span>
        {result.truncated && (
          <span className="rounded-full border border-amber-500/40 bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-200">
            budget reached — partial evidence
          </span>
        )}
      </div>

      <TabBar tabs={RESULT_TABS} active={tab} onChange={setTab} label="Search result sections" />

      <div className="min-h-0 flex-1 overflow-y-auto pr-1">
        {tab === 'summary' && (
          <div className="space-y-2">
            <div className="grid grid-cols-2 gap-2 sm:grid-cols-3">
              {countTiles(counts).map((tile) => (
                <div key={tile.key} className="rounded-lg border border-slate-800 bg-slate-900/50 px-2.5 py-2">
                  <p className="text-[10px] tracking-wide text-slate-500 uppercase">{tile.label}</p>
                  <p
                    className={[
                      'font-mono text-lg',
                      tile.tone === 'crit'
                        ? 'text-rose-300'
                        : tile.tone === 'warn'
                          ? 'text-amber-300'
                          : tile.tone === 'ok'
                            ? 'text-emerald-300'
                            : 'text-slate-200',
                    ].join(' ')}
                  >
                    {tile.value}
                  </p>
                  <p className="text-[10px] text-slate-500">{tile.hint}</p>
                </div>
              ))}
            </div>

            <Section title="Budget">
              <p className="font-mono text-xs text-slate-300">
                {result.budget.scenarios_used}/{result.budget.max_scenarios} scenarios · timeout {result.budget.timeout_s}s
                {result.budget.exceeded ? ` · stopped by ${result.budget.exceeded}` : ' · no limit reached'}
              </p>
            </Section>

            <Section title="Configuration">
              <p className="font-mono text-xs break-words text-slate-300">
                method v{String(versions.search_method_version ?? '?')} · simulator {String(versions.model_name ?? '?')} v
                {String(versions.model_version ?? '?')} · safety engine v{String(versions.safety_engine_version ?? '?')} ·
                search engine v{String(versions.search_engine_version ?? '?')}
              </p>
              <p className="mt-1 text-[11px] text-slate-500">
                Deterministic: {String(versions.deterministic ?? '?')} · AI involved: {String(versions.ai_involved ?? '?')}
              </p>
            </Section>

            {result.notes.length > 0 && (
              <Section title="Notes">
                <ul className="list-disc space-y-1 pl-4 text-xs text-slate-400">
                  {result.notes.map((note) => (
                    <li key={note}>{note}</li>
                  ))}
                </ul>
              </Section>
            )}
          </div>
        )}

        {tab === 'failures' && (
          <div className="flex h-full min-h-0 flex-col gap-2">
            <div className="flex shrink-0 flex-wrap items-center gap-2">
              <select
                aria-label="Filter failures by status"
                value={filter.status}
                onChange={(event) => {
                  setPage(1)
                  setFilter((current) => ({ ...current, status: event.target.value as FailureFilter['status'] }))
                }}
                className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"
              >
                <option value="all">Any failing status</option>
                <option value="violation">Violation</option>
                <option value="near_limit">Near limit</option>
                <option value="safeguard_activated">Safeguard</option>
              </select>
              <select
                aria-label="Filter failures by variable"
                value={filter.variable}
                onChange={(event) => {
                  setPage(1)
                  setFilter((current) => ({ ...current, variable: event.target.value }))
                }}
                className="rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"
              >
                <option value="all">Any variable</option>
                {failureOptions.map((name) => (
                  <option key={name} value={name}>
                    {name}
                  </option>
                ))}
              </select>
              <input
                value={filter.query}
                onChange={(event) => {
                  setPage(1)
                  setFilter((current) => ({ ...current, query: event.target.value }))
                }}
                placeholder="Filter text"
                aria-label="Filter failures by text"
                className="min-w-32 flex-1 rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-xs text-slate-200"
              />
            </div>

            {failures.length === 0 ? (
              <StatePanel
                tone={result.failures.length === 0 ? 'neutral' : 'warn'}
                title={result.failures.length === 0 ? 'No failure scenarios in this range' : 'No rows match the filter'}
                hint={
                  result.failures.length === 0
                    ? 'Every sampled point stayed inside its limits. Widen the range or vary another variable.'
                    : `${result.failures.length} failure(s) were recorded; clear the filter to see them.`
                }
              />
            ) : (
              <>
                <ul className="min-h-0 flex-1 space-y-1.5 overflow-y-auto pr-1">
                  {failurePage.items.map((failure) => (
                    <li key={failure.key} className="rounded-lg border border-slate-800 bg-slate-900/50 px-2.5 py-2">
                      <div className="flex items-center justify-between gap-2">
                        <StatusBadge label={failure.status.replace(/_/g, ' ')} tone={statusTone(failure.status)} />
                        <span className="font-mono text-[11px] text-slate-500">{peakSummary(failure)}</span>
                      </div>
                      <p className="mt-1 font-mono text-xs break-words text-slate-300">{describeValues(failure.values)}</p>
                      {failure.worst_finding && (
                        <p className="mt-0.5 text-xs text-slate-400">{failure.worst_finding.message}</p>
                      )}
                      {failure.shutdown_at_s !== null && (
                        <p className="mt-0.5 text-[11px] text-amber-300">safeguard shutdown at {failure.shutdown_at_s}s</p>
                      )}
                    </li>
                  ))}
                </ul>
                <Pager page={failurePage.page} pageCount={failurePage.pageCount} total={failurePage.total} onPage={setPage} />
              </>
            )}
          </div>
        )}

        {tab === 'boundaries' && (
          <div className="space-y-2">
            {result.boundaries.length === 0 ? (
              <StatePanel
                tone="neutral"
                title="No boundary candidate"
                hint="Either every point was acceptable, or refinement is off. A flat result is an honest answer."
              />
            ) : (
              result.boundaries.map((boundary) => (
                <Section key={boundary.variable} title={boundary.variable.replace(/_/g, ' ')}>
                  <p className="text-xs text-slate-300">{describeBoundary(boundary)}</p>
                  <p className="mt-1 text-[11px] text-slate-500">
                    {boundary.evaluations} refinement evaluation(s)
                    {boundary.boundary_estimate === null ? '' : ` · estimate ${formatNumber(boundary.boundary_estimate)}`}
                  </p>
                </Section>
              ))
            )}
          </div>
        )}

        {tab === 'ranking' && (
          <div className="space-y-2">
            {result.sensitivity.length === 0 ? (
              <StatePanel tone="neutral" title="No ranking in this run" hint="Run a sensitivity search to rank the variables." />
            ) : (
              <table className="w-full text-left text-xs">
                <thead className="text-[10px] tracking-wide text-slate-500 uppercase">
                  <tr>
                    <th className="py-1">Variable</th>
                    <th className="py-1">Influence</th>
                    <th className="py-1">Low end</th>
                    <th className="py-1">High end</th>
                    <th className="py-1">Note</th>
                  </tr>
                </thead>
                <tbody>
                  {result.sensitivity.map((row) => (
                    <tr key={row.variable} className="border-t border-slate-800 align-top">
                      <td className="py-1.5 pr-2 font-mono text-slate-300">{row.variable}</td>
                      <td className="py-1.5 pr-2">
                        <StatusBadge
                          label={row.influence}
                          tone={
                            row.influence === 'critical'
                              ? 'crit'
                              : row.influence === 'high'
                                ? 'warn'
                                : row.influence === 'moderate'
                                  ? 'warn'
                                  : 'idle'
                          }
                        />
                      </td>
                      <td className="py-1.5 pr-2 text-slate-400">
                        {formatNumber(row.low_value, 2)} → {row.low_status.replace(/_/g, ' ')}
                      </td>
                      <td className="py-1.5 pr-2 text-slate-400">
                        {formatNumber(row.high_value, 2)} → {row.high_status.replace(/_/g, ' ')}
                      </td>
                      <td className="py-1.5 text-slate-500">{row.note}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {tab === 'trace' && (
          <div className="flex h-full min-h-0 flex-col gap-2">
            <ol className="min-h-0 flex-1 space-y-1 overflow-y-auto pr-1 font-mono text-[11px] text-slate-400">
              {tracePage.items.map((entry, index) => (
                <li key={index} className="border-b border-slate-900 pb-1">
                  {describeTrace(entry)}
                </li>
              ))}
            </ol>
            <Pager page={tracePage.page} pageCount={tracePage.pageCount} total={tracePage.total} onPage={setPage} />
          </div>
        )}
      </div>
    </div>
  )
}
