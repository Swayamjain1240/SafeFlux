import type { ReactNode } from 'react'

export type StateTone = 'neutral' | 'warn' | 'crit'

const TONE_CLASS: Record<StateTone, string> = {
  neutral: 'border-slate-800 bg-slate-900/50 text-slate-300',
  warn: 'border-amber-500/40 bg-amber-500/5 text-amber-200',
  crit: 'border-rose-600/50 bg-rose-950/40 text-rose-200',
}

export interface StatePanelAction {
  label: string
  onAct: () => void
}

/**
 * Centred, viewport-safe message for loading / empty / error states (Part 6).
 * It fills the available region instead of overflowing it, so a failed or
 * empty page never triggers page-level scrolling.
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
      <div className={`max-w-md rounded-xl border px-5 py-6 text-center ${TONE_CLASS[tone]}`}>
        <p className="text-base font-semibold">{title}</p>
        {hint && <p className="mt-1.5 text-sm opacity-80">{hint}</p>}
        {children}
        {action && (
          <button
            type="button"
            onClick={action.onAct}
            className="mt-4 rounded-lg border border-slate-600 px-4 py-2 text-sm text-slate-200 transition hover:bg-slate-800"
          >
            {action.label}
          </button>
        )}
      </div>
    </div>
  )
}
