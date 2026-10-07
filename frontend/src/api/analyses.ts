import { apiGet, apiPost } from './client'
import type {
  AnalysisOut,
  EventsPage,
  FailureDetail,
  HistoryPage,
  ReportPayload,
  ReverifyDocument,
} from '../types/analysis'

/**
 * Analysis API — mirrors /api/v1/analyses/* (Part 9).
 *
 * The session cookie is the only authorization; no owner id is ever supplied
 * by the client. A duplicate click is a server 409, not a client guess.
 */

export function runAnalysis(payload: { plant_id: string; goal: string }): Promise<AnalysisOut> {
  return apiPost<AnalysisOut>('/analyses/run', payload)
}

export function fetchAnalyses(page: number, pageSize: number): Promise<HistoryPage> {
  return apiGet<HistoryPage>(`/analyses?page=${page}&page_size=${pageSize}`)
}

export function fetchAnalysis(id: string): Promise<AnalysisOut> {
  return apiGet<AnalysisOut>(`/analyses/${encodeURIComponent(id)}`)
}

export function fetchAnalysisEvents(id: string, afterSeq: number): Promise<EventsPage> {
  return apiGet<EventsPage>(`/analyses/${encodeURIComponent(id)}/events?after_seq=${afterSeq}`)
}

/** The stored evidence document, typed at the call site (the envelope is generic). */
export async function fetchResultDocument<T>(id: string): Promise<T> {
  const data = await apiGet<{ status: string; result: Record<string, unknown> }>(
    `/analyses/${encodeURIComponent(id)}/result`,
  )
  return data.result as T
}

export function fetchFailureDetail(analysisId: string, failureId: string): Promise<FailureDetail> {
  return apiGet(
    `/analyses/${encodeURIComponent(analysisId)}/failures/${encodeURIComponent(failureId)}`,
  )
}

export function runReverify(
  analysisId: string,
  payload: { mitigations: Record<string, number>; goal?: string },
): Promise<AnalysisOut & { result: ReverifyDocument }> {
  return apiPost(`/analyses/${encodeURIComponent(analysisId)}/reverify`, payload)
}

export function fetchReport(analysisId: string): Promise<ReportPayload> {
  return apiGet<ReportPayload>(`/analyses/${encodeURIComponent(analysisId)}/report`)
}

/** The PDF is a download, not JSON: fetch it as a blob through the same client. */
export async function downloadReportPdf(analysisId: string): Promise<void> {
  const { apiClient } = await import('./client')
  const response = await apiClient.get(
    `/analyses/${encodeURIComponent(analysisId)}/report.pdf`,
    { responseType: 'blob' },
  )
  const url = URL.createObjectURL(response.data as Blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `safeflux-report-${analysisId}.pdf`
  anchor.click()
  URL.revokeObjectURL(url)
}
