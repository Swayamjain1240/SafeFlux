/**
 * Analysis domain types — mirror of the Part 9 backend documents
 * (Backend/app/analyses/constants.py, Backend/app/api/routes/analyses.py).
 *
 * Everything here is *recorded reality*: the events were written by the code
 * that did the work, and every number in a result came from the Part 4/5/7
 * deterministic layers. No type here invents or defaults a measurement.
 */

export type AnalysisKind = 'auto' | 'counterfactual' | 'reverify'

export type AnalysisStatus = 'running' | 'complete' | 'failed' | 'interrupted'

/** The canonical event kinds, in the order the pipeline can emit them. */
export const EVENT_KINDS = [
  'understanding_change',
  'mapping_equipment',
  'planning',
  'running_scenario',
  'observing_result',
  'refining_boundary',
  'finding_violation',
  'running_counterfactual',
  'checking_safeguard',
  'ai_summary',
  'complete',
  'failed',
] as const

export type EventKind = (typeof EVENT_KINDS)[number]

/** Mirror of backend EVENT_LABELS — same wording, one source of truth each. */
export const EVENT_LABELS: Record<EventKind, string> = {
  understanding_change: 'Understanding change',
  mapping_equipment: 'Mapping affected equipment',
  planning: 'Planning investigation',
  running_scenario: 'Running scenario',
  observing_result: 'Observing result',
  refining_boundary: 'Refining boundary',
  finding_violation: 'Finding violation',
  running_counterfactual: 'Running counterfactual',
  checking_safeguard: 'Checking safeguard',
  ai_summary: 'AI explanation',
  complete: 'Analysis complete',
  failed: 'Analysis failed',
}

export interface InterpretedChange {
  text: string
  direction: string | null
  magnitude: string | null
  magnitude_value: number | null
  is_percent: boolean
  variables: string[]
  unrecognised: string[]
}

export interface AnalysisCounts {
  scenarios?: number
  failing?: number
  violation?: number
  safeguard_activated?: number
  failures_stored?: number
  counterfactuals?: number
  headline?: string
  pivot_status?: string
  disclaimer?: string
  [key: string]: unknown
}

export interface AnalysisOut {
  id: string
  plant_id: string
  kind: AnalysisKind
  status: AnalysisStatus
  goal: string
  parent_id: string | null
  counts: AnalysisCounts | null
  error: string | null
  created_at: string
  finished_at: string | null
  has_result?: boolean
  disclaimer?: string
  result?: ReverifyDocument
}

export interface HistoryPage {
  items: AnalysisOut[]
  page: number
  page_size: number
  total: number
  pages: number
}

export interface AnalysisEventOut {
  seq: number
  kind: EventKind
  label: string | null
  payload: Record<string, unknown> | null
  elapsed_ms: number
}

export interface EventsPage {
  status: AnalysisStatus
  events: AnalysisEventOut[]
  last_seq: number
}

export type SafetyStatus = 'safe' | 'near_limit' | 'safeguard_activated' | 'violation'

export interface SafetyFinding {
  type: string
  status: string
  severity: string
  timestamp_s: number | null
  measured_value: number | null
  limit: number
  near_limit: number
  scenario_id: string | null
  message: string
}

export interface StoredFailure {
  key: string
  label: string
  values: Record<string, number>
  status: SafetyStatus
  rank: number
  observation_only: boolean
  peaks: Record<string, number | null>
  limit_exceeded: Record<string, boolean>
  shutdown_at_s: number | null
  worst_finding: SafetyFinding | null
  findings: SafetyFinding[]
  cached?: boolean
}

export interface CounterfactualRow {
  variable: string
  value: number
  label: string
  status_before: string | null
  status: string
  improved: boolean | null
  peaks: Record<string, number | null>
  changes: { variable: string; before: number | null; after: number | null; delta: number | null }[]
  case_key: string
  ai_explanation: string | null
}

