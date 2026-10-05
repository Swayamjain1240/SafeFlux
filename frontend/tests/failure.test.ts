/**
 * API failure classification + session-expiry tests (Part 6).
 *
 * These cover three of the required UI states without a DOM: backend offline,
 * expired session, and a plain API error — plus the guard that keeps the login
 * probe's 401 from causing a redirect loop.
 *
 *     npm --prefix frontend run test:unit
 */

import assert from 'node:assert/strict'
import { test } from 'node:test'

import { classifyApiFailure } from '../src/api/failure.ts'
import {
  SESSION_EXPIRED_EVENT,
  emitSessionExpired,
  onSessionExpired,
  shouldNotifySessionExpiry,
} from '../src/api/sessionEvents.ts'

test('transport failures are classified as offline', () => {
  assert.equal(classifyApiFailure({ code: 'NETWORK_ERROR' }), 'offline')
  assert.equal(classifyApiFailure({ code: 'TIMEOUT' }), 'offline')
  assert.equal(classifyApiFailure({ code: 'ECONNABORTED' }), 'offline')
  assert.equal(classifyApiFailure({ status: 0 }), 'offline')
  assert.equal(classifyApiFailure({}), 'offline')
})

test('a 401 on a protected call is an expired session', () => {
  assert.equal(classifyApiFailure({ status: 401 }), 'session')
})

test('other HTTP statuses are ordinary API errors', () => {
  assert.equal(classifyApiFailure({ status: 404 }), 'unknown')
  assert.equal(classifyApiFailure({ status: 500 }), 'unknown')
  assert.equal(classifyApiFailure({ status: 422, code: 'VALIDATION_ERROR' }), 'unknown')
})

test('absence of a failure is not a failure', () => {
  assert.equal(classifyApiFailure(null), null)
  assert.equal(classifyApiFailure(undefined), null)
})

test('only protected endpoints signal session expiry', () => {
  assert.equal(shouldNotifySessionExpiry(401, '/plants/p1/telemetry/current'), true)
  assert.equal(shouldNotifySessionExpiry(401, '/simulations/run'), true)
  assert.equal(shouldNotifySessionExpiry(401, '/plants'), true)
})

test('auth probes and non-401 responses never signal expiry', () => {
  assert.equal(shouldNotifySessionExpiry(401, '/auth/session'), false)
  assert.equal(shouldNotifySessionExpiry(401, '/auth/login'), false)
  assert.equal(shouldNotifySessionExpiry(401, '/auth/logout'), false)
  assert.equal(shouldNotifySessionExpiry(404, '/plants'), false)
  assert.equal(shouldNotifySessionExpiry(null, undefined), false)
  // An unidentifiable URL still fails closed to the login screen.
  assert.equal(shouldNotifySessionExpiry(401, null), true)
})

test('session-expired events reach registered listeners and unsubscribe cleanly', () => {
  const target = new EventTarget()
  let calls = 0
  const off = onSessionExpired(() => {
    calls += 1
  }, target)

  emitSessionExpired(target)
  assert.equal(calls, 1)

  off()
  emitSessionExpired(target)
  assert.equal(calls, 1)
  assert.equal(SESSION_EXPIRED_EVENT, 'safeflux:session-expired')
})

test('a missing target is a no-op rather than an exception', () => {
  emitSessionExpired(null)
  const off = onSessionExpired(() => undefined, null)
  off()
})
