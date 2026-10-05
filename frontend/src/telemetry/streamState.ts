/**
 * Pure telemetry stream state machine (Part 5).
 *
 * No DOM and no React: this is the reconnect/merge logic behind the live
 * monitor, kept separate so it can be unit-tested deterministically. It merges
 * replayed frames by sequence (a reconnect replays from the start), bounds the
 * retained window, and models the connection lifecycle.
 */

export type StreamPhase = 'idle' | 'connecting' | 'live' | 'reconnecting' | 'complete' | 'error'

export interface StreamFrame {
  sequence: number
  status: string
  time_s: number
  values: Record<string, number>
  observed: Record<string, number>
  limits: Record<string, number>
  near_limits: Record<string, number>
  pump_running: boolean
}

export interface StreamState {
  phase: StreamPhase
  frames: StreamFrame[]
  lastSequence: number | null
  attempts: number
  maxFrames: number
}

export const MAX_STREAM_ATTEMPTS = 5

export type StreamAction =
  | { type: 'connect' }
  | { type: 'frame'; frame: StreamFrame }
  | { type: 'complete' }
  | { type: 'error' }
  | { type: 'disconnect' }
  | { type: 'reset' }

export function initialStreamState(maxFrames = 400): StreamState {
  return { phase: 'idle', frames: [], lastSequence: null, attempts: 0, maxFrames }
}

/** Insert/replace a frame by sequence, keeping the newest `maxFrames`. */
export function mergeFrame(frames: StreamFrame[], frame: StreamFrame, maxFrames: number): StreamFrame[] {
  const next = frames.slice()
  const existing = next.findIndex((item) => item.sequence === frame.sequence)
  if (existing >= 0) {
    next[existing] = frame
  } else {
    // Keep the array ordered by sequence; incoming frames may skip or arrive late.
    let index = next.length
    while (index > 0 && next[index - 1].sequence > frame.sequence) index -= 1
    next.splice(index, 0, frame)
  }
  if (maxFrames > 0 && next.length > maxFrames) {
    return next.slice(next.length - maxFrames)
  }
  return next
}

export function reduceStream(state: StreamState, action: StreamAction): StreamState {
  switch (action.type) {
    case 'connect':
      return { ...state, phase: 'connecting' }
    case 'frame': {
      const frames = mergeFrame(state.frames, action.frame, state.maxFrames)
      const lastSequence = frames.length ? frames[frames.length - 1].sequence : state.lastSequence
      return { ...state, phase: 'live', frames, lastSequence, attempts: 0 }
    }
    case 'complete':
      return { ...state, phase: 'complete', attempts: 0 }
    case 'error': {
      const attempts = state.attempts + 1
      return {
        ...state,
        attempts,
        phase: attempts >= MAX_STREAM_ATTEMPTS ? 'error' : 'reconnecting',
      }
    }
    case 'disconnect':
      // Keep frames/lastSequence so a reconnect can continue seamlessly.
      return { ...state, phase: 'idle' }
    case 'reset':
      return { ...initialStreamState(state.maxFrames), phase: 'connecting' }
    default:
      return state
  }
}

/** Exponential backoff (ms) for reconnection attempts, capped at 8s. */
export function nextReconnectDelay(attempts: number, baseMs = 500): number {
  const delay = baseMs * 2 ** Math.max(0, attempts)
  return Math.min(delay, 8000)
}
