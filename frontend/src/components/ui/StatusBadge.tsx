import type { Tone } from '../../dashboard/viewState'

const TONE_CLASS: Record<Tone, string> = {
  ok: 'border-safe/40 bg-safe/10 text-safe',
  warn: 'border-warn/40 bg-warn/10 text-warn',
  crit: 'border-crit/50 bg-crit/10 text-crit',
  idle: 'border-edge bg-panel text-slate-400',
}

const DOT_CLASS: Record<Tone, string> = {
  ok: 'bg-safe',
  warn: 'bg-warn',
  crit: 'bg-crit',
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
