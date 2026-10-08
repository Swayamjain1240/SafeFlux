import { type ReactNode, useEffect, useRef } from 'react'
import { useLocation } from 'react-router-dom'
import { gsap } from 'gsap'
import { ROUTE_TRANSITION_MS, shouldAnimateRoute } from '../animation/routeTransitionPlan'
import { useReducedMotion } from '../animation/useReducedMotion'

/**
 * Page transition wrapper (visual transformation).
 *
 * One short fade-and-rise per route change so the workspace feels responsive;
 * the timeline is killed on unmount and skipped entirely under reduced motion
 * or on first paint. The wrapper keeps `h-full min-h-0` so every page's
 * one-viewport contract is preserved.
 */
export function RouteTransition({ children }: { children: ReactNode }) {
  const location = useLocation()
  const reducedMotion = useReducedMotion()
  const ref = useRef<HTMLDivElement>(null)
  const lastPath = useRef<string | null>(null)

  useEffect(() => {
    const element = ref.current
    const firstRender = lastPath.current === null
    const samePath = lastPath.current === location.pathname
    lastPath.current = location.pathname

    if (!element || !shouldAnimateRoute({ reducedMotion, firstRender, samePath })) return

    const tween = gsap.fromTo(
      element,
      { opacity: 0, y: 8 },
      {
        opacity: 1,
        y: 0,
        duration: ROUTE_TRANSITION_MS / 1000,
        ease: 'power2.out',
        clearProps: 'transform,opacity',
      },
    )
    return () => {
      tween.kill()
    }
  }, [location.pathname, reducedMotion])

  return (
    <div ref={ref} className="flex h-full min-h-0 flex-col">
      {children}
    </div>
  )
}
