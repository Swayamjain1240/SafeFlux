/**
 * Deterministic unit tests for the telemetry stream state machine (Part 5).
 * Runs with the Node test runner (no browser, no extra dependencies):
 *
 *     npm --prefix frontend run test:unit
 */

import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  MAX_STREAM_ATTEMPTS,
  initialStreamState,
  mergeFrame,
  nextReconnectDelay,
  reduceStream,
  type StreamFrame,
  type StreamState,
} from '../src/telemetry/streamState.ts'

function frame(sequence: number, status = 'safe'): StreamFrame {
  return {
    sequence,
    status,
    time_s: sequence,
    values: { temperature_c: sequence },
    observed: { temperature_c: sequence },
    limits: { temperature_c: 100 },
    near_limits: { temperature_c: 90 },
    pump_running: true,
  }
}

function feed(state: StreamState, ...sequences: number[]): StreamState {
  return sequences.reduce((acc, sequence) => reduceStream(acc, { type: 'frame', frame: frame(sequence) }), state)
}

test('frames append in order and advance phase to live', () => {
  const state = feed(reduceStream(initialStreamState(), { type: 'connect' }), 0, 1, 2)
  assert.equal(state.phase, 'live')
  assert.deepEqual(
    state.frames.map((f) => f.sequence),
    [0, 1, 2],
  )
  assert.equal(state.lastSequence, 2)
})

test('connect sets connecting phase', () => {
  assert.equal(reduceStream(initialStreamState(), { type: 'connect' }).phase, 'connecting')
})

test('replayed reconnect frames replace by sequence (no duplicates)', () => {
  let state = feed(initialStreamState(), 0, 1, 2)
  // A reconnect replays from the start — values must be replaced, not doubled.
  state = feed(state, 0, 1, 2, 3)
  assert.deepEqual(
    state.frames.map((f) => f.sequence),
    [0, 1, 2, 3],
  )
  assert.equal(state.lastSequence, 3)
})

test('out-of-order frames are inserted by sequence', () => {
  const state = feed(initialStreamState(), 0, 2, 1)
  assert.deepEqual(
    state.frames.map((f) => f.sequence),
    [0, 1, 2],
  )
})

test('retained frames are bounded to the newest window', () => {
  let state = initialStreamState(3)
  state = feed(state, 0, 1, 2, 3, 4)
  assert.deepEqual(
    state.frames.map((f) => f.sequence),
    [2, 3, 4],
  )
  assert.equal(mergeFrame(state.frames, frame(1), 3).length, 3)
})

test('errors back off then give up after the attempt budget', () => {
  let state = initialStreamState()
  for (let i = 0; i < MAX_STREAM_ATTEMPTS - 1; i += 1) {
    state = reduceStream(state, { type: 'error' })
    assert.equal(state.phase, 'reconnecting')
  }
  state = reduceStream(state, { type: 'error' })
  assert.equal(state.phase, 'error')
  assert.equal(state.attempts, MAX_STREAM_ATTEMPTS)
})

test('a successful frame clears the reconnect attempt counter', () => {
  let state = reduceStream(initialStreamState(), { type: 'error' })
  state = reduceStream(state, { type: 'frame', frame: frame(0) })
  assert.equal(state.attempts, 0)
  assert.equal(state.phase, 'live')
})

test('complete ends the stream and resets attempts', () => {
  let state = feed(reduceStream(initialStreamState(), { type: 'error' }), 0)
  state = reduceStream(state, { type: 'complete' })
  assert.equal(state.phase, 'complete')
  assert.equal(state.attempts, 0)
})

test('disconnect preserves frames for a seamless reconnect', () => {
  const live = feed(initialStreamState(), 0, 1)
  const down = reduceStream(live, { type: 'disconnect' })
  assert.equal(down.phase, 'idle')
  assert.equal(down.frames.length, 2)
  assert.equal(down.lastSequence, 1)
})

test('reset clears frames and returns to connecting', () => {
  const state = reduceStream(feed(initialStreamState(), 0, 1), { type: 'reset' })
  assert.equal(state.phase, 'connecting')
  assert.equal(state.frames.length, 0)
  assert.equal(state.lastSequence, null)
})

test('reconnect backoff grows and is capped', () => {
  assert.equal(nextReconnectDelay(0, 500), 500)
  assert.equal(nextReconnectDelay(1, 500), 1000)
  assert.equal(nextReconnectDelay(2, 500), 2000)
  assert.equal(nextReconnectDelay(10, 500), 8000)
})
