/**
 * Search planning tests (Part 7) — the pure half of the search workspace.
 *
 * The browser must never build a request the server would reject, and it must
 * never present a number the backend did not produce. These tests pin the
 * client-side mirror of the server's bounds, the preset allowlist filter, the
 * pagination/filtering behaviour and the value formatting.
 *
 *     npm --prefix frontend run test:unit
 */

import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  MAX_MULTI_STEPS,
  MAX_SWEEP_STEPS,
  availablePresets,
  axisCount,
  buildSearchRequest,
  countTiles,
  defaultDraft,
  defaultSteps,
  describeBoundary,
  describeTrace,
  describeValues,
  draftIssues,
  filterFailures,
  formatNumber,
  gridSize,
  paginate,
  parseNumberInput,
  parseOptionalNumberInput,
  plannedScenarios,
  runTone,
  statusTone,
} from '../src/search/plan.ts'

import type { SearchLimits, SearchFailure } from '../src/types/search.ts'

const LIMITS: SearchLimits = {
  max_scenarios: 150,
  max_combinations: 36,
  max_refinement_depth: 6,
  timeout_s: 90,
  max_duration_s: 3600,
  min_time_step_s: 0.05,
  max_samples: 20000,
}

function failure(overrides: Partial<SearchFailure> = {}): SearchFailure {
  return {
    key: 'cooling_factor=0.0',
    label: 'sweep',
    values: { cooling_factor: 0 },
    status: 'violation',
    rank: 3,
    observation_only: false,
    peaks: { temperature_c: 180.4, pressure_bar: 6.2, level_pct: 45 },
    limit_exceeded: { temperature_c: true },
    shutdown_at_s: null,
    worst_finding: {
      type: 'temperature_c',
      status: 'violation',
      severity: 'critical',
      timestamp_s: 120,
      measured_value: 180.4,
      limit: 150,
      near_limit: 135,
      scenario_id: 'sweep',
      message: 'peak 180.4 degC vs limit 150.0 degC',
    },
    findings: [],
    cached: false,
    ...overrides,
  }
}

test('the allowlist mirror matches the server ceilings', () => {
  assert.equal(MAX_SWEEP_STEPS, 25)
  assert.equal(MAX_MULTI_STEPS, 7)
  assert.equal(defaultSteps('sweep', 100), MAX_SWEEP_STEPS)
  assert.equal(defaultSteps('combinations', 100), MAX_MULTI_STEPS)
  assert.equal(defaultSteps('sweep', 1), 2)
})

test('axis count is enforced per mode before the request leaves the browser', () => {
  const sweep = axisCount('sweep', [{ variable: 'cooling_factor', steps: 9 }])
  assert.deepEqual(sweep, { min: 1, max: 1, ok: true })
  assert.equal(axisCount('sweep', []).ok, false)
  assert.equal(
    axisCount('sweep', [
      { variable: 'cooling_factor', steps: 9 },
      { variable: 'feed_factor', steps: 9 },
    ]).ok,
    false,
  )
  assert.equal(axisCount('sensitivity', []).ok, true)
  assert.equal(axisCount('sensitivity', [{ variable: 'cooling_factor', steps: 9 }]).ok, false)
  assert.equal(axisCount('combinations', [{ variable: 'cooling_factor', steps: 3 }]).ok, true)
})

test('presets are filtered by what the server actually allowlists', () => {
  const all = availablePresets([
    'cooling_factor',
    'feed_factor',
    'outlet_factor',
    'valve_target_pct',
    'pump_factor',
    'shutdown_delay_s',
    'temperature_sensor_bias_c',
  ])
  assert.ok(all.length >= 8)
  const ids = all.map((preset) => preset.id)
  assert.ok(ids.includes('cooling_degradation'))
  assert.ok(ids.includes('rank_variables'))

  // A preset whose variables are not allowlisted must never be offered.
  const limited = availablePresets(['cooling_factor'])
  const limitedIds = limited.map((preset) => preset.id)
  assert.ok(limitedIds.includes('cooling_degradation'))
  assert.ok(!limitedIds.includes('feed_increase'))
  assert.ok(!limitedIds.includes('cooling_feed'))
  // Sensitivity needs no variable, so it stays available.
  assert.ok(limitedIds.includes('rank_variables'))
})

