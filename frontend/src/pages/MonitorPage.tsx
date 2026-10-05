import { useMemo, useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { runScenario, type ScenarioInput } from '../api/telemetry'
import { ErrorPanel } from '../components/ErrorPanel'
import { ProcessTopology } from '../components/plant/ProcessTopology'
import { TelemetryCards } from '../components/monitor/TelemetryCards'
import { TelemetryChart } from '../components/monitor/TelemetryChart'
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

const PHASE_LABEL: Record<string, string> = {
  idle: 'Idle',
  connecting: 'Connecting',
  live: 'Live',
  reconnecting: 'Reconnecting',
  complete: 'Replay complete',
  error: 'Stream error',
}

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
      <div className={`rounded-lg border px-2.5 py-1.5 text-xs font-semibold uppercase ${STATUS_CLASS[safety.status]}`}>
        {safety.status.replace('_', ' ')}
      </div>
      <ul className="space-y-1">
        {safety.findings.map((finding) => (
          <li key={finding.type} className="flex items-center justify-between gap-2 text-[11px]">
            <span className="text-slate-300">{finding.type}</span>
            <span className={STATUS_CLASS[finding.status].split(' ').pop()}>
              {finding.status.replace('_', ' ')}
              {finding.measured_value !== null ? ` · ${finding.measured_value.toFixed(1)}` : ''}
            </span>
          </li>
        ))}
      </ul>
      <ul className="space-y-1 border-t border-slate-800 pt-2">
        {safety.safeguards
          .filter((timing) => timing.trigger_time_s !== null)
          .map((timing) => (
            <li key={timing.safeguard} className="font-mono text-[10px] text-slate-500">
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

  // Default to the first plant without an effect that re-runs on every render.
  const plantId = selectedId ?? plants[0]?.id ?? null
  const detail = usePlant(plantId)
  const stream = useTelemetry(plantId, started)
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
      onSuccess: () => setStarted(true),
    })
  }

  if (list.isLoading) {
    return <p className="text-sm text-slate-500">Loading plants…</p>
  }
  if (list.isError) {
    return <ErrorPanel error={list.error} title="Could not load plants" />
  }
  if (plants.length === 0) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 text-center">
        <p className="text-sm text-slate-300">No plants configured yet.</p>
        <Link
          to="/plant"
          className="rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400"
        >
          Configure a plant
        </Link>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <div className="flex shrink-0 flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold text-white">Live monitor</h1>
          <p className="text-xs text-slate-500">
            Deterministic simulated telemetry · SSE stream · no LLM per tick.
          </p>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs text-slate-300">
          <span
            aria-hidden="true"
            className={`h-2 w-2 rounded-full ${
              stream.phase === 'live' ? 'bg-emerald-400' : stream.phase === 'error' ? 'bg-rose-500' : 'bg-amber-400'
            }`}
          />
          {PHASE_LABEL[stream.phase] ?? stream.phase}
        </span>
      </div>

      <div className="flex shrink-0 flex-wrap items-center gap-2">
        <select
          value={plantId ?? ''}
          onChange={(event) => {
            setSelectedId(event.target.value)
            setStarted(false)
          }}
          className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs text-slate-200"
        >
          {plants.map((plant) => (
            <option key={plant.id} value={plant.id}>
              {plant.name}
            </option>
          ))}
        </select>
        <select
          value={presetId}
          onChange={(event) => setPresetId(event.target.value)}
          className="rounded-lg border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs text-slate-200"
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
          className="rounded-lg bg-cyan-500 px-4 py-1.5 text-xs font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:opacity-60"
        >
          {run.isPending ? 'Running…' : 'Run & stream'}
        </button>
      </div>

      {run.isError && (
        <div className="shrink-0">
          <ErrorPanel error={run.error} title="Could not run scenario" />
        </div>
      )}

      <div className="grid min-h-0 flex-1 grid-cols-1 gap-3 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        {/* Desktop: process graph + safety. Mobile hides it (one viz at a time). */}
        <div className="hidden min-h-0 flex-col gap-3 lg:flex">
          {detail.data && <ProcessTopology plant={detail.data.plant} />}
          <div className="min-h-0 flex-1 overflow-auto rounded-xl border border-slate-800 bg-slate-900/60 p-3">
            <p className="mb-2 text-[10px] tracking-wide text-slate-500 uppercase">
              Safety verdict (deterministic)
            </p>
            <SafetyPanel safety={safety} />
          </div>
        </div>

        {/* Chart workspace: cards + tabs (the single mobile visualization). */}
        <div className="flex min-h-0 flex-col gap-3">
          <TelemetryCards frame={lastFrame} />
          <TelemetryChart frames={stream.frames} />
        </div>
      </div>
    </div>
  )
}
