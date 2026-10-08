import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { StatePanel } from '../components/ui/StatePanel'
import { Panel } from '../components/ui/Panel'
import { StatusBadge } from '../components/ui/StatusBadge'
import { TabBar, type TabItem } from '../components/ui/TabBar'
import { IconChevronRight } from '../components/ui/Icons'
import { useAnalysis, useAnalysisEvents } from '../hooks/useAnalyses'
import { deriveAgentStages } from '../animation/agentStages'
import { EVENT_LABELS, type AnalysisEventOut, type EventKind } from '../types/analysis'

/**
 * Live investigation (Part 9) — the actual backend events, cursor-polled.
 *
 * There is no local timer that advances a fake progress state: the timeline
 * grows only when the backend reports new events, and each row shows the real
 * elapsed time the event carries. While the run works and nothing new has
 * arrived, the page says exactly that. The step navigator lets the engineer
 * read one event's recorded payload at a time instead of one long scroll.
 *
 * Visual transformation: the stage rail (plan → simulate → observe →
 * investigate → re-test) is derived from the recorded events only, so a stage
 * lights up because its event exists — never because time passed.
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

/** Stage rail: real recorded events only (see animation/agentStages.ts). */
function StageRail({ events, status }: { events: AnalysisEventOut[]; status: string }) {
  const stages = useMemo(
    () => deriveAgentStages(events.map((event) => event.kind), status),
    [events, status],
  )

  return (
    <ol className="flex shrink-0 items-stretch gap-1.5 overflow-x-auto" aria-label="Agent stages">
      {stages.map((stage, index) => {
        const tone =
          stage.state === 'complete' ? 'border-safe/40 bg-safe/5' : stage.state === 'active' ? 'border-accent/50 bg-accent/10 glow-accent' : 'border-edge/70 bg-panel/60'
        const dot =
          stage.state === 'complete' ? 'bg-safe' : stage.state === 'active' ? 'bg-accent' : 'bg-slate-600'
        const text =
          stage.state === 'complete' ? 'text-safe' : stage.state === 'active' ? 'text-accent' : 'text-slate-500'
        return (
          <li key={stage.id} className="flex min-w-0 flex-1 items-center gap-1.5">
            <div className={`flex min-w-0 flex-1 items-center gap-2 rounded-md border px-2.5 py-2 ${tone}`}>
              <span aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} />
              <span className={`truncate text-[11px] font-semibold tracking-[0.12em] uppercase ${text}`}>
                {stage.label}
              </span>
              <span className="ml-auto hidden text-[10px] text-slate-500 sm:inline">
                {stage.state === 'complete' ? 'recorded' : stage.state === 'active' ? 'awaiting' : '—'}
              </span>
            </div>
            {index < stages.length - 1 && (
              <IconChevronRight className="hidden h-3.5 w-3.5 shrink-0 text-slate-600 sm:block" />
            )}
          </li>
        )
      })}
    </ol>
  )
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

  const lastEvent = events.length ? events[events.length - 1] : null

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <header className="flex shrink-0 flex-wrap items-end justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold tracking-[0.22em] text-accent/80 uppercase">
            Agent investigation
          </p>
          <h1 className="text-base font-semibold tracking-tight text-white sm:text-lg">
            Live investigation
          </h1>
          <p className="truncate text-xs text-slate-500">{analysis.goal || '(no goal text)'}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge
            label={`status: ${status}`}
            tone={status === 'failed' ? 'crit' : status === 'complete' ? 'ok' : 'warn'}
          />
          <StatusBadge
            label={`${events.length} event${events.length === 1 ? '' : 's'}`}
            tone={events.length ? 'ok' : 'idle'}
            title="Real pipeline events recorded by the backend"
          />
          <StatusBadge
            label={lastEvent ? `t + ${formatElapsed(lastEvent.elapsed_ms)}` : 'no timing yet'}
            tone="idle"
            title="Elapsed time carried by the latest recorded event"
          />
        </div>
        <nav className="flex w-full gap-2 text-xs sm:w-auto">
          {finished && analysis.has_result !== false && (
            <Link
              to={`/analysis/${analysis.id}/investigation`}
              className="rounded-md border border-accent/40 px-3 py-1.5 text-accent transition hover:bg-accent/10"
            >
              Open evidence
            </Link>
          )}
          <Link
            to="/history"
            className="rounded-md border border-edge-strong px-3 py-1.5 text-slate-300 transition hover:border-accent/40 hover:text-slate-100"
          >
            History
          </Link>
        </nav>
      </header>

      <StageRail events={events} status={status ?? 'running'} />

      <TabBar tabs={TABS} active={view} onChange={setView} label="Live view sections" />

      <Panel
        className="min-h-0 flex-1"
        bodyClassName="min-h-0 flex flex-col p-4"
        title={view === 'timeline' ? 'Recorded events' : 'Event payload'}
        hint="measured offsets from run start · nothing animated to look active"
        scroll
      >
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
          <EventDetail
            event={selectedEvent}
            finished={finished}
            count={events.length}
            onNavigate={setSelected}
          />
        )}
      </Panel>
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
        <p className="rounded-md border border-edge/80 bg-void/60 px-3 py-2 text-sm text-slate-400">
          Waiting for the first recorded event from the backend. The run is working; nothing is
          simulated here.
        </p>
      )}
      {pollError && events.length === 0 && (
        <p role="alert" className="rounded-md border border-warn/40 bg-warn/5 px-3 py-2 text-sm text-warn">
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
              className="flex w-full items-center justify-between gap-3 rounded-md border border-edge/70 bg-void/50 px-3 py-2 text-left transition hover:border-accent/40 hover:bg-accent/5"
            >
              <span className="flex min-w-0 items-center gap-3">
                <span className="stat-num shrink-0 rounded bg-surface-2 px-1.5 py-0.5 text-[10px] text-slate-400">
                  #{String(event.seq).padStart(2, '0')}
                </span>
                <span className="truncate text-sm text-slate-200">
                  {EVENT_LABELS[event.kind] ?? event.kind}
                </span>
              </span>
              <span className="stat-num shrink-0 text-xs text-slate-500">
                {formatElapsed(event.elapsed_ms)}
              </span>
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
        <p className="rounded-md border border-safe/40 bg-safe/5 px-3 py-2 text-sm text-safe">
          Analysis complete. The full evidence document is stored — open it from the evidence page.
        </p>
      )}
      {status === 'failed' && (
        <p className="rounded-md border border-crit/50 bg-crit/10 px-3 py-2 text-sm text-crit">
          Analysis failed. The events above are the record of how far it got.
        </p>
      )}
      {status === 'interrupted' && (
        <p className="rounded-md border border-warn/40 bg-warn/5 px-3 py-2 text-sm text-warn">
          The backend restarted while this run was in flight; its outcome is unknown. Re-run the
          analysis to produce a complete record.
        </p>
      )}
    </div>
  )
}

