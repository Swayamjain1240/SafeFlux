/**
 * Safeguard-evidence view derivation (QA Part 2, BUG-02).
 *
 * A re-verification run is stored as its own analysis row (`kind:
 * "reverification"`) whose evidence document carries the before/after
 * comparison — it has no `safeguards` section at all. The safeguards screen
 * used to read straight through `result.safeguards.note`, so deep-linking to
 * that record's safeguards page threw (`Cannot read properties of undefined`)
 * and the error boundary replaced the page.
 *
 * The document section is therefore optional by contract: this helper turns
 * any stored document into either real evidence or an explicit "no evidence
 * here, look at the parent" view, and the page renders both without throwing.
 */

import type { SafeguardTiming } from '../types/analysis'

/** The shape we rely on — structurally satisfied by both stored documents. */
export interface SafeguardsSource {
  safeguards?: {
    case_key?: string
    case_label?: string
    timings?: SafeguardTiming[] | null
    note?: string | null
  } | null
  parent_id?: string | null
}

export interface SafeguardsEvidence {
  note: string | null
  caseLabel: string | null
  timings: SafeguardTiming[]
}

export type SafeguardsView =
  | { kind: 'evidence'; evidence: SafeguardsEvidence }
  | { kind: 'no-evidence'; parentId: string | null }

export function safeguardsView(result: SafeguardsSource | null | undefined): SafeguardsView {
  const section = result?.safeguards
  if (!section) {
    return { kind: 'no-evidence', parentId: result?.parent_id ?? null }
  }
  return {
    kind: 'evidence',
    evidence: {
      note: section.note ?? null,
      caseLabel: section.case_label || section.case_key || null,
      timings: Array.isArray(section.timings) ? section.timings : [],
    },
  }
}
