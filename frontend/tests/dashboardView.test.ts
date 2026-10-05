/**
 * Dashboard view-state tests (Part 6).
 *
 * Every required UI state is a pure function of the query inputs, so the
 * branches are exercised directly: loading, empty data, API error, expired
 * session, backend offline, telemetry disconnected, plus reduced-motion.
 *
 *     npm --prefix frontend run test:unit
 */

import assert from 'node:assert/strict'
import { test } from 'node:test'

import { deriveDashboardView, type DashboardInput } from '../src/dashboard/viewState.ts'

function input(overrides: Partial<DashboardInput> = {}): DashboardInput {
  return {
    plantsLoading: false,
    plantsError: null,
    plantCount: 1,
    telemetry: 'ready',
    safetyStatus: 'safe',
    pumpRunning: true,
    reducedMotion: false,
    ...overrides,
  }
}

test('loading while the plant query is pending', () => {
  const view = deriveDashboardView(input({ plantsLoading: true, plantCount: 0 }))
  assert.equal(view.status, 'loading')
  assert.equal(view.pipelineMotion, 'static')
  assert.equal(view.pumpMotion, 'still')
})

test('empty data when no plant is configured', () => {
  const view = deriveDashboardView(input({ plantCount: 0 }))
  assert.equal(view.status, 'empty')
  assert.match(view.headline, /No plants/)
  assert.match(view.hint, /Plant setup/)
})

test('backend offline when the API cannot be reached', () => {
  const view = deriveDashboardView(input({ plantsError: 'offline' }))
  assert.equal(view.status, 'offline')
  assert.match(view.headline, /unreachable/i)
  assert.equal(view.pipelineMotion, 'static')
})

test('expired session is reported distinctly from other errors', () => {
  const view = deriveDashboardView(input({ plantsError: 'session' }))
  assert.equal(view.status, 'session-expired')
  assert.match(view.hint, /Sign in again/)
})

test('generic API error keeps its own message', () => {
  const view = deriveDashboardView(input({ plantsError: 'unknown' }))
  assert.equal(view.status, 'error')
  assert.match(view.headline, /Could not load/)
})

test('telemetry disconnected shows a bad stream badge but keeps the layout ready', () => {
  const view = deriveDashboardView(input({ telemetry: 'disconnected' }))
  assert.equal(view.status, 'ready')
  assert.equal(view.streamLabel, 'Telemetry disconnected')
  assert.equal(view.streamTone, 'crit')
  assert.equal(view.pipelineMotion, 'static', 'no flowing pipeline without telemetry')
})

test('no scenario run yet is an idle state, not an error', () => {
  const view = deriveDashboardView(input({ telemetry: 'empty' }))
  assert.equal(view.status, 'ready')
  assert.equal(view.streamLabel, 'No scenario run yet')
  assert.equal(view.streamTone, 'idle')
})

test('live telemetry with a running pump animates the pipeline', () => {
  const view = deriveDashboardView(input())
  assert.equal(view.status, 'ready')
  assert.equal(view.streamLabel, 'Telemetry live')
  assert.equal(view.pipelineMotion, 'flow')
  assert.equal(view.pumpMotion, 'spin')
})

test('a stopped pump never spins even when telemetry is live', () => {
  const view = deriveDashboardView(input({ pumpRunning: false }))
  assert.equal(view.pumpMotion, 'still')
  assert.equal(view.pipelineMotion, 'flow')
})

test('reduced motion disables every animation', () => {
  const view = deriveDashboardView(
    input({ reducedMotion: true, safetyStatus: 'violation', pumpRunning: true }),
  )
  assert.equal(view.pipelineMotion, 'static')
  assert.equal(view.pumpMotion, 'still')
  assert.equal(view.warningPulse, 'none')
  assert.equal(view.safetyTone, 'crit', 'the colour still communicates the state')
})

test('safety status maps to pulse severity', () => {
  assert.equal(deriveDashboardView(input({ safetyStatus: 'safe' })).warningPulse, 'none')
  assert.equal(deriveDashboardView(input({ safetyStatus: 'near_limit' })).warningPulse, 'warn')
  assert.equal(deriveDashboardView(input({ safetyStatus: 'safeguard_activated' })).warningPulse, 'warn')
  assert.equal(deriveDashboardView(input({ safetyStatus: 'violation' })).warningPulse, 'crit')
  assert.equal(deriveDashboardView(input({ safetyStatus: 'unknown' })).safetyTone, 'idle')
})

test('blocked states never advertise a live stream', () => {
  for (const error of ['offline', 'session', 'unknown'] as const) {
    const view = deriveDashboardView(input({ plantsError: error }))
    assert.equal(view.streamTone, 'idle')
    assert.equal(view.pipelineMotion, 'static')
  }
})
