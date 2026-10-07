import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { StatePanel } from '../components/ui/StatePanel'
import { TabBar, type TabItem } from '../components/ui/TabBar'
import { useAnalysis, useAnalysisEvents } from '../hooks/useAnalyses'
import { EVENT_LABELS, type AnalysisEventOut, type EventKind } from '../types/analysis'

/**
 * Live investigation (Part 9) — the actual backend events, cursor-polled.
 *
 * There is no local timer that advances a fake progress state: the timeline
 * grows only when the backend reports new events, and each row shows the real
 * elapsed time the event carries. While the run works and nothing new has
 * arrived, the page says exactly that. The step navigator lets the engineer
 * read one event's recorded payload at a time instead of one long scroll.
 */

type View = 'timeline' | 'detail'

const TABS: readonly TabItem<View>[] = [
  { id: 'timeline', label: 'Timeline' },
  { id: 'detail', label: 'Event detail' },
]

function formatElapsed(ms: number): string {
  if (ms < 1000) return `${ms} ms`
  return `${(ms / 1000).toFixed(1)} s`
}

function payloadLines(event: AnalysisEventOut): string[] {
  const payload = event.payload ?? {}
  return Object.entries(payload)
    .filter(([, value]) => value !== undefined && value !== null)
    .map(([key, value]) => `${key}: ${typeof value === 'object' ? JSON.stringify(value) : String(value)}`)
    .slice(0, 12)
}

