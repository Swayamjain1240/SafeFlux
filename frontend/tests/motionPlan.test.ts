/**
 * Motion plan tests (Part 6).
 *
 * Guards the animation rule: only state-communicating motion is planned,
 * reduced-motion plans nothing at all, and the plan changes only when the
 * state that justifies it changes.
 *
 *     npm --prefix frontend run test:unit
 */

import assert from 'node:assert/strict'
import { test } from 'node:test'

import { buildMotionPlan, pulseFor, type MotionInput } from '../src/animation/motion.ts'

function input(overrides: Partial<MotionInput> = {}): MotionInput {
  return {
    reducedMotion: false,
    hasTelemetry: true,
    pumpRunning: true,
    safetyStatus: 'safe',
    stateKey: 'safe',
    ...overrides,
  }
}

test('reduced motion produces a fully static plan', () => {
  const plan = buildMotionPlan(
    input({ reducedMotion: true, pumpRunning: true, safetyStatus: 'violation', stateKey: 'violation' }),
  )
  assert.equal(plan.pipeline, 'static')
  assert.equal(plan.rotor, 'still')
  assert.equal(plan.pulse, 'none')
  assert.equal(plan.flashOnStateChange, false)
})

test('pipeline only flows when there is telemetry to justify it', () => {
  assert.equal(buildMotionPlan(input({ hasTelemetry: true })).pipeline, 'flow')
  assert.equal(buildMotionPlan(input({ hasTelemetry: false })).pipeline, 'static')
})

test('the rotor spins only while the pump runs', () => {
  assert.equal(buildMotionPlan(input({ pumpRunning: true })).rotor, 'spin')
  assert.equal(buildMotionPlan(input({ pumpRunning: false })).rotor, 'still')
})

test('pulse severity follows the safety status', () => {
  assert.equal(pulseFor('safe'), 'none')
  assert.equal(pulseFor('unknown'), 'none')
  assert.equal(pulseFor('near_limit'), 'warn')
  assert.equal(pulseFor('safeguard_activated'), 'warn')
  assert.equal(pulseFor('violation'), 'crit')
  assert.equal(buildMotionPlan(input({ safetyStatus: 'violation', stateKey: 'violation' })).pulse, 'crit')
})

test('no pulse for a healthy process — do not animate everything', () => {
  assert.equal(buildMotionPlan(input()).pulse, 'none')
  assert.equal(buildMotionPlan(input()).flashOnStateChange, true, 'flash still allowed on change')
})

test('the plan carries the state key so a status change retriggers the flash', () => {
  const plan = buildMotionPlan(input({ stateKey: 'violation' }))
  assert.equal(plan.stateKey, 'violation')
  assert.notEqual(plan.stateKey, 'safe')
})

test('motion stays static when the process is idle and unhealthy', () => {
  const plan = buildMotionPlan(input({ hasTelemetry: false, pumpRunning: false, safetyStatus: 'violation' }))
  assert.equal(plan.pipeline, 'static')
  assert.equal(plan.rotor, 'still')
  assert.equal(plan.pulse, 'crit', 'a critical process still pulses for attention')
})
