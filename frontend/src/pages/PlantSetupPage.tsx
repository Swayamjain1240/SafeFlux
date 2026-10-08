import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ErrorPanel } from '../components/ErrorPanel'
import { Panel } from '../components/ui/Panel'
import { StatusBadge } from '../components/ui/StatusBadge'
import { InstrumentTile } from '../components/ui/Instrument'
import { IconChevronRight } from '../components/ui/Icons'
import { PlantWizard } from '../components/plant/PlantWizard'
import { ProcessTopology } from '../components/plant/ProcessTopology'
import { useDeletePlant, usePlant, usePlantList } from '../hooks/usePlants'
import type { PlantDetail, PlantSummary } from '../types/plant'

type Mode = 'list' | 'new' | 'detail'

function fmtDate(value: string): string {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleDateString()
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="panel-inset px-2.5 py-2">
      <p className="text-[10px] tracking-wide text-slate-500 uppercase">{label}</p>
      <p className="stat-num mt-0.5 text-sm text-slate-200">{value}</p>
    </div>
  )
}

function PlantCard({ plant, onSelect }: { plant: PlantSummary; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className="panel flex w-full flex-col gap-1 p-3 text-left transition hover:border-accent/40"
    >
      <span className="flex items-center justify-between gap-2">
        <span className="truncate text-sm font-semibold text-slate-100">{plant.name}</span>
        <IconChevronRight className="h-4 w-4 shrink-0 text-slate-600" />
      </span>
      <span className="truncate text-xs text-slate-500">{plant.location || 'No location set'}</span>
      {plant.description && (
        <span className="line-clamp-2 text-[11px] text-slate-500">{plant.description}</span>
      )}
      <span className="stat-num mt-1 text-[10px] text-slate-600">
        Updated {fmtDate(plant.updated_at)}
      </span>
    </button>
  )
}

