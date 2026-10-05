import { useEffect, useReducer, useRef } from 'react'
import { fetchTelemetryHistory, telemetryStreamUrl } from '../api/telemetry'
import {
  MAX_STREAM_ATTEMPTS,
  initialStreamState,
  nextReconnectDelay,
  reduceStream,
  type StreamState,
} from '../telemetry/streamState'
import type { TelemetryFrame } from '../types/telemetry'

const MAX_FRAMES = 600

/**
 * Live telemetry hook: hydrates recent history, then streams new frames over
 * SSE, reconnecting with capped backoff. No LLM is involved — frames are
 * deterministic simulator output.
 */
export function useTelemetry(plantId: string | null, enabled: boolean): StreamState {
  const [state, dispatch] = useReducer(reduceStream, undefined, () => initialStreamState(MAX_FRAMES))
  const attempts = useRef(0)

  useEffect(() => {
    if (!plantId || !enabled) return
    let cancelled = false
    let source: EventSource | null = null
    let timer: number | undefined

    dispatch({ type: 'connect' })

    // Seed from bounded history so the chart is populated before SSE arrives.
    fetchTelemetryHistory(plantId, MAX_FRAMES)
      .then((data) => {
        if (cancelled) return
        for (const frame of data.frames) {
          dispatch({ type: 'frame', frame })
        }
      })
      .catch(() => {
        /* history is best-effort; the stream below is the live source */
      })

    const open = () => {
      if (cancelled) return
      source = new EventSource(telemetryStreamUrl(plantId), { withCredentials: true })

      source.addEventListener('telemetry', (event) => {
        attempts.current = 0
        dispatch({ type: 'frame', frame: JSON.parse((event as MessageEvent).data) as TelemetryFrame })
      })
      source.addEventListener('complete', () => {
        dispatch({ type: 'complete' })
        source?.close()
      })
      source.onerror = () => {
        source?.close()
        dispatch({ type: 'error' })
        attempts.current += 1
        if (attempts.current < MAX_STREAM_ATTEMPTS) {
          timer = window.setTimeout(open, nextReconnectDelay(attempts.current))
        }
      }
    }

    open()
    return () => {
      cancelled = true
      source?.close()
      if (timer) window.clearTimeout(timer)
      dispatch({ type: 'disconnect' })
    }
  }, [plantId, enabled])

  return state
}
