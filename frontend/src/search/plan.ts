/**
 * Search planning helpers (Part 7) — pure, dependency-free and unit-tested.
 *
 * The browser never invents a search the server would reject: the draft is
 * validated against the *server's* limits (GET /searches/capabilities) before
 * the Run button is enabled, and the request builder can only tighten a budget,
 * never loosen one. Nothing here is a safety verdict: the simulator and the
 * safety engine on the backend decide every number shown.
 */

import type { Tone } from '../dashboard/viewState'
import type {
  BoundaryCandidate,
  SearchCounts,
  SearchFailure,
  SearchLimits,
  SearchMode,
  SearchRunInput,
  SearchTraceEntry,
  SearchVariable,
} from '../types/search'

// One definition of a tone for the whole UI (StatusBadge consumes the same one).
export type { Tone }

/** Hard client-side mirror of the engine ceilings (Backend/app/search/constants.py). */
export const MAX_SWEEP_STEPS = 25
export const MAX_MULTI_STEPS = 7
export const MAX_COMBINATION_AXES = 2
export const MAX_REFINEMENT_DEPTH_CEILING = 12
export const DEFAULT_TIMEOUT_INPUT = 60

export const MODES: readonly SearchMode[] = ['sweep', 'sensitivity', 'combinations']

export const MODE_LABELS: Record<SearchMode, string> = {
  sweep: 'Sweep one variable',
  sensitivity: 'Sensitivity',
  combinations: 'Two-variable grid',
}

export const MODE_HINTS: Record<SearchMode, string> = {
  sweep: 'Coarse sweep, then a bounded refinement of the first safe/unsafe boundary.',
  sensitivity: 'Perturbs every allowlisted variable one at a time and ranks its influence.',
  combinations: 'A bounded grid over two variables, limited by the configured combination budget.',
}

export interface AxisDraft {
  variable: SearchVariable
  steps: number
}

export interface SearchPreset {
  id: string
  label: string
  hint: string
  mode: SearchMode
  axes: AxisDraft[]
  refine: boolean
}

/**
 * Named starting points. They pre-fill a *plan*; they never encode a verdict,
 * so a preset that finds nothing is an ordinary, honest result.
 */
export const SEARCH_PRESETS: readonly SearchPreset[] = [
  {
    id: 'cooling_degradation',
    label: 'Cooling degradation',
    hint: 'Sweeps retained cooling from full to none — the classic thermal runaway bracket.',
    mode: 'sweep',
    axes: [{ variable: 'cooling_factor', steps: 9 }],
    refine: true,
  },
  {
    id: 'feed_increase',
    label: 'Feed increase',
    hint: 'Sweeps feed flow up to 5× to look for a thermal or level boundary.',
    mode: 'sweep',
    axes: [{ variable: 'feed_factor', steps: 9 }],
    refine: true,
  },
  {
    id: 'outlet_restriction',
    label: 'Outlet restriction',
    hint: 'Sweeps outlet capacity from full to blocked to look for a level/volume boundary.',
    mode: 'sweep',
    axes: [{ variable: 'outlet_factor', steps: 9 }],
    refine: true,
  },
  {
    id: 'valve_stuck',
    label: 'Valve stuck',
    hint: 'Holds the outlet valve at a fixed position across the range.',
    mode: 'sweep',
    axes: [{ variable: 'valve_target_pct', steps: 9 }],
    refine: true,
  },
  {
    id: 'pump_variation',
    label: 'Pump variation',
    hint: 'Sweeps pump output from stopped to 2× (a multiplicative fault, not a trip).',
    mode: 'sweep',
    axes: [{ variable: 'pump_factor', steps: 9 }],
    refine: true,
  },
  {
    id: 'shutdown_delay',
    label: 'Shutdown delay',
    hint: 'Sweeps the safeguard delay from immediate to 600 s — a safeguard property, not a process fault.',
    mode: 'sweep',
    axes: [{ variable: 'shutdown_delay_s', steps: 9 }],
    refine: true,
  },
  {
    id: 'sensor_bias',
    label: 'Temperature sensor bias',
    hint: 'Observation only: a sensor changes what the plant reports, never the true trajectory.',
    mode: 'sweep',
    axes: [{ variable: 'temperature_sensor_bias_c', steps: 9 }],
    refine: false,
  },
  {
    id: 'cooling_feed',
    label: 'Cooling × feed',
    hint: 'Two-variable grid: feed increase against lost cooling, bounded by the combination budget.',
    mode: 'combinations',
    axes: [
      { variable: 'cooling_factor', steps: 3 },
      { variable: 'feed_factor', steps: 3 },
    ],
    refine: false,
  },
  {
    id: 'rank_variables',
    label: 'Rank every variable',
    hint: 'Runs the one-at-a-time sensitivity pass to decide what deserves a deeper search.',
    mode: 'sensitivity',
    axes: [],
    refine: false,
  },
]