function PlantDetailView({
  plant,
  onBack,
  onDeleted,
}: {
  plant: PlantDetail
  onBack: () => void
  onDeleted: () => void
}) {
  const deletePlant = useDeletePlant()
  const [confirming, setConfirming] = useState(false)
  const [deleteError, setDeleteError] = useState<unknown>(null)

  async function handleDelete() {
    setDeleteError(null)
    try {
      await deletePlant.mutateAsync(plant.id)
      onDeleted()
    } catch (error) {
      setDeleteError(error)
    }
  }

  const temperatureRatio = (plant.state.temperature_c / plant.safety_limits.max_temperature_c) * 100
  const pressureRatio = (plant.state.pressure_bar / plant.safety_limits.max_pressure_bar) * 100
  const levelRatio = (plant.state.level_pct / plant.safety_limits.max_level_pct) * 100

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <header className="flex shrink-0 flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold tracking-[0.22em] text-accent/80 uppercase">
            Plant configuration
          </p>
          <h1 className="truncate text-base font-semibold tracking-tight text-white sm:text-lg">
            {plant.name}
          </h1>
          <p className="truncate text-xs text-slate-500">
            {plant.location || 'No location set'} · created {fmtDate(plant.created_at)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <StatusBadge
            label={plant.state.pump_running ? 'pump running at start' : 'pump stopped at start'}
            tone={plant.state.pump_running ? 'ok' : 'idle'}
          />
          <StatusBadge
            label={plant.safeguards.auto_shutdown_enabled ? 'auto shutdown armed' : 'auto shutdown off'}
            tone={plant.safeguards.auto_shutdown_enabled ? 'ok' : 'warn'}
          />
          <Link
            to="/monitor"
            className="rounded-md border border-edge-strong px-3 py-1.5 text-xs text-slate-300 transition hover:border-accent/40 hover:text-slate-100"
          >
            Live monitor
          </Link>
          <button
            type="button"
            onClick={onBack}
            className="rounded-md border border-edge-strong px-3 py-1.5 text-xs text-slate-300 transition hover:border-accent/40 hover:text-slate-100"
          >
            All plants
          </button>
        </div>
      </header>

      {plant.description && <p className="text-xs text-slate-400">{plant.description}</p>}

      <div className="grid shrink-0 gap-2 lg:grid-cols-[0.95fr_1.05fr]">
        <Panel className="h-52 sm:h-60" bodyClassName="p-0 overflow-hidden" title="Process model">
          <ProcessTopology plant={plant} />
        </Panel>
        <Panel className="h-52 sm:h-60" bodyClassName="flex flex-col gap-2" title="Initial state vs limits">
          <div className="grid grid-cols-3 gap-2">
            <InstrumentTile
              label="Temperature"
              value={plant.state.temperature_c.toFixed(1)}
              unit="°C"
              tone={temperatureRatio > 100 ? 'crit' : temperatureRatio > 90 ? 'warn' : 'ok'}
              rail={temperatureRatio}
              caption={`limit ${plant.safety_limits.max_temperature_c} °C`}
            />
            <InstrumentTile
              label="Pressure"
              value={plant.state.pressure_bar.toFixed(2)}
              unit="bar"
              tone={pressureRatio > 100 ? 'crit' : pressureRatio > 90 ? 'warn' : 'ok'}
              rail={pressureRatio}
              caption={`limit ${plant.safety_limits.max_pressure_bar} bar`}
            />
            <InstrumentTile
              label="Level"
              value={plant.state.level_pct.toFixed(1)}
              unit="%"
              tone={levelRatio > 100 ? 'crit' : levelRatio > 90 ? 'warn' : 'ok'}
              rail={levelRatio}
              caption={`limit ${plant.safety_limits.max_level_pct}%`}
            />
          </div>
          <p className="text-[11px] leading-relaxed text-slate-500">
            These are the starting values of the simulation model. SafeFlux uses them as the
            baseline for every scenario it explores; they are never command values sent anywhere.
          </p>
        </Panel>
      </div>

      <Panel
        className="min-h-0 flex-1"
        bodyClassName="grid auto-rows-min grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4"
        scroll
        title="Model parameters"
        hint="design input, not a live control system"
      >
        <Fact label="Feed flow" value={`${plant.config.feed_flow_lpm} L/min`} />
        <Fact label="Cooling" value={`${plant.config.cooling_pct}%`} />
        <Fact label="Valve" value={`${plant.config.valve_position_pct}%`} />
        <Fact label="Heater" value={`${plant.config.heater_power_pct}%`} />
        <Fact label="Shutdown delay" value={`${plant.config.shutdown_delay_s} s`} />
        <Fact label="Trip delay" value={`${plant.safeguards.trip_delay_s} s`} />
        <Fact label="Max T" value={`${plant.safety_limits.max_temperature_c} °C`} />
        <Fact label="Max P" value={`${plant.safety_limits.max_pressure_bar} bar`} />
        <Fact label="Max level" value={`${plant.safety_limits.max_level_pct}%`} />
        <Fact label="Auto shutdown" value={plant.safeguards.auto_shutdown_enabled ? 'Armed' : 'Off'} />
        <Fact label="HT trip" value={plant.safeguards.high_temperature_trip ? 'Enabled' : 'Off'} />
        <Fact label="HP trip" value={plant.safeguards.high_pressure_trip ? 'Enabled' : 'Off'} />
        <Fact label="HL trip" value={plant.safeguards.high_level_trip ? 'Enabled' : 'Off'} />
        <Fact label="Updated" value={fmtDate(plant.updated_at)} />
      </Panel>

      <div className="flex shrink-0 flex-wrap items-center gap-2 border-t border-edge/70 pt-3">
        {deleteError !== null && <ErrorPanel error={deleteError} title="Could not delete plant" />}
        {confirming ? (
          <>
            <span className="flex items-center gap-2 text-xs text-crit">
              Delete this plant and its configuration? This cannot be undone.
            </span>
            <button
              type="button"
              onClick={() => void handleDelete()}
              disabled={deletePlant.isPending}
              className="rounded-md border border-crit/55 bg-crit/10 px-3 py-1.5 text-xs font-semibold text-crit transition hover:bg-crit/20 disabled:opacity-60"
            >
              {deletePlant.isPending ? 'Deleting…' : 'Yes, delete'}
            </button>
            <button
              type="button"
              onClick={() => setConfirming(false)}
              className="rounded-md border border-edge-strong px-3 py-1.5 text-xs text-slate-300 transition hover:border-accent/40 hover:text-slate-100"
            >
              Cancel
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => setConfirming(true)}
            className="rounded-md border border-edge-strong px-3 py-1.5 text-xs text-slate-400 transition hover:border-crit/55 hover:text-crit"
          >
            Delete plant
          </button>
        )}
      </div>
    </div>
  )
}

