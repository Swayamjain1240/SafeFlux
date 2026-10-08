import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="grid-bg flex h-full flex-col items-center justify-center gap-3 px-4 text-center">
      <p className="stat-num text-5xl font-semibold text-edge-strong">404</p>
      <p className="text-[10px] font-semibold tracking-[0.22em] text-slate-500 uppercase">
        Route not registered
      </p>
      <h1 className="text-xl font-semibold text-slate-100">Page not found</h1>
      <p className="max-w-sm text-sm text-slate-400">
        That route does not exist in the SafeFlux workspace. Nothing was changed and no analysis
        was affected.
      </p>
      <Link
        to="/"
        className="mt-1 rounded-md border border-edge-strong px-4 py-2 text-sm text-slate-300 transition hover:border-accent/40 hover:text-slate-100"
      >
        Back to home
      </Link>
    </div>
  )
}
