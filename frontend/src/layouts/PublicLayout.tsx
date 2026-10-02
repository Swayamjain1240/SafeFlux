import { Link, Outlet } from 'react-router-dom'
import { Logo } from '../components/Logo'

/**
 * Public shell: landing + auth pages.
 * The document itself never scrolls — each page fills the remaining viewport
 * and manages any overflow in its own content region.
 */
export default function PublicLayout() {
  return (
    <div className="flex h-full flex-col">
      <header className="shrink-0 border-b border-slate-800 bg-slate-950/90 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-7xl items-center justify-between px-4">
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

      <main className="min-h-0 flex-1 overflow-y-auto">
        <Outlet />
      </main>

      <footer className="shrink-0 border-t border-slate-900 bg-slate-950/80 py-2">
        <p className="mx-auto max-w-7xl px-4 text-center text-[11px] leading-snug text-slate-600">
          SafeFlux is a hackathon research prototype and decision-support system. It never controls
          real industrial equipment.
        </p>
      </footer>
    </div>
  )
}