export interface SafeguardTiming {
  safeguard: string
  variable: string | null
  trigger_time_s: number | null
  response_time_s: number | null
  violation_time_s: number | null
  prevented: boolean | null
  note: string
}

export interface SearchResultMeta {
  mode: string
  status: string
  counts: Record<string, number>
  cases: StoredFailure[]
  failures: StoredFailure[]
  boundaries: Record<string, unknown>[]
  notes: string[]
  [key: string]: unknown
}

export interface AiExplanation {
  headline?: string
  text?: string
  [key: string]: unknown
}

/** The stored evidence document of one completed auto analysis. */
export interface AnalysisResult {
  analysis_id: string
  kind: AnalysisKind
  goal: string
  interpreted_change: InterpretedChange
  plan: Record<string, unknown>
  original: SearchResultMeta
  failures: StoredFailure[]
  pivot: StoredFailure | null
  counterfactuals: CounterfactualRow[]
  safeguards: { case_key: string; case_label: string; timings: SafeguardTiming[]; note: string }
  ai_explanation: AiExplanation | null
  notes: string[]
  versions: Record<string, unknown>
  series_keys: string[]
  timeline_order: EventKind[]
  stage_index: Record<string, number>
}

export interface FailureDetail {
  analysis_id: string
  failure_id: string
  case_label: string
  scenario: { values: Record<string, number>; duration_s: number | null; time_step_s: number | null }
  configured_limits: { max_temperature_c: number; max_pressure_bar: number; max_level_pct: number }
  first_violation: SafetyFinding | null
  peaks: Record<string, number | null>
  status: SafetyStatus
  findings: SafetyFinding[]
  safeguard_events: SafeguardTiming[]
  series: Record<string, number[]>
  search_context: { mode: string; counts: Record<string, number> | null; boundaries: unknown[]; notes: string[] }
  note: string
}

export interface ReverifyComparisonRow {
  failure_id: string
  case_label: string
  status_before: string
  status_after: string
  peaks_before: Record<string, number | null>
  peaks_after: Record<string, number | null>
  improved: boolean
}

export interface ReverifyDocument {
  kind: 'reverify'
  parent_id: string
  mitigations: Record<string, number>
  mitigation_labels: string[]
  changed: string[]
  case_values: Record<string, number>
  comparison: { scenarios_retested: number; failing_before: number; failing_after: number }
  rows: ReverifyComparisonRow[]
  verdict: string
  note: string
}

export interface ReportPayload {
  analysis_id: string
  status: AnalysisStatus
  kind: AnalysisKind
  goal: string
  created_at: string
  tabs: {
    overview: { interpreted_change: InterpretedChange; counts: Record<string, number> | null; status: string | null; notes: string[] }
    scenarios: { cases: StoredFailure[] | null; boundaries: Record<string, unknown>[] | null; mode: string | null }
    failures: { failures: StoredFailure[] | null }
    counterfactuals: { rows: CounterfactualRow[] | null }
    safeguards: { timings: SafeguardTiming[] | null; note: string | null }
    evidence: { notes: string[] | null; versions: Record<string, unknown> | null; disclaimer: string | null; ai_explanation: AiExplanation | null }
  }
}

/** Allowlisted reverify mitigations with their bounds (mirror of MITIGATION_BOUNDS). */
export const MITIGATION_FIELDS = [
  { key: 'shutdown_delay_s', label: 'Shutdown delay', unit: 's', min: 0, max: 120, step: 1 },
  { key: 'cooling_capacity_pct', label: 'Cooling capacity', unit: '%', min: 0, max: 150, step: 1 },
  { key: 'operating_target_pct', label: 'Operating target', unit: '%', min: 0, max: 100, step: 1 },
  { key: 'feed_factor', label: 'Feed factor', unit: '×', min: 0, max: 2, step: 0.05 },
  { key: 'outlet_factor', label: 'Outlet factor', unit: '×', min: 0, max: 2, step: 0.05 },
  { key: 'cooling_factor', label: 'Cooling factor', unit: '×', min: 0, max: 1.5, step: 0.05 },
] as const
