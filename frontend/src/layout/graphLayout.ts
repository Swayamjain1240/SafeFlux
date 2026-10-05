/**
 * Process-graph orientation (Part 6).
 *
 * The locked process is a five-stage line plus three reactor utilities. Drawn
 * horizontally it is wide and short; drawn vertically it is narrow and tall.
 * A container only ever fits one of those well, and React Flow will happily
 * shrink the other past legibility, so the choice is made here — pure, so it
 * can be unit-tested at every brief target size.
 *
 * Everything is in React Flow units (the same units as node positions and the
 * `w-40` card class in `ProcessGraph.tsx`, i.e. a 160px card).
 *
 *     npm --prefix frontend run test:unit
 */

export type GraphOrientation = 'horizontal' | 'vertical'

/** Card width — must stay in sync with the `w-40` class in `ProcessGraph.tsx`. */
export const NODE_WIDTH = 160

/** React Flow footprints of the two layouts, including the utility column/row. */
export const GRAPH_BOUNDS: Record<GraphOrientation, { width: number; height: number }> = {
  // feed -> pump -> reactor -> valve -> product, utilities above/below.
  horizontal: { width: 4 * 200 + NODE_WIDTH, height: 376 },
  // the same line stacked, utilities to the right.
  vertical: { width: 260 + NODE_WIDTH, height: 4 * 180 + 76 },
}

/**
 * Below this scale the 12px node labels round to something unreadable, so the
 * line is rotated instead of shrunk. Chosen so the conventional horizontal
 * P&ID is kept wherever it can still be read (1920×1080, and the wide half of a
 * 1366 laptop at high zoom) and rotated only when it genuinely cannot fit.
 */
const MIN_HORIZONTAL_SCALE = 0.62

/** Scale the graph would be rendered at if laid out horizontally. */
export function horizontalFitScale(width: number, height: number): number {
  return Math.min(width / GRAPH_BOUNDS.horizontal.width, height / GRAPH_BOUNDS.horizontal.height)
}

export function chooseGraphOrientation(width: number, height: number): GraphOrientation {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
    return 'horizontal'
  }
  return horizontalFitScale(width, height) >= MIN_HORIZONTAL_SCALE ? 'horizontal' : 'vertical'
}
