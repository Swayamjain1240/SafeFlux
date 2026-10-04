import type { PlantCreatePayload } from '../types/plant'

/**
 * Client-side wizard validation (UX only — the backend re-validates everything).
 * Numeric inputs are kept as strings in the draft so partial typing is possible;
 * they are parsed and range-checked here and converted to numbers on submit.
 */

export interface PlantDraft {
  name: string
  description: string
  location: string
  config: {
    feed_flow_lpm: string
    cooling_pct: string
    valve_position_pct: string
    heater_power_pct: string
    shutdown_delay_s: string
  }
  state: {
    pump_running: boolean
    temperature_c: string
    pressure_bar: string
    level_pct: string
  }
  safety_limits: {
    max_temperature_c: string
    max_pressure_bar: string
    max_level_pct: string
  }
  safeguards: {
    auto_shutdown_enabled: boolean
    high_temperature_trip: boolean
    high_pressure_trip: boolean
    high_level_trip: boolean
    trip_delay_s: string
  }
}

export type FieldErrors = Record<string, string>

interface RangeRule {
  field: string
  label: string
  min: number
  max: number
  integer?: boolean
}

function numberField(
  raw: unknown,
  label: string,
  min: number,
  max: number,
  integer = false,
): string | null {
  const trimmed = typeof raw === 'string' ? raw.trim() : raw == null ? '' : String(raw).trim()
  if (trimmed === '') return `${label} is required.`
  const value = Number(trimmed)
  if (!Number.isFinite(value)) return `${label} must be a number.`
  if (integer && !Number.isInteger(value)) return `${label} must be a whole number.`
  if (value < min) return `${label} must be at least ${min}.`
  if (value > max) return `${label} must be at most ${max}.`
  return null
}

function applyRanges(draft: Record<string, unknown>, rules: RangeRule[]): FieldErrors {
  const errors: FieldErrors = {}
  for (const rule of rules) {
    const message = numberField(draft[rule.field], rule.label, rule.min, rule.max, rule.integer)
    if (message) errors[rule.field] = message
  }
  return errors
}

/** Step 1 — plant identity. */
export function validateIdentity(draft: PlantDraft): FieldErrors {
  const errors: FieldErrors = {}
  const name = draft.name.trim()
  if (!name) errors.name = 'Plant name is required.'
  else if (name.length > 120) errors.name = 'Plant name must be 120 characters or fewer.'
  if (draft.description.length > 500)
    errors.description = 'Description must be 500 characters or fewer.'
  if (draft.location.length > 120) errors.location = 'Location must be 120 characters or fewer.'
  return errors
}

/** Step 2 — operating conditions (PlantConfig). */
export function validateConditions(draft: PlantDraft): FieldErrors {
  return applyRanges(draft.config, [
    { field: 'feed_flow_lpm', label: 'Feed flow', min: 0, max: 500 },
    { field: 'cooling_pct', label: 'Cooling', min: 0, max: 100 },
    { field: 'valve_position_pct', label: 'Valve position', min: 0, max: 100 },
    { field: 'heater_power_pct', label: 'Heater power', min: 0, max: 100 },
    { field: 'shutdown_delay_s', label: 'Shutdown delay', min: 0, max: 3600, integer: true },
  ])
}

/** Step 3 — initial equipment / process state (PlantState). */
export function validateState(draft: PlantDraft): FieldErrors {
  return applyRanges(draft.state, [
    { field: 'temperature_c', label: 'Temperature', min: -50, max: 1000 },
    { field: 'pressure_bar', label: 'Pressure', min: 0, max: 500 },
    { field: 'level_pct', label: 'Level', min: 0, max: 100 },
  ])
}

/** Step 4 — safety limits + safeguards, including state-below-limit consistency. */
export function validateSafety(draft: PlantDraft): FieldErrors {
  const errors = applyRanges(draft.safety_limits, [
    { field: 'max_temperature_c', label: 'Max temperature', min: -50, max: 1000 },
    { field: 'max_pressure_bar', label: 'Max pressure', min: 0, max: 500 },
    { field: 'max_level_pct', label: 'Max level', min: 0, max: 100 },
  ])
  Object.assign(
    errors,
    applyRanges(draft.safeguards, [
      { field: 'trip_delay_s', label: 'Trip delay', min: 0, max: 3600, integer: true },
    ]),
  )

  // Consistent only when both steps have valid numbers.
  if (!errors.max_temperature_c && !numberError(draft.state.temperature_c)) {
    if (parsedNum(draft.state.temperature_c) > parsedNum(draft.safety_limits.max_temperature_c))
      errors.state_temperature = 'Initial temperature exceeds the maximum temperature limit.'
  }
  if (!errors.max_pressure_bar && !numberError(draft.state.pressure_bar)) {
    if (parsedNum(draft.state.pressure_bar) > parsedNum(draft.safety_limits.max_pressure_bar))
      errors.state_pressure = 'Initial pressure exceeds the maximum pressure limit.'
  }
  if (!errors.max_level_pct && !numberError(draft.state.level_pct)) {
    if (parsedNum(draft.state.level_pct) > parsedNum(draft.safety_limits.max_level_pct))
      errors.state_level = 'Initial level exceeds the maximum level limit.'
  }
  return errors
}

function parsedNum(value: string): number {
  return Number(value.trim())
}

function numberError(value: string): boolean {
  const trimmed = value.trim()
  return trimmed === '' || !Number.isFinite(Number(trimmed))
}

/** Run every step's validator (used by the review step before submit). */
export function validateAll(draft: PlantDraft): FieldErrors {
  return {
    ...validateIdentity(draft),
    ...validateConditions(draft),
    ...validateState(draft),
    ...validateSafety(draft),
  }
}

/** Convert the string draft into the typed payload the API expects. */
export function draftToPayload(draft: PlantDraft): PlantCreatePayload {
  return {
    name: draft.name.trim(),
    description: draft.description.trim(),
    location: draft.location.trim(),
    config: {
      feed_flow_lpm: Number(draft.config.feed_flow_lpm),
      cooling_pct: Number(draft.config.cooling_pct),
      valve_position_pct: Number(draft.config.valve_position_pct),
      heater_power_pct: Number(draft.config.heater_power_pct),
      shutdown_delay_s: Number(draft.config.shutdown_delay_s),
    },
    state: {
      pump_running: draft.state.pump_running,
      temperature_c: Number(draft.state.temperature_c),
      pressure_bar: Number(draft.state.pressure_bar),
      level_pct: Number(draft.state.level_pct),
    },
    safety_limits: {
      max_temperature_c: Number(draft.safety_limits.max_temperature_c),
      max_pressure_bar: Number(draft.safety_limits.max_pressure_bar),
      max_level_pct: Number(draft.safety_limits.max_level_pct),
    },
    safeguards: {
      auto_shutdown_enabled: draft.safeguards.auto_shutdown_enabled,
      high_temperature_trip: draft.safeguards.high_temperature_trip,
      high_pressure_trip: draft.safeguards.high_pressure_trip,
      high_level_trip: draft.safeguards.high_level_trip,
      trip_delay_s: Number(draft.safeguards.trip_delay_s),
    },
  }
}
