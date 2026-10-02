import { apiGet } from './client'
import type { HealthData } from '../types/api'

/** GET /api/v1/health — liveness probe used by the landing status badge. */
export function fetchHealth(): Promise<HealthData> {
  return apiGet<HealthData>('/health')
}
