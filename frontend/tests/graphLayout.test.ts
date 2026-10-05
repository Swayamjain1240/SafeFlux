/**
 * Process-graph orientation tests (Part 6).
 *
 * The one-viewport rule needs the P&ID to stay readable, not merely present:
 * when a container cannot show the wide horizontal line at a legible scale it
 * must be rotated rather than shrunk. The cases below are the brief's target
 * sizes plus the odd shapes a resizable desktop window actually produces.
 *
 *     npm --prefix frontend run test:unit
 */

import assert from 'node:assert/strict'
import { test } from 'node:test'

import {
  chooseGraphOrientation,
  GRAPH_BOUNDS,
  horizontalFitScale,
} from '../src/layout/graphLayout.ts'

test('the wide desktop column keeps the conventional horizontal line', () => {
  // Half of a 1920 dashboard workspace, comfortably tall.
  assert.equal(chooseGraphOrientation(930, 880), 'horizontal')
  assert.equal(chooseGraphOrientation(930, 568), 'horizontal')
})

test('narrow or short containers rotate the line instead of shrinking it', () => {
  // 1366×768 wide column: horizontal would render at ~0.56, below legibility.
  assert.equal(chooseGraphOrientation(586, 568), 'vertical')
  // Tablet and mobile process tabs are tall and narrow.
  assert.equal(chooseGraphOrientation(510, 717), 'vertical')
  assert.equal(chooseGraphOrientation(358, 700), 'vertical')
})

test('a rotated line really does render larger than a squashed one', () => {
  const verticalFit = (w: number, h: number) =>
    Math.min(w / GRAPH_BOUNDS.vertical.width, h / GRAPH_BOUNDS.vertical.height)
  for (const [w, h] of [
    [586, 568],
    [510, 717],
    [358, 700],
  ] as const) {
    assert.ok(
      verticalFit(w, h) > horizontalFitScale(w, h),
      `expected vertical to fit better at ${w}×${h} (${verticalFit(w, h)} vs ${horizontalFitScale(w, h)})`,
    )
  }
})

test('horizontal is only chosen while it stays above the legibility floor', () => {
  // Any container the chooser renders horizontally must clear the floor the
  // threshold promises; containers below it must not be rendered horizontally.
  const floor = 0.62
  for (const [w, h] of [
    [930, 880],
    [930, 568],
    [586, 568],
    [510, 717],
    [358, 700],
  ] as const) {
    const orientation = chooseGraphOrientation(w, h)
    if (orientation === 'horizontal') {
      assert.ok(
        horizontalFitScale(w, h) >= floor - 0.001,
        `horizontal chosen at an unreadable scale at ${w}×${h}`,
      )
    } else {
      assert.ok(
        horizontalFitScale(w, h) < floor + 0.001,
        `rotated although horizontal was still legible at ${w}×${h}`,
      )
    }
  }
})

test('degenerate measurements fall back to horizontal rather than breaking', () => {
  assert.equal(chooseGraphOrientation(0, 0), 'horizontal')
  assert.equal(chooseGraphOrientation(Number.NaN, 700), 'horizontal')
  assert.equal(chooseGraphOrientation(-10, 700), 'horizontal')
})
