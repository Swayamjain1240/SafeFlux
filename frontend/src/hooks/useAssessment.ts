import { useCallback, useSyncExternalStore } from 'react'
import {
  clearAssessment,
  getAssessment,
  recordAssessment,
  subscribeAssessment,
  type AssessmentRecord,
} from '../analysis/assessmentStore'

/** Reactive view of the cached backend assessment for one plant. */
export function useAssessmentFor(plantId: string | null): AssessmentRecord | null {
  const snapshot = useSyncExternalStore(subscribeAssessment, getAssessment, getAssessment)
  if (!snapshot || !plantId || snapshot.plantId !== plantId) return null
  return snapshot
}

export function useRecordAssessment(): (record: AssessmentRecord) => void {
  return useCallback((record: AssessmentRecord) => recordAssessment(record), [])
}

export function useClearAssessment(): () => void {
  return useCallback(() => clearAssessment(), [])
}
