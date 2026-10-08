/**
 * Route-transition plan tests (visual transformation).
 *
 * Navigation motion must never delay the user and must disappear entirely for
 * reduced-motion users, so the decision is a pure function.
 *
 *     npm --prefix frontend run test:unit
 */

import assert from 'node:assert/strict'
import { test } from 'node:test'

import { ROUTE_TRANSITION_MS, shouldAnimateRoute } from '../src/animation/routeTransitionPlan.ts'

test('a real route change animates briefly', () => {
  assert.equal(shouldAnimateRoute({ reducedMotion: false, firstRender: false, samePath: false }), true)
  assert.ok(ROUTE_TRANSITION_MS <= 500, 'transitions must stay within the 200-500ms budget')
})

test('reduced motion disables the transition completely', () => {
  assert.equal(shouldAnimateRoute({ reducedMotion: true, firstRender: false, samePath: false }), false)
})

test('the first paint and repeated renders never animate', () => {
  assert.equal(shouldAnimateRoute({ reducedMotion: false, firstRender: true, samePath: false }), false)
  assert.equal(shouldAnimateRoute({ reducedMotion: false, firstRender: false, samePath: true }), false)
})
