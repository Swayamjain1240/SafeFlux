import { Link } from 'react-router-dom'
import { useHealth } from '../hooks/useHealth'
import { TwinCanvas } from '../components/TwinCanvas'
import { Panel } from '../components/ui/Panel'
import { StatusBadge } from '../components/ui/StatusBadge'
import { IconAnalyze, IconChevronRight, IconShield } from '../components/ui/Icons'
import type { TwinStatus } from '../three/reactorTwin'

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
  { cooling: '100%', status: 'SAFE', tone: 'text-safe' },
  { cooling: '70%', status: 'SAFE', tone: 'text-safe' },
  { cooling: '50%', status: 'NEAR_LIMIT', tone: 'text-warn' },
  { cooling: '40%', status: 'VIOLATION', tone: 'text-crit' },
  { cooling: '41%', status: 'VIOLATION (refined boundary)', tone: 'text-crit' },
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

/**
 * The twin mirrors the same health probe the header states — it carries no
 * numbers and claims no plant state. The label under it says so.
 */
function twinStatusFromHealth(online: boolean, failed: boolean): TwinStatus {
  if (online) return 'normal'
  if (failed) return 'critical'
  return 'warning'
}

function HealthIndicator() {
  const { data, isError } = useHealth()
  const online = Boolean(data)
  const tone = online ? 'ok' : isError ? 'crit' : 'warn'
  const label = online
    ? `API online · v${data?.version} · ${data?.environment}`
    : isError
      ? 'API offline — start the backend'
      : 'Connecting to API…'

  return (
    <StatusBadge
      label={label}
      tone={tone}
      title="Live health probe of the SafeFlux backend"
    />
  )
}