export default function PlantSetupPage() {
  const [mode, setMode] = useState<Mode>('list')
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const list = usePlantList()
  const detail = usePlant(mode === 'detail' ? selectedId : null)

  function openPlant(id: string) {
    setSelectedId(id)
    setMode('detail')
  }

  function handleCreated(plant: PlantDetail) {
    setSelectedId(plant.id)
    setMode('detail')
  }

  if (mode === 'new') {
    return <PlantWizard onCreated={handleCreated} onCancel={() => setMode('list')} />
  }

  if (mode === 'detail') {
    if (detail.isLoading) {
      return <p className="text-sm text-slate-500">Loading plant…</p>
    }
    if (detail.isError || !detail.data) {
      return (
        <div className="flex flex-col gap-3">
          <ErrorPanel error={detail.error} title="Could not load plant" />
          <button
            type="button"
            onClick={() => setMode('list')}
            className="self-start rounded-md border border-edge-strong px-3 py-1.5 text-xs text-slate-300 transition hover:border-accent/40 hover:text-slate-100"
          >
            Back to plant list
          </button>
        </div>
      )
    }
    return (
      <PlantDetailView
        plant={detail.data.plant}
        onBack={() => setMode('list')}
        onDeleted={() => setMode('list')}
      />
    )
  }

  const plants = list.data?.plants ?? []

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <header className="flex shrink-0 flex-wrap items-end justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold tracking-[0.22em] text-accent/80 uppercase">
            Configuration
          </p>
          <h1 className="text-base font-semibold tracking-tight text-white sm:text-lg">
            Plant setup
          </h1>
          <p className="text-xs text-slate-500">
            Configure the simulation model — a design input, never a live control system.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setMode('new')}
          className="rounded-md bg-accent px-4 py-2 text-sm font-semibold text-void transition hover:bg-accent-soft"
        >
          New plant
        </button>
      </header>

      {list.isLoading && <p className="text-sm text-slate-500">Loading plants…</p>}
      {list.isError && <ErrorPanel error={list.error} title="Could not load plants" />}

      <Panel
        className="min-h-0 flex-1"
        bodyClassName="min-h-0"
        scroll
        title="Configured plants"
        hint={`${plants.length} model${plants.length === 1 ? '' : 's'}`}
      >
        {!list.isLoading && !list.isError && plants.length === 0 && (
          <div className="flex h-full flex-col items-center justify-center gap-1 rounded-md border border-dashed border-edge-strong p-6 text-center">
            <p className="text-sm text-slate-300">No plants configured yet.</p>
            <p className="text-xs text-slate-500">
              Create your first plant to define the process the simulator will test.
            </p>
          </div>
        )}

        {plants.length > 0 && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {plants.map((plant) => (
              <PlantCard key={plant.id} plant={plant} onSelect={() => openPlant(plant.id)} />
            ))}
          </div>
        )}
      </Panel>
    </div>
  )
}