function EventDetail({
  event,
  finished,
  count,
  onNavigate,
}: {
  event: AnalysisEventOut | null
  finished: boolean
  count: number
  onNavigate: (seq: number) => void
}) {
  if (!event) {
    return <p className="text-sm text-slate-400">No event selected yet.</p>
  }
  const lines = payloadLines(event)
  const firstSeq = 1
  return (
    <div className="flex min-h-0 flex-col gap-3">
      <StepNavigator
        count={count}
        current={event.seq}
        onNavigate={onNavigate}
        firstSeq={firstSeq}
      />
      <h2 className="text-sm font-semibold text-slate-200">
        <span className="stat-num text-slate-500">#{String(event.seq).padStart(2, '0')}</span>{' '}
        {EVENT_LABELS[event.kind] ?? event.kind}
      </h2>
      <p className="text-xs text-slate-500">
        Elapsed from run start: <span className="stat-num">{formatElapsed(event.elapsed_ms)}</span>
      </p>
      {lines.length > 0 ? (
        <dl className="grid gap-1 rounded-md border border-edge/70 bg-void/60 p-3 text-xs">
          {lines.map((line) => (
            <div key={line} className="stat-num break-all text-slate-300">
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
 * Step navigator — prev/next across the recorded events, so one event's payload
 * is read at a time without scrolling the page (one-viewport rule).
 */
function StepNavigator({
  count,
  current,
  onNavigate,
  firstSeq,
}: {
  count: number
  current: number
  onNavigate: (seq: number) => void
  firstSeq: number
}) {
  if (count === 0) return null
  const button =
    'rounded-md border border-edge-strong px-2.5 py-1 text-[11px] text-slate-300 transition enabled:hover:border-accent/40 enabled:hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-40'
  return (
    <div className="flex shrink-0 items-center gap-2">
      <button
        type="button"
        className={button}
        onClick={() => onNavigate(Math.max(firstSeq, current - 1))}
        disabled={current <= firstSeq}
      >
        ← Previous
      </button>
      <span className="stat-num text-xs text-slate-500">
        {current} / {count}
      </span>
      <button
        type="button"
        className={button}
        onClick={() => onNavigate(Math.min(count, current + 1))}
        disabled={current >= count}
      >
        Next →
      </button>
    </div>
  )
}
