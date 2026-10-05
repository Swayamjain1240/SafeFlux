/**
 * Viewport classification for the one-viewport rule (Part 6).
 *
 * Pure and dependency-free so the responsive behaviour is unit-testable:
 * given a width/height we decide which panels share the screen and which are
 * switched via tabs. Width *and* height matter — a 1366×768 laptop is wide but
 * short, so it gets the compact (two-column, no wasted rows) layout rather than
 * the full desktop one.
 */

export type ViewportClass = 'mobile' | 'tablet' | 'laptop' | 'desktop'

export type DashboardTab = 'overview' | 'process' | 'findings'

export const DASHBOARD_TABS: readonly DashboardTab[] = ['overview', 'process', 'findings']

/** Wider than a tablet and tall enough for the full two-column workspace. */
const MIN_WIDE_WIDTH = 1200
/** A short window (small laptop / split screen) needs compact cards. */
const MIN_TALL_HEIGHT = 800
/** Below this width the workspace switches to one-panel-at-a-time tabs. */
const MIN_TAB_WIDTH = 768

export function classifyViewport(width: number, height: number): ViewportClass {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0) return 'mobile'
  if (width < MIN_TAB_WIDTH) return 'mobile'
  if (width < MIN_WIDE_WIDTH) return 'tablet'
  if (height < MIN_TALL_HEIGHT) return 'laptop'
  return 'desktop'
}

/** Two columns only where height also allows them. */
export function usesWideLayout(viewport: ViewportClass): boolean {
  return viewport === 'desktop' || viewport === 'laptop'
}

/**
 * Which dashboard panels render now. Wide layouts show everything at once;
 * tablet/mobile show one primary panel so nothing is clipped or hidden behind
 * an unreachable scroll.
 */
export function visiblePanels(
  viewport: ViewportClass,
  activeTab: DashboardTab,
): { process: boolean; overview: boolean; findings: boolean } {
  if (usesWideLayout(viewport)) {
    return { process: true, overview: true, findings: true }
  }
  return {
    process: activeTab === 'process',
    overview: activeTab === 'overview',
    findings: activeTab === 'findings',
  }
}

/** Metric cards per row — fewer columns when space is tight. */
export function metricColumns(viewport: ViewportClass): 2 | 3 | 4 {
  switch (viewport) {
    case 'desktop':
      return 4
    case 'laptop':
      return 3
    case 'tablet':
      return 3
    default:
      return 2
  }
}

/** "Compact" mode drops secondary hints so short screens never clip a card. */
export function isCompact(viewport: ViewportClass): boolean {
  return viewport === 'laptop' || viewport === 'mobile'
}