export default function LandingPage() {
  const { data, isError } = useHealth()
  const twinStatus = twinStatusFromHealth(Boolean(data), isError)

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 sm:py-8 lg:gap-10 lg:py-12">
      {/* Hero ---------------------------------------------------------------- */}
      <section className="grid min-h-[calc(100dvh-9.5rem)] grid-cols-1 items-center gap-6 lg:min-h-[36rem] lg:grid-cols-[1.02fr_0.98fr] lg:gap-10">
        <div className="flex min-w-0 flex-col gap-4">
          <span className="inline-flex w-fit items-center gap-2 rounded-md border border-accent/30 bg-accent/8 px-2.5 py-1 text-[10px] font-semibold tracking-[0.18em] text-accent uppercase">
            Nebius × NVIDIA Global AI Hackathon · Best Apps &amp; Agents
          </span>

          <div className="min-w-0">
            <p className="text-[11px] font-semibold tracking-[0.36em] text-slate-500 uppercase">
              SafeFlux
            </p>
            <h1 className="mt-1 text-3xl leading-[1.08] font-semibold tracking-tight text-white sm:text-4xl lg:text-5xl">
              Discover hidden process failures{' '}
              <span className="bg-gradient-to-r from-accent via-accent-soft to-ai bg-clip-text text-transparent">
                before they become real incidents
              </span>
            </h1>
          </div>

          <p className="max-w-xl text-sm leading-relaxed text-slate-400 sm:text-base">
            Describe a proposed engineering change. SafeFlux autonomously searches a digital
            simulation for hidden unsafe conditions, verifies every finding deterministically, and
            presents the evidence for human review.
          </p>

          <p className="panel-inset w-fit px-3 py-2 text-xs text-slate-300">
            <span className="text-accent">AI searches for danger</span>
            <span className="mx-2 text-slate-600">→</span>
            <span className="text-safe">Simulator proves it</span>
            <span className="mx-2 text-slate-600">→</span>
            <span className="text-slate-200">Engineer decides</span>
          </p>

          <div className="flex flex-wrap items-center gap-2 sm:gap-3">
            <Link
              to="/signup"
              className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2.5 text-sm font-semibold text-void transition hover:bg-accent-soft sm:px-5"
            >
              Launch SafeFlux
              <IconChevronRight className="h-4 w-4" />
            </Link>
            <a
              href="#system"
              className="inline-flex items-center gap-2 rounded-md border border-edge-strong px-4 py-2.5 text-sm font-semibold text-slate-200 transition hover:border-accent/40 hover:text-white sm:px-5"
            >
              Explore system
            </a>
            <HealthIndicator />
          </div>
        </div>

        {/* Digital twin — illustration only, and labelled as such */}
        <div className="flex min-w-0 flex-col gap-2">
          <Panel
            title="Digital twin"
            hint="illustrative process shape · no live values"
            className="h-[19rem] sm:h-[22rem] lg:h-[30rem]"
            bodyClassName="relative overflow-hidden"
          >
            <div className="grid-bg absolute inset-0 opacity-70" />
            <TwinCanvas status={twinStatus} className="h-full w-full" />
          </Panel>
          <p className="text-[11px] leading-snug text-slate-500">
            This twin illustrates the process shape (feed tank → pump → reactor → outlet). Live
            values and the real topology are on the Monitor page; no number here is a claim.
          </p>
        </div>
      </section>

      {/* System detail ------------------------------------------------------- */}
      <section id="system" className="grid gap-4 lg:grid-cols-[1.15fr_1fr]">
        <Panel title="Investigation loop" hint="one bounded run, in order" className="min-h-0">
          <ol className="grid gap-2 sm:grid-cols-2">
            {PIPELINE.map((item) => (
              <li key={item.name} className="panel-inset flex gap-3 px-3 py-2.5">
                <span className="stat-num text-[11px] text-slate-600">{item.step}</span>
                <div className="min-w-0">
                  <p className="text-[11px] font-semibold tracking-[0.2em] text-accent uppercase">
                    {item.name}
                  </p>
                  <p className="mt-0.5 text-xs leading-relaxed text-slate-400">{item.detail}</p>
                </div>
              </li>
            ))}
          </ol>
        </Panel>

        <Panel title="Boundary hunting" hint="cooling effectiveness → status">
          <ul className="flex flex-col gap-1.5">
            {BOUNDARY_ROWS.map((row) => (
              <li
                key={row.cooling}
                className="panel-inset flex items-center justify-between gap-3 px-3 py-2 text-sm"
              >
                <span className="stat-num text-slate-300">{row.cooling}</span>
                <span className={`stat-num text-xs ${row.tone}`}>{row.status}</span>
              </li>
            ))}
          </ul>
          <p className="mt-3 text-[11px] leading-relaxed text-slate-500">
            Simulated boundaries under the selected model — never certified real-world safety
            limits.
          </p>
        </Panel>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {GUARDRAILS.map((item) => (
          <Panel key={item.title} className="min-h-0" bodyClassName="flex flex-col gap-1.5">
            <IconShield className="h-4 w-4 text-accent/80" />
            <h3 className="text-sm font-semibold text-slate-100">{item.title}</h3>
            <p className="text-xs leading-relaxed text-slate-500">{item.body}</p>
          </Panel>
        ))}
      </section>

      {/* Closing CTA --------------------------------------------------------- */}
      <section className="panel flex flex-col items-start justify-between gap-4 px-5 py-5 sm:flex-row sm:items-center">
        <div className="min-w-0">
          <h2 className="text-base font-semibold text-white sm:text-lg">
            Run the hunt on your own process change
          </h2>
          <p className="mt-1 text-xs text-slate-400 sm:text-sm">
            One change description, one bounded search, one evidence document you can defend.
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Link
            to="/signup"
            className="inline-flex items-center gap-2 rounded-md bg-accent px-4 py-2.5 text-sm font-semibold text-void transition hover:bg-accent-soft"
          >
            <IconAnalyze className="h-4 w-4" />
            Launch SafeFlux
          </Link>
          <Link
            to="/login"
            className="rounded-md border border-edge-strong px-4 py-2.5 text-sm font-semibold text-slate-200 transition hover:border-accent/40 hover:text-white"
          >
            Log in
          </Link>
        </div>
      </section>
    </div>
  )
}
