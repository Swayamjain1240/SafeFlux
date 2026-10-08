/**
 * Sign-out / session-drop regression tests (QA Part 2, BUG-01).
 *
 * The defect: sign-out cleared the local session with
 * `queryClient.removeQueries(...)`. For the actively-mounted session query the
 * observer kept its last result, the provider kept reporting `authenticated`,
 * and `handleSignOut`'s `navigate('/login')` was bounced straight back to
 * `/dashboard` by LoginPage's authenticated redirect — the shell never
 * unmounted and every later request 401'd until a manual reload.
 *
 * These tests drive a real `QueryObserver` headlessly (no DOM, no extra
 * dependencies) and pin the shipped contract: after `dropSession` the
 * observer the app renders from reports `unauthenticated`, without waiting
 * for a refetch.
 *
 *     npm --prefix frontend run test:unit
 */

import assert from 'node:assert/strict'
import { test } from 'node:test'

import { QueryClient, QueryObserver } from '@tanstack/react-query'

import {
  SESSION_KEY,
  deriveAuthStatus,
  dropSession,
  type SessionData,
} from '../src/auth/session.ts'

const USER = { id: 'u-1', fullName: 'QA Engineer', email: 'qa@example.com' }

/** A client + active observer mirroring the mounted AuthProvider query. */
function primedObserver() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false, staleTime: 60_000 } },
  })
  client.setQueryData<SessionData>(SESSION_KEY, { user: USER })

  const observer = new QueryObserver<SessionData>(client, {
    queryKey: SESSION_KEY,
    queryFn: async () => {
      throw new Error('the session query must not be refetched by a drop')
    },
  })
  const notifications: ReturnType<typeof observer.getCurrentResult>[] = []
  const unsubscribe = observer.subscribe((result) => {
    notifications.push(result)
  })
  return { client, observer, notifications, unsubscribe }
}

function settle(): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, 10))
}

test('auth status derivation is total and fails closed', () => {
  assert.equal(
    deriveAuthStatus({ isPending: true, isSuccess: false, data: undefined }),
    'loading',
  )
  assert.equal(
    deriveAuthStatus({ isPending: false, isSuccess: true, data: { user: USER } }),
    'authenticated',
  )
  // The explicit drop: successful query, null payload → signed out.
  assert.equal(
    deriveAuthStatus({ isPending: false, isSuccess: true, data: null }),
    'unauthenticated',
  )
  // Server answered without a session / transport error → signed out.
  assert.equal(
    deriveAuthStatus({ isPending: false, isSuccess: true, data: undefined }),
    'unauthenticated',
  )
  assert.equal(
    deriveAuthStatus({ isPending: false, isSuccess: false, data: undefined }),
    'unauthenticated',
  )
})

test('sign-out flips an actively-mounted session query to unauthenticated', async () => {
  const { client, observer, notifications, unsubscribe } = primedObserver()
  assert.equal(deriveAuthStatus(observer.getCurrentResult()), 'authenticated')

  dropSession(client)

  // Synchronously visible to the render the shell would perform next…
  assert.equal(observer.getCurrentResult().data, null)
  assert.equal(deriveAuthStatus(observer.getCurrentResult()), 'unauthenticated')

  // …and delivered to subscribed components without a refetch happening.
  await settle()
  assert.ok(notifications.length > 0, 'the observer must be notified of the drop')
  const last = notifications[notifications.length - 1]
  assert.equal(deriveAuthStatus(last), 'unauthenticated')

  unsubscribe()
})

test('a dropped session stays out until a new sign-in primes it', async () => {
  const { client, observer, unsubscribe } = primedObserver()

  dropSession(client)
  await settle()
  assert.equal(deriveAuthStatus(observer.getCurrentResult()), 'unauthenticated')

  // Dropping twice stays signed out (sign-out is idempotent).
  dropSession(client)
  await settle()
  assert.equal(deriveAuthStatus(observer.getCurrentResult()), 'unauthenticated')

  // Signing back in primes the same mounted query without a reload.
  client.setQueryData<SessionData>(SESSION_KEY, { user: USER })
  await settle()
  assert.equal(deriveAuthStatus(observer.getCurrentResult()), 'authenticated')

  unsubscribe()
})