/** Presets whose variables the server actually allowlists (never assume). */
export function availablePresets(allowlisted: readonly string[]): SearchPreset[] {
  const names = new Set(allowlisted)
  return SEARCH_PRESETS.filter((preset) => preset.axes.every((axis) => names.has(axis.variable)))
}

export function axisCount(mode: SearchMode, axes: readonly AxisDraft[]): { min: number; max: number; ok: boolean } {
  const min = mode === 'sweep' ? 1 : mode === 'combinations' ? 1 : 0
  const max = mode === 'sweep' ? 1 : mode === 'combinations' ? MAX_COMBINATION_AXES : 0
  const count = axes.length
  // A sensitivity pass takes no axes, so a leftover axis is a mismatched draft
  // that the server would reject -- report it rather than quietly ignoring it.
  return { min, max, ok: count >= min && count <= max }
}

export function defaultSteps(mode: SearchMode, steps?: number): number {
  const ceiling = mode === 'combinations' ? MAX_MULTI_STEPS : MAX_SWEEP_STEPS
  const fallback = mode === 'combinations' ? 3 : 9
  const value = Math.floor(steps ?? fallback)
  return Math.min(Math.max(value, 2), ceiling)
}

export function gridSize(axes: readonly AxisDraft[]): number {
  return axes.reduce((total, axis) => total * (axis.steps || 1), 1)
}

/** How many simulations the plan will ask for, before any refinement. */
export function plannedScenarios(mode: SearchMode, axes: readonly AxisDraft[]): number {
  if (mode === 'sensitivity') return 0 // ranked by the server from the allowlist
  if (mode === 'combinations') return gridSize(axes)
  return axes.length === 1 ? defaultSteps('sweep', axes[0].steps) : 0
}

/** Numeric input parsing: junk or a cleared field becomes the fallback, never NaN. */
export function parseNumberInput(raw: string, fallback: number): number {
  if (raw.trim() === '') return fallback
  const value = Number(raw)
  return Number.isFinite(value) ? value : fallback
}

/** Optional numeric input: an empty or unusable field means "use the server default". */
export function parseOptionalNumberInput(raw: string): number | null {
  if (raw.trim() === '') return null
  const value = Number(raw)
  return Number.isFinite(value) ? value : null
}

export interface SearchDraft {
  plantId: string | null
  mode: SearchMode
  axes: AxisDraft[]
  durationS: number
  timeStepS: number
  label: string
  refine: boolean
  refinementDepth: number | null
  nearLimitFraction: number | null
  maxScenarios: number | null
  timeoutS: number | null
}

export function defaultDraft(preset?: SearchPreset): SearchDraft {
  return {
    plantId: null,
    mode: preset?.mode ?? 'sweep',
    axes: preset ? preset.axes.map((axis) => ({ ...axis })) : [{ variable: 'cooling_factor', steps: 9 }],
    durationS: 300,
    timeStepS: 1,
    label: 'search',
    refine: preset?.refine ?? true,
    refinementDepth: null,
    nearLimitFraction: null,
    maxScenarios: null,
    timeoutS: null,
  }
}

/**
 * Everything the server would reject, computed *before* submitting so the UI can
 * explain why Run is disabled. Mirrors Backend/app/schemas/search.py and
 * SearchLimits.validation_errors; the server remains the authority.
 */