export default function AnalysisLivePage() {
  const { id } = useParams<{ id: string }>()
  const analysisQuery = useAnalysis(id)
  const analysis = analysisQuery.data
  const { events, pollError } = useAnalysisEvents(id, analysis?.status)
  const [view, setView] = useState<View>('timeline')
  const [selected, setSelected] = useState<number>(1)

  const status = analysis?.status
  const lastKind = events.length > 0 ? events[events.length - 1].kind : null
  const finished = status === 'complete' || status === 'failed'

  const selectedEvent = useMemo(
    () => events.find((event) => event.seq === selected) ?? events[events.length - 1] ?? null,
    [events, selected],
  )

  if (analysisQuery.isLoading) return <StatePanel title="Loading analysis…" />
  if (analysisQuery.isError || !analysis) {
    return (
      <StatePanel
        tone="crit"
        title="Analysis not found"
        hint="It may belong to another account."
        action={{ label: 'Back to history', onAct: () => window.history.back() }}
      />
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <header className="shrink-0">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-lg font-semibold text-slate-100">Live investigation</h1>
            <p className="text-xs text-slate-400">
              {analysis.goal || '(no goal text)'} · status:{' '}
              <span className={status === 'failed' ? 'text-rose-300' : 'text-cyan-300'}>{status}</span>
            </p>
          </div>
          <nav className="flex gap-2 text-xs">
            {finished && analysis.has_result !== false && (
              <Link
                to={`/analysis/${analysis.id}/investigation`}
                className="rounded-lg border border-slate-700 px-3 py-1.5 text-slate-200 transition hover:bg-slate-800"
              >
                Open evidence
              </Link>
            )}
            <Link
              to="/history"
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-slate-300 transition hover:bg-slate-800"
            >
              History
            </Link>
          </nav>
        </div>
      </header>

      <TabBar tabs={TABS} active={view} onChange={setView} label="Live view sections" />

      <section className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-slate-800 bg-slate-900/50 p-4">
        {view === 'timeline' ? (
          <EventTimeline
            events={events}
            status={status ?? 'running'}
            pollError={pollError !== null}
            lastKind={lastKind}
            onSelect={(seq) => {
              setSelected(seq)
              setView('detail')
            }}
          />
        ) : (
          <EventDetail event={selectedEvent} finished={finished} />
        )}
      </section>
    </div>
  )
}

function EventTimeline({
  events,
  status,
  pollError,
  lastKind,
  onSelect,
}: {
  events: AnalysisEventOut[]
  status: string
  pollError: boolean
  lastKind: EventKind | null
  onSelect: (seq: number) => void
}) {
  const working = status === 'running'
  return (
    <div className="flex flex-col gap-2">
      <p className="text-xs text-slate-500">
        These are the backend's real pipeline events. Times are measured offsets from run start.
      </p>
      {events.length === 0 && working && !pollError && (
        <p className="rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2 text-sm text-slate-400">
          Waiting for the first recorded event from the backend. The run is working; nothing is
          simulated here.
        </p>
      )}
      {pollError && events.length === 0 && (
        <p role="alert" className="rounded-lg border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-sm text-amber-200">
          The event stream could not be read. The run itself is unaffected; retry will pick up
          where the cursor stopped.
        </p>
      )}
      <ol className="flex flex-col gap-1.5">
        {events.map((event) => (
          <li key={event.seq}>
            <button
              type="button"
              onClick={() => onSelect(event.seq)}
              className="flex w-full items-center justify-between gap-3 rounded-lg border border-slate-800 bg-slate-950/60 px-3 py-2 text-left transition hover:border-cyan-500/40"
            >
              <span className="flex min-w-0 items-center gap-3">
                <span className="shrink-0 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-400">
                  #{event.seq}
                </span>
                <span className="truncate text-sm text-slate-200">{EVENT_LABELS[event.kind] ?? event.kind}</span>
              </span>
              <span className="shrink-0 text-xs text-slate-500">{formatElapsed(event.elapsed_ms)}</span>
            </button>
          </li>
        ))}
      </ol>
      {working && events.length > 0 && (
        <p className="text-xs text-slate-500">
          Last recorded: {EVENT_LABELS[lastKind as EventKind] ?? lastKind}. Polling the backend for
          the next real event.
        </p>
      )}
      {status === 'complete' && (
        <p className="rounded-lg border border-emerald-500/40 bg-emerald-500/5 px-3 py-2 text-sm text-emerald-200">
          Analysis complete. The full evidence document is stored — open it from the evidence page.
        </p>
      )}
      {status === 'failed' && (
        <p className="rounded-lg border border-rose-600/50 bg-rose-950/40 px-3 py-2 text-sm text-rose-200">
          Analysis failed. The events above are the record of how far it got.
        </p>
      )}
      {status === 'interrupted' && (
        <p className="rounded-lg border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-sm text-amber-200">
          The backend restarted while this run was in flight; its outcome is unknown. Re-run the
          analysis to produce a complete record.
        </p>
      )}
    </div>
  )
}

function EventDetail({ event, finished }: { event: AnalysisEventOut | null; finished: boolean }) {
  if (!event) {
    return <p className="text-sm text-slate-400">No event selected yet.</p>
  }
  const lines = payloadLines(event)
  return (
    <div className="flex min-h-0 flex-col gap-3">
      <StepNavigator count={0} current={event.seq} onNavigate={() => undefined} hidden />
      <h2 className="text-sm font-semibold text-slate-200">
        #{event.seq} {EVENT_LABELS[event.kind] ?? event.kind}
      </h2>
      <p className="text-xs text-slate-500">Elapsed from run start: {formatElapsed(event.elapsed_ms)}</p>
      {lines.length > 0 ? (
        <dl className="grid gap-1 rounded-lg border border-slate-800 bg-slate-950/60 p-3 text-xs">
          {lines.map((line) => (
            <div key={line} className="break-all font-mono text-slate-300">
              {line}
            </div>
          ))}
        </dl>
      ) : (
        <p className="text-xs text-slate-500">This event carries no recorded payload.</p>
      )}
      {!finished && (
        <p className="text-[11px] text-slate-500">
          Later events may still arrive; this detail updates as the backend records them.
        </p>
      )}
    </div>
  )
}

/**
 * Step navigator — prev/next across the recorded events. Rendered inline
 * inside the detail pane (hidden when used decoratively above).
 */
function StepNavigator({
  count,
  current,
  onNavigate,
  hidden,
}: {
  count: number
  current: number
  onNavigate: (seq: number) => void
  hidden?: boolean
}) {
  if (hidden) return null
  return (
    <div className="flex items-center gap-2">
      <button type="button" onClick={() => onNavigate(Math.max(1, current - 1))} disabled={current <= 1}>
        ← Previous
      </button>
      <span className="text-xs text-slate-500">
        {current} / {count}
      </span>
      <button type="button" onClick={() => onNavigate(Math.min(count, current + 1))} disabled={current >= count}>
        Next →
      </button>
    </div>
  )
}
