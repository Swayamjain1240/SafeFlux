import type { Tone } from '../../dashboard/viewState'

const TONE_CLASS: Record<Tone, string> = {
  ok: 'border-emerald-500/40 bg-emerald-500/10 text-emerald-300',
  warn: 'border-amber-500/40 bg-amber-500/10 text-amber-300',
  crit: 'border-rose-500/50 bg-rose-500/10 text-rose-300',
  idle: 'border-slate-700 bg-slate-900 text-slate-400',
}

const DOT_CLASS: Record<Tone, string> = {
  ok: 'bg-emerald-400',
  warn: 'bg-amber-400',
  crit: 'bg-rose-500',
  idle: 'bg-slate-500',
}

/**
 * Compact status chip (Part 6) used for safety state and telemetry state.
 * Colour alone is never the only signal — the label always states the value.
 */
export function StatusBadge({
  label,
  tone,
  title,
}: {
  label: string
  tone: Tone
  title?: string
}) {
  return (
    <span
      title={title}
      className={`inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-medium whitespace-nowrap ${TONE_CLASS[tone]}`}
    >
      <span aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 rounded-full ${DOT_CLASS[tone]}`} />
      {label}
    </span>
  )
}
