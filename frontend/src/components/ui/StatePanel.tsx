import type { ReactNode } from 'react'

export type StateTone = 'neutral' | 'warn' | 'crit'

const TONE_CLASS: Record<StateTone, string> = {
  neutral: 'border-edge/80 bg-panel/60 text-slate-300',
  warn: 'border-warn/40 bg-warn/5 text-warn',
  crit: 'border-crit/50 bg-crit/10 text-crit',
}

export interface StatePanelAction {
  label: string
  onAct: () => void
}

/**
 * Centred, viewport-safe message for loading / empty / error states (Part 6).
 * It fills the available region instead of overflowing it, so a failed or
 * empty page never triggers page-level scrolling.
 *
 * Visual transformation: shares the instrument surface language — restrained
 * radius, token border, one optional recovery action.
 */
export function StatePanel({
  tone = 'neutral',
  title,
  hint,
  action,
  children,
}: {
  tone?: StateTone
  title: string
  hint?: string
  action?: StatePanelAction
  children?: ReactNode
}) {
  return (
    <div className="flex h-full min-h-0 items-center justify-center px-2">
      <div className={`max-w-md rounded-md border px-5 py-6 text-center ${TONE_CLASS[tone]}`}>
        <p className="text-base font-semibold">{title}</p>
        {hint && <p className="mt-1.5 text-sm opacity-80">{hint}</p>}
        {children}
        {action && (
          <button
            type="button"
            onClick={action.onAct}
            className="mt-4 rounded-md border border-edge-strong px-4 py-2 text-sm text-slate-200 transition hover:bg-surface-2"
          >
            {action.label}
          </button>
        )}
      </div>
    </div>
  )
}
