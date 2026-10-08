import { useState, type FormEvent } from 'react'
import { useCreatePlant } from '../../hooks/usePlants'
import {
  DEFAULT_CONFIG,
  DEFAULT_LIMITS,
  DEFAULT_SAFEGUARDS,
  DEFAULT_STATE,
  type PlantDetail,
} from '../../types/plant'
import {
  draftToPayload,
  type FieldErrors,
  type PlantDraft,
  validateAll,
  validateConditions,
  validateIdentity,
  validateSafety,
  validateState,
} from '../../utils/plantValidation'
import { ErrorPanel } from '../ErrorPanel'
import { ProcessTopology } from './ProcessTopology'

const STEP_LABELS = ['Identity', 'Conditions', 'Equipment', 'Safety', 'Review']
const LAST_STEP = STEP_LABELS.length - 1

function makeDraft(): PlantDraft {
  return {
    name: '',
    description: '',
    location: '',
    config: {
      feed_flow_lpm: String(DEFAULT_CONFIG.feed_flow_lpm),
      cooling_pct: String(DEFAULT_CONFIG.cooling_pct),
      valve_position_pct: String(DEFAULT_CONFIG.valve_position_pct),
      heater_power_pct: String(DEFAULT_CONFIG.heater_power_pct),
      shutdown_delay_s: String(DEFAULT_CONFIG.shutdown_delay_s),
    },
    state: {
      pump_running: DEFAULT_STATE.pump_running,
      temperature_c: String(DEFAULT_STATE.temperature_c),
      pressure_bar: String(DEFAULT_STATE.pressure_bar),
      level_pct: String(DEFAULT_STATE.level_pct),
    },
    safety_limits: {
      max_temperature_c: String(DEFAULT_LIMITS.max_temperature_c),
      max_pressure_bar: String(DEFAULT_LIMITS.max_pressure_bar),
      max_level_pct: String(DEFAULT_LIMITS.max_level_pct),
    },
    safeguards: {
      auto_shutdown_enabled: DEFAULT_SAFEGUARDS.auto_shutdown_enabled,
      high_temperature_trip: DEFAULT_SAFEGUARDS.high_temperature_trip,
      high_pressure_trip: DEFAULT_SAFEGUARDS.high_pressure_trip,
      high_level_trip: DEFAULT_SAFEGUARDS.high_level_trip,
      trip_delay_s: String(DEFAULT_SAFEGUARDS.trip_delay_s),
    },
  }
}

function previewPlant(draft: PlantDraft): PlantDetail {
  const payload = draftToPayload(draft)
  return {
    id: 'preview',
    name: payload.name || 'Untitled plant',
    description: payload.description,
    location: payload.location,
    config: payload.config,
    state: payload.state,
    safety_limits: payload.safety_limits,
    safeguards: payload.safeguards,
    created_at: '',
    updated_at: '',
  }
}

const RANGES: Record<string, { min: number; max: number; step: number }> = {
  feed_flow_lpm: { min: 0, max: 500, step: 1 },
  cooling_pct: { min: 0, max: 100, step: 1 },
  valve_position_pct: { min: 0, max: 100, step: 1 },
  heater_power_pct: { min: 0, max: 100, step: 1 },
  shutdown_delay_s: { min: 0, max: 3600, step: 1 },
  temperature_c: { min: -50, max: 1000, step: 1 },
  pressure_bar: { min: 0, max: 500, step: 0.1 },
  level_pct: { min: 0, max: 100, step: 1 },
  max_temperature_c: { min: -50, max: 1000, step: 1 },
  max_pressure_bar: { min: 0, max: 500, step: 0.1 },
  max_level_pct: { min: 0, max: 100, step: 1 },
  trip_delay_s: { min: 0, max: 3600, step: 1 },
}

interface NumberFieldProps {
  id: string
  label: string
  unit?: string
  value: string
  onChange: (value: string) => void
  error?: string
}

function NumberField({ id, label, unit, value, onChange, error }: NumberFieldProps) {
  const range = RANGES[id]
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-xs font-medium text-slate-400">
        {label}
        {unit && <span className="ml-1 text-slate-600">({unit})</span>}
      </label>
      <input
        id={id}
        name={id}
        type="number"
        inputMode="decimal"
        value={value}
        min={range?.min}
        max={range?.max}
        step={range?.step}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        onChange={(event) => onChange(event.target.value)}
        className={[
          'stat-num w-full rounded-md border bg-void/60 px-3 py-2 text-sm text-slate-100 outline-none transition',
          'focus:border-accent focus:ring-2 focus:ring-accent/25',
          error ? 'border-crit/70' : 'border-edge-strong',
        ].join(' ')}
      />
      {error && (
        <p id={`${id}-error`} className="mt-1 text-xs text-crit">
          {error}
        </p>
      )}
    </div>
  )
}

