/**
 * Session-expiry signalling between the HTTP client and the auth provider
 * (Part 6).
 *
 * The backend is the authority: when a protected request answers 401 the app
 * must drop its local session cache so the route guard redirects to login.
 * The decision logic is kept here — pure and testable — because the login
 * *probe* 401s are expected (wrong password, no session yet) and must never
 * trigger a redirect loop.
 */

export const SESSION_EXPIRED_EVENT = 'safeflux:session-expired'

/** Endpoints whose 401 is a normal answer rather than an expired session. */
const AUTH_PROBE_PATHS: readonly string[] = ['/auth/session', '/auth/login', '/auth/logout']

export function shouldNotifySessionExpiry(status?: number | null, url?: string | null): boolean {
  if (status !== 401) return false
  const path = (url ?? '').toLowerCase()
  if (AUTH_PROBE_PATHS.some((probe) => path.includes(probe))) return false
  return true
}

function defaultTarget(): EventTarget | null {
  return typeof window === 'undefined' ? null : window
}

export function emitSessionExpired(target: EventTarget | null = defaultTarget()): void {
  target?.dispatchEvent(new Event(SESSION_EXPIRED_EVENT))
}

export function onSessionExpired(
  handler: () => void,
  target: EventTarget | null = defaultTarget(),
): () => void {
  if (!target) return () => undefined
  target.addEventListener(SESSION_EXPIRED_EVENT, handler)
  return () => target.removeEventListener(SESSION_EXPIRED_EVENT, handler)
}
