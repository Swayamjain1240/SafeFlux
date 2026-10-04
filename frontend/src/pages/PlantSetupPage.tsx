import { useState } from 'react'
import { Link } from 'react-router-dom'
import { ErrorPanel } from '../components/ErrorPanel'
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
    <div className="rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2">
      <p className="text-[10px] tracking-wide text-slate-500 uppercase">{label}</p>
      <p className="mt-0.5 font-mono text-sm text-slate-200">{value}</p>
    </div>
  )
}

function PlantCard({ plant, onSelect }: { plant: PlantSummary; onSelect: () => void }) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className="flex w-full flex-col rounded-xl border border-slate-800 bg-slate-900/60 p-3 text-left transition hover:border-cyan-500/40 hover:bg-slate-900"
    >
      <span className="text-sm font-semibold text-slate-100">{plant.name}</span>
      <span className="mt-0.5 text-xs text-slate-500">
        {plant.location || 'No location set'}
      </span>
      {plant.description && (
        <span className="mt-1 line-clamp-2 text-[11px] text-slate-500">{plant.description}</span>
      )}
      <span className="mt-2 text-[10px] text-slate-600">Updated {fmtDate(plant.updated_at)}</span>
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

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h2 className="text-base font-semibold text-white">{plant.name}</h2>
          <p className="text-xs text-slate-500">
            {plant.location || 'No location set'} · created {fmtDate(plant.created_at)}
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            to="/monitor"
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 transition hover:bg-slate-800"
          >
            Live monitor
          </Link>
          <button
            type="button"
            onClick={onBack}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 transition hover:bg-slate-800"
          >
            All plants
          </button>
        </div>
      </div>

      {plant.description && <p className="text-sm text-slate-400">{plant.description}</p>}

      <ProcessTopology plant={plant} />

      <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4">
        <Fact label="Feed flow" value={`${plant.config.feed_flow_lpm} L/min`} />
        <Fact label="Cooling" value={`${plant.config.cooling_pct}%`} />
        <Fact label="Valve" value={`${plant.config.valve_position_pct}%`} />
        <Fact label="Heater" value={`${plant.config.heater_power_pct}%`} />
        <Fact label="Shutdown delay" value={`${plant.config.shutdown_delay_s} s`} />
        <Fact label="Pump at start" value={plant.state.pump_running ? 'Running' : 'Stopped'} />
        <Fact label="Initial T" value={`${plant.state.temperature_c} °C`} />
        <Fact label="Initial P" value={`${plant.state.pressure_bar} bar`} />
        <Fact label="Initial level" value={`${plant.state.level_pct}%`} />
        <Fact label="Max T" value={`${plant.safety_limits.max_temperature_c} °C`} />
        <Fact label="Max P" value={`${plant.safety_limits.max_pressure_bar} bar`} />
        <Fact label="Max level" value={`${plant.safety_limits.max_level_pct}%`} />
        <Fact label="Auto shutdown" value={plant.safeguards.auto_shutdown_enabled ? 'Armed' : 'Off'} />
        <Fact label="Trip delay" value={`${plant.safeguards.trip_delay_s} s`} />
      </div>

      {deleteError !== null && <ErrorPanel error={deleteError} title="Could not delete plant" />}

      <div className="flex flex-wrap items-center gap-2 border-t border-slate-800 pt-3">
        {confirming ? (
          <>
            <span className="text-xs text-rose-300">
              Delete this plant and its configuration? This cannot be undone.
            </span>
            <button
              type="button"
              onClick={() => void handleDelete()}
              disabled={deletePlant.isPending}
              className="rounded-lg border border-rose-700 px-3 py-1.5 text-xs text-rose-300 transition hover:bg-rose-950/50 disabled:opacity-60"
            >
              {deletePlant.isPending ? 'Deleting…' : 'Yes, delete'}
            </button>
            <button
              type="button"
              onClick={() => setConfirming(false)}
              className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 transition hover:bg-slate-800"
            >
              Cancel
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => setConfirming(true)}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-400 transition hover:border-rose-700 hover:text-rose-300"
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
    return (
      <PlantWizard onCreated={handleCreated} onCancel={() => setMode('list')} />
    )
  }

  if (mode === 'detail') {
    if (detail.isLoading) {
      return <p className="text-sm text-slate-500">Loading plant…</p>
    }
    if (detail.isError || !detail.data) {
      return (
        <div className="space-y-3">
          <ErrorPanel error={detail.error} title="Could not load plant" />
          <button
            type="button"
            onClick={() => setMode('list')}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 transition hover:bg-slate-800"
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
    <div className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold text-white">Plant setup</h1>
          <p className="text-xs text-slate-500">
            Configure the simulation model — a design input, never a live control system.
          </p>
        </div>
        <button
          type="button"
          onClick={() => setMode('new')}
          className="rounded-lg bg-cyan-500 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400"
        >
          New plant
        </button>
      </div>

      {list.isLoading && <p className="text-sm text-slate-500">Loading plants…</p>}
      {list.isError && <ErrorPanel error={list.error} title="Could not load plants" />}
      {!list.isLoading && !list.isError && plants.length === 0 && (
        <div className="rounded-xl border border-dashed border-slate-800 bg-slate-900/40 p-6 text-center">
          <p className="text-sm text-slate-300">No plants configured yet.</p>
          <p className="mt-1 text-xs text-slate-500">
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
    </div>
  )
}
