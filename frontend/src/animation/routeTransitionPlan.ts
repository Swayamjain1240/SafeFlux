/**
 * Route transition plan (visual transformation).
 *
 * Navigation must feel immediate: a 240 ms fade-and-rise, never a cinematic
 * delay. The decision is a pure function so reduced-motion behaviour and the
 * "no animation on first paint / same route" rule are unit-testable; the GSAP
 * runner lives in `components/RouteTransition.tsx`.
 */

export const ROUTE_TRANSITION_MS = 240

export interface RouteTransitionInput {
  /** `prefers-reduced-motion` disables the transition entirely. */
  reducedMotion: boolean
  /** The first render is the initial page load — nothing to transition from. */
  firstRender: boolean
  /** Consecutive renders of the same path must not re-animate. */
  samePath: boolean
}

export function shouldAnimateRoute(input: RouteTransitionInput): boolean {
  if (input.reducedMotion) return false
  if (input.firstRender) return false
  if (input.samePath) return false
  return true
}
