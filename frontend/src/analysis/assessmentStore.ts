/**
 * Last safety assessment (Part 6).
 *
 * The backend is stateless about assessments (they are returned by
 * `POST /simulations/run` but not yet persisted — that arrives with AnalysisRun
 * in Part 7). The dashboard still needs "recent findings" and "analysis status
 * if one exists", so the monitor records what the API returned here. Nothing is
 * computed client-side: this is only a cache of the backend's own verdict, and
 * it is dropped with the tab.
 */

import type { SafetyAssessment } from '../types/telemetry'

export interface AssessmentRecord {
  plantId: string
  scenarioLabel: string | null
  recordedAt: number
  safety: SafetyAssessment
}

let snapshot: AssessmentRecord | null = null
const listeners = new Set<() => void>()

function emit(): void {
  for (const listener of listeners) listener()
}

/** Remember the assessment a run returned for one plant. */
export function recordAssessment(next: AssessmentRecord): void {
  snapshot = next
  emit()
}

/** Drop the cached assessment (e.g. after sign-out). */
export function clearAssessment(): void {
  if (snapshot === null) return
  snapshot = null
  emit()
}

export function getAssessment(): AssessmentRecord | null {
  return snapshot
}

export function subscribeAssessment(listener: () => void): () => void {
  listeners.add(listener)
  return () => {
    listeners.delete(listener)
  }
}
