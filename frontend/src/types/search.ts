/**
 * Deterministic scenario search types — mirror of the Part 7 backend schemas
 * (Backend/app/schemas/search.py and Backend/app/search/result.py).
 *
 * The variable *names* are declared here only as a fallback for the presets;
 * the UI renders whatever GET /searches/capabilities returns, so a variable
 * cannot become searchable in the browser by accident.
 */

export type SearchVariable =
  | 'cooling_factor'
  | 'feed_factor'
  | 'outlet_factor'
  | 'valve_target_pct'
  | 'pump_factor'
  | 'shutdown_delay_s'
  | 'temperature_sensor_bias_c'

export type SearchMode = 'sweep' | 'sensitivity' | 'combinations'

export type RiskDirection = 'increasing' | 'decreasing' | 'neutral'

export interface SearchVariableSpec {
  variable: SearchVariable
  label: string
  unit: string
  minimum: number
  maximum: number
  default: number
  neutral: number | null
  direction: RiskDirection
  is_safeguard: boolean
  is_observation_only: boolean
}

export interface SearchLimits {
  max_scenarios: number
  max_combinations: number
  max_refinement_depth: number
  timeout_s: number
  max_duration_s: number
  min_time_step_s: number
  max_samples: number
}

export interface SearchVersions {
  search_engine_version: string
  search_method_version: string
  simulator_version: string
  model_name: string
  model_version: string
  safety_engine_version: string
  deterministic: boolean
  ai_involved: boolean
}

export interface SearchCapabilities {
  variables: SearchVariableSpec[]
  modes: SearchMode[]
  limits: SearchLimits
  versions: SearchVersions
}

export interface SearchAxisInput {
  variable: SearchVariable
  steps?: number
  minimum?: number
  maximum?: number
}

export interface SearchPlanInput {
  duration_s: number
  time_step_s: number
  start_s?: number
  label?: string
}

export interface SearchRunInput {
  plant_id: string
  mode: SearchMode
  plan: SearchPlanInput
  axes: SearchAxisInput[]
  refine: boolean
  refinement_depth?: number
  near_limit_fraction?: number
  max_scenarios?: number
  max_combinations?: number
  timeout_s?: number
}

export interface SearchCounts {
  scenarios: number
  safe: number
  near_limit: number
  safeguard_activated: number
  violation: number
  failing: number
  observation_only: number
  evaluations: number
  cache_hits: number
  distinct_cases: number
  boundary_candidates: number
}

export interface SearchFinding {
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

export interface SearchCase {
  key: string
  label: string
  values: Record<string, number>
  status: string
  rank: number
  observation_only: boolean
  peaks: Record<string, number | null>
  limit_exceeded: Record<string, boolean>
  shutdown_at_s: number | null
  worst_finding: SearchFinding | null
  findings: SearchFinding[]
  cached: boolean
}

export type SearchFailure = SearchCase

export interface BoundaryCandidate {
  variable: string
  last_safe: number | null
  first_unsafe: number | null
  boundary_estimate: number | null
  uncertainty: number | null
  monotonicity: string
  method: string
  refined: boolean
  evaluations: number
}

export interface SensitivityRow {
  variable: string
  baseline_value: number | null
  baseline_status: string
  low_value: number
  low_status: string
  high_value: number
  high_status: string
  worst_delta: number
  influence: string
  note: string
}

export interface SearchTraceEntry {
  kind: string
  detail: Record<string, unknown>
}

export interface SearchBudgetUsage {
  scenarios_used: number
  max_scenarios: number
  scenarios_remaining: number
  timeout_s: number
  elapsed_s: number
  exceeded: string | null
}

export interface SearchResult {
  plant: Record<string, unknown>
  mode: string
  status: string
  truncated: boolean
  counts: SearchCounts
  cases: SearchCase[]
  failures: SearchFailure[]
  boundaries: BoundaryCandidate[]
  sensitivity: SensitivityRow[]
  trace: SearchTraceEntry[]
  budget: SearchBudgetUsage
  config: Record<string, unknown>
  notes: string[]
}
