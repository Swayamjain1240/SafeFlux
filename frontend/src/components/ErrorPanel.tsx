import { safeErrorMessage } from '../utils/errorMessage'

interface ErrorPanelProps {
  error: unknown
  title?: string
}

/** Inline error panel used by forms and query states (safe messages only). */
export function ErrorPanel({ error, title = 'Request failed' }: ErrorPanelProps) {
  return (
    <div
      role="alert"
      className="rounded-lg border border-rose-700/60 bg-rose-950/40 px-3 py-2 text-sm text-rose-200"
    >
      <p className="font-medium">{title}</p>
      <p className="mt-0.5 text-rose-300/90">{safeErrorMessage(error)}</p>
    </div>
  )
}
