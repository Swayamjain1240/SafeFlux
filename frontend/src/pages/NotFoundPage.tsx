import { Link } from 'react-router-dom'

export default function NotFoundPage() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 px-4 text-center">
      <p className="font-mono text-6xl font-bold text-slate-700">404</p>
      <h1 className="text-xl font-semibold text-slate-100">Page not found</h1>
      <p className="max-w-sm text-sm text-slate-400">
        That route does not exist in the SafeFlux workspace.
      </p>
      <Link
        to="/"
        className="rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 transition hover:bg-slate-800"
      >
        Back to home
      </Link>
    </div>
  )
}
