import { useEffect, useState } from 'react'
import { classifyViewport, type ViewportClass } from './viewport'

export interface Viewport {
  width: number
  height: number
  viewport: ViewportClass
}

/**
 * Live viewport size (Part 6).
 *
 * Width *and* height are tracked because the one-viewport rule is about height
 * as much as width: a 1366×768 laptop must use the compact layout even though
 * it is wider than a tablet. Falls back to a neutral small size when the
 * window object is unavailable.
 */
export function useViewport(): Viewport {
  const [state, setState] = useState<Viewport>(() => {
    if (typeof window === 'undefined') return { width: 390, height: 844, viewport: 'mobile' }
    const { innerWidth, innerHeight } = window
    return { width: innerWidth, height: innerHeight, viewport: classifyViewport(innerWidth, innerHeight) }
  })

  useEffect(() => {
    if (typeof window === 'undefined') return
    let frame = 0
    const onResize = () => {
      cancelAnimationFrame(frame)
      frame = requestAnimationFrame(() => {
        const width = window.innerWidth
        const height = window.innerHeight
        setState({ width, height, viewport: classifyViewport(width, height) })
      })
    }
    onResize()
    window.addEventListener('resize', onResize)
    return () => {
      cancelAnimationFrame(frame)
      window.removeEventListener('resize', onResize)
    }
  }, [])

  return state
}
