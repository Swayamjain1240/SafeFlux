import { useQuery } from '@tanstack/react-query'
import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { fetchTelemetryCurrent } from '../api/telemetry'
import { classifyApiFailure, type QueryFailure } from '../api/failure'
import { ApiError } from '../api/client'
import { useAuth } from '../auth/context'
import { useAssessmentFor } from '../hooks/useAssessment'
import { usePlantList, usePlant } from '../hooks/usePlants'
import { useReducedMotion } from '../animation/useReducedMotion'
import { useViewport } from '../layout/useViewport'
import { deriveDashboardView, type Tone } from '../dashboard/viewState'
import {
  DASHBOARD_TABS,
  isCompact,
  metricColumns,
  usesWideLayout,
  visiblePanels,
  type DashboardTab,
} from '../layout/viewport'
import { ProcessGraph, type ProcessSnapshot } from '../components/plant/ProcessGraph'
import { MetricGrid } from '../components/dashboard/MetricGrid'
import { FindingsPanel } from '../components/dashboard/FindingsPanel'
import { StatePanel } from '../components/ui/StatePanel'
import { StatusBadge } from '../components/ui/StatusBadge'
import { TabBar } from '../components/ui/TabBar'
import { IconPulse, IconShield } from '../components/ui/Icons'

function failureOf(error: unknown): QueryFailure | null {
  if (!error) return null
  if (error instanceof ApiError) return classifyApiFailure({ status: error.status, code: error.code })
  return 'unknown'
}

const TAB_ITEMS = DASHBOARD_TABS.map((id) => ({
  id,
  label: id === 'overview' ? 'Overview' : id === 'process' ? 'Process' : 'Findings',
}))

/**
 * Compact command-cell used by the status rail: uppercase caption, primary
 * value and an optional hint — the control-room equivalent of a bezel readout.
 */
