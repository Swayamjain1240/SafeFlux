import { Link } from 'react-router-dom'

export function Logo({ to = '/', compact = false }: { to?: string; compact?: boolean }) {
  return (
    <Link to={to} className="flex items-center gap-2 transition-opacity hover:opacity-80">
      <svg viewBox="0 0 32 32" aria-hidden="true" className="h-7 w-7 shrink-0">
        <path
          d="M16 2 4 7v9c0 7.2 5.1 12.4 12 14 6.9-1.6 12-6.8 12-14V7L16 2Z"
          fill="#0b0f14"
          stroke="#00d9ff"
          strokeWidth="1.6"
        />
        <path
          d="M16 8c1.8 3 5 4.6 5 8.4A5 5 0 0 1 16 21.4a5 5 0 0 1-5-5c0-2.4 1.6-3.7 2.6-5.6.7-1.3 1.3-2.4 2.4-2.8Z"
          fill="#f59e0b"
        />
      </svg>
      <span className="text-base font-semibold tracking-tight text-slate-100">
        Safe<span className="text-accent">Flux</span>
      </span>
      {!compact && (
        <span className="hidden text-xs text-slate-500 lg:inline">
          process-safety failure hunter
        </span>
      )}
    </Link>
  )
}
