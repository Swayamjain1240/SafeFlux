/** Telemetry + safety types — mirror of the Part 5 backend schemas. */

export type SafetyStatus = 'safe' | 'near_limit' | 'safeguard_activated' | 'violation'

export interface TelemetryFrame {
  type: 'telemetry'
  plant_id: string
  sequence: number
  time_s: number
  status: SafetyStatus
  values: Record<string, number>
  observed: Record<string, number>
  limits: Record<string, number>
  near_limits: Record<string, number>
  pump_running: boolean
}

export interface TelemetryCurrentData {
  plantId: string
  frame: TelemetryFrame | null
}

export interface TelemetryHistoryData {
  plantId: string
  count: number
  limit: number
  frames: TelemetryFrame[]
}

export interface SafetyFinding {
  type: string
  status: SafetyStatus
  severity: 'none' | 'low' | 'high' | 'critical'
  timestamp_s: number | null
  measured_value: number | null
  limit: number
  near_limit: number
  scenario_id: string | null
  message: string
}

export interface SafeguardTiming {
  safeguard: string
  variable: string | null
  trigger_time_s: number | null
  response_time_s: number | null
  violation_time_s: number | null
  prevented: boolean | null
  note: string
}

export interface SafetyAssessment {
  status: SafetyStatus
  findings: SafetyFinding[]
  safeguards: SafeguardTiming[]
  scenario_id: string | null
  summary: Record<string, unknown>
  metadata: Record<string, unknown>
}

export interface SimulationResult {
  series: Record<string, number[] | boolean[]>
  extrema: Record<string, { min: { value: number }; max: { value: number }; final: number }>
  summary: Record<string, unknown>
  events: Array<{ time_s: number; kind: string; detail: Record<string, unknown> }>
  metadata: Record<string, unknown>
}

export interface SimulationRunData {
  result: SimulationResult
  safety: SafetyAssessment
}
