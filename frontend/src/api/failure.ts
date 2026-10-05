/**
 * Failure classification for API queries (Part 6).
 *
 * Pure primitives only (no axios import) so the mapping from a transport
 * failure to a user-facing state — backend offline, expired session, or a
 * plain API error — is unit-testable without a DOM or a server.
 */

export type QueryFailure = 'offline' | 'session' | 'unknown'

export interface FailureInput {
  status?: number | undefined
  code?: string | undefined
}

const OFFLINE_CODES = new Set(['NETWORK_ERROR', 'TIMEOUT', 'ECONNABORTED'])

/**
 * Map a failed request to a failure class.
 *
 * - no HTTP status (or a transport code) → the API could not be reached,
 * - 401 → the session expired or was revoked,
 * - anything else → a normal API error the backend already explained.
 *
 * Returns `null` for "no failure".
 */
export function classifyApiFailure(input: FailureInput | null | undefined): QueryFailure | null {
  if (!input) return null
  const { status, code } = input
  if (code && OFFLINE_CODES.has(code)) return 'offline'
  if (status === undefined || status === null || status === 0) return 'offline'
  if (status === 401) return 'session'
  return 'unknown'
}
