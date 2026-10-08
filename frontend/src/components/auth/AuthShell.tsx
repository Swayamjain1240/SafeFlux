import type { ReactNode } from 'react'
import { Logo } from '../Logo'
import { IconPulse, IconShield } from '../ui/Icons'

/**
 * Auth shell (visual transformation, §31).
 *
 * Desktop: brand + animated industrial signal panel on the left, the form on
 * the right. Mobile: single panel, form only. The left panel is CSS/SVG motion
 * at low opacity — no 3D and no extra requests, so authentication stays fast.
 * It is decorative (`aria-hidden`) and collapses entirely under
 * prefers-reduced-motion via the global media query.
 */
function SignalStrip() {
  // One slow sweep across a static signal trace: motion, not noise.
  return (
    <div className="panel-inset relative h-24 overflow-hidden" aria-hidden="true">
      <svg viewBox="0 0 400 96" className="h-full w-full" preserveAspectRatio="none">
        <g stroke="#1e2a38" strokeWidth="1">
          <path d="M0 24h400M0 48h400M0 72h400" />
        </g>
        <path
          d="M0 76 L48 74 L64 60 L80 70 L104 26 L128 66 L152 58 L176 70 L208 44 L232 72 L256 64 L288 52 L312 70 L344 62 L400 68"
          fill="none"
          stroke="#00d9ff"
          strokeWidth="1.6"
          strokeOpacity="0.75"
        />
        <path
          d="M0 76 L48 74 L64 60 L80 70 L104 26 L128 66 L152 58 L176 70 L208 44 L232 72 L256 64 L288 52 L312 70 L344 62 L400 68"
          fill="none"
          stroke="#f43f5e"
          strokeWidth="1.6"
          strokeDasharray="14 220"
          strokeDashoffset="234"
          style={{ animation: 'sf-sweep 4.5s linear infinite' }}
        />
      </svg>
    </div>
  )
}

export function AuthShell({ children }: { children: ReactNode }) {
  return (
    <div className="grid min-h-full lg:grid-cols-[1.05fr_0.95fr]">
      <aside className="grid-bg hidden flex-col justify-between border-r border-edge/70 p-8 lg:flex">
        <div className="flex items-center gap-3">
          <Logo />
        </div>

        <div className="flex flex-col gap-4">
          <p className="text-[10px] font-semibold tracking-[0.26em] text-accent/80 uppercase">
            Autonomous process-safety failure hunter
          </p>
          <h2 className="max-w-md text-2xl leading-tight font-semibold tracking-tight text-white">
            Find the failure you were about to ship — in simulation, before it exists in the plant.
          </h2>
          <SignalStrip />
          <ul className="flex flex-col gap-2 text-xs text-slate-400">
            <li className="flex items-center gap-2">
              <IconPulse className="h-4 w-4 shrink-0 text-accent/70" />
              Deterministic telemetry — the simulator is the only authority on numbers.
            </li>
            <li className="flex items-center gap-2">
              <IconShield className="h-4 w-4 shrink-0 text-accent/70" />
              Read-only decision support. Nothing here can touch real equipment.
            </li>
          </ul>
        </div>

        <p className="max-w-sm text-[11px] leading-relaxed text-slate-600">
          Hackathon research prototype. Findings are simulated evidence for human review, not a
          certification of plant safety.
        </p>
      </aside>

      <section className="flex items-center justify-center px-4 py-6 sm:px-6">{children}</section>
    </div>
  )
}
