import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ApiError } from '../api/client'
import { StatePanel } from '../components/ui/StatePanel'
import { Panel } from '../components/ui/Panel'
import { TabBar, type TabItem } from '../components/ui/TabBar'
import { IconAnalyze } from '../components/ui/Icons'
import { usePlantList } from '../hooks/usePlants'
import { useRunAnalysis } from '../hooks/useAnalyses'
import { EVENT_LABELS, type EventKind, type InterpretedChange } from '../types/analysis'

/**
 * New autonomous analysis (Part 9) — the end-user workflow entry.
 *
 * The engineer describes the change, reviews the *interpreted change* (read
 * mechanically by the backend from the sanitized text), then FIND HIDDEN
 * RISKS starts one real bounded run. A duplicate click while a run is in
 * flight is disabled locally and answered 409 by the server regardless; the
 * run is synchronous, so the workspace navigates to the live page where the
 * actual events appear as they happened.
 *
 * Visual transformation: the question leads ("What changed?"), the input reads
 * as one instrument, and the button is the single accent element on the screen.
 */

type Pane = 'describe' | 'plan'

const SUGGESTION = 'Increase production throughput by 30%.'

const TABS: readonly TabItem<Pane>[] = [
  { id: 'describe', label: 'Describe the change' },
  { id: 'plan', label: 'What will be tested' },
]

function describeInterpretation(interpretation: InterpretedChange | null): string[] {
  if (!interpretation) return []
  const lines: string[] = []
  if (interpretation.direction === 'increase') lines.push('Direction read: increase.')
  else if (interpretation.direction === 'decrease') lines.push('Direction read: decrease.')
  else if (interpretation.direction === 'conflicting')
    lines.push('Direction words conflict; the text will be treated as data only.')
  if (interpretation.magnitude)
    lines.push(`Magnitude read: ${interpretation.magnitude}${interpretation.is_percent ? ' (percent)' : ''}.`)
  if (interpretation.variables.length > 0)
    lines.push(`Affected allowlisted variables: ${interpretation.variables.join(', ')}.`)
  for (const gap of interpretation.unrecognised) lines.push(`Note: ${gap}.`)
  if (lines.length === 0) lines.push('No direction or equipment noun was recognised; a default bounded search will run.')
  return lines
}

/**
 * Search-space motif: one row of candidate scenarios with a single amber bar
 * marking where the boundary search concentrates. Decorative, no motion, no
 * numbers — the run itself decides every value.
 */
function SearchSpaceMotif() {
  const heights = [6, 9, 13, 18, 24, 30, 36, 40, 34, 27, 21, 16, 11, 8, 6, 4]
  return (
    <div className="panel-inset flex shrink-0 items-end gap-1 px-3 py-1.5" aria-hidden="true">
      {heights.map((height, index) => (
        <span
          key={`${height}-${index}`}
          className={`w-full rounded-sm ${index === 7 ? 'bg-amber-400/80' : 'bg-accent/25'}`}
          style={{ height }}
        />
      ))}
    </div>
  )
}