export function draftIssues(draft: SearchDraft, limits: SearchLimits): string[] {
  const issues: string[] = []
  if (!draft.plantId) issues.push('Select a plant to search.')
  const shape = axisCount(draft.mode, draft.axes)
  if (!shape.ok) {
    issues.push(
      draft.mode === 'sweep'
        ? 'A sweep takes exactly one variable.'
        : `This mode takes ${shape.min}–${shape.max} variables.`,
    )
  }
  if (draft.mode !== 'sensitivity') {
    const seen = new Set<string>()
    for (const axis of draft.axes) {
      if (seen.has(axis.variable)) issues.push('Each axis must name a different variable.')
      seen.add(axis.variable)
    }
  }
  if (!(draft.durationS > 0)) issues.push('Duration must be greater than zero.')
  else if (draft.durationS > limits.max_duration_s) issues.push('Duration exceeds the maximum allowed.')
  if (!(draft.timeStepS > 0)) issues.push('Time step must be greater than zero.')
  else if (draft.timeStepS < limits.min_time_step_s) issues.push('Time step is below the minimum allowed.')
  if (draft.refine && draft.mode === 'sweep' && (draft.refinementDepth ?? 0) > limits.max_refinement_depth) {
    issues.push('Refinement depth exceeds the configured maximum.')
  }
  if (draft.mode === 'combinations' && gridSize(draft.axes) > limits.max_combinations) {
    issues.push('The grid is larger than the configured combination budget.')
  }
  const planned = plannedScenarios(draft.mode, draft.axes)
  if (draft.maxScenarios !== null) {
    if (draft.maxScenarios > limits.max_scenarios) issues.push('Scenario budget exceeds the configured maximum.')
    else if (planned > draft.maxScenarios) issues.push('The plan needs more scenarios than the budget allows.')
  } else if (planned > limits.max_scenarios) {
    issues.push('The plan needs more scenarios than the configured budget.')
  }
  if (draft.timeoutS !== null && draft.timeoutS > limits.timeout_s) {
    issues.push('Timeout exceeds the configured maximum.')
  }
  return issues
}

/** Server-ready payload. Omitted fields keep the server's own defaults. */
export function buildSearchRequest(draft: SearchDraft): SearchRunInput {
  const request: SearchRunInput = {
    plant_id: draft.plantId ?? '',
    mode: draft.mode,
    plan: {
      duration_s: draft.durationS,
      time_step_s: draft.timeStepS,
      label: draft.label.trim() || 'search',
    },
    axes: draft.mode === 'sensitivity' ? [] : draft.axes.map((axis) => ({ variable: axis.variable, steps: defaultSteps(draft.mode, axis.steps) })),
    refine: draft.mode === 'sweep' ? draft.refine : false,
  }
  if (draft.refinementDepth !== null) request.refinement_depth = draft.refinementDepth
  if (draft.nearLimitFraction !== null) request.near_limit_fraction = draft.nearLimitFraction
  if (draft.maxScenarios !== null) request.max_scenarios = draft.maxScenarios
  if (draft.timeoutS !== null) request.timeout_s = draft.timeoutS
  return request
}

// ---------------------------------------------------------------------------
// Result presentation helpers (pure)
// ---------------------------------------------------------------------------

export function statusTone(status: string): Tone {
  switch (status) {
    case 'safe':
      return 'ok'
    case 'near_limit':
      return 'warn'
    case 'safeguard_activated':
      return 'warn'
    case 'violation':
      return 'crit'
    default:
      return 'idle'
  }
}

export function runTone(status: string): Tone {
  if (status === 'complete') return 'ok'
  if (status === 'truncated') return 'warn'
  return 'idle'
}

export interface CountTile {
  key: string
  label: string
  value: number
  tone: Tone
  hint: string
}

/** The four required counts first, then the evidence-bearing extras. */
export function countTiles(counts: SearchCounts): CountTile[] {
  const value = (key: keyof SearchCounts) => counts[key] ?? 0
  return [
    { key: 'scenarios', label: 'Scenarios', value: value('scenarios'), tone: 'idle', hint: 'Distinct cases evaluated' },
    { key: 'safe', label: 'Safe', value: value('safe'), tone: 'ok', hint: 'Stayed inside every limit' },
    { key: 'near_limit', label: 'Near limit', value: value('near_limit'), tone: 'warn', hint: 'Approached a configured limit' },
    { key: 'violation', label: 'Violation', value: value('violation'), tone: 'crit', hint: 'Crossed a configured limit' },
    {
      key: 'safeguard_activated',
      label: 'Safeguard',
      value: value('safeguard_activated'),
      tone: 'warn',
      hint: 'A trip ended the scenario',
    },
    {
      key: 'boundary_candidates',
      label: 'Boundaries',
      value: value('boundary_candidates'),
      tone: 'idle',
      hint: 'Safe/unsafe edges found',
    },
  ]
}

export function formatNumber(value: number | null | undefined, digits = 4): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return '—'
  return Number(value.toFixed(digits)).toString()
}

