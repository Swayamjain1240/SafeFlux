/** Plant domain types — mirror of Backend/app/schemas/plant.py. */

export interface PlantConfig {
  feed_flow_lpm: number
  cooling_pct: number
  valve_position_pct: number
  heater_power_pct: number
  shutdown_delay_s: number
}

export interface PlantState {
  pump_running: boolean
  temperature_c: number
  pressure_bar: number
  level_pct: number
}

export interface SafetyLimits {
  max_temperature_c: number
  max_pressure_bar: number
  max_level_pct: number
}

export interface SafeguardConfig {
  auto_shutdown_enabled: boolean
  high_temperature_trip: boolean
  high_pressure_trip: boolean
  high_level_trip: boolean
  trip_delay_s: number
}

export interface PlantSummary {
  id: string
  name: string
  description: string
  location: string
  created_at: string
  updated_at: string
}

export interface PlantDetail extends PlantSummary {
  config: PlantConfig
  state: PlantState
  safety_limits: SafetyLimits
  safeguards: SafeguardConfig
}

export interface PlantListResponse {
  plants: PlantSummary[]
}

export interface PlantDetailResponse {
  plant: PlantDetail
}

export interface PlantStateResponse {
  plantId: string
  state: PlantState
}

/** Full create payload (Step 5 review → POST /plants). */
export interface PlantCreatePayload {
  name: string
  description: string
  location: string
  config: PlantConfig
  state: PlantState
  safety_limits: SafetyLimits
  safeguards: SafeguardConfig
}

/** Sensible MVP defaults, matching the backend model defaults. */
export const DEFAULT_CONFIG: PlantConfig = {
  feed_flow_lpm: 100,
  cooling_pct: 100,
  valve_position_pct: 50,
  heater_power_pct: 60,
  shutdown_delay_s: 5,
}

export const DEFAULT_STATE: PlantState = {
  pump_running: true,
  temperature_c: 25,
  pressure_bar: 1,
  level_pct: 50,
}

export const DEFAULT_LIMITS: SafetyLimits = {
  max_temperature_c: 150,
  max_pressure_bar: 10,
  max_level_pct: 90,
}

export const DEFAULT_SAFEGUARDS: SafeguardConfig = {
  auto_shutdown_enabled: true,
  high_temperature_trip: true,
  high_pressure_trip: true,
  high_level_trip: true,
  trip_delay_s: 2,
}
