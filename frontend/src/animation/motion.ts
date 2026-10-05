/**
 * Motion plan for the process graph (Part 6).
 *
 * Animation must communicate state, never decorate. This pure function decides
 * *what* moves — pipeline flow, pump rotor, warning/critical pulse and the
 * state-change flash — and a React hook (see `useProcessMotion`) owns the GSAP
 * timelines. Keeping the decision here makes reduced-motion and the "no
 * animation without meaning" rule unit-testable.
 */

import type { SafetyStatusLike } from '../dashboard/viewState'

export type SafetyStatus = SafetyStatusLike

export interface MotionInput {
  /** `prefers-reduced-motion` is honoured absolutely: nothing animates. */
  reducedMotion: boolean
  /** Telemetry exists, so a flowing pipeline actually means something. */
  hasTelemetry: boolean
  pumpRunning: boolean
  safetyStatus: SafetyStatus
  /** Changes when the safety status changes; drives the state-change flash. */
  stateKey: string
}

export interface MotionPlan {
  pipeline: 'flow' | 'static'
  rotor: 'spin' | 'still'
  pulse: 'none' | 'warn' | 'crit'
  flashOnStateChange: boolean
  stateKey: string
}

export function pulseFor(safetyStatus: SafetyStatus): 'none' | 'warn' | 'crit' {
  if (safetyStatus === 'violation') return 'crit'
  if (safetyStatus === 'near_limit' || safetyStatus === 'safeguard_activated') return 'warn'
  return 'none'
}

export function buildMotionPlan(input: MotionInput): MotionPlan {
  if (input.reducedMotion) {
    return {
      pipeline: 'static',
      rotor: 'still',
      pulse: 'none',
      flashOnStateChange: false,
      stateKey: input.stateKey,
    }
  }
  return {
    pipeline: input.hasTelemetry ? 'flow' : 'static',
    rotor: input.pumpRunning ? 'spin' : 'still',
    pulse: pulseFor(input.safetyStatus),
    flashOnStateChange: true,
    stateKey: input.stateKey,
  }
}