export function describeBoundary(boundary: BoundaryCandidate): string {
  const edges =
    boundary.last_safe === null || boundary.first_unsafe === null
      ? 'no safe/unsafe edge inside the tested range'
      : `last safe ${formatNumber(boundary.last_safe)}, first unsafe ${formatNumber(boundary.first_unsafe)}`
  const method = boundary.refined ? `refined by ${boundary.method}` : 'coarse resolution'
  const tolerance = boundary.uncertainty === null ? '' : ` · ±${formatNumber(boundary.uncertainty)}`
  return `${edges} · ${method} · ${boundary.monotonicity}${tolerance}`
}

const VALUE_KEYS = ['cooling_factor', 'feed_factor', 'outlet_factor', 'valve_target_pct', 'pump_factor', 'shutdown_delay_s', 'temperature_sensor_bias_c']

export function describeValues(values: Record<string, number>): string {
  const names = Object.keys(values).sort((left, right) => {
    const leftIndex = VALUE_KEYS.indexOf(left)
    const rightIndex = VALUE_KEYS.indexOf(right)
    return (leftIndex < 0 ? VALUE_KEYS.length : leftIndex) - (rightIndex < 0 ? VALUE_KEYS.length : rightIndex)
  })
  return names.map((name) => `${name}=${formatNumber(values[name], 6)}`).join(', ')
}

export function describeTrace(entry: SearchTraceEntry): string {
  const detail = entry.detail ?? {}
  const phase = typeof detail.phase === 'string' ? detail.phase : entry.kind
  const parts: string[] = [phase]
  if (typeof detail.variable === 'string') parts.push(String(detail.variable))
  if (typeof detail.value === 'number') parts.push(formatNumber(detail.value, 6))
  if (detail.values && typeof detail.values === 'object') {
    const values = detail.values as Record<string, number>
    parts.push(describeValues(values))
  }
  if (typeof detail.status === 'string') parts.push(String(detail.status))
  if (typeof detail.method === 'string') parts.push(String(detail.method))
  if (typeof detail.reason === 'string') parts.push(`stopped: ${detail.reason}`)
  if (detail.cached === true) parts.push('cached')
  return parts.join(' · ')
}

export interface FailureFilter {
  status: 'all' | 'near_limit' | 'safeguard_activated' | 'violation'
  variable: 'all' | string
  query: string
}

export function defaultFailureFilter(): FailureFilter {
  return { status: 'all', variable: 'all', query: '' }
}

export function filterFailures(
  failures: readonly SearchFailure[],
  filter: FailureFilter,
): SearchFailure[] {
  const needle = filter.query.trim().toLowerCase()
  return failures.filter((failure) => {
    if (filter.status !== 'all' && failure.status !== filter.status) return false
    if (filter.variable !== 'all' && !(filter.variable in failure.values)) return false
    if (!needle) return true
    const haystack = [
      failure.label,
      failure.key,
      failure.worst_finding?.message ?? '',
      describeValues(failure.values),
    ]
      .join(' ')
      .toLowerCase()
    return haystack.includes(needle)
  })
}

export interface Page<T> {
  items: T[]
  page: number
  pageCount: number
  total: number
}

/** Clamped pagination: an out-of-range page never renders an empty view. */
export function paginate<T>(items: readonly T[], page: number, pageSize: number): Page<T> {
  const size = Math.max(1, Math.floor(pageSize))
  const total = items.length
  const pageCount = Math.max(1, Math.ceil(total / size))
  const requested = Number.isFinite(page) ? Math.floor(page) : 1
  const current = Math.min(Math.max(requested, 1), pageCount)
  const start = (current - 1) * size
  return { items: items.slice(start, start + size), page: current, pageCount, total }
}

export function peakSummary(failure: SearchFailure): string {
  const temperature = failure.peaks?.temperature_c
  const pressure = failure.peaks?.pressure_bar
  const level = failure.peaks?.level_pct
  const parts = [
    temperature === null || temperature === undefined ? null : `T ${formatNumber(temperature, 2)} °C`,
    pressure === null || pressure === undefined ? null : `P ${formatNumber(pressure, 3)} bar`,
    level === null || level === undefined ? null : `L ${formatNumber(level, 2)} %`,
  ].filter((part): part is string => part !== null)
  return parts.join(' · ') || 'no peaks recorded'
}
