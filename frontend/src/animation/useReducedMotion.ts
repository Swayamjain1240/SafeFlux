import { useEffect, useState } from 'react'

/**
 * `prefers-reduced-motion` as a live value (Part 6).
 *
 * Returns `true` when the OS/user asks for reduced motion, so every GSAP
 * timeline can be skipped entirely rather than merely shortened. Defaults to
 * `false` when the query is unavailable (SSR/tests).
 */
export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false)

  useEffect(() => {
    if (typeof window === 'undefined' || typeof window.matchMedia !== 'function') return
    const query = window.matchMedia('(prefers-reduced-motion: reduce)')
    const apply = () => setReduced(query.matches)
    apply()
    if (typeof query.addEventListener === 'function') {
      query.addEventListener('change', apply)
      return () => query.removeEventListener('change', apply)
    }
    // Safari < 14 fallback
    query.addListener(apply)
    return () => query.removeListener(apply)
  }, [])

  return reduced
}
