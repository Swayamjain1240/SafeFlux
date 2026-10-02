import { Link, Outlet } from 'react-router-dom'
import { Logo } from '../components/Logo'

/** Public shell: landing + auth pages. Marketing pages may scroll. */
export default function PublicLayout() {
  return (
    <div className="flex min-h-full flex-col">
      <header className="sticky top-0 z-10 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between px-4">
          <Logo />
          <nav className="flex items-center gap-2">
            <Link
              to="/login"
              className="rounded-lg px-3 py-1.5 text-sm text-slate-300 transition hover:bg-slate-800 hover:text-white"
            >
              Log in
            </Link>
            <Link
              to="/signup"
              className="rounded-lg bg-cyan-500 px-3 py-1.5 text-sm font-medium text-slate-950 transition hover:bg-cyan-400"
            >
              Start review
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="border-t border-slate-900 py-4">
        <p className="mx-auto max-w-6xl px-4 text-center text-xs text-slate-600">
          SafeFlux is a hackathon research prototype and decision-support system. It never controls
          real industrial equipment.
        </p>
      </footer>
    </div>
  )
}
