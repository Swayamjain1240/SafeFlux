import type { ComponentType, SVGProps } from 'react'
import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { Logo } from '../components/Logo'
import { RouteTransition } from '../components/RouteTransition'
import { StatusBadge } from '../components/ui/StatusBadge'
import {
  IconAnalyze,
  IconDashboard,
  IconHistory,
  IconMonitor,
  IconPlant,
  IconSignOut,
} from '../components/ui/Icons'
import { useHealth } from '../hooks/useHealth'

interface NavItem {
  to: string
  label: string
  hint: string
  icon: ComponentType<SVGProps<SVGSVGElement>>
}

/**
 * Workspace navigation. Labels are the control-room verbs; the underlying
 * routes and pages are unchanged (visual transformation only).
 */
const NAV_ITEMS: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', hint: 'Plant overview', icon: IconDashboard },
  { to: '/plant', label: 'Plant', hint: 'Configuration', icon: IconPlant },
  { to: '/monitor', label: 'Monitor', hint: 'Live telemetry', icon: IconMonitor },
  { to: '/analysis/new', label: 'Analyze', hint: 'New investigation', icon: IconAnalyze },
  { to: '/history', label: 'History', hint: 'Runs & reports', icon: IconHistory },
]

function desktopNavClass(isActive: boolean): string {
  return [
    'group flex items-center gap-2.5 rounded-md px-2.5 py-2 text-[13px] transition',
    isActive
      ? 'bg-accent/10 text-accent ring-1 ring-accent/25'
      : 'text-slate-400 hover:bg-surface-2/70 hover:text-slate-200',
  ].join(' ')
}

function mobileNavClass(isActive: boolean): string {
  return [
    'shrink-0 rounded-md px-2.5 py-1.5 text-xs font-medium transition',
    isActive ? 'bg-accent/12 text-accent' : 'text-slate-400 hover:text-slate-200',
  ].join(' ')
}

/**
 * Authenticated workspace shell — the one-viewport rule lives here: the
 * document never scrolls; header/sidebar are fixed and only the content region
 * scrolls internally when a view genuinely needs it.
 */
export default function AppLayout() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()
  const health = useHealth()

  async function handleSignOut() {
    await signOut()
    navigate('/login', { replace: true })
  }

  const apiOnline = health.isSuccess
  const apiTone = apiOnline ? 'ok' : health.isPending ? 'idle' : 'crit'
  const apiLabel = apiOnline ? 'API online' : health.isPending ? 'API checking' : 'API offline'

  return (
    <div className="grid-bg flex h-[100dvh] flex-col overflow-hidden bg-void">
      {/* ── Command header: identity, live system state, operator ─────────── */}
      <header className="flex h-14 shrink-0 items-center justify-between border-b border-edge/80 bg-panel/80 pr-2 pl-3 backdrop-blur">
        <div className="flex min-w-0 items-center gap-3">
          <Logo to="/dashboard" compact />
          <span className="hidden truncate text-[11px] tracking-[0.18em] text-slate-500 uppercase lg:inline">
            Safety analysis workspace
          </span>
        </div>

        <div className="flex min-w-0 items-center gap-2.5">
          <StatusBadge label={apiLabel} tone={apiTone} title="SafeFlux API status" />
          <span
            className="hidden items-center gap-1.5 text-[11px] text-slate-500 xl:inline-flex"
            title="Every number comes from the deterministic simulator and safety engine"
          >
            <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-accent" />
            Deterministic core
          </span>
          <span className="hidden max-w-40 truncate text-xs text-slate-400 sm:inline">
            {user ? user.fullName : 'Engineer'}
          </span>
          <button
            type="button"
            onClick={() => void handleSignOut()}
            className="inline-flex items-center gap-1.5 rounded-md border border-edge-strong px-2.5 py-1.5 text-xs text-slate-300 transition hover:border-crit/40 hover:bg-crit/10 hover:text-crit"
          >
            <IconSignOut className="h-3.5 w-3.5 md:hidden" />
            <span className="hidden md:inline">Sign out</span>
            <span className="md:hidden">Exit</span>
          </button>
        </div>
      </header>

      <div className="flex min-h-0 flex-1">
        {/* ── Desktop rail ─────────────────────────────────────────────────── */}
        <aside className="hidden w-56 shrink-0 flex-col border-r border-edge/80 bg-graphite/70 md:flex">
          <p className="px-3 pt-3 pb-1.5 text-[10px] font-semibold tracking-[0.18em] text-slate-500 uppercase">
            Workspace
          </p>
          <nav className="flex-1 space-y-0.5 overflow-y-auto px-2" aria-label="Workspace">
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon
              return (
                <NavLink key={item.to} to={item.to} end className={({ isActive }) => desktopNavClass(isActive)}>
                  {({ isActive }) => (
                    <>
                      <Icon className={`h-4 w-4 shrink-0 ${isActive ? 'text-accent' : 'text-slate-500 group-hover:text-slate-400'}`} />
                      <span className="flex min-w-0 flex-col">
                        <span className="truncate">{item.label}</span>
                        <span className="truncate text-[10px] text-slate-600">{item.hint}</span>
                      </span>
                    </>
                  )}
                </NavLink>
              )
            })}
          </nav>

          <div className="space-y-2 border-t border-edge/70 p-3">
            <div className="panel-inset px-2.5 py-2">
              <p className="text-[10px] font-semibold tracking-[0.16em] text-slate-500 uppercase">
                System
              </p>
              <p className="mt-1 flex items-center gap-1.5 text-[11px] text-slate-400">
                <span
                  aria-hidden="true"
                  className={`h-1.5 w-1.5 rounded-full ${apiOnline ? 'bg-safe' : health.isPending ? 'bg-slate-500' : 'bg-crit'}`}
                />
                {apiLabel}
              </p>
              <p className="mt-0.5 text-[11px] text-slate-500">Simulator authoritative</p>
            </div>
            <p className="text-[10px] leading-relaxed text-slate-600">
              AI searches for danger → Simulator proves it → Engineer decides.
            </p>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col overflow-hidden">
          {/* ── Mobile: compact horizontal nav, one panel at a time ────────── */}
          <nav
            className="flex shrink-0 gap-1 overflow-x-auto border-b border-edge/70 bg-panel/60 px-2 py-1.5 md:hidden"
            aria-label="Workspace"
          >
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end
                className={({ isActive }) => mobileNavClass(isActive)}
              >
                {item.label}
              </NavLink>
            ))}
          </nav>

          {/* One-viewport rule: the content region never scrolls as a page.
              Each view manages its own internal, bounded scrolling instead. */}
          <main className="min-h-0 flex-1 overflow-hidden p-3 md:p-4">
            <RouteTransition>
              <Outlet />
            </RouteTransition>
          </main>
        </div>
      </div>
    </div>
  )
}
