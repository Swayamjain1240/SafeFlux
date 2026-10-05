import { useEffect, useMemo, type RefObject } from 'react'
import { gsap } from 'gsap'
import { buildMotionPlan, type MotionInput, type MotionPlan } from './motion'

type MotionProps = Omit<MotionInput, 'stateKey'> & {
  stateKey: string
  /**
   * React Flow mounts its edge paths only after nodes are measured, so the
   * first effect pass sees no edges. The graph flips this once the flow has
   * initialised; without it the pipeline tween would silently never start.
   */
  edgesReady: boolean
  /**
   * Changes whenever the graph is rebuilt (e.g. the layout switches between the
   * horizontal and vertical P&ID). React Flow recreates its edge elements then,
   * which discards the inline dash styles, so the plan must be re-applied.
   */
  graphKey: string
}

const SELECTOR = {
  pipeline: '.sf-flow-main .react-flow__edge-path',
  rotor: '[data-sf-rotor]',
  pulse: '[data-sf-pulse]',
  state: '[data-sf-state]',
} as const

function list<T extends Element>(root: ParentNode, selector: string): T[] {
  return Array.from(root.querySelectorAll<T>(selector))
}

/**
 * Drives the process-graph animation from a `MotionPlan` (Part 6).
 *
 * - pipeline flow: dashed stroke travel along the main-flow edges,
 * - pump running: rotor rotation (transform only),
 * - warning / critical: one restrained opacity pulse,
 * - state change: a single short flash when the safety status changes.
 *
 * Every timeline is created inside a `gsap.context` bound to the container, so
 * `ctx.revert()` kills them all on unmount or when the plan changes — no leaked
 * tweens. When `prefers-reduced-motion` is set the plan is fully static and
 * nothing is created at all.
 */
export function useProcessMotion(
  container: RefObject<HTMLElement | null>,
  props: MotionProps,
): void {
  const { reducedMotion, hasTelemetry, pumpRunning, safetyStatus, stateKey, edgesReady, graphKey } =
    props

  const plan: MotionPlan = useMemo(
    () => buildMotionPlan({ reducedMotion, hasTelemetry, pumpRunning, safetyStatus, stateKey }),
    [reducedMotion, hasTelemetry, pumpRunning, safetyStatus, stateKey],
  )

  useEffect(() => {
    const root = container.current
    const inert =
      plan.pipeline === 'static' &&
      plan.rotor === 'still' &&
      plan.pulse === 'none' &&
      !plan.flashOnStateChange
    if (!root || !edgesReady || inert) return

    // React Flow measures nodes first and only then mounts edge paths — and it
    // re-mounts them whenever the graph is re-laid out, which discards the
    // inline dash styles GSAP wrote. So instead of a one-shot pass we apply the
    // flow to whichever main-flow paths are still unstyled, on mount and on
    // every subsequent graph change. Tweens are registered on `ctx`, so
    // `ctx.revert()` stays authoritative over everything created here.
    let pipelineFrame = 0

    const applyPipeline = () => {
      const fresh = list<SVGPathElement>(root, SELECTOR.pipeline).filter(
        (path) => !path.style.strokeDasharray,
      )
      if (fresh.length === 0) return
      gsap.set(fresh, { strokeDasharray: '7 11' })
      gsap.to(fresh, { strokeDashoffset: -36, duration: 1.7, ease: 'none', repeat: -1 })
    }

    const ctx = gsap.context(() => {
      if (plan.rotor === 'spin') {
        const rotors = list<HTMLElement>(root, SELECTOR.rotor)
        if (rotors.length > 0) {
          gsap.to(rotors, {
            rotation: 360,
            duration: 1.5,
            ease: 'none',
            repeat: -1,
            transformOrigin: '50% 50%',
            force3D: false,
          })
        }
      }

      if (plan.pulse !== 'none') {
        const targets = list<HTMLElement>(root, SELECTOR.pulse)
        if (targets.length > 0) {
          gsap.to(targets, {
            opacity: 0.4,
            duration: 0.75,
            yoyo: true,
            repeat: -1,
            ease: 'sine.inOut',
          })
        }
      }

      if (plan.flashOnStateChange) {
        const targets = list<HTMLElement>(root, SELECTOR.state)
        if (targets.length > 0) {
          gsap.fromTo(
            targets,
            { opacity: 0.3, scale: 0.97 },
            {
              opacity: 1,
              scale: 1,
              duration: 0.4,
              ease: 'power2.out',
              stagger: 0.05,
              clearProps: 'opacity,scale',
            },
          )
        }
      }
    }, root)

    let observer: MutationObserver | null = null
    if (plan.pipeline === 'flow') {
      ctx.add(applyPipeline)
      observer = new MutationObserver(() => {
        cancelAnimationFrame(pipelineFrame)
        pipelineFrame = requestAnimationFrame(() => ctx.add(applyPipeline))
      })
      observer.observe(root, { childList: true, subtree: true })
    }

    return () => {
      observer?.disconnect()
      cancelAnimationFrame(pipelineFrame)
      ctx.revert()
    }
  }, [container, plan, edgesReady, graphKey])
}
