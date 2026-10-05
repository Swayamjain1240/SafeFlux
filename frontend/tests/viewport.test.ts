/**
 * Viewport classification tests (Part 6) — the one-viewport rule needs both
 * width and height: a 1366×768 laptop is wide but short, so it must use the
 * compact layout rather than the full desktop one.
 *
 *     npm --prefix frontend run test:unit
 */

import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  classifyViewport,
  isCompact,
  metricColumns,
  usesWideLayout,
  visiblePanels,
} from '../src/layout/viewport.ts'

test('brief target viewports classify as expected', () => {
  assert.equal(classifyViewport(1920, 1080), 'desktop')
  assert.equal(classifyViewport(1366, 768), 'laptop')
  assert.equal(classifyViewport(1024, 768), 'tablet')
  assert.equal(classifyViewport(390, 844), 'mobile')
})

test('height alone can downgrade a wide window to compact cards', () => {
  assert.equal(classifyViewport(1600, 700), 'laptop')
  assert.equal(classifyViewport(2560, 600), 'laptop')
  // Width still allows two columns; only the cards get compact.
  assert.equal(usesWideLayout(classifyViewport(1600, 700)), true)
  assert.equal(isCompact(classifyViewport(1600, 700)), true)
})

test('desktop and laptop share the two-column wide layout', () => {
  assert.equal(usesWideLayout('desktop'), true)
  assert.equal(usesWideLayout('laptop'), true)
  assert.equal(usesWideLayout('tablet'), false)
  assert.equal(usesWideLayout('mobile'), false)
})

test('wide layouts show every dashboard panel at once', () => {
  for (const viewport of ['desktop', 'laptop'] as const) {
    const panels = visiblePanels(viewport, 'process')
    assert.deepEqual(panels, { process: true, overview: true, findings: true })
  }
})

test('tablet and mobile show exactly one primary panel', () => {
  for (const viewport of ['tablet', 'mobile'] as const) {
    assert.deepEqual(visiblePanels(viewport, 'overview'), { process: false, overview: true, findings: false })
    assert.deepEqual(visiblePanels(viewport, 'process'), { process: true, overview: false, findings: false })
    assert.deepEqual(visiblePanels(viewport, 'findings'), { process: false, overview: false, findings: true })
  }
})

test('metric columns shrink as space tightens', () => {
  assert.equal(metricColumns('desktop'), 4)
  assert.equal(metricColumns('laptop'), 3)
  assert.equal(metricColumns('tablet'), 3)
  assert.equal(metricColumns('mobile'), 2)
})

test('short and narrow viewports use compact cards', () => {
  assert.equal(isCompact('laptop'), true)
  assert.equal(isCompact('mobile'), true)
  assert.equal(isCompact('desktop'), false)
  assert.equal(isCompact('tablet'), false)
})

test('degenerate measurements fall back to mobile rather than breaking', () => {
  assert.equal(classifyViewport(0, 0), 'mobile')
  assert.equal(classifyViewport(Number.NaN, 800), 'mobile')
  assert.equal(classifyViewport(767, 1200), 'mobile')
  assert.equal(classifyViewport(768, 1200), 'tablet')
})
