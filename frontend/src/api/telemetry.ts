import { apiGet, apiPost } from './client'
import type {
  SimulationRunData,
  TelemetryCurrentData,
  TelemetryHistoryData,
} from '../types/telemetry'

/**
 * Telemetry + safety API — mirrors /api/v1/plants/{id}/telemetry/* and
 * /api/v1/simulations/run. The session cookie (withCredentials) is the only
 * authorization; no owner id is ever sent from the client.
 */

const baseURL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1').replace(
  /\/+$/,
  '',
)

export interface ScenarioFaultInput {
  type: string
  start_s: number
  factor?: number
  target_pct?: number
}

export interface ScenarioInput {
  duration_s: number
  time_step_s: number
  label?: string
  faults?: ScenarioFaultInput[]
}

export function fetchTelemetryCurrent(plantId: string): Promise<TelemetryCurrentData> {
  return apiGet<TelemetryCurrentData>(`/plants/${encodeURIComponent(plantId)}/telemetry/current`)
}

export function fetchTelemetryHistory(
  plantId: string,
  limit?: number,
): Promise<TelemetryHistoryData> {
  const query = limit ? `?limit=${encodeURIComponent(limit)}` : ''
  return apiGet<TelemetryHistoryData>(
    `/plants/${encodeURIComponent(plantId)}/telemetry/history${query}`,
  )
}

export function runScenario(plantId: string, scenario: ScenarioInput): Promise<SimulationRunData> {
  return apiPost<SimulationRunData>('/simulations/run', { plant_id: plantId, scenario })
}

/** SSE URL for the live telemetry stream (cookies are sent with credentials). */
export function telemetryStreamUrl(plantId: string): string {
  return `${baseURL}/plants/${encodeURIComponent(plantId)}/telemetry/stream`
}
