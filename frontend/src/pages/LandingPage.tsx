import { useState, type ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useHealth } from '../hooks/useHealth'

type TabId = 'loop' | 'boundary' | 'guardrails'

const TABS: { id: TabId; label: string }[] = [
  { id: 'loop', label: 'Investigation loop' },
  { id: 'boundary', label: 'Boundary hunting' },
  { id: 'guardrails', label: 'Guardrails' },
]

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
    body: 'Read-only decision support. No PLC, no DCS, no valve actuation — ever.',
  },
  {
    title: 'AI searches, simulator proves',
    body: 'The model never invents numbers. Every finding traces to deterministic evidence.',
  },
  {
    title: 'The engineer decides',
    body: 'Reports end with evidence and limitations — approval always stays human.',
  },
  {
    title: 'Secured by default',
    body: 'Server-side authorization, strict CORS, rate limits and safe error envelopes.',
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

function LoopPanel(): ReactNode {
  return (
    <ol className="space-y-2">
      {PIPELINE.map((item) => (
        <li
          key={item.name}
          className="flex items-baseline gap-3 rounded-lg border border-slate-800/70 bg-slate-950/40 px-3 py-2.5"
        >
          <span className="font-mono text-xs text-slate-600">{item.step}</span>
          <div className="min-w-0">
            <p className="text-xs font-semibold tracking-widest text-cyan-400">{item.name}</p>
            <p className="mt-0.5 text-xs leading-relaxed text-slate-400 sm:text-sm">
              {item.detail}
            </p>
          </div>
        </li>
      ))}
    </ol>
  )
}

function BoundaryPanel(): ReactNode {
  return (
    <div className="font-mono text-sm">
      <p className="mb-2 text-[11px] tracking-widest text-slate-500 uppercase">
        cooling effectiveness → status
      </p>
      <ul className="space-y-1.5">
        {BOUNDARY_ROWS.map((row) => (
          <li
            key={row.cooling}
            className="flex items-center justify-between gap-3 rounded-lg border border-slate-800/70 bg-slate-950/40 px-3 py-2"
          >
            <span className="text-slate-300">{row.cooling}</span>
            <span className={`text-xs sm:text-sm ${row.tone}`}>{row.status}</span>
          </li>
        ))}
      </ul>
      <p className="mt-3 text-[11px] leading-relaxed text-slate-500">
        Simulated boundaries under the selected model — never certified real-world safety limits.
      </p>
    </div>
  )
}

function GuardrailsPanel(): ReactNode {
  return (
    <div className="grid gap-2 sm:grid-cols-2">
      {GUARDRAILS.map((item) => (
        <div key={item.title} className="rounded-lg border border-slate-800/70 bg-slate-950/40 p-3">
          <h3 className="text-xs font-semibold text-slate-200 sm:text-sm">{item.title}</h3>
          <p className="mt-1 text-[11px] leading-relaxed text-slate-500 sm:text-xs">{item.body}</p>
        </div>
      ))}
    </div>
  )
}

const PANELS: Record<TabId, () => ReactNode> = {
  loop: LoopPanel,
  boundary: BoundaryPanel,
  guardrails: GuardrailsPanel,
}

/**
 * Single-viewport landing: hero on the left, tabbed detail panel on the right.
 * Nothing is clipped — the panel scrolls inside itself if space runs short,
 * and the document never scrolls (one-viewport rule applied to marketing too).
 */
export default function LandingPage() {
  const [activeTab, setActiveTab] = useState<TabId>('loop')
  const ActivePanel = PANELS[activeTab]

  return (
    <div className="grid h-full min-h-0 grid-rows-[auto_minmax(0,1fr)] gap-3 bg-[radial-gradient(ellipse_at_top_left,rgba(34,211,238,0.10),transparent_55%)] p-3 sm:gap-4 sm:p-4 lg:grid-cols-[1.05fr_1fr] lg:grid-rows-1 lg:gap-6 lg:p-6">
      {/* Hero */}
      <section className="flex min-h-0 flex-col justify-center gap-3 text-center lg:text-left">
        <span className="inline-flex justify-center self-center rounded-full border border-cyan-500/40 bg-cyan-500/10 px-3 py-1 text-[10px] font-medium tracking-widest text-cyan-300 uppercase lg:self-start">
          Nebius × NVIDIA Global AI Hackathon · Best Apps &amp; Agents
        </span>

        <h1 className="text-2xl leading-tight font-bold tracking-tight text-white sm:text-3xl lg:text-4xl">
          Hunt process failures{' '}
          <span className="bg-gradient-to-r from-cyan-400 to-amber-400 bg-clip-text text-transparent">
            before they become real
          </span>
        </h1>

        <p className="text-xs leading-relaxed text-slate-400 sm:text-sm lg:text-base">
          Describe a proposed engineering change. SafeFlux autonomously searches a digital
          simulation for hidden unsafe conditions, verifies findings deterministically, and
          presents the evidence for human review.
        </p>

        <p className="self-center rounded-lg border border-slate-800 bg-slate-900/60 px-3 py-1.5 font-mono text-[11px] text-slate-300 sm:text-xs lg:self-start">
          AI searches for danger → Simulator proves it → Engineer decides.
        </p>

        <div className="flex flex-wrap items-center justify-center gap-2 sm:gap-3 lg:justify-start">
          <Link
            to="/signup"
            className="rounded-xl bg-cyan-500 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 sm:px-5"
          >
            Create your account
          </Link>
          <Link
            to="/login"
            className="rounded-xl border border-slate-700 px-4 py-2.5 text-sm font-semibold text-slate-200 transition hover:bg-slate-800 sm:px-5"
          >
            Log in
          </Link>
          <ApiStatus />
        </div>
      </section>

      {/* Tabbed detail panel — one primary panel at a time */}
      <section className="flex min-h-0 flex-col overflow-hidden rounded-2xl border border-slate-800 bg-slate-900/50 backdrop-blur">
        <div
          role="tablist"
          aria-label="SafeFlux details"
          className="flex shrink-0 flex-wrap gap-1 border-b border-slate-800 p-2"
        >
          {TABS.map((tab) => (
            <button
              key={tab.id}
              type="button"
              role="tab"
              aria-selected={activeTab === tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={[
                'rounded-md px-2.5 py-1.5 text-xs transition sm:px-3 sm:text-sm',
                activeTab === tab.id
                  ? 'bg-cyan-500/15 text-cyan-300 ring-1 ring-cyan-500/30'
                  : 'text-slate-400 hover:bg-slate-800/70 hover:text-slate-200',
              ].join(' ')}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div
          role="tabpanel"
          className="min-h-0 flex-1 overflow-y-auto p-2.5 sm:p-3"
        >
          <ActivePanel />
        </div>
      </section>
    </div>
  )
}