function ToggleField({
  id,
  label,
  description,
  checked,
  onChange,
}: {
  id: string
  label: string
  description?: string
  checked: boolean
  onChange: (checked: boolean) => void
}) {
  return (
    <label
      htmlFor={id}
      className="flex cursor-pointer items-start gap-3 rounded-md border border-edge/80 bg-void/50 px-3 py-2 transition hover:border-edge-strong"
    >
      <input
        id={id}
        name={id}
        type="checkbox"
        checked={checked}
        onChange={(event) => onChange(event.target.checked)}
        className="mt-0.5 h-4 w-4 shrink-0 rounded border-edge-strong bg-surface accent-accent"
      />
      <span>
        <span className="block text-xs font-medium text-slate-200">{label}</span>
        {description && <span className="block text-[11px] text-slate-500">{description}</span>}
      </span>
    </label>
  )
}

function SummaryRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-baseline justify-between gap-3 py-0.5">
      <span className="text-[11px] text-slate-500">{label}</span>
      <span className="stat-num text-[11px] text-slate-200">{value}</span>
    </div>
  )
}

interface PlantWizardProps {
  onCreated: (plant: PlantDetail) => void
  onCancel: () => void
}

/**
 * Five-step, one-viewport wizard: identity → conditions → equipment →
 * safety → review. Every step fits a single viewport; Back/Next stay visible.
 */
