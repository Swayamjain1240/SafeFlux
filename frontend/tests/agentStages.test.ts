/**
 * Agent stage rail tests (visual transformation).
 *
 * The rail must reflect recorded backend events only: no stage may look
 * complete without its event, and nothing may look active after the run
 * stopped. These tests pin that contract.
 *
 *     npm --prefix frontend run test:unit
 */

import assert from 'node:assert/strict'
import { test } from 'node:test'

import { AGENT_STAGE_DEFS, deriveAgentStages } from '../src/animation/agentStages.ts'

test('with no events only the first stage is active while running', () => {
  const stages = deriveAgentStages([], 'running')
  assert.equal(stages.length, AGENT_STAGE_DEFS.length)
  assert.deepEqual(
    stages.map((stage) => stage.state),
    ['active', 'pending', 'pending', 'pending', 'pending'],
  )
})

test('a recorded stage is complete and the next one is active', () => {
  const stages = deriveAgentStages(['understanding_change', 'planning', 'running_scenario'], 'running')
  assert.deepEqual(
    stages.map((stage) => stage.state),
    ['complete', 'complete', 'active', 'pending', 'pending'],
  )
})

test('a finished run never shows an active stage', () => {
  const stages = deriveAgentStages(
    ['understanding_change', 'planning', 'running_scenario', 'observing_result', 'checking_safeguard'],
    'complete',
  )
  assert.deepEqual(
    stages.map((stage) => stage.state),
    ['complete', 'complete', 'complete', 'pending', 'complete'],
  )
})

test('a failed run keeps only what was really recorded', () => {
  const stages = deriveAgentStages(['understanding_change'], 'failed')
  assert.deepEqual(
    stages.map((stage) => stage.state),
    ['complete', 'pending', 'pending', 'pending', 'pending'],
  )
})

test('the stage order matches the documented pipeline', () => {
  assert.deepEqual(
    AGENT_STAGE_DEFS.map((def) => def.id),
    ['plan', 'simulate', 'observe', 'investigate', 'retest'],
  )
})
