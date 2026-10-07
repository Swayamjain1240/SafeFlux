import { useMemo, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { ApiError } from '../api/client'
import { StatePanel } from '../components/ui/StatePanel'
import { useReverify, useResultDocument } from '../hooks/useAnalyses'
import { MITIGATION_FIELDS, type ReverifyDocument } from '../types/analysis'

/**
 * Re-verification (Part 9) — the engineer changes a simulated mitigation and
 * the backend re-runs *the parent's failing scenarios* with it applied.
 *
 * The comparison shows the real before/after per case, and the verdict line is
 * the backend's fixed sentence — never a guarantee. Mitigation inputs are
 * bounded on the client too, but the server re-checks every key and bound.
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
  const canSubmit = Boolean(id) && hasFailures && Object.keys(payload).length > 0 && !reverify.isPending

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
      <header className="shrink-0">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="min-w-0">
            <h1 className="text-lg font-semibold text-slate-100">Re-verification</h1>
            <p className="truncate text-xs text-slate-400">{parent.goal}</p>
          </div>
          <Link
            to={`/analysis/${id}/safeguards`}
            className="rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-300 transition hover:bg-slate-800"
          >
            Safeguards
          </Link>
        </div>
      </header>

      <section className="min-h-0 flex-1 overflow-y-auto rounded-xl border border-slate-800 bg-slate-900/50 p-4">
        {!hasFailures ? (
          <p className="rounded-lg border border-emerald-500/40 bg-emerald-500/5 px-3 py-2 text-sm text-emerald-200">
            The parent analysis found no failing scenarios, so there is nothing to re-verify: within
            the tested simulation scenarios, no unsafe condition was detected. {parent.notes?.length ? '' : ''}
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
      </section>
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
        them applied; nothing outside the simulation changes.
      </p>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="self-start rounded-lg border border-slate-700 px-3 py-1.5 text-xs text-slate-200 transition hover:bg-slate-800"
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
                <span>
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
                className="rounded-lg border border-slate-700 bg-slate-950 px-2 py-1.5 text-sm text-slate-100 focus:border-cyan-500/60 focus:outline-none"
              />
            </label>
          ))}
        </div>
      )}
      {error && (
        <p role="alert" className="rounded-lg border border-rose-600/50 bg-rose-950/40 px-3 py-2 text-sm text-rose-200">
          {error}
        </p>
      )}
      <div className="flex justify-end">
        <button
          type="button"
          disabled={!canSubmit}
          onClick={onSubmit}
          className="rounded-lg bg-cyan-500/20 px-5 py-2 text-sm font-semibold text-cyan-200 ring-1 ring-cyan-500/40 transition enabled:hover:bg-cyan-500/30 disabled:cursor-not-allowed disabled:opacity-40"
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
    <div className="mt-4 flex flex-col gap-2">
      <h2 className="text-xs font-semibold tracking-widest text-slate-400 uppercase">
        Before / after ({document.comparison.scenarios_retested} scenarios retested)
      </h2>
      <div className="overflow-hidden rounded-lg border border-slate-800">
        <table className="w-full text-left text-xs">
          <thead className="bg-slate-950/80 text-slate-500">
            <tr>
              <th className="px-2 py-1.5 font-medium">Scenario</th>
              <th className="px-2 py-1.5 font-medium">Before</th>
              <th className="px-2 py-1.5 font-medium">After</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/70">
            {document.rows.map((row) => (
              <tr key={row.failure_id}>
                <td className="break-all px-2 py-1.5 text-slate-300">{row.case_label}</td>
                <td className="px-2 py-1.5 text-rose-300">{row.status_before}</td>
                <td className={`px-2 py-1.5 ${row.status_after === 'safe' ? 'text-emerald-300' : 'text-rose-300'}`}>
                  {row.status_after}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className={`text-sm ${improved ? 'text-cyan-200' : 'text-amber-200'}`}>
        {document.verdict}
      </p>
      <p className="text-[11px] text-slate-500">{document.note}</p>
    </div>
  )
}