export function PlantWizard({ onCreated, onCancel }: PlantWizardProps) {
  const [step, setStep] = useState(0)
  const [draft, setDraft] = useState<PlantDraft>(makeDraft)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [submitError, setSubmitError] = useState<unknown>(null)
  const createPlant = useCreatePlant()

  function patch<K extends keyof PlantDraft>(key: K, value: PlantDraft[K]) {
    setDraft((current) => ({ ...current, [key]: value }))
  }

  function stepValidator(index: number): FieldErrors {
    if (index === 0) return validateIdentity(draft)
    if (index === 1) return validateConditions(draft)
    if (index === 2) return validateState(draft)
    if (index === 3) return validateSafety(draft)
    return validateAll(draft)
  }

  function handleNext() {
    const nextErrors = stepValidator(step)
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length === 0) {
      setStep((current) => Math.min(current + 1, LAST_STEP))
    }
  }

  function handleBack() {
    setErrors({})
    setStep((current) => Math.max(current - 1, 0))
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const nextErrors = validateAll(draft)
    setErrors(nextErrors)
    if (Object.keys(nextErrors).length > 0) return

    setSubmitError(null)
    try {
      const response = await createPlant.mutateAsync(draftToPayload(draft))
      onCreated(response.plant)
    } catch (error) {
      setSubmitError(error)
    }
  }

  const submitting = createPlant.isPending

  return (
    <form onSubmit={handleSubmit} noValidate className="mx-auto flex w-full max-w-2xl flex-col gap-3">
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-100">New plant configuration</h2>
          <p className="text-xs text-slate-500">
            Step {step + 1} of {STEP_LABELS.length} · {STEP_LABELS[step]}
          </p>
        </div>
        <button
          type="button"
          onClick={onCancel}
          className="rounded-md border border-edge-strong px-3 py-1.5 text-xs text-slate-300 transition hover:bg-surface-2"
        >
          Cancel
        </button>
      </div>

      <div className="flex gap-1.5" aria-hidden="true">
        {STEP_LABELS.map((label, index) => (
          <div
            key={label}
            className={`h-1 flex-1 rounded-full ${index <= step ? 'bg-accent' : 'bg-edge-strong'}`}
          />
        ))}
      </div>

      <div className="rounded-md border border-edge/80 bg-panel/60 p-3 sm:p-4">
        {step === 0 && (
          <div className="space-y-3">
            <div>
              <label htmlFor="name" className="mb-1 block text-xs font-medium text-slate-400">
                Plant name<span className="text-accent"> *</span>
              </label>
              <input
                id="name"
                name="name"
                value={draft.name}
                maxLength={120}
                aria-invalid={errors.name ? true : undefined}
                aria-describedby={errors.name ? 'name-error' : undefined}
                onChange={(event) => patch('name', event.target.value)}
                placeholder="Reactor R-101 pilot plant"
                className={[
                  'w-full rounded-md border bg-void/60 px-3 py-2 text-sm text-slate-100 outline-none transition',
                  'placeholder:text-slate-600 focus:border-accent focus:ring-2 focus:ring-accent/25',
                  errors.name ? 'border-crit/70' : 'border-edge-strong',
                ].join(' ')}
              />
              {errors.name && (
                <p id="name-error" className="mt-1 text-xs text-crit">
                  {errors.name}
                </p>
              )}
            </div>
            <div>
              <label htmlFor="location" className="mb-1 block text-xs font-medium text-slate-400">
                Location
              </label>
              <input
                id="location"
                name="location"
                value={draft.location}
                maxLength={120}
                onChange={(event) => patch('location', event.target.value)}
                placeholder="Unit 4 · Process Hall A"
                className="w-full rounded-md border border-edge-strong bg-void/60 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-accent focus:ring-2 focus:ring-accent/25"
              />
            </div>
            <div>
              <label
                htmlFor="description"
                className="mb-1 block text-xs font-medium text-slate-400"
              >
                Description
              </label>
              <textarea
                id="description"
                name="description"
                value={draft.description}
                maxLength={500}
                rows={3}
                onChange={(event) => patch('description', event.target.value)}
                placeholder="What this plant models and any notes for the analysis."
                className="w-full resize-none rounded-md border border-edge-strong bg-void/60 px-3 py-2 text-sm text-slate-100 outline-none transition placeholder:text-slate-600 focus:border-accent focus:ring-2 focus:ring-accent/25"
              />
            </div>
          </div>
        )}

        {step === 1 && (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <NumberField
              id="feed_flow_lpm"
              label="Feed flow"
              unit="L/min"
              value={draft.config.feed_flow_lpm}
              onChange={(value) => patch('config', { ...draft.config, feed_flow_lpm: value })}
              error={errors.feed_flow_lpm}
            />
            <NumberField
              id="cooling_pct"
              label="Cooling"
              unit="%"
              value={draft.config.cooling_pct}
              onChange={(value) => patch('config', { ...draft.config, cooling_pct: value })}
              error={errors.cooling_pct}
            />
            <NumberField
              id="valve_position_pct"
              label="Valve position"
              unit="% open"
              value={draft.config.valve_position_pct}
              onChange={(value) =>
                patch('config', { ...draft.config, valve_position_pct: value })
              }
              error={errors.valve_position_pct}
            />
            <NumberField
              id="heater_power_pct"
              label="Heater power"
              unit="%"
              value={draft.config.heater_power_pct}
              onChange={(value) => patch('config', { ...draft.config, heater_power_pct: value })}
              error={errors.heater_power_pct}
            />
            <NumberField
              id="shutdown_delay_s"
              label="Shutdown delay"
              unit="s"
              value={draft.config.shutdown_delay_s}
              onChange={(value) => patch('config', { ...draft.config, shutdown_delay_s: value })}
              error={errors.shutdown_delay_s}
            />
          </div>
        )}

        {step === 2 && (
          <div className="space-y-3">
            <ToggleField
              id="pump_running"
              label="Feed pump running at start"
              description="Initial state of Pump P-101."
              checked={draft.state.pump_running}
              onChange={(checked) => patch('state', { ...draft.state, pump_running: checked })}
            />
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <NumberField
                id="temperature_c"
                label="Temperature"
                unit="°C"
                value={draft.state.temperature_c}
                onChange={(value) => patch('state', { ...draft.state, temperature_c: value })}
                error={errors.temperature_c}
              />
              <NumberField
                id="pressure_bar"
                label="Pressure"
                unit="bar"
                value={draft.state.pressure_bar}
                onChange={(value) => patch('state', { ...draft.state, pressure_bar: value })}
                error={errors.pressure_bar}
              />
              <NumberField
                id="level_pct"
                label="Level"
                unit="%"
                value={draft.state.level_pct}
                onChange={(value) => patch('state', { ...draft.state, level_pct: value })}
                error={errors.level_pct}
              />
            </div>
          </div>
        )}

        {step === 3 && (
          <div className="space-y-3">
            <p className="text-[11px] text-slate-500">
              Trip limits arm the safety engine (Part 5). The initial state must sit below them.
            </p>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <NumberField
                id="max_temperature_c"
                label="Max temperature"
                unit="°C"
                value={draft.safety_limits.max_temperature_c}
                onChange={(value) =>
                  patch('safety_limits', { ...draft.safety_limits, max_temperature_c: value })
                }
                error={errors.max_temperature_c || errors.state_temperature}
              />
              <NumberField
                id="max_pressure_bar"
                label="Max pressure"
                unit="bar"
                value={draft.safety_limits.max_pressure_bar}
                onChange={(value) =>
                  patch('safety_limits', { ...draft.safety_limits, max_pressure_bar: value })
                }
                error={errors.max_pressure_bar || errors.state_pressure}
              />
              <NumberField
                id="max_level_pct"
                label="Max level"
                unit="%"
                value={draft.safety_limits.max_level_pct}
                onChange={(value) =>
                  patch('safety_limits', { ...draft.safety_limits, max_level_pct: value })
                }
                error={errors.max_level_pct || errors.state_level}
              />
            </div>
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
              <ToggleField
                id="auto_shutdown_enabled"
                label="Automatic shutdown"
                checked={draft.safeguards.auto_shutdown_enabled}
                onChange={(checked) =>
                  patch('safeguards', { ...draft.safeguards, auto_shutdown_enabled: checked })
                }
              />
              <ToggleField
                id="high_temperature_trip"
                label="High-temperature trip"
                checked={draft.safeguards.high_temperature_trip}
                onChange={(checked) =>
                  patch('safeguards', { ...draft.safeguards, high_temperature_trip: checked })
                }
              />
              <ToggleField
                id="high_pressure_trip"
                label="High-pressure trip"
                checked={draft.safeguards.high_pressure_trip}
                onChange={(checked) =>
                  patch('safeguards', { ...draft.safeguards, high_pressure_trip: checked })
                }
              />
              <ToggleField
                id="high_level_trip"
                label="High-level trip"
                checked={draft.safeguards.high_level_trip}
                onChange={(checked) =>
                  patch('safeguards', { ...draft.safeguards, high_level_trip: checked })
                }
              />
            </div>
            <div className="sm:max-w-[10rem]">
              <NumberField
                id="trip_delay_s"
                label="Trip delay"
                unit="s"
                value={draft.safeguards.trip_delay_s}
                onChange={(value) => patch('safeguards', { ...draft.safeguards, trip_delay_s: value })}
                error={errors.trip_delay_s}
              />
            </div>
          </div>
        )}

        {step === 4 && (
          <div className="space-y-3">
            <div className="grid grid-cols-1 gap-x-6 gap-y-1 sm:grid-cols-2">
              <SummaryRow label="Name" value={draft.name || '—'} />
              <SummaryRow label="Location" value={draft.location || '—'} />
              <SummaryRow label="Feed flow" value={`${draft.config.feed_flow_lpm} L/min`} />
              <SummaryRow label="Cooling" value={`${draft.config.cooling_pct}%`} />
              <SummaryRow label="Valve" value={`${draft.config.valve_position_pct}% open`} />
              <SummaryRow label="Heater power" value={`${draft.config.heater_power_pct}%`} />
              <SummaryRow label="Shutdown delay" value={`${draft.config.shutdown_delay_s} s`} />
              <SummaryRow
                label="Pump at start"
                value={draft.state.pump_running ? 'Running' : 'Stopped'}
              />
              <SummaryRow
                label="Initial T/P/L"
                value={`${draft.state.temperature_c}°C · ${draft.state.pressure_bar} bar · ${draft.state.level_pct}%`}
              />
              <SummaryRow
                label="Trip limits T/P/L"
                value={`${draft.safety_limits.max_temperature_c}°C · ${draft.safety_limits.max_pressure_bar} bar · ${draft.safety_limits.max_level_pct}%`}
              />
              <SummaryRow label="Trip delay" value={`${draft.safeguards.trip_delay_s} s`} />
              <SummaryRow
                label="Safeguards armed"
                value={
                  [
                    draft.safeguards.high_temperature_trip && 'T',
                    draft.safeguards.high_pressure_trip && 'P',
                    draft.safeguards.high_level_trip && 'L',
                  ]
                    .filter(Boolean)
                    .join(' · ') || 'none'
                }
              />
            </div>
            <ProcessTopology plant={previewPlant(draft)} />
          </div>
        )}
      </div>

      {submitError !== null && <ErrorPanel error={submitError} title="Could not save plant" />}
      {step === LAST_STEP && Object.keys(errors).length > 0 && (
        <p className="text-xs text-crit">
          Some earlier steps need attention. Use Back to fix them.
        </p>
      )}

      <div className="flex gap-2">
        <button
          type="button"
          onClick={step === 0 ? onCancel : handleBack}
          className="flex-1 rounded-md border border-edge-strong px-4 py-2.5 text-sm text-slate-300 transition hover:bg-surface-2"
        >
          {step === 0 ? 'Cancel' : 'Back'}
        </button>
        {step < LAST_STEP ? (
          <button
            type="button"
            onClick={handleNext}
            className="flex-1 rounded-md bg-accent px-4 py-2.5 text-sm font-semibold text-void transition hover:bg-accent-soft"
          >
            Next
          </button>
        ) : (
          <button
            type="submit"
            disabled={submitting}
            className="flex-1 rounded-md bg-accent px-4 py-2.5 text-sm font-semibold text-void transition hover:bg-accent-soft disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? 'Saving…' : 'Save plant'}
          </button>
        )}
      </div>
    </form>
  )
}
