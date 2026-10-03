import { ApiError } from '../api/client'
import { safeErrorMessage } from '../utils/errorMessage'

interface ErrorPanelProps {
  error: unknown
  title?: string
}

/**
 * Inline error panel used by forms and query states.
 * Renders only the backend's curated, already-sanitized message plus any
 * per-field validation details. Text is inserted as React children, so it
 * is always escaped — never rendered as raw HTML.
 */
export function ErrorPanel({ error, title = 'Request failed' }: ErrorPanelProps) {
  const details = error instanceof ApiError ? error.details : undefined

  return (
    <div
      role="alert"
      className="rounded-lg border border-rose-700/60 bg-rose-950/40 px-3 py-2 text-sm text-rose-200"
    >
      <p className="font-medium">{title}</p>
      <p className="mt-0.5 text-rose-300/90">{safeErrorMessage(error)}</p>
      {details && details.length > 0 && (
        <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-rose-300/90">
          {details.map((detail) => (
            <li key={`${detail.field}:${detail.message}`}>{detail.message}</li>
          ))}
        </ul>
      )}
    </div>
  )
}
