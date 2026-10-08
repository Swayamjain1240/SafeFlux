import { useEffect, useRef, useState } from 'react'
import { useReducedMotion } from '../animation/useReducedMotion'
import type { ReactorTwinHandle, TwinStatus } from '../three/reactorTwin'

/**
 * Landing-hero digital twin (visual transformation, §10–12).
 *
 * Performance contract, in order of importance:
 *   1. `three` itself is a dynamic import, requested only after first paint —
 *      so no app route pays for it, and the hero text paints first.
 *   2. The animation loop runs only while the canvas is on screen and the tab
 *      is visible; scrolling away stops it and the last frame remains.
 *   3. Reduced-motion users get one static frame, re-rendered on state/size
 *      change (no continuous motion at all).
 *   4. The handle disposes every geometry, material and the renderer on
 *      unmount, and the scene is simplified on narrow viewports.
 *
 * If WebGL is unavailable the component degrades to a labelled static
 * schematic — never a fake animation.
 */

const IDLE_TIMEOUT_MS = 600

function whenIdle(callback: () => void): () => void {
  const view = window as Window & {
    requestIdleCallback?: (cb: () => void, options?: { timeout: number }) => number
    cancelIdleCallback?: (handle: number) => void
  }
  if (typeof view.requestIdleCallback === 'function') {
    const handle = view.requestIdleCallback(callback, { timeout: IDLE_TIMEOUT_MS })
    return () => view.cancelIdleCallback?.(handle)
  }
  const handle = window.setTimeout(callback, 220)
  return () => window.clearTimeout(handle)
}

function StaticSchematic() {
  return (
    <svg viewBox="0 0 320 220" role="img" aria-label="Static schematic of a reactor skid: feed tank, pump, reactor vessel with cooling coil, and outlet line." className="h-full w-full">
      <defs>
        <linearGradient id="twin-shell" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#1a222e" />
          <stop offset="100%" stopColor="#0b0f14" />
        </linearGradient>
      </defs>
      <g stroke="#2b3b4e" strokeWidth="1.2" fill="none">
        <rect x="140" y="46" width="78" height="120" rx="6" fill="url(#twin-shell)" />
        <ellipse cx="179" cy="46" rx="39" ry="9" fill="#151c26" />
        <ellipse cx="179" cy="166" rx="39" ry="9" fill="#151c26" />
        <path d="M150 74h58M150 96h58M150 118h58" stroke="#3b4c60" />
        <rect x="34" y="96" width="44" height="66" rx="5" fill="url(#twin-shell)" />
        <rect x="88" y="146" width="26" height="22" rx="3" fill="#151c26" />
        <path d="M56 96v-14h84M78 150h34" stroke="#3b4c60" strokeDasharray="4 4" />
        <path d="M218 86h52v78" stroke="#3b4c60" />
        <circle cx="179" cy="30" r="4" fill="#00d9ff" />
        <path d="M120 178h118" stroke="#1e2a38" />
      </g>
    </svg>
  )
}

export function TwinCanvas({
  status,
  className = '',
}: {
  /** Mirrors the API health probe the page already shows (see LandingPage). */
  status: TwinStatus
  className?: string
}) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const handleRef = useRef<ReactorTwinHandle | null>(null)
  const visibleRef = useRef(true)
  const statusRef = useRef(status)
  const reducedMotion = useReducedMotion()
  const [unavailable, setUnavailable] = useState(false)

  useEffect(() => {
    statusRef.current = status
    handleRef.current?.setStatus(status)
  }, [status])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    let cancelled = false
    let cleanupIdle: (() => void) | undefined
    let observer: IntersectionObserver | undefined
    let resizeObserver: ResizeObserver | undefined
    let onVisibility: (() => void) | undefined

    cleanupIdle = whenIdle(() => {
      void import('../three/reactorTwin')
        .then(({ createReactorTwin }) => {
          if (cancelled) return
          const narrow = container.clientWidth < 560
          const handle = createReactorTwin(container, {
            reducedMotion,
            simplified: narrow,
          })
          if (!handle) {
            setUnavailable(true)
            return
          }
          handleRef.current = handle
          handle.setStatus(statusRef.current)

          if (typeof IntersectionObserver === 'function') {
            observer = new IntersectionObserver(
              (entries) => {
                const entry = entries[0]
                if (!entry) return
                visibleRef.current = entry.isIntersecting
                if (entry.isIntersecting && document.visibilityState !== 'hidden') handle.start()
                else handle.stop()
              },
              { threshold: 0.05 },
            )
            observer.observe(container)
          } else {
            handle.start()
          }

          if (typeof ResizeObserver === 'function') {
            resizeObserver = new ResizeObserver(() => handle.resize())
            resizeObserver.observe(container)
          } else {
            window.addEventListener('resize', handle.resize)
          }

          onVisibility = () => {
            if (document.visibilityState === 'hidden') handle.stop()
            else if (visibleRef.current) handle.start()
          }
          document.addEventListener('visibilitychange', onVisibility)
        })
        .catch(() => {
          if (!cancelled) setUnavailable(true)
        })
    })

    return () => {
      cancelled = true
      cleanupIdle?.()
      observer?.disconnect()
      resizeObserver?.disconnect()
      if (onVisibility) document.removeEventListener('visibilitychange', onVisibility)
      handleRef.current?.dispose()
      handleRef.current = null
    }
    // Mount-only: status is pushed through the effect above, and a change of
    // reduced-motion preference re-mounts the scene deliberately.
  }, [reducedMotion])

  return (
    <div className={`relative overflow-hidden ${className}`}>
      <div ref={containerRef} className="absolute inset-0" aria-hidden="true" />
      {unavailable && (
        <div className="absolute inset-0 p-4">
          <StaticSchematic />
        </div>
      )}
      <span className="sr-only">
        Illustration of a reactor skid — feed tank, pump, reactor with cooling coil and outlet
        line. The live process topology with real values is on the Monitor page.
      </span>
    </div>
  )
}
