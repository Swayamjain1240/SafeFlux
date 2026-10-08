import { useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { runScenario, type ScenarioInput } from '../api/telemetry'
import { ErrorPanel } from '../components/ErrorPanel'
import { ProcessGraph, type ProcessSnapshot } from '../components/plant/ProcessGraph'
import { TelemetryCards } from '../components/monitor/TelemetryCards'
import { TelemetryChart } from '../components/monitor/TelemetryChart'
import { Panel } from '../components/ui/Panel'
import { StatePanel } from '../components/ui/StatePanel'
import { StatusBadge } from '../components/ui/StatusBadge'
import { TabBar } from '../components/ui/TabBar'
import { IconPulse } from '../components/ui/Icons'
import { useReducedMotion } from '../animation/useReducedMotion'
import { useRecordAssessment } from '../hooks/useAssessment'
import { useViewport } from '../layout/useViewport'
import { usesWideLayout } from '../layout/viewport'
import { usePlant, usePlantList } from '../hooks/usePlants'
import { useTelemetry } from '../hooks/useTelemetry'
import type { SafetyAssessment, SafetyStatus } from '../types/telemetry'

interface Preset {
  id: string
  label: string
  scenario: ScenarioInput
}

const PRESETS: Preset[] = [
  { id: 'baseline', label: 'Baseline', scenario: { duration_s: 180, time_step_s: 1, label: 'baseline' } },
  {
    id: 'cooling_loss',
    label: 'Cooling loss',
    scenario: {
      duration_s: 300,
      time_step_s: 1,
      label: 'cooling loss',
      faults: [{ type: 'cooling_loss', start_s: 0 }],
    },
  },
  {
    id: 'feed_increase',
    label: 'Feed increase',
    scenario: {
      duration_s: 300,
      time_step_s: 1,
      label: 'feed increase',
      faults: [{ type: 'feed_increase', start_s: 0, factor: 3 }],
    },
  },
  {
    id: 'outlet_restriction',
    label: 'Outlet restriction',
    scenario: {
      duration_s: 300,
      time_step_s: 1,
      label: 'outlet restriction',
      faults: [{ type: 'outlet_restriction', start_s: 0, factor: 0.3 }],
    },
  },
]

const STATUS_CLASS: Record<SafetyStatus, string> = {
  safe: 'border-emerald-500/40 bg-emerald-500/5 text-emerald-300',
  near_limit: 'border-amber-500/40 bg-amber-500/5 text-amber-300',
  safeguard_activated: 'border-cyan-500/40 bg-cyan-500/5 text-cyan-300',
  violation: 'border-rose-500/50 bg-rose-500/10 text-rose-300',
}

type AnyStatus = 'safe' | 'near_limit' | 'safeguard_activated' | 'violation' | 'unknown'

const KNOWN_STATUSES = new Set<string>([
  'safe',
  'near_limit',
  'safeguard_activated',
  'violation',
])

const PHASE_LABEL: Record<string, string> = {
  idle: 'Idle',
  connecting: 'Connecting',
  live: 'Live',
  reconnecting: 'Reconnecting',
  complete: 'Replay complete',
  error: 'Stream error',
}

const PHASE_TONE: Record<string, 'ok' | 'warn' | 'crit' | 'idle'> = {
  live: 'ok',
  connecting: 'warn',
  reconnecting: 'warn',
  error: 'crit',
  idle: 'idle',
  complete: 'idle',
}

const CONTROL_CLASS =
  'rounded-md border border-edge-strong bg-surface px-2 py-1.5 text-xs text-slate-200 transition hover:border-accent/40'

function SafetyPanel({ safety }: { safety: SafetyAssessment | null }) {
  if (!safety) {
    return (
      <p className="text-xs text-slate-500">
        Run a scenario to produce a deterministic safety verdict. The AI never decides this.
      </p>
    )
  }
  return (
    <div className="space-y-2">
      <div className={`rounded-md border px-2.5 py-1.5 text-xs font-semibold uppercase ${STATUS_CLASS[safety.status]}`}>
        {safety.status.replace('_', ' ')}
      </div>
      <ul className="space-y-1">
        {safety.findings.map((finding) => (
          <li key={finding.type} className="flex items-center justify-between gap-2 text-[11px]">
            <span className="text-slate-300">{finding.type}</span>
            <span className={`stat-num ${STATUS_CLASS[finding.status].split(' ').pop()}`}>
              {finding.status.replace('_', ' ')}
              {finding.measured_value !== null ? ` · ${finding.measured_value.toFixed(1)}` : ''}
            </span>
          </li>
        ))}
      </ul>
      <ul className="space-y-1 border-t border-edge/70 pt-2">
        {safety.safeguards
          .filter((timing) => timing.trigger_time_s !== null)
          .map((timing) => (
            <li key={timing.safeguard} className="stat-num text-[10px] text-slate-500">
              {timing.safeguard}: trig {timing.trigger_time_s}s · resp{' '}
              {timing.response_time_s ?? '—'}s · viol {timing.violation_time_s ?? '—'}s ·{' '}
              <span className={timing.prevented ? 'text-emerald-400' : 'text-rose-400'}>
                {timing.prevented === null ? 'n/a' : timing.prevented ? 'prevented' : 'too late'}
              </span>
            </li>
          ))}
      </ul>
      <p className="text-[10px] leading-relaxed text-slate-600">
        Simulation only — never a claim about a real plant.
      </p>
    </div>
  )
}

export default function MonitorPage() {
  const list = usePlantList()
  const plants = list.data?.plants ?? []
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [presetId, setPresetId] = useState(PRESETS[0].id)
  const [started, setStarted] = useState(false)
  const [monitorTab, setMonitorTab] = useState<'telemetry' | 'process'>('telemetry')

  // Default to the first plant without an effect that re-runs on every render.
  const plantId = selectedId ?? plants[0]?.id ?? null
  const detail = usePlant(plantId)
  const plant = detail.data?.plant ?? null
  const stream = useTelemetry(plantId, started)
  const reducedMotion = useReducedMotion()
  const { viewport } = useViewport()
  const wide = usesWideLayout(viewport)
  const recordAssessment = useRecordAssessment()
  const run = useMutation({
    mutationFn: (scenario: ScenarioInput) => runScenario(plantId as string, scenario),
  })

  const preset = useMemo(() => PRESETS.find((p) => p.id === presetId) ?? PRESETS[0], [presetId])
  const lastFrame = stream.frames.length ? stream.frames[stream.frames.length - 1] : null
  const safety = run.data?.safety ?? null

  function handleStart() {
    if (!plantId) return
    setStarted(false)
    run.mutate(preset.scenario, {
      onSuccess: (data) => {
        // The dashboard reads this to show recent findings + analysis status.
        recordAssessment({
          plantId,
          scenarioLabel: preset.scenario.label ?? preset.id,
          recordedAt: Date.now(),
          safety: data.safety,
        })
        setStarted(true)
      },
    })
  }

  if (list.isLoading) {
    return <StatePanel title="Loading plants…" hint="Fetching your configured plants." />
  }
  if (list.isError) {
    return (
      <div className="h-full min-h-0">
        <StatePanel
          tone="crit"
          title="Could not load plants"
          hint="The API returned an error while loading your plants."
        >
          <div className="mt-3 text-left">
            <ErrorPanel error={list.error} title="Details" />
          </div>
        </StatePanel>
      </div>
    )
  }
  if (plants.length === 0) {
    return (
      <StatePanel title="No plants configured yet" hint="Create a plant before running a scenario.">
        <Link
          to="/plant"
          className="mt-4 inline-block rounded-md bg-accent px-4 py-2 text-sm font-semibold text-void transition hover:bg-accent-soft"
        >
          Configure a plant
        </Link>
      </StatePanel>
    )
  }

  const values: ProcessSnapshot = {
    temperature_c: lastFrame?.values.temperature_c ?? plant?.state.temperature_c ?? 0,
    pressure_bar: lastFrame?.values.pressure_bar ?? plant?.state.pressure_bar ?? 0,
    level_pct: lastFrame?.values.level_pct ?? plant?.state.level_pct ?? 0,
    feed_flow_lpm: lastFrame?.values.feed_flow_lpm ?? plant?.config.feed_flow_lpm ?? 0,
    outlet_flow_lpm: lastFrame?.values.outlet_flow_lpm ?? 0,
    pump_running: lastFrame?.pump_running ?? plant?.state.pump_running ?? false,
  }
  // streamState frames carry a plain string; narrow it to the known statuses.
  const safetyStatus: AnyStatus = safety
    ? safety.status
    : lastFrame && KNOWN_STATUSES.has(lastFrame.status)
      ? (lastFrame.status as AnyStatus)
      : 'unknown'

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      {/* ── Header: what is streaming, and how healthy the stream is ──────── */}
      <header className="flex shrink-0 flex-wrap items-end justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold tracking-[0.22em] text-accent/80 uppercase">
            Live telemetry
          </p>
          <h1 className="text-base font-semibold tracking-tight text-white sm:text-lg">Live monitor</h1>
          <p className="truncate text-xs text-slate-500">
            Deterministic simulated telemetry · SSE stream · no LLM per tick.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge
            label={PHASE_LABEL[stream.phase] ?? stream.phase}
            tone={PHASE_TONE[stream.phase] ?? 'idle'}
            title="Telemetry stream state"
          />
          <StatusBadge
            label={lastFrame ? `t = ${lastFrame.time_s.toFixed(0)}s` : 'no frames'}
            tone={lastFrame ? 'ok' : 'idle'}
            title="Simulated time from the latest streamed frame"
          />
        </div>
      </header>

      {/* ── Run controls ─────────────────────────────────────────────────── */}
      <div className="flex shrink-0 flex-wrap items-center gap-2">
        <select
          value={plantId ?? ''}
          onChange={(event) => {
            setSelectedId(event.target.value)
            setStarted(false)
          }}
          aria-label="Select plant"
          className={CONTROL_CLASS}
        >
          {plants.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
        <select
          value={presetId}
          onChange={(event) => setPresetId(event.target.value)}
          aria-label="Select scenario preset"
          className={CONTROL_CLASS}
        >
          {PRESETS.map((item) => (
            <option key={item.id} value={item.id}>
              {item.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={handleStart}
          disabled={run.isPending || !plantId}
          className="inline-flex items-center gap-1.5 rounded-md bg-accent px-4 py-1.5 text-xs font-semibold text-void transition hover:bg-accent-soft disabled:opacity-60"
        >
          <IconPulse className="h-3.5 w-3.5" />
          {run.isPending ? 'Running…' : 'Run & stream'}
        </button>
        <span className="text-[11px] text-slate-500">
          {plant ? `${plant.name} · ${plant.config.feed_flow_lpm} L/min feed` : ''}
        </span>
      </div>

      {run.isError && (
        <div className="shrink-0">
          <ErrorPanel error={run.error} title="Could not run scenario" />
        </div>
      )}

      {!wide && (
        <TabBar
          tabs={[
            { id: 'telemetry', label: 'Telemetry' },
            { id: 'process', label: 'Process & safety' },
          ]}
          active={monitorTab}
          onChange={setMonitorTab}
          label="Monitor panels"
        />
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        {/* Desktop: process graph + safety. Narrow viewports pick one panel. */}
        <div className={`min-h-0 flex-col gap-3 ${wide ? 'flex' : monitorTab === 'process' ? 'flex' : 'hidden'}`}>
          {plant && (
            <ProcessGraph
              plant={plant}
              values={values}
              safetyStatus={safetyStatus}
              reducedMotion={reducedMotion}
              className="h-52 sm:h-64"
            />
          )}
          <Panel
            title="Safety verdict"
            hint="deterministic — AI never decides this"
            className="min-h-0 flex-1"
            scroll
          >
            <SafetyPanel safety={safety} />
          </Panel>
        </div>

        {/* Chart workspace: cards + tabs (the single mobile visualization). */}
        <div className={`min-h-0 min-w-0 flex-col gap-3 ${wide ? 'flex' : monitorTab === 'telemetry' ? 'flex' : 'hidden'}`}>
          <TelemetryCards frame={lastFrame} />
          <div className="min-h-0 flex-1">
            <TelemetryChart frames={stream.frames} />
          </div>
        </div>
      </div>
    </div>
  )
}
