/**
 * Dashboard view state (Part 6).
 *
 * One pure reducer maps query states to what the engineer should see, so
 * loading / empty / API error / expired session / backend offline /
 * telemetry-disconnected are all explicit, testable states instead of
 * ad-hoc conditionals spread through the component.
 */

import type { QueryFailure } from '../api/failure'

export type SafetyStatusLike =
  | 'safe'
  | 'near_limit'
  | 'safeguard_activated'
  | 'violation'
  | 'unknown'

export type TelemetryFeed = 'loading' | 'ready' | 'empty' | 'disconnected'

export interface DashboardInput {
  plantsLoading: boolean
  plantsError: QueryFailure | null
  plantCount: number
  telemetry: TelemetryFeed
  safetyStatus: SafetyStatusLike
  pumpRunning: boolean
  reducedMotion: boolean
}

export type DashboardStatus =
  | 'loading'
  | 'offline'
  | 'session-expired'
  | 'error'
  | 'empty'
  | 'ready'

export type Tone = 'ok' | 'warn' | 'crit' | 'idle'

export interface DashboardViewState {
  status: DashboardStatus
  headline: string
  hint: string
  streamLabel: string
  streamTone: Tone
  safetyTone: Tone
  pipelineMotion: 'flow' | 'static'
  pumpMotion: 'spin' | 'still'
  warningPulse: 'none' | 'warn' | 'crit'
}

const SAFETY_TONE: Record<SafetyStatusLike, Tone> = {
  safe: 'ok',
  near_limit: 'warn',
  safeguard_activated: 'warn',
  violation: 'crit',
  unknown: 'idle',
}

interface Blocked {
  headline: string
  hint: string
}

const BLOCKED: Record<Exclude<DashboardStatus, 'ready'>, Blocked> = {
  loading: {
    headline: 'Loading workspace…',
    hint: 'Fetching your plants and configuration.',
  },
  offline: {
    headline: 'Backend unreachable',
    hint: 'Start the SafeFlux API (uvicorn) on port 8000, then retry.',
  },
  'session-expired': {
    headline: 'Session expired',
    hint: 'Sign in again to continue — the backend rejected the session.',
  },
  error: {
    headline: 'Could not load plants',
    hint: 'The API returned an error while loading your plants.',
  },
  empty: {
    headline: 'No plants configured yet',
    hint: 'Create a plant in Plant setup, then run a scenario in the live monitor.',
  },
}

function streamLabelFor(telemetry: TelemetryFeed): string {
  switch (telemetry) {
    case 'ready':
      return 'Telemetry live'
    case 'loading':
      return 'Connecting…'
    case 'disconnected':
      return 'Telemetry disconnected'
    default:
      return 'No scenario run yet'
  }
}

function streamToneFor(telemetry: TelemetryFeed): Tone {
  switch (telemetry) {
    case 'ready':
      return 'ok'
    case 'loading':
      return 'warn'
    case 'disconnected':
      return 'crit'
    default:
      return 'idle'
  }
}

function statusOf(input: DashboardInput): DashboardStatus {
  if (input.plantsError === 'offline') return 'offline'
  if (input.plantsError === 'session') return 'session-expired'
  if (input.plantsError) return 'error'
  if (input.plantsLoading) return 'loading'
  if (input.plantCount === 0) return 'empty'
  return 'ready'
}

function pulseFor(safetyStatus: SafetyStatusLike, reducedMotion: boolean): 'none' | 'warn' | 'crit' {
  if (reducedMotion) return 'none'
  if (safetyStatus === 'violation') return 'crit'
  if (safetyStatus === 'near_limit' || safetyStatus === 'safeguard_activated') return 'warn'
  return 'none'
}

export function deriveDashboardView(input: DashboardInput): DashboardViewState {
  const status = statusOf(input)
  const safetyTone = SAFETY_TONE[input.safetyStatus]

  if (status !== 'ready') {
    const blocked = BLOCKED[status]
    return {
      status,
      headline: blocked.headline,
      hint: blocked.hint,
      streamLabel: status === 'loading' ? 'Connecting…' : 'Idle',
      streamTone: 'idle',
      safetyTone,
      pipelineMotion: 'static',
      pumpMotion: 'still',
      warningPulse: 'none',
    }
  }

  const hasLiveStream = input.telemetry === 'ready'
  return {
    status,
    headline: '',
    hint: '',
    streamLabel: streamLabelFor(input.telemetry),
    streamTone: streamToneFor(input.telemetry),
    safetyTone,
    pipelineMotion: input.reducedMotion || !hasLiveStream ? 'static' : 'flow',
    pumpMotion: input.reducedMotion || !input.pumpRunning ? 'still' : 'spin',
    warningPulse: pulseFor(input.safetyStatus, input.reducedMotion),
  }
}
