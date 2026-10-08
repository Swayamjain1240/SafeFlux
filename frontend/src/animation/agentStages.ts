/**
 * Agent stage rail (visual transformation).
 *
 * The live investigation screen shows the agent's workflow — plan, simulate,
 * observe, investigate, re-test — but every node state is derived from the
 * pipeline events the backend actually recorded. There is no timer here and no
 * optimistic progress: a stage is `complete` because its event exists, and
 * `active` only as the immediate successor of the last recorded stage while the
 * run is still working (an ordering hint from the fixed pipeline, never a
 * claim that work is happening).
 *
 * Pure and unit-tested; the page renders it with the design-system classes.
 */

import type { EventKind } from '../types/analysis'

export type AgentStageId = 'plan' | 'simulate' | 'observe' | 'investigate' | 'retest'

export type AgentStageState = 'pending' | 'active' | 'complete'

export interface AgentStage {
  id: AgentStageId
  label: string
  kinds: EventKind[]
  state: AgentStageState
}

/** Fixed pipeline order — mirrors the backend's recorded stage sequence. */
export const AGENT_STAGE_DEFS: readonly { id: AgentStageId; label: string; kinds: EventKind[] }[] = [
  { id: 'plan', label: 'Plan', kinds: ['understanding_change', 'mapping_equipment', 'planning'] },
  { id: 'simulate', label: 'Simulate', kinds: ['running_scenario'] },
  { id: 'observe', label: 'Observe', kinds: ['observing_result'] },
  {
    id: 'investigate',
    label: 'Investigate',
    kinds: ['refining_boundary', 'finding_violation', 'running_counterfactual'],
  },
  { id: 'retest', label: 'Re-test', kinds: ['checking_safeguard'] },
]

export function deriveAgentStages(recordedKinds: readonly EventKind[], status: string): AgentStage[] {
  const recorded = new Set<EventKind>(recordedKinds)
  const working = status === 'running' || status === 'pending'

  const lastRecordedIndex = (() => {
    for (let stageIndex = AGENT_STAGE_DEFS.length - 1; stageIndex >= 0; stageIndex -= 1) {
      if (AGENT_STAGE_DEFS[stageIndex].kinds.some((kind) => recorded.has(kind))) return stageIndex
    }
    return -1
  })()

  const activeIndex = working ? Math.min(lastRecordedIndex + 1, AGENT_STAGE_DEFS.length - 1) : -1

  return AGENT_STAGE_DEFS.map((def, index) => {
    const complete = def.kinds.some((kind) => recorded.has(kind))
    const state: AgentStageState = complete
      ? 'complete'
      : index === activeIndex
        ? 'active'
        : 'pending'
    return { id: def.id, label: def.label, kinds: def.kinds, state }
  })
}
