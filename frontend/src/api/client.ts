import axios, { AxiosError, type AxiosRequestConfig } from 'axios'
import type { ApiEnvelope, FieldError } from '../types/api'

/**
 * API client rules:
 * - one base URL from VITE_API_BASE_URL (public config, no secrets),
 * - every response follows {success, data} / {success, error} envelopes,
 * - failures are normalized to ApiError with a safe user-facing message
 *   (never stack traces, SQL, paths or provider details).
 */
export class ApiError extends Error {
  readonly code: string
  readonly status?: number
  readonly details?: FieldError[]

  constructor(code: string, message: string, status?: number, details?: FieldError[]) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
    this.details = details
  }
}

const baseURL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1').replace(
  /\/+$/,
  '',
)

export const apiClient = axios.create({
  baseURL,
  timeout: 20000,
  withCredentials: true,
  headers: { Accept: 'application/json' },
})

// Normalize every failure into ApiError (envelope-aware).
apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError<unknown>) => {
    const body = error.response?.data
    if (body && typeof body === 'object' && 'success' in body && body.success === false) {
      const envelope = body as { success: false; error: { code: string; message: string; details?: FieldError[] } }
      return Promise.reject(
        new ApiError(envelope.error.code, envelope.error.message, error.response?.status, envelope.error.details),
      )
    }
    if (!error.response) {
      const code = error.code === 'ECONNABORTED' ? 'TIMEOUT' : 'NETWORK_ERROR'
      const message =
        code === 'TIMEOUT'
          ? 'The request timed out. Please try again.'
          : 'Cannot reach the SafeFlux API. Check that the backend is running.'
      return Promise.reject(new ApiError(code, message))
    }
    return Promise.reject(
      new ApiError('HTTP_ERROR', `Request failed (status ${error.response.status}).`, error.response.status),
    )
  },
)

function unwrap<T>(body: ApiEnvelope<T>): T {
  if (body && typeof body === 'object' && 'success' in body) {
    if (body.success) return body.data
    throw new ApiError(body.error.code, body.error.message, undefined, body.error.details)
  }
  throw new ApiError('MALFORMED_RESPONSE', 'The API returned an unexpected response.')
}

export async function apiGet<T>(path: string, config?: AxiosRequestConfig): Promise<T> {
  const response = await apiClient.get<ApiEnvelope<T>>(path, config)
  return unwrap(response.data)
}

export async function apiPost<T>(path: string, data?: unknown, config?: AxiosRequestConfig): Promise<T> {
  const response = await apiClient.post<ApiEnvelope<T>>(path, data, config)
  return unwrap(response.data)
}
