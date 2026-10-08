import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { StatePanel } from '../components/ui/StatePanel'
import { Panel } from '../components/ui/Panel'
import { StatusBadge } from '../components/ui/StatusBadge'
import { IconChevronRight } from '../components/ui/Icons'
import { useReverify, useResultDocument } from '../hooks/useAnalyses'
import { MITIGATION_FIELDS, type ReverifyDocument } from '../types/analysis'

/**
 * Re-verification (Part 9) — the engineer changes a simulated mitigation and
 * the backend re-runs *the parent's failing scenarios* with it applied.
 *
 * The comparison shows the real before/after per case, and the verdict line is
 * the backend's fixed sentence — never a guarantee. Mitigation inputs are
 * bounded on the client too, but the server re-checks every key and bound.
 *
 * Visual transformation: the result is a split before / after readout, and the
 * closing line keeps the spec's required wording ("within tested scenarios").
 */

export default function ReverifyPage() {
  const { id } = useParams<{ id: string }>()
  const parentQuery = useResultDocument(id)
  const reverify = useReverify(id)
  const [values, setValues] = useState<Record<string, number>>({})
  const [error, setError] = useState<string | null>(null)
  const [done, setDone] = useState<ReverifyDocument | null>(null)

  const parent = parentQuery.data
  const hasFailures = (parent?.failures?.length ?? 0) > 0

  const payload = useMemo(
    () =>
      Object.fromEntries(
        Object.entries(values).filter(([, value]) => Number.isFinite(value)),
      ) as Record<string, number>,
    [values],
  )
  const canSubmit =
    Boolean(id) && hasFailures && Object.keys(payload).length > 0 && !reverify.isPending

  function submit() {
    if (!id || !canSubmit) return
    setError(null)
    reverify.mutate(
      { mitigations: payload },
      {
        onSuccess: (response) => setDone(response.result ?? null),
        onError: (err) => {
          if (err instanceof ApiError) setError(err.message)
          else setError('The re-verification could not be run. Please try again.')
        },
      },
    )
  }

  if (parentQuery.isLoading) return <StatePanel title="Loading the analysis…" />
  if (parentQuery.isError || !parent) {
    return (
      <StatePanel
        tone="crit"
        title="Analysis not found"
        hint="It may belong to another account."
        action={{ label: 'Back to history', onAct: () => window.history.back() }}
      />
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-3">
      <header className="flex shrink-0 flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-semibold tracking-[0.22em] text-accent/80 uppercase">
            Re-verification
          </p>
          <h1 className="truncate text-base font-semibold tracking-tight text-white sm:text-lg">
            Apply a mitigation and re-run the failing scenarios
          </h1>
          <p className="truncate text-xs text-slate-500">{parent.goal}</p>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <Link
            to={`/analysis/${id}/investigation`}
            className="rounded-md border border-edge-strong px-3 py-1.5 text-slate-300 transition hover:border-accent/40 hover:text-slate-100"
          >
            Investigation
          </Link>
          <Link
            to={`/analysis/${id}/safeguards`}
            className="rounded-md border border-edge-strong px-3 py-1.5 text-slate-300 transition hover:border-accent/40 hover:text-slate-100"
          >
            Safeguards
          </Link>
        </div>
      </header>

      <Panel
        className="min-h-0 flex-1"
        bodyClassName="flex min-h-0 flex-col gap-3"
        scroll
        title={done ? 'Before / after' : 'Simulated mitigations'}
        hint="nothing outside the simulation changes"
      >
        {!hasFailures ? (
          <p className="rounded-md border border-safe/40 bg-safe/5 px-3 py-2 text-sm text-safe">
            The parent analysis found no failing scenarios, so there is nothing to re-verify:
            within the tested simulation scenarios, no unsafe condition was detected.
          </p>
        ) : (
          <MitigationForm
            disabled={reverify.isPending}
            values={values}
            onChange={setValues}
            onSubmit={submit}
            error={error}
            canSubmit={canSubmit}
          />
        )}
        {done && <Comparison document={done} />}
      </Panel>
    </div>
  )
}

/** A form value is kept only when it parses inside the field's bounds. */
function getNextNumber(raw: string, min: number, max: number): number | null {
  if (raw.trim() === '') return null
  const value = Number.parseFloat(raw)
  if (!Number.isFinite(value)) return null
  if (value < min || value > max) return null
  return value
}

function MitigationForm({
  disabled,
  values,
  onChange,
  onSubmit,
  error,
  canSubmit,
}: {
  disabled: boolean
  values: Record<string, number>
  onChange: (values: Record<string, number>) => void
  onSubmit: () => void
  error: string | null
  canSubmit: boolean
}) {
  const [open, setOpen] = useState(false)
  return (
    <div className="flex flex-col gap-3">
      <p className="text-xs text-slate-500">
        Choose one or more simulated mitigations. The affected failing scenarios are re-run with
        them applied.
      </p>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="self-start rounded-md border border-edge-strong px-3 py-1.5 text-xs text-slate-200 transition hover:border-accent/40 hover:text-white"
        aria-expanded={open}
      >
        {open ? 'Hide mitigations' : 'Change a mitigation'}
      </button>
      {open && (
        <div className="grid gap-3 sm:grid-cols-2">
          {MITIGATION_FIELDS.map((field) => (
            <label key={field.key} className="flex flex-col gap-1 text-xs text-slate-400">
              <span className="flex justify-between">
                <span className="text-slate-200">{field.label}</span>
                <span className="stat-num">
                  {field.min}–{field.max} {field.unit}
                </span>
              </span>
              <input
                type="number"
                inputMode="decimal"
                min={field.min}
                max={field.max}
                step={field.step}
                value={values[field.key] ?? ''}
                onChange={(event) => {
                  const raw = event.target.value
                  const next = getNextNumber(raw, field.min, field.max)
                  const nextValues = { ...values }
                  if (next === null) delete nextValues[field.key]
                  else nextValues[field.key] = next
                  onChange(nextValues)
                }}
                className="stat-num rounded-md border border-edge-strong bg-void/70 px-2 py-1.5 text-sm text-slate-100 focus:border-accent/60 focus:outline-none"
              />
            </label>
          ))}
        </div>
      )}
      {error && (
        <p
          role="alert"
          className="rounded-md border border-crit/50 bg-crit/10 px-3 py-2 text-sm text-crit"
        >
          {error}
        </p>
      )}
      <div className="flex justify-end">
        <button
          type="button"
          disabled={!canSubmit}
          onClick={onSubmit}
          className="inline-flex items-center gap-2 rounded-md bg-accent px-5 py-2 text-sm font-semibold text-void transition enabled:hover:bg-accent-soft disabled:cursor-not-allowed disabled:opacity-40"
        >
          {disabled ? 'Re-running scenarios…' : 'Run affected scenarios again'}
        </button>
      </div>
    </div>
  )
}

function Comparison({ document }: { document: ReverifyDocument }) {
  const improved = document.comparison.failing_after < document.comparison.failing_before
  return (
    <div className="flex flex-col gap-3">
      {/* Split before / after readout */}
      <div className="grid grid-cols-[1fr_auto_1fr] items-stretch gap-2">
        <div className="panel-inset flex flex-col justify-center px-3 py-2.5">
          <p className="text-[10px] font-semibold tracking-[0.18em] text-slate-500 uppercase">
            Before
          </p>
          <p className="stat-num mt-1 text-2xl leading-none text-crit">
            {document.comparison.failing_before}
          </p>
          <p className="mt-1 text-[11px] text-slate-500">failing scenarios recorded</p>
        </div>
        <div className="flex items-center">
          <IconChevronRight className="h-5 w-5 text-slate-600" />
        </div>
        <div
          className={`panel-inset flex flex-col justify-center px-3 py-2.5 ${
            improved ? 'border-safe/40' : 'border-warn/40'
          }`}
        >
          <p className="text-[10px] font-semibold tracking-[0.18em] text-slate-500 uppercase">
            After mitigation
          </p>
          <p
            className={`stat-num mt-1 text-2xl leading-none ${
              improved ? 'text-safe' : 'text-warn'
            }`}
          >
            {document.comparison.failing_after}
          </p>
          <p className="mt-1 text-[11px] text-slate-500">
            {document.comparison.scenarios_retested} scenarios retested
          </p>
        </div>
      </div>

      <div className="overflow-hidden rounded-md border border-edge/80">
        <table className="w-full text-left text-xs">
          <thead className="bg-void/80 text-slate-500">
            <tr>
              <th className="px-2 py-1.5 font-medium">Scenario</th>
              <th className="px-2 py-1.5 font-medium">Before</th>
              <th className="px-2 py-1.5 font-medium">After</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-edge/70">
            {document.rows.map((row) => (
              <tr key={row.failure_id}>
                <td className="break-all px-2 py-1.5 text-slate-300">{row.case_label}</td>
                <td className="px-2 py-1.5">
                  <StatusBadge label={row.status_before} tone="crit" />
                </td>
                <td className="px-2 py-1.5">
                  <StatusBadge
                    label={row.status_after}
                    tone={row.status_after === 'safe' ? 'ok' : 'crit'}
                  />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className={`text-sm ${improved ? 'text-safe' : 'text-warn'}`}>
        {document.verdict}
      </p>
      <p className="text-[11px] text-slate-500">{document.note}</p>
      <p className="text-[11px] text-slate-500">
        A zero-failure result applies to the tested scenarios only. It is not a certification of
        plant safety, and SafeFlux never actuates real equipment.
      </p>
    </div>
  )
}
