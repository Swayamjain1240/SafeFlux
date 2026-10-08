/**
 * Session-cache semantics shared by the auth provider and its regression
 * tests (QA Part 2).
 *
 * The defect these exist to prevent: sign-out (and a 401-driven expiry) used
 * `queryClient.removeQueries(...)` to drop the local session copy. For the
 * session query that is *actively mounted* — the workspace shell is still
 * rendering when the button is clicked — removal alone leaves the observer
 * serving its last result, so the provider keeps reporting `authenticated`,
 * `ProtectedRoute` never redirects, and every later data request 401s under a
 * stale shell until a manual reload.
 *
 * Dropping the session therefore writes an explicit `null` into the cache:
 * the mounted observer re-renders with `data === null`, which
 * `deriveAuthStatus` maps to `unauthenticated` immediately, with no refetch
 * needed. The backend remains the authority — this only mirrors its answer.
 */

import type { QueryClient } from '@tanstack/react-query'
import type { AuthStatus, SessionResponse } from './context'

export const SESSION_KEY = ['auth', 'session'] as const

/** What the cache holds for the session: a user, or an explicit "dropped". */
export type SessionData = SessionResponse | null

/** The subset of the query state the auth status depends on (structural). */
export interface SessionQueryState {
  isPending: boolean
  isSuccess: boolean
  data: SessionData | undefined
}

/** Single source of truth for turning query state into the app's auth status. */
export function deriveAuthStatus(state: SessionQueryState): AuthStatus {
  if (state.isPending) return 'loading'
  if (state.isSuccess && state.data) return 'authenticated'
  return 'unauthenticated'
}

/**
 * Drop the local session copy.
 *
 * Must be `setQueryData(null)`, never `removeQueries`: an active observer is
 * handed a value, so the status flips synchronously and the route guard can
 * redirect. See the file docstring for the bug this prevents.
 */
export function dropSession(queryClient: QueryClient): void {
  queryClient.setQueryData<SessionData>(SESSION_KEY, null)
}