test('a valid draft produces a server-shaped request and nothing extra', () => {
  const draft = { ...defaultDraft(), plantId: 'plant-1', label: '  cooling sweep  ' }
  const request = buildSearchRequest(draft)

  assert.equal(request.plant_id, 'plant-1')
  assert.equal(request.mode, 'sweep')
  assert.deepEqual(request.axes, [{ variable: 'cooling_factor', steps: 9 }])
  assert.equal(request.plan.label, 'cooling sweep')
  assert.equal(request.refine, true)
  // Untouched optional budgets stay absent so the server's defaults apply.
  assert.equal('max_scenarios' in request, false)
  assert.equal('timeout_s' in request, false)
  assert.equal('near_limit_fraction' in request, false)
})

test('optional budgets are forwarded exactly as typed (the server enforces them)', () => {
  const draft = {
    ...defaultDraft(),
    plantId: 'plant-1',
    maxScenarios: 24,
    timeoutS: 30,
    refinementDepth: 2,
    nearLimitFraction: 0.8,
  }
  const request = buildSearchRequest(draft)
  assert.equal(request.max_scenarios, 24)
  assert.equal(request.timeout_s, 30)
  assert.equal(request.refinement_depth, 2)
  assert.equal(request.near_limit_fraction, 0.8)
})

test('sensitivity sends no axes even if a draft still carries some', () => {
  const draft = {
    ...defaultDraft(),
    plantId: 'plant-1',
    mode: 'sensitivity' as const,
    axes: [{ variable: 'cooling_factor' as const, steps: 9 }],
  }
  const request = buildSearchRequest(draft)
  assert.deepEqual(request.axes, [])
  assert.equal(request.refine, false)
})

test('draft issues mirror the server rejections and clear when the plan is sound', () => {
  const base = { ...defaultDraft(), plantId: 'plant-1' }
  assert.deepEqual(draftIssues(base, LIMITS), [])

  assert.deepEqual(draftIssues({ ...base, plantId: null }, LIMITS), ['Select a plant to search.'])
  assert.ok(draftIssues({ ...base, durationS: 0 }, LIMITS).length > 0)
  assert.ok(draftIssues({ ...base, timeStepS: 0.001 }, LIMITS).length > 0)
  assert.ok(draftIssues({ ...base, axes: [] }, LIMITS).some((issue) => issue.includes('one variable')))
  assert.ok(
    draftIssues(
      { ...base, mode: 'combinations', axes: [{ variable: 'cooling_factor', steps: 7 }, { variable: 'feed_factor', steps: 7 }] },
      LIMITS,
    ).some((issue) => issue.includes('combination budget')),
  )
  assert.ok(draftIssues({ ...base, maxScenarios: 5 }, LIMITS).some((issue) => issue.includes('more scenarios')))
  assert.ok(draftIssues({ ...base, maxScenarios: 5000 }, LIMITS).some((issue) => issue.includes('configured maximum')))
  assert.ok(draftIssues({ ...base, timeoutS: 500 }, LIMITS).some((issue) => issue.includes('Timeout')))
  assert.ok(
    draftIssues({ ...base, refine: true, refinementDepth: 9 }, LIMITS).some((issue) => issue.includes('Refinement depth')),
  )
})

test('planned scenario counts follow each mode without inventing work', () => {
  assert.equal(plannedScenarios('sweep', [{ variable: 'cooling_factor', steps: 9 }]), 9)
  assert.equal(
    plannedScenarios('combinations', [
      { variable: 'cooling_factor', steps: 3 },
      { variable: 'feed_factor', steps: 4 },
    ]),
    12,
  )
  assert.equal(gridSize([]), 1)
  assert.equal(plannedScenarios('sensitivity', []), 0)
})

test('numeric input parsing never lets NaN into a payload', () => {
  assert.equal(parseNumberInput('120', 300), 120)
  assert.equal(parseNumberInput('', 300), 300)
  assert.equal(parseNumberInput('abc', 300), 300)
  assert.equal(parseOptionalNumberInput(''), null)
  assert.equal(parseOptionalNumberInput('  '), null)
  assert.equal(parseOptionalNumberInput('0.8'), 0.8)
  assert.equal(parseOptionalNumberInput('nope'), null)
})

test('count tiles lead with the four required counts', () => {
  const tiles = countTiles({
    scenarios: 9,
    safe: 8,
    near_limit: 0,
    violation: 1,
    safeguard_activated: 0,
    failing: 1,
    boundary_candidates: 1,
  })
  assert.deepEqual(
    tiles.map((tile) => tile.key),
    ['scenarios', 'safe', 'near_limit', 'violation', 'safeguard_activated', 'boundary_candidates'],
  )
  assert.equal(tiles.find((tile) => tile.key === 'violation')?.tone, 'crit')
  assert.equal(tiles.find((tile) => tile.key === 'safe')?.tone, 'ok')
})