function CommandCell({
  label,
  value,
  hint,
  tone = 'idle',
  icon,
}: {
  label: string
  value: string
  hint?: string
  tone?: Tone
  icon?: ReactNode
}) {
  const dot = {
    ok: 'bg-emerald-400',
    warn: 'bg-amber-400',
    crit: 'bg-rose-500',
    idle: 'bg-slate-500',
  }[tone]

  return (
    <div className="panel-inset flex min-w-0 items-center gap-2.5 px-2.5 py-2">
      {icon ? (
        <span className="shrink-0 text-slate-500" aria-hidden="true">
          {icon}
        </span>
      ) : (
        <span aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 rounded-full ${dot}`} />
      )}
      <div className="min-w-0">
        <p className="truncate text-[10px] font-semibold tracking-[0.16em] text-slate-500 uppercase">
          {label}
        </p>
        <p className="truncate text-xs font-medium text-slate-200">{value}</p>
        {hint && <p className="truncate text-[10px] text-slate-500">{hint}</p>}
      </div>
    </div>
  )
}

function AnalysisStrip({
  record,
  compact,
}: {
  record: ReturnType<typeof useAssessmentFor>
  compact: boolean
}) {
  let body: ReactNode
  if (record) {
    body = (
      <>
        <p className="stat-num truncate text-sm text-accent">
          {record.scenarioLabel ?? record.safety.scenario_id ?? 'scenario'} ·{' '}
          {record.safety.status.replace(/_/g, ' ')}
        </p>
        {!compact && (
          <p className="mt-0.5 truncate text-[11px] text-slate-500">
            Deterministic verdict returned by the backend ·{' '}
            {new Date(record.recordedAt).toLocaleTimeString()}
          </p>
        )}
      </>
    )
  } else {
    body = (
      <>
        <p className="text-sm text-slate-300">No analysis in progress</p>
        {!compact && (
          <p className="mt-0.5 text-[11px] text-slate-500">
            Run a scenario to produce a verdict ·{' '}
            <Link to="/analysis/new" className="text-accent hover:text-accent-soft">
              let the search find the boundary
            </Link>
          </p>
        )}
      </>
    )
  }
  return (
    <div className="panel-inset shrink-0 border-l-2 border-l-accent/60 px-3 py-2">
      <p className="text-[10px] font-semibold tracking-[0.16em] text-slate-500 uppercase">
        Analysis status
      </p>
      <div className="mt-0.5 min-w-0">{body}</div>
    </div>
  )
}

export default function DashboardPage() {
  const { user } = useAuth()
  const plantsQuery = usePlantList()
  const plants = plantsQuery.data?.plants ?? []
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [tab, setTab] = useState<DashboardTab>('overview')

  const plantId = selectedId ?? plants[0]?.id ?? null
  const detail = usePlant(plantId)
  const plant = detail.data?.plant ?? null
  const record = useAssessmentFor(plantId)
  const reducedMotion = useReducedMotion()
  const { viewport } = useViewport()

  const currentQuery = useQuery({
    queryKey: ['telemetry', 'current', plantId ?? ''],
    queryFn: () => fetchTelemetryCurrent(plantId as string),
    enabled: Boolean(plantId),
    refetchInterval: 5000,
    retry: false,
  })

  const frame = currentQuery.data?.frame ?? null
  const telemetry: 'loading' | 'ready' | 'empty' | 'disconnected' = !plantId
    ? 'empty'
    : currentQuery.isPending
      ? 'loading'
      : currentQuery.isError
        ? 'disconnected'
        : frame
          ? 'ready'
          : 'empty'

  const safetyStatus = record
    ? record.safety.status
    : frame
      ? frame.status
      : 'unknown'

  const view = deriveDashboardView({
    plantsLoading: plantsQuery.isPending,
    plantsError: plantsQuery.isError ? failureOf(plantsQuery.error) : null,
    plantCount: plants.length,
    telemetry,
    safetyStatus,
    pumpRunning: frame?.pump_running ?? plant?.state.pump_running ?? false,
    reducedMotion,
  })

  if (view.status !== 'ready') {
    const action =
      view.status === 'empty'
        ? { label: 'Configure a plant', onAct: () => undefined }
        : view.status === 'offline' || view.status === 'error'
          ? { label: 'Retry', onAct: () => void plantsQuery.refetch() }
          : undefined
    return (
      <div className="flex h-full min-h-0 flex-col gap-3">
        <Header title="Engineering dashboard" subtitle={view.headline} />
        <div className="min-h-0 flex-1">
          <StatePanel
            tone={view.status === 'offline' || view.status === 'error' ? 'crit' : 'warn'}
            title={view.headline}
            hint={view.hint}
            action={view.status === 'empty' ? undefined : action}
          >
            {view.status === 'empty' && (
              <Link
                to="/plant"
                className="mt-4 inline-block rounded-md bg-accent px-4 py-2 text-sm font-semibold text-void transition hover:bg-accent-soft"
              >
                Configure a plant
              </Link>
            )}
            {view.status === 'session-expired' && (
              <Link
                to="/login"
                className="mt-4 inline-block rounded-md bg-accent px-4 py-2 text-sm font-semibold text-void transition hover:bg-accent-soft"
              >
                Sign in again
              </Link>
            )}
          </StatePanel>
        </div>
      </div>
    )
  }

  if (!plant) {
    return (
      <div className="flex h-full min-h-0 flex-col gap-3">
        <Header title="Engineering dashboard" subtitle="Loading plant…" />
        <div className="min-h-0 flex-1">
          <StatePanel title="Loading plant…" hint="Fetching the configuration for this plant." />
        </div>
      </div>
    )
  }

  const values: ProcessSnapshot = {
    temperature_c: frame?.values.temperature_c ?? plant.state.temperature_c,
    pressure_bar: frame?.values.pressure_bar ?? plant.state.pressure_bar,
    level_pct: frame?.values.level_pct ?? plant.state.level_pct,
    feed_flow_lpm: frame?.values.feed_flow_lpm ?? plant.config.feed_flow_lpm,
    outlet_flow_lpm: frame?.values.outlet_flow_lpm ?? 0,
    pump_running: frame?.pump_running ?? plant.state.pump_running,
  }

  const wide = usesWideLayout(viewport)
  const compact = isCompact(viewport)
  const columns = metricColumns(viewport)
  const panels = visiblePanels(viewport, tab)
  const live = telemetry === 'ready'
  const safetyLabel = record
    ? record.safety.status.replace(/_/g, ' ')
    : frame
      ? frame.status.replace(/_/g, ' ')
      : 'No telemetry yet'

  const violations = record
    ? record.safety.findings.filter((finding) => finding.status === 'violation').length
    : 0

  const processPanel = (
    <section className="flex h-full min-h-0 min-w-0 flex-col gap-2">
      <ProcessGraph
        plant={plant}
        values={values}
        safetyStatus={safetyStatus}
        reducedMotion={reducedMotion}
        className="min-h-0 flex-1"
      />
      <AnalysisStrip record={record} compact={compact} />
    </section>
  )

  const metricsPanel = (
    <MetricGrid plant={plant} values={values} live={live} columns={columns} compact={compact} />
  )

  const findingsPanel = <FindingsPanel record={record} className="h-full" />

  // Command rail: the four states an operator checks before anything else.
  const rail = (
    <div className={`grid shrink-0 gap-2 ${compact ? 'grid-cols-2' : 'grid-cols-2 xl:grid-cols-4'}`}>
      <CommandCell
        label="Safety state"
        value={safetyLabel}
        tone={view.safetyTone}
        hint={record || frame ? 'from the deterministic engine' : 'run a scenario'}
      />
      <CommandCell
        label="Telemetry"
        value={view.streamLabel}
        tone={view.streamTone}
        hint={live ? 'streaming now' : 'no live stream'}
        icon={<IconPulse className="h-4 w-4" />}
      />
      <CommandCell
        label="Findings"
        value={violations > 0 ? `${violations} violation${violations === 1 ? '' : 's'}` : 'None active'}
        tone={violations > 0 ? 'crit' : record ? 'ok' : 'idle'}
        hint={record ? `last run ${new Date(record.recordedAt).toLocaleTimeString()}` : 'no verdict yet'}
        icon={<IconShield className="h-4 w-4" />}
      />
      <CommandCell
        label="Plant"
        value={plant.name}
        tone="idle"
        hint={plant.location || 'configured process'}
      />
    </div>
  )

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <Header
        title="Engineering dashboard"
        eyebrow="Command center"
        subtitle={`${user?.fullName ?? 'Engineer'} · ${plant.name}${plant.location ? ` · ${plant.location}` : ''}`}
        right={
          <>
            <select
              value={plantId ?? ''}
              onChange={(event) => {
                setSelectedId(event.target.value)
                setTab('overview')
              }}
              aria-label="Select plant"
              className="max-w-40 truncate rounded-md border border-edge-strong bg-surface px-2 py-1.5 text-xs text-slate-200"
            >
              {plants.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
            <StatusBadge label={safetyLabel} tone={view.safetyTone} />
            <StatusBadge label={view.streamLabel} tone={view.streamTone} />
          </>
        }
      />

      {rail}

      {!wide && <TabBar tabs={TAB_ITEMS} active={tab} onChange={setTab} label="Dashboard panels" />}

      {/* The process graph gets the wider column so the full line stays
          readable at the narrow end of the wide layout (e.g. 1366×768). */}
      {wide ? (
        <div className="grid min-h-0 flex-1 gap-3 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)]">
          <div className="min-h-0">{processPanel}</div>
          <div className="flex min-h-0 min-w-0 flex-col gap-3">
            <div className="min-h-0 shrink-0">{metricsPanel}</div>
            <div className="min-h-0 flex-1">{findingsPanel}</div>
          </div>
        </div>
      ) : (
        <div className="min-h-0 flex-1">
          {panels.process ? processPanel : panels.overview ? metricsPanel : findingsPanel}
        </div>
      )}
    </div>
  )
}

function Header({
  title,
  subtitle,
  eyebrow,
  right,
}: {
  title: string
  subtitle: string
  eyebrow?: string
  right?: ReactNode
}) {
  return (
    <header className="flex shrink-0 flex-wrap items-end justify-between gap-2">
      <div className="min-w-0">
        {eyebrow && (
          <p className="text-[10px] font-semibold tracking-[0.22em] text-accent/80 uppercase">
            {eyebrow}
          </p>
        )}
        <h1 className="text-base font-semibold tracking-tight text-white sm:text-lg">{title}</h1>
        <p className="truncate text-xs text-slate-500">{subtitle}</p>
      </div>
      {right && <div className="flex min-w-0 flex-wrap items-center gap-2">{right}</div>}
    </header>
  )
}
