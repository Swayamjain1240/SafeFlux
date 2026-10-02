/** Shared API envelope types (mirror of Backend/app/core/responses.py). */

export interface FieldError {
  field: string
  message: string
}

export interface ApiErrorBody {
  code: string
  message: string
  details?: FieldError[]
}

export type ApiEnvelope<T> =
  | { success: true; data: T }
  | { success: false; error: ApiErrorBody }

export interface HealthData {
  status: 'ok'
  service: string
  version: string
  environment: string
}
