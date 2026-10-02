import { Component, type ErrorInfo, type ReactNode } from 'react'

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
}

/**
 * Catches render-time failures and shows a safe recovery screen.
 * Internal error details are logged locally, never rendered (XSS/leak rule).
 */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error, _info: ErrorInfo): void {
    console.error('SafeFlux UI error:', error.message)
  }

  render(): ReactNode {
    if (this.state.hasError) {
      return (
        <div className="flex h-full min-h-[60vh] flex-col items-center justify-center gap-4 p-8 text-center">
          <span aria-hidden="true" className="text-4xl">
            ⚠️
          </span>
          <h1 className="text-xl font-semibold text-slate-100">Something went wrong</h1>
          <p className="max-w-md text-sm leading-relaxed text-slate-400">
            The interface hit an unexpected error. Reload to try again. No plant, simulation or
            analysis was affected.
          </p>
          <button
            type="button"
            onClick={() => window.location.reload()}
            className="rounded-lg bg-cyan-500 px-4 py-2 text-sm font-medium text-slate-950 transition hover:bg-cyan-400"
          >
            Reload application
          </button>
        </div>
      )
    }
    return this.props.children
  }
}
