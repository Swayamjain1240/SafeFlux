import { ApiError } from '../api/client'
import { safeErrorMessage } from '../utils/errorMessage'
import { IconAlert } from './ui/Icons'

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
      className="flex gap-2 rounded-md border border-crit/50 bg-crit/10 px-3 py-2 text-sm text-crit"
    >
      <IconAlert className="mt-0.5 h-4 w-4 shrink-0 text-crit" />
      <div className="min-w-0">
        <p className="font-medium">{title}</p>
        <p className="mt-0.5 text-crit/90">{safeErrorMessage(error)}</p>
        {details && details.length > 0 && (
          <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-crit/90">
            {details.map((detail) => (
              <li key={`${detail.field}:${detail.message}`}>{detail.message}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
