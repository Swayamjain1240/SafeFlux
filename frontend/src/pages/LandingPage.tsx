import { Link } from 'react-router-dom'
import { useHealth } from '../hooks/useHealth'

const PIPELINE = [
  {
    step: '01',
    name: 'PLAN',
    detail: 'The engineer describes the proposed change — e.g. “raise throughput 30%”.',
  },
  {
    step: '02',
    name: 'SIMULATE',
    detail: 'A deterministic process model evolves temperature, pressure, flow and level.',
  },
  {
    step: '03',
    name: 'OBSERVE',
    detail: 'Search drives toward boundaries: near-limit regions and hidden violations.',
  },
  {
    step: '04',
    name: 'INVESTIGATE',
    detail: 'Counterfactuals and safeguard-timing checks produce traceable evidence.',
  },
]

const BOUNDARY_ROWS = [
  { cooling: '100%', status: 'SAFE', tone: 'text-emerald-400' },
  { cooling: '70%', status: 'SAFE', tone: 'text-emerald-400' },
  { cooling: '50%', status: 'NEAR_LIMIT', tone: 'text-amber-400' },
  { cooling: '40%', status: 'VIOLATION', tone: 'text-rose-400' },
  { cooling: '41%', status: 'VIOLATION (refined boundary)', tone: 'text-rose-300' },
]

const GUARDRAILS = [
  {
    title: 'Never touches a real plant',
    body: 'SafeFlux is read-only decision support. No PLC, no DCS, no valve actuation — ever.',
  },
  {
    title: 'AI searches, simulator proves',
    body: 'The model never invents numbers. Every finding traces back to deterministic evidence.',
  },
  {
    title: 'The engineer decides',
    body: 'Reports end with evidence and limitations — approval always stays human.',
  },
  {
    title: 'Secured by default',
    body: 'Server-side authorization, strict CORS, rate limits and safe error envelopes from day one.',
  },
]

function ApiStatus() {
  const { data, isError, isPending } = useHealth()

  let dotClass = 'bg-amber-400'
  let label = 'Connecting to API…'
  if (data) {
    dotClass = 'bg-emerald-400'
    label = `API online · v${data.version} · ${data.environment}`
  } else if (isError) {
    dotClass = 'bg-rose-500'
    label = 'API offline — start the backend'
  }

  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-slate-700 bg-slate-900/80 px-3 py-1 text-xs text-slate-300">
      <span
        aria-hidden="true"
        className={`h-2 w-2 rounded-full ${dotClass} ${isPending ? 'animate-pulse' : ''}`}
      />
      {label}
    </span>
  )
}

export default function LandingPage() {
  return (
    <div className="relative">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 top-0 h-[440px] bg-[radial-gradient(ellipse_at_top,rgba(34,211,238,0.16),transparent_65%)]"
      />

      {/* Hero */}
      <section className="relative mx-auto max-w-6xl px-4 pt-14 pb-16 text-center sm:pt-20">
        <span className="inline-block rounded-full border border-cyan-500/40 bg-cyan-500/10 px-3 py-1 text-[11px] font-medium tracking-widest text-cyan-300 uppercase">
          Nebius × NVIDIA Global AI Hackathon · Best Apps &amp; Agents
        </span>

        <h1 className="mx-auto mt-6 max-w-3xl text-4xl leading-tight font-bold tracking-tight text-white sm:text-5xl">
          Hunt process failures{' '}
          <span className="bg-gradient-to-r from-cyan-400 to-amber-400 bg-clip-text text-transparent">
            before they become real
          </span>
        </h1>

        <p className="mx-auto mt-5 max-w-2xl text-base leading-relaxed text-slate-400 sm:text-lg">
          SafeFlux lets a process-safety engineer describe a proposed change, autonomously searches a
          digital simulation for hidden unsafe conditions, verifies findings deterministically, and
          presents the evidence for human review.
        </p>

        <p className="mx-auto mt-4 max-w-xl rounded-lg border border-slate-800 bg-slate-900/60 px-4 py-2 font-mono text-sm text-slate-300">
          AI searches for danger → Simulator proves it → Engineer decides.
        </p>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Link
            to="/signup"
            className="rounded-xl bg-cyan-500 px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400"
          >
            Create your account
          </Link>
          <Link
            to="/login"
            className="rounded-xl border border-slate-700 px-6 py-3 text-sm font-semibold text-slate-200 transition hover:bg-slate-800"
          >
            Log in
          </Link>
        </div>

        <div className="mt-6 flex justify-center">
          <ApiStatus />
        </div>
      </section>

      {/* Pipeline */}
      <section className="border-y border-slate-900 bg-slate-950/60 py-14">
        <div className="mx-auto max-w-6xl px-4">
          <h2 className="text-center text-sm font-semibold tracking-widest text-slate-500 uppercase">
            The investigation loop
          </h2>
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {PIPELINE.map((item) => (
              <div
                key={item.name}
                className="rounded-xl border border-slate-800 bg-slate-900/50 p-5 transition hover:border-cyan-500/40"
              >
                <div className="flex items-baseline justify-between">
                  <span className="text-xs font-mono text-slate-600">{item.step}</span>
                  <span className="text-sm font-semibold tracking-widest text-cyan-400">
                    {item.name}
                  </span>
                </div>
                <p className="mt-3 text-sm leading-relaxed text-slate-400">{item.detail}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Boundary hunting example */}
      <section className="mx-auto max-w-6xl px-4 py-14">
        <div className="grid items-center gap-8 lg:grid-cols-2">
          <div>
            <h2 className="text-2xl font-semibold text-white">
              It searches <span className="text-cyan-400">toward</span> the danger boundary
            </h2>
            <p className="mt-3 text-sm leading-relaxed text-slate-400">
              Random scenario generation misses the edge. SafeFlux refines operating regions until
              it brackets the transition from safe to unsafe — then verifies it with the
              deterministic simulator and shows you the evidence.
            </p>
            <p className="mt-3 text-xs leading-relaxed text-slate-500">
              Simulated boundaries under the selected model — never certified real-world safety
              limits.
            </p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 font-mono text-sm">
            <p className="mb-3 text-xs tracking-widest text-slate-500 uppercase">
              cooling effectiveness → status
            </p>
            <ul className="space-y-2">
              {BOUNDARY_ROWS.map((row) => (
                <li key={row.cooling} className="flex items-center justify-between gap-4">
                  <span className="text-slate-300">{row.cooling}</span>
                  <span className={row.tone}>{row.status}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* Guardrails */}
      <section className="border-t border-slate-900 bg-slate-950/60 py-14">
        <div className="mx-auto max-w-6xl px-4">
          <h2 className="text-center text-sm font-semibold tracking-widest text-slate-500 uppercase">
            Hard guardrails
          </h2>
          <div className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {GUARDRAILS.map((item) => (
              <div key={item.title} className="rounded-xl border border-slate-800 p-5">
                <h3 className="text-sm font-semibold text-slate-200">{item.title}</h3>
                <p className="mt-2 text-xs leading-relaxed text-slate-500">{item.body}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Final CTA */}
      <section className="mx-auto max-w-6xl px-4 py-16 text-center">
        <h2 className="text-2xl font-semibold text-white">Ready to review a change safely?</h2>
        <Link
          to="/signup"
          className="mt-5 inline-block rounded-xl bg-cyan-500 px-6 py-3 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400"
        >
          Start with the foundation
        </Link>
      </section>
    </div>
  )
}
