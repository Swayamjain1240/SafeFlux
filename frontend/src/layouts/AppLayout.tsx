import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { Logo } from '../components/Logo'

interface NavItem {
  to: string
  label: string
}

const NAV_ITEMS: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/plant', label: 'Plant setup' },
  { to: '/monitor', label: 'Live monitor' },
  { to: '/analysis/new', label: 'New analysis' },
  { to: '/history', label: 'History' },
]

function navClass(isActive: boolean): string {
  return [
    'block rounded-lg px-3 py-2 text-sm transition',
    isActive
      ? 'bg-cyan-500/10 text-cyan-300 ring-1 ring-cyan-500/30'
      : 'text-slate-400 hover:bg-slate-800/70 hover:text-slate-200',
  ].join(' ')
}

/**
 * Authenticated workspace shell — the one-viewport rule lives here:
 * the document never scrolls; header/nav are fixed and only the content
 * region scrolls internally when a view genuinely needs it.
 */
export default function AppLayout() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()

  async function handleSignOut() {
    await signOut()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex h-full flex-col overflow-hidden">
      <header className="flex h-12 shrink-0 items-center justify-between border-b border-slate-800 bg-slate-900/70 pr-2 pl-3">
        <div className="flex items-center gap-3">
          <Logo to="/dashboard" compact />
          <span className="hidden rounded bg-slate-800 px-2 py-0.5 text-[10px] font-medium tracking-widest text-slate-400 uppercase sm:inline">
            MVP workspace
          </span>
        </div>
        <div className="flex items-center gap-3">
          <span className="hidden text-xs text-slate-400 sm:inline">
            {user ? user.fullName : 'Engineer'}
          </span>
          <button
            type="button"
            onClick={() => void handleSignOut()}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 transition hover:bg-slate-800"
          >
            Sign out
          </button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        <aside className="hidden w-56 shrink-0 flex-col border-r border-slate-800 bg-slate-950/60 md:flex">
          <nav className="flex-1 space-y-1 overflow-y-auto p-3">
            {NAV_ITEMS.map((item) => (
              <NavLink key={item.to} to={item.to} className={({ isActive }) => navClass(isActive)} end>
                {item.label}
              </NavLink>
            ))}
          </nav>
          <p className="border-t border-slate-900 p-3 text-[11px] leading-relaxed text-slate-500">
            AI searches for danger → Simulator proves it → Engineer decides.
          </p>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          {/* Mobile: one primary panel at a time — compact horizontal nav. */}
          <nav className="flex shrink-0 gap-1 overflow-x-auto border-b border-slate-800 px-2 py-1.5 md:hidden">
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={({ isActive }) =>
                  [
                    'shrink-0 rounded-md px-2.5 py-1 text-xs transition',
                    isActive ? 'bg-cyan-500/15 text-cyan-300' : 'text-slate-400 hover:text-slate-200',
                  ].join(' ')
                }
                end
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          <main className="min-h-0 flex-1 overflow-y-auto p-4">
            <Outlet />
          </main>
        </div>
      </div>
    </div>
  )
}
