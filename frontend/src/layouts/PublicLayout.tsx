import { Link, Outlet } from 'react-router-dom'
import { Logo } from '../components/Logo'

/**
 * Public shell: landing + auth pages.
 *
 * The landing page may scroll (product spec §9); the header and footer stay in
 * the document flow, while auth pages keep their form inside one viewport by
 * staying compact. The industrial grid and the accent hairline sit behind
 * everything at low opacity so the content stays dominant.
 */
export default function PublicLayout() {
  return (
    <div className="grid-bg flex min-h-dvh flex-col bg-void">
      <header className="sticky top-0 z-20 shrink-0 border-b border-edge/80 bg-void/85 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-7xl items-center justify-between gap-3 px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <Logo />
            <span className="hidden text-[10px] font-semibold tracking-[0.22em] text-slate-500 uppercase sm:inline">
              Safety analysis workspace
            </span>
          </div>
          <nav className="flex items-center gap-2">
            <Link
              to="/login"
              className="rounded-md px-3 py-1.5 text-sm text-slate-300 transition hover:bg-surface/70 hover:text-white"
            >
              Log in
            </Link>
            <Link
              to="/signup"
              className="rounded-md bg-accent px-3 py-1.5 text-sm font-semibold text-void transition hover:bg-accent-soft"
            >
              Launch SafeFlux
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1">
        <Outlet />
      </main>

      <footer className="shrink-0 border-t border-edge/70 bg-void/70 py-3">
        <p className="mx-auto max-w-7xl px-4 text-center text-[11px] leading-snug text-slate-600 sm:px-6">
          SafeFlux is a hackathon research prototype and decision-support system. It never controls
          real industrial equipment.
        </p>
      </footer>
    </div>
  )
}