export default function AnalysisNewPage() {
  const navigate = useNavigate()
  const plantsQuery = usePlantList()
  const run = useRunAnalysis()
  const [pane, setPane] = useState<Pane>('describe')
  const [goal, setGoal] = useState('')
  const [error, setError] = useState<string | null>(null)

  const plants = useMemo(
    () => (plantsQuery.data?.plants ?? []).map((plant) => ({ id: plant.id, name: plant.name })),
    [plantsQuery.data],
  )
  const plantId = plants[0]?.id ?? null

  const trimmed = goal.trim()
  const tooLong = goal.length > 2000
  const canRun = Boolean(plantId) && trimmed.length > 0 && !tooLong && !run.isPending

  function handleSubmit() {
    if (!canRun || !plantId) return
    setError(null)
    run.mutate(
      { plant_id: plantId, goal: trimmed },
      {
        onSuccess: (analysis) => {
          void navigate(`/analysis/${analysis.id}/live`)
        },
        onError: (err) => {
          if (err instanceof ApiError) setError(err.message)
          else setError('The analysis could not be started. Please try again.')
        },
      },
    )
  }

  if (plantsQuery.isLoading) {
    return <StatePanel title="Loading plants…" hint="The workspace needs one of your plants." />
  }
  if (plants.length === 0) {
    return (
      <StatePanel
        tone="warn"
        title="No plant configured yet"
        hint="An analysis runs over one of your configured plants."
        action={{ label: 'Set up a plant', onAct: () => void navigate('/plant') }}
      />
    )
  }
  if (plantsQuery.isError) {
    return (
      <StatePanel
        tone="crit"
        title="Plants could not be loaded"
        hint="Check that the backend is reachable, then retry."
        action={{ label: 'Retry', onAct: () => void plantsQuery.refetch() }}
      />
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <header className="flex shrink-0 flex-wrap items-end justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold tracking-[0.22em] text-accent/80 uppercase">
            Autonomous analysis
          </p>
          <h1 className="text-base font-semibold tracking-tight text-white sm:text-lg">
            What changed?
          </h1>
          <p className="truncate text-xs text-slate-500">
            Plant: <span className="text-slate-300">{plants[0]?.name}</span> · SafeFlux explores
            simulated scenarios only; it never actuates real equipment.
          </p>
        </div>
      </header>

      <SearchSpaceMotif />

      <TabBar tabs={TABS} active={pane} onChange={setPane} label="Analysis sections" />

      <Panel
        className="min-h-0 flex-1"
        bodyClassName="flex min-h-0 flex-col p-4"
        title={pane === 'describe' ? 'Engineering change' : 'Planned investigation'}
        hint={
          pane === 'describe'
            ? 'describe it the way you would to a colleague'
            : 'fixed, honest shape of one run'
        }
      >
        {pane === 'describe' ? (
          <div className="flex min-h-0 flex-1 flex-col gap-4">
            <label htmlFor="analysis-goal" className="text-sm font-medium text-slate-200">
              Proposed engineering change
            </label>
            <textarea
              id="analysis-goal"
              value={goal}
              maxLength={2000}
              rows={5}
              placeholder={SUGGESTION}
              onChange={(event) => setGoal(event.target.value)}
              className="min-h-24 w-full flex-1 resize-none rounded-md border border-edge-strong bg-void/70 px-3 py-2.5 text-sm leading-relaxed text-slate-100 placeholder:text-slate-600 focus:border-accent/60 focus:outline-none"
            />
            <div className="flex items-center justify-between text-xs text-slate-500">
              <button
                type="button"
                onClick={() => setGoal(SUGGESTION)}
                className="rounded border border-edge-strong px-2 py-1 text-slate-300 transition hover:border-accent/40 hover:text-slate-100"
              >
                Use example
              </button>
              <span className="stat-num">{goal.length}/2000</span>
            </div>
            {error && (
              <p role="alert" className="rounded-md border border-rose-600/50 bg-rose-950/40 px-3 py-2 text-sm text-rose-200">
                {error}
              </p>
            )}
            <div className="mt-auto flex items-center justify-end gap-3">
              <Link to="/dashboard" className="text-xs text-slate-400 hover:text-slate-200">
                Cancel
              </Link>
              <button
                type="button"
                disabled={!canRun}
                onClick={handleSubmit}
                className="inline-flex items-center gap-2 rounded-md bg-accent px-5 py-2 text-sm font-semibold tracking-wide text-void transition enabled:hover:bg-accent-soft disabled:cursor-not-allowed disabled:opacity-40"
              >
                <IconAnalyze className="h-4 w-4" />
                {run.isPending ? 'Running analysis…' : 'FIND HIDDEN RISKS'}
              </button>
            </div>
          </div>
        ) : (
          <PlanPreview goal={trimmed} />
        )}
      </Panel>
    </div>
  )
}

/**
 * What will be tested — the fixed, honest shape of one run. The interpreted
 * change is derived locally with the same mechanical rules the backend uses,
 * purely as a preview; the run itself re-reads the sanitized text server-side.
 */
function PlanPreview({ goal }: { goal: string }) {
  const preview = useMemo(() => previewInterpretation(goal), [goal])
  const stages: EventKind[] = [
    'understanding_change',
    'mapping_equipment',
    'planning',
    'running_scenario',
    'observing_result',
    'refining_boundary',
    'finding_violation',
    'running_counterfactual',
    'checking_safeguard',
  ]
  return (
    <div className="flex min-h-0 flex-col gap-4 overflow-y-auto">
      <div>
        <h2 className="text-sm font-semibold text-slate-200">Interpreted change</h2>
        <ul className="mt-2 space-y-1 text-xs text-slate-400">
          {describeInterpretation(preview).map((line) => (
            <li key={line}>{line}</li>
          ))}
        </ul>
        <p className="mt-2 text-[11px] text-slate-500">
          This preview is a local reading of your text. The backend re-reads the sanitized
          text itself when the run starts; the simulator, not this reading, decides every number.
        </p>
      </div>
      <div>
        <h2 className="text-sm font-semibold text-slate-200">Stages the run will record</h2>
        <ol className="mt-2 space-y-1">
          {stages.map((kind, index) => (
            <li key={kind} className="panel-inset flex items-center gap-2 px-2.5 py-1.5 text-xs text-slate-300">
              <span className="stat-num text-[10px] text-slate-500">
                {String(index + 1).padStart(2, '0')}
              </span>
              {EVENT_LABELS[kind]}
            </li>
          ))}
        </ol>
        <p className="mt-2 text-[11px] text-slate-500">
          Each stage appears on the live page only when the backend actually finished it,
          with its real elapsed time. Nothing is animated to look active.
        </p>
      </div>
    </div>
  )
}

/** Local mirror of the backend's mechanical reading (direction/magnitude only). */
function previewInterpretation(text: string): InterpretedChange | null {
  const value = text.trim()
  if (!value) return null
  const lowered = value.toLowerCase()
  const increaseWords = ['increase', 'raise', 'boost', 'more', 'higher', 'ramp up', 'step up']
  const decreaseWords = ['decrease', 'reduce', 'less', 'lower', 'cut', 'shut down', 'turn down']
  const hasIncrease = increaseWords.some((word) => lowered.includes(word))
  const hasDecrease = decreaseWords.some((word) => lowered.includes(word))
  const direction = hasIncrease && !hasDecrease ? 'increase' : hasDecrease && !hasIncrease ? 'decrease' : hasIncrease && hasDecrease ? 'conflicting' : null
  const match = /(\d+(?:\.\d+)?)\s*(%|x)?/.exec(lowered)
  const magnitudeValue = match ? Number.parseFloat(match[1]) : null
  const isPercent = Boolean(match?.[2] === '%')
  const magnitude = magnitudeValue === null ? null : `${match?.[1] ?? ''}${isPercent ? '%' : match?.[2] === 'x' ? 'x' : ''}`
  return {
    text: value,
    direction,
    magnitude,
    magnitude_value: magnitudeValue,
    is_percent: isPercent,
    variables: [],
    unrecognised: [],
  }
}
