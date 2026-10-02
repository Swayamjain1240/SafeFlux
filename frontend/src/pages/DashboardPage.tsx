import { useAuth } from '../auth/context'
import { useHealth } from '../hooks/useHealth'

interface StatCard {
  label: string
  value: string
  hint: string
}

const STATS: StatCard[] = [
  { label: 'Plant configurations', value: '0', hint: 'Plant setup ships in Part 3' },
  { label: 'Active analyses', value: '0', hint: 'Scenario search ships in Part 7' },
  { label: 'Safety findings', value: '—', hint: 'Safety engine ships in Part 5' },
  { label: 'Safeguard checks', value: '—', hint: 'Safeguards ship in Part 9' },
]

export default function DashboardPage() {
  const { user } = useAuth()
  const health = useHealth()

  return (
    <div className="flex h-full min-h-0 flex-col gap-4">
      <div className="flex shrink-0 flex-wrap items-end justify-between gap-2">
        <div>
          <h1 className="text-lg font-semibold text-white">
            {user ? `Welcome, ${user.fullName}` : 'Engineering dashboard'}
          </h1>
          <p className="text-xs text-slate-500">
            Foundation is live — data populates as build parts land.
          </p>
        </div>
        <span className="inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs text-slate-300">
          <span
            aria-hidden="true"
            className={`h-2 w-2 rounded-full ${
              health.data ? 'bg-emerald-400' : health.isError ? 'bg-rose-500' : 'bg-amber-400'
            }`}
          />
          {health.data
            ? `API ${health.data.status} · v${health.data.version} · ${health.data.environment}`
            : health.isError
              ? 'API offline'
              : 'Connecting…'}
        </span>
      </div>

      <div className="grid min-h-0 flex-1 grid-cols-2 content-start gap-3 lg:grid-cols-4">
        {STATS.map((card) => (
          <div
            key={card.label}
            className="rounded-xl border border-slate-800 bg-slate-900/60 p-4"
          >
            <p className="text-xs text-slate-500">{card.label}</p>
            <p className="mt-1 text-2xl font-semibold text-slate-200">{card.value}</p>
            <p className="mt-1 text-[11px] text-slate-600">{card.hint}</p>
          </div>
        ))}
      </div>

      <div className="shrink-0 rounded-xl border border-cyan-500/20 bg-cyan-500/5 p-4">
        <p className="font-mono text-sm text-cyan-300">
          AI searches for danger → Simulator proves it → Engineer decides.
        </p>
        <p className="mt-1 text-xs text-slate-500">
          SafeFlux never controls real industrial equipment. All analysis happens inside the
          deterministic simulation.
        </p>
      </div>
    </div>
  )
}
