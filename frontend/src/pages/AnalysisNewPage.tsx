import { useMemo, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { ErrorPanel } from '../components/ErrorPanel'
import { StatePanel } from '../components/ui/StatePanel'
import { TabBar } from '../components/ui/TabBar'
import { usePlantList } from '../hooks/usePlants'
import { useRunSearch, useSearchCapabilities } from '../hooks/useSearches'
import { useViewport } from '../layout/useViewport'
import { usesWideLayout } from '../layout/viewport'
import {
  availablePresets,
  buildSearchRequest,
  defaultDraft,
  draftIssues,
  type SearchDraft,
  type SearchPreset,
} from '../search/plan'
import { SearchControls } from '../search/SearchControls'
import { SearchResults } from '../search/SearchResults'

type Pane = 'controls' | 'results'

/**
 * New analysis — the deterministic scenario search workspace (Part 7).
 *
 * One viewport: the plan editor and the result viewer are two panes that share
 * the screen on a wide layout and switch via tabs on a tablet/mobile one. The
 * engineer chooses a variable and a resolution; the search itself decides which
 * values matter, the simulator produces the trajectories, and the safety engine
 * produces the verdicts. No AI is involved anywhere in this page.
 */
export default function AnalysisNewPage() {
  const { viewport } = useViewport()
  const wide = usesWideLayout(viewport)
  const navigate = useNavigate()
  const plantsQuery = usePlantList()
  const capabilitiesQuery = useSearchCapabilities()
  const run = useRunSearch()

  const [draft, setDraft] = useState<SearchDraft>(() => defaultDraft())
  const [presetId, setPresetId] = useState('cooling_degradation')
  const [pane, setPane] = useState<Pane>('controls')

  const capabilities = capabilitiesQuery.data ?? null
  const plants = useMemo(
    () => (plantsQuery.data?.plants ?? []).map((plant) => ({ id: plant.id, name: plant.name })),
    [plantsQuery.data],
  )
  const presets = useMemo(
    () => availablePresets((capabilities?.variables ?? []).map((spec) => spec.variable)),
    [capabilities],
  )

  // The first plant is the default so a single-plant workspace needs no extra click.
  const plantId = draft.plantId ?? plants[0]?.id ?? null
  const effective: SearchDraft = { ...draft, plantId }
  const issues = capabilities ? draftIssues(effective, capabilities.limits) : []
  const canRun = Boolean(capabilities) && issues.length === 0 && !run.isPending

  function applyPreset(preset: SearchPreset) {
    setPresetId(preset.id)
    setDraft((current) => ({
      ...defaultDraft(preset),
      plantId: current.plantId,
      durationS: current.durationS,
      timeStepS: current.timeStepS,
      label: preset.id,
    }))
  }

  function submit() {
    if (!canRun) return
    // One click, one search: the mutation's pending state disables the button,
    // so a double click cannot start a second run.
    run.mutate(buildSearchRequest(effective), {
      onSuccess: () => {
        if (!wide) setPane('results')
      },
    })
  }

  let body
  if (capabilitiesQuery.isPending || plantsQuery.isPending) {
    body = <StatePanel tone="neutral" title="Loading search capabilities…" />
  } else if (capabilitiesQuery.isError) {
    body = (
      <div className="p-2">
        <ErrorPanel error={capabilitiesQuery.error} title="Search is unavailable" />
      </div>
    )
  } else if (plants.length === 0) {
    body = (
      <StatePanel
        tone="neutral"
        title="No plant to search"
        hint="A search runs real scenarios on a configured plant."
        action={{ label: 'Configure a plant', onAct: () => navigate('/plant') }}
      />
    )
  } else if (capabilities) {
    const controls = (
      <SearchControls
        capabilities={capabilities}
        plants={plants}
        presets={presets}
        presetId={presetId}
        draft={effective}
        issues={issues}
        running={run.isPending}
        onPreset={applyPreset}
        onDraft={(patch) => setDraft((current) => ({ ...current, ...patch }))}
        onRun={submit}
      />
    )
    // Remount per result so the viewer's tab/page/filter state starts fresh.
    const results = (
      <SearchResults
        key={run.data ? `result-${run.submittedAt}` : 'no-result'}
        result={run.data ?? null}
        running={run.isPending}
        error={run.error}
      />
    )

    body = wide ? (
      <div className="flex min-h-0 flex-1 gap-3">
        <div className="flex min-h-0 w-80 shrink-0 flex-col rounded-xl border border-slate-800 bg-slate-900/40 p-3">
          {controls}
        </div>
        <div className="flex min-h-0 min-w-0 flex-1 flex-col rounded-xl border border-slate-800 bg-slate-900/40 p-3">
          {results}
        </div>
      </div>
    ) : (
      <div className="flex min-h-0 flex-1 flex-col gap-2">
        <TabBar
          tabs={[
            { id: 'controls' as Pane, label: 'Plan' },
            { id: 'results' as Pane, label: 'Results' },
          ]}
          active={pane}
          onChange={setPane}
          label="Analysis panes"
        />
        <div className="flex min-h-0 min-w-0 flex-1 flex-col rounded-xl border border-slate-800 bg-slate-900/40 p-3">
          {pane === 'controls' ? controls : results}
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex shrink-0 flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold text-slate-100">New analysis</h1>
          <p className="text-xs text-slate-400">
            Search → Simulator → Safety engine → Evidence. The search chooses the values; the engineer decides what
            they mean.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-full border border-emerald-500/40 bg-emerald-500/10 px-2.5 py-1 text-[11px] text-emerald-300">
            Deterministic · no AI
          </span>
          <Link
            to="/monitor"
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 transition hover:bg-slate-800"
          >
            Live monitor
          </Link>
        </div>
      </div>

      {body}
    </div>
  )
}