test('filters narrow failures by status, variable and text', () => {
  const rows = [
    failure(),
    failure({ key: 'feed_factor=3', values: { feed_factor: 3 }, status: 'near_limit', peaks: { temperature_c: 140 } }),
    failure({ key: 'pump_factor=0', values: { pump_factor: 0 }, status: 'safeguard_activated' }),
  ]

  assert.equal(filterFailures(rows, { status: 'all', variable: 'all', query: '' }).length, 3)
  assert.equal(filterFailures(rows, { status: 'violation', variable: 'all', query: '' }).length, 1)
  assert.equal(filterFailures(rows, { status: 'all', variable: 'feed_factor', query: '' }).length, 1)
  // Text matching is case-insensitive and searches the values, not just the label.
  assert.equal(filterFailures(rows, { status: 'all', variable: 'all', query: 'FEED_factor' }).length, 1)
  assert.equal(filterFailures(rows, { status: 'all', variable: 'all', query: 'cooling' }).length, 1)
  assert.equal(filterFailures(rows, { status: 'all', variable: 'all', query: 'nothing here' }).length, 0)
})

test('pagination clamps instead of showing an empty page', () => {
  const items = Array.from({ length: 20 }, (_, index) => index)
  const first = paginate(items, 1, 8)
  assert.deepEqual(first.items, [0, 1, 2, 3, 4, 5, 6, 7])
  assert.equal(first.pageCount, 3)
  assert.equal(first.total, 20)

  const last = paginate(items, 3, 8)
  assert.deepEqual(last.items, [16, 17, 18, 19])
  assert.equal(paginate(items, 99, 8).page, 3)
  assert.equal(paginate(items, 0, 8).page, 1)
  assert.equal(paginate(items, Number.NaN, 8).page, 1)
  const empty = paginate([], 4, 8)
  assert.equal(empty.pageCount, 1)
  assert.equal(empty.page, 1)
  assert.deepEqual(empty.items, [])
})

test('status and run tones map to the shared badge colours', () => {
  assert.equal(statusTone('safe'), 'ok')
  assert.equal(statusTone('near_limit'), 'warn')
  assert.equal(statusTone('safeguard_activated'), 'warn')
  assert.equal(statusTone('violation'), 'crit')
  assert.equal(statusTone('unknown'), 'idle')
  assert.equal(runTone('complete'), 'ok')
  assert.equal(runTone('truncated'), 'warn')
})

test('values, boundaries and trace entries format without inventing precision', () => {
  assert.equal(describeValues({ feed_factor: 3, cooling_factor: 0.09375 }), 'cooling_factor=0.09375, feed_factor=3')
  assert.equal(formatNumber(null), '—')
  assert.equal(formatNumber(Number.NaN), '—')
  assert.equal(formatNumber(0.09375, 4), '0.0938')

  const boundary = describeBoundary({
    variable: 'cooling_factor',
    last_safe: 0.095703,
    first_unsafe: 0.09375,
    boundary_estimate: 0.094726,
    uncertainty: 0.001953,
    monotonicity: 'decreasing',
    method: 'bisection',
    refined: true,
    evaluations: 6,
  })
  assert.match(boundary, /last safe 0\.0957/)
  assert.match(boundary, /first unsafe 0\.0938/)
  assert.match(boundary, /refined by bisection/)
  assert.match(boundary, /decreasing/)

  const coarse = describeBoundary({
    variable: 'feed_factor',
    last_safe: null,
    first_unsafe: null,
    boundary_estimate: null,
    uncertainty: 0,
    monotonicity: 'insufficient',
    method: 'none',
    refined: false,
    evaluations: 0,
  })
  assert.match(coarse, /no safe\/unsafe edge/)

  assert.match(
    describeTrace({ kind: 'sweep', detail: { phase: 'sweep', variable: 'cooling_factor', value: 0, status: 'violation' } }),
    /sweep · cooling_factor · 0 · violation/,
  )
  assert.match(
    describeTrace({
      kind: 'refine',
      detail: { phase: 'refine', method: 'bisection', variable: 'cooling_factor', value: 0.09375, status: 'violation', cached: true },
    }),
    /bisection/,
  )
  assert.match(
    describeTrace({ kind: 'stop', detail: { reason: 'scenarios', phase: 'refine' } }),
    /stopped: scenarios/,
  )
})
