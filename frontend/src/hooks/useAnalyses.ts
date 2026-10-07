import { useEffect, useRef, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  downloadReportPdf,
  fetchAnalyses,
  fetchAnalysis,
  fetchAnalysisEvents,
  fetchFailureDetail,
  fetchReport,
  fetchResultDocument,
  runAnalysis,
  runReverify,
} from '../api/analyses'
import type { AnalysisEventOut, AnalysisResult, EventsPage } from '../types/analysis'

/**
 * Analysis hooks (Part 9). Polling the events cursor is the only "live"
 * mechanism: the page asks the backend what happened, and shows exactly that.
 * No timers fake progress — while the run works there is simply nothing new
 * to show, and the page says so.
 */

export const analysisKeys = {
  history: (page: number, pageSize: number) => ['analyses', 'history', page, pageSize] as const,
  detail: (id: string) => ['analyses', id] as const,
  events: (id: string) => ['analyses', id, 'events'] as const,
  failure: (id: string, failureId: string) => ['analyses', id, 'failures', failureId] as const,
  report: (id: string) => ['analyses', id, 'report'] as const,
}

export function useAnalysesHistory(page: number, pageSize: number) {
  return useQuery({
    queryKey: analysisKeys.history(page, pageSize),
    queryFn: () => fetchAnalyses(page, pageSize),
  })
}

export function useAnalysis(id: string | undefined) {
  return useQuery({
    queryKey: analysisKeys.detail(id ?? ''),
    queryFn: () => fetchAnalysis(id as string),
    enabled: Boolean(id),
  })
}

export function useRunAnalysis() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: { plant_id: string; goal: string }) => runAnalysis(payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['analyses'] })
    },
  })
}

export function useReverify(analysisId: string | undefined) {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: (payload: { mitigations: Record<string, number>; goal?: string }) =>
      runReverify(analysisId as string, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ['analyses'] })
    },
  })
}

/** The stored evidence document of one analysis, typed by the caller. */
export function useResultDocument(id: string | undefined) {
  return useQuery<AnalysisResult, unknown>({
    queryKey: ['analyses', id ?? '', 'result'],
    queryFn: () => fetchResultDocument<AnalysisResult>(id as string),
    enabled: Boolean(id),
    retry: false,
  })
}

export function useFailureDetail(analysisId: string | undefined, failureId: string | undefined) {
  return useQuery({
    queryKey: analysisKeys.failure(analysisId ?? '', failureId ?? ''),
    queryFn: () => fetchFailureDetail(analysisId as string, failureId as string),
    enabled: Boolean(analysisId && failureId),
    retry: false,
  })
}

export function useReport(analysisId: string | undefined) {
  return useQuery({
    queryKey: analysisKeys.report(analysisId ?? ''),
    queryFn: () => fetchReport(analysisId as string),
    enabled: Boolean(analysisId),
    retry: false,
  })
}

export function useDownloadReportPdf() {
  return useMutation({
    mutationFn: (analysisId: string) => downloadReportPdf(analysisId),
  })
}

/**
 * Cursor-polled events reader. Pass `reset` (a run id) to start a new cursor.
 * The poll stops when the analysis leaves `running`. The returned events are
 * the accumulated, de-duplicated seqs read from the backend — nothing local.
 */
export function useAnalysisEvents(
  analysisId: string | undefined,
  status: string | undefined,
): { events: AnalysisEventOut[]; pollError: unknown; done: boolean } {
  const [committed, setCommitted] = useState<AnalysisEventOut[]>([])
  const cursorRef = useRef(0)
  const done = status !== undefined && status !== 'running'

  const query = useQuery<EventsPage, unknown>({
    queryKey: analysisKeys.events(analysisId ?? ''),
    queryFn: () => fetchAnalysisEvents(analysisId as string, cursorRef.current),
    enabled: Boolean(analysisId),
    refetchInterval: done ? false : 1200,
  })

  // Commit new events through state; the effect only runs when the payload
  // identity changes (an external fetch result), which is the supported
  // use for synchronizing with an external system.
  const payload = query.data
  useEffect(() => {
    if (!payload || payload.events.length === 0) return
    setCommitted((previous) => {
      const seen = new Set(previous.map((event) => event.seq))
      const fresh = payload.events.filter((event) => !seen.has(event.seq))
      if (fresh.length === 0) return previous
      cursorRef.current = Math.max(cursorRef.current, payload.last_seq)
      return [...previous, ...fresh]
    })
  }, [payload])

  return { events: committed, pollError: query.error ?? null, done }
}
