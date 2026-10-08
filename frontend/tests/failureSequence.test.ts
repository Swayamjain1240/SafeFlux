import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  buildSequenceSteps,
  hasRecordedViolation,
  labelForType,
  orderFindingSequence,
  toneForStatus,
} from '../src/animation/failureSequence.ts'
import type { SafetyFinding } from '../src/types/analysis.ts'

function finding(partial: Partial<SafetyFinding>): SafetyFinding {
  return {
    type: 'pressure_limit',
    status: 'violation',
    severity: 'critical',
    timestamp_s: 10,
    measured_value: 4.4,
    limit: 4,
    near_limit: 3.6,
    scenario_id: 'case-a',
    message: 'Pressure exceeded the configured limit.',
    ...partial,
  }
}

test('findings are ordered by their own recorded timestamps', () => {
  const late = finding({ type: 'late', timestamp_s: 71 })
  const early = finding({ type: 'early', timestamp_s: 55 })
  const middle = finding({ type: 'middle', timestamp_s: 60 })
  const ordered = orderFindingSequence([late, early, middle])
  assert.deepEqual(
    ordered.map((item) => item.type),
    ['early', 'middle', 'late'],
  )
})

test('findings without a timestamp keep their relative order and sort last', () => {
  const noTimeA = finding({ type: 'no-time-a', timestamp_s: null })
  const noTimeB = finding({ type: 'no-time-b', timestamp_s: null })
  const timed = finding({ type: 'timed', timestamp_s: 12 })
  const ordered = orderFindingSequence([noTimeA, timed, noTimeB])
  assert.deepEqual(
    ordered.map((item) => item.type),
    ['timed', 'no-time-a', 'no-time-b'],
  )
})

test('equal timestamps preserve the engine output order', () => {
  const a = finding({ type: 'a', timestamp_s: 30 })
  const b = finding({ type: 'b', timestamp_s: 30 })
  assert.deepEqual(
    orderFindingSequence([a, b]).map((item) => item.type),
    ['a', 'b'],
  )
})

test('statuses map to the safety tones, including shutdown', () => {
  assert.equal(toneForStatus('violation'), 'crit')
  assert.equal(toneForStatus('shutdown'), 'crit')
  assert.equal(toneForStatus('near_limit'), 'warn')
  assert.equal(toneForStatus('safeguard_activated'), 'warn')
  assert.equal(toneForStatus('safe'), 'ok')
  assert.equal(toneForStatus('unknown_state'), 'idle')
})

test('steps carry a readable label, the real numbers and 1-based index', () => {
  const steps = buildSequenceSteps([
    finding({ type: 'high_pressure_alarm', timestamp_s: 55, measured_value: 4.61, limit: 4.5 }),
    finding({ type: 'emergency_shutdown', timestamp_s: 76, status: 'shutdown', measured_value: null }),
  ])
  assert.equal(steps.length, 2)
  assert.equal(steps[0].label, 'High pressure alarm')
  assert.equal(steps[0].index, 1)
  assert.equal(steps[0].measured, '4.61')
  assert.equal(steps[0].limit, '4.50')
  assert.equal(steps[0].tone, 'crit')
  assert.equal(steps[1].measured, null)
  assert.equal(steps[1].label, 'Emergency shutdown')
})

test('violation detection follows the recorded statuses only', () => {
  assert.equal(hasRecordedViolation([finding({ status: 'violation' })]), true)
  assert.equal(
    hasRecordedViolation([finding({ status: 'near_limit' }), finding({ status: 'safe', type: 'ok' })]),
    false,
  )
  assert.equal(hasRecordedViolation([]), false)
})

test('empty type labels never produce blank text', () => {
  assert.equal(labelForType(''), '')
  assert.equal(labelForType('outlet_restriction'), 'Outlet restriction')
})
