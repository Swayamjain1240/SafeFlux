/**
 * Safeguards-view regression tests (QA Part 2, BUG-02).
 *
 * The defect: deep-linking to a re-verification record's safeguards page
 * (`/analysis/<reverify-id>/safeguards`) crashed the UI with
 * `Cannot read properties of undefined (reading 'note')`, because a reverify
 * evidence document has no `safeguards` section and the page read through it
 * unguarded. The revertify document shape below is taken from a real stored
 * document (keys: kind, parent_id, mitigations, comparison, rows, verdict,
 * note).
 *
 *     npm --prefix frontend run test:unit
 */

import assert from 'node:assert/strict'
import { test } from 'node:test'

import { safeguardsView } from '../src/analysis/safeguardsView.ts'

const TIMING = {
  safeguard: 'High temperature trip',
  trigger_time_s: 8,
  response_time_s: 10,
  violation_time_s: 9,
  prevented: false,
  note: 'Safeguard response occurred after the simulated violation.',
}

test('a full analysis document yields its safeguard evidence', () => {
  const view = safeguardsView({
    safeguards: { case_key: 'k1', case_label: 'Cooling lost', timings: [TIMING], note: 'Measured in the tested scenario.' },
  })
  assert.equal(view.kind, 'evidence')
  if (view.kind !== 'evidence') return
  assert.equal(view.evidence.note, 'Measured in the tested scenario.')
  assert.equal(view.evidence.caseLabel, 'Cooling lost')
  assert.equal(view.evidence.timings.length, 1)
})

test('a re-verification document is an explicit no-evidence view, never a crash', () => {
  // Exact key set of the stored reverify document that crashed the page.
  const reverifyDocument = {
    kind: 'reverification',
    parent_id: 'an-4bd604d85976',
    mitigations: { feed_factor: 1.0 },
    mitigation_labels: ['Restore feed to nominal'],
    changed: ['feed_factor'],
    comparison: { before: { violations: 9 }, after: { violations: 0 } },
    rows: [{}, {}, {}, {}, {}, {}, {}, {}, {}],
    verdict: 'No unsafe condition was detected within the tested simulation scenarios.',
    note: 'Comparison of the same deterministic critical case before and after.',
  }

  const view = safeguardsView(reverifyDocument)
  assert.equal(view.kind, 'no-evidence')
  if (view.kind !== 'no-evidence') return
  assert.equal(view.parentId, 'an-4bd604d85976')
})

test('a document without a parent still yields a safe fallback', () => {
  const view = safeguardsView({})
  assert.deepEqual(view, { kind: 'no-evidence', parentId: null })
  assert.equal(safeguardsView(null).kind, 'no-evidence')
  assert.equal(safeguardsView(undefined).kind, 'no-evidence')
})

test('null timings and blank labels never leak into the header', () => {
  const view = safeguardsView({
    safeguards: { case_key: 'k1', case_label: '', timings: null, note: null },
  })
  assert.equal(view.kind, 'evidence')
  if (view.kind !== 'evidence') return
  assert.deepEqual(view.evidence.timings, [])
  assert.equal(view.evidence.caseLabel, 'k1')
  assert.equal(view.evidence.note, null)
})
