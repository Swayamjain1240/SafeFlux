import { useState, type ReactNode } from 'react'
import { TabBar } from '../components/ui/TabBar'
import {
  MODE_HINTS,
  MODE_LABELS,
  MODES,
  axisCount,
  defaultSteps,
  formatNumber,
  parseNumberInput,
  parseOptionalNumberInput,
  plannedScenarios,
  type AxisDraft,
  type SearchDraft,
  type SearchPreset,
} from './plan'
import type { SearchCapabilities, SearchMode, SearchVariable } from '../types/search'

const FIELD_CLASS =
  'w-full rounded-md border border-slate-700 bg-slate-950/60 px-2 py-1 text-xs text-slate-200 focus:border-cyan-500/60 focus:outline-none'
const LABEL_CLASS = 'text-[10px] tracking-wide text-slate-500 uppercase'

function Field({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className={LABEL_CLASS}>{label}</span>
      {children}
      {hint && <span className="mt-0.5 block text-[10px] text-slate-500">{hint}</span>}
    </label>
  )
}

function specFor(capabilities: SearchCapabilities, variable: SearchVariable) {
  return capabilities.variables.find((spec) => spec.variable === variable) ?? null
}

/**
 * Plan editor (Part 7).
 *
 * Every control is rendered from GET /searches/capabilities, so the browser can
 * only offer variables the server allowlists, and the allowlisted range of each
 * variable is shown next to the steps — the point of Part 7 is that the engineer
 * picks a *variable and a resolution*, not a list of values.
 */
export function SearchControls({
  capabilities,
  plants,
  presets,
  presetId,
  draft,
  issues,
  running,
  onPreset,
  onDraft,
  onRun,
}: {
  capabilities: SearchCapabilities
  plants: { id: string; name: string }[]
  presets: SearchPreset[]
  presetId: string
  draft: SearchDraft
  issues: string[]
  running: boolean
  onPreset: (preset: SearchPreset) => void
  onDraft: (patch: Partial<SearchDraft>) => void
  onRun: () => void
}) {
  const [advanced, setAdvanced] = useState(false)
  const preset = presets.find((item) => item.id === presetId) ?? null
  const shape = axisCount(draft.mode, draft.axes)
  const planned = plannedScenarios(draft.mode, draft.axes)

  function updateAxis(index: number, patch: Partial<AxisDraft>) {
    const axes = draft.axes.map((axis, position) => (position === index ? { ...axis, ...patch } : axis))
    onDraft({ axes })
  }

  function switchMode(mode: SearchMode) {
    // A mode change rebuilds the axes: a sweep is meaningless in a grid and a
    // grid is too large for a sweep, so the client never sends a mismatched plan.
    if (mode === 'sensitivity') return onDraft({ mode, axes: [] })
    if (mode === 'combinations') {
      const axes = draft.axes.length >= 2 ? draft.axes.slice(0, 2) : [
        draft.axes[0] ?? { variable: 'cooling_factor' as SearchVariable, steps: 3 },
        { variable: 'feed_factor' as SearchVariable, steps: 3 },
      ]
      return onDraft({ mode, axes: axes.map((axis) => ({ ...axis, steps: defaultSteps('combinations', axis.steps) })) })
    }
    return onDraft({ mode, axes: [draft.axes[0] ?? { variable: 'cooling_factor' as SearchVariable, steps: 9 }] })
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-2">
      <div className="min-h-0 flex-1 space-y-2.5 overflow-y-auto pr-1">
        <Field label="Plant">
          <select
            value={draft.plantId ?? ''}
            onChange={(event) => onDraft({ plantId: event.target.value || null })}
            className={FIELD_CLASS}
          >
            <option value="">Select a plant…</option>
            {plants.map((plant) => (
              <option key={plant.id} value={plant.id}>
                {plant.name}
              </option>
            ))}
          </select>
        </Field>

        <Field label="Preset" hint={preset?.hint}>
          <select
            value={presetId}
            onChange={(event) => {
              const chosen = presets.find((item) => item.id === event.target.value)
              if (chosen) onPreset(chosen)
            }}
            className={FIELD_CLASS}
          >
            {presets.map((item) => (
              <option key={item.id} value={item.id}>
                {item.label}
              </option>
            ))}
          </select>
        </Field>

        <div>
          <span className={LABEL_CLASS}>Search method</span>
          <div className="mt-1">
            <TabBar
              tabs={MODES.map((mode) => ({ id: mode, label: MODE_LABELS[mode] }))}
              active={draft.mode}
              onChange={switchMode}
              label="Search method"
            />
          </div>
          <p className="mt-1 text-[10px] text-slate-500">{MODE_HINTS[draft.mode]}</p>
        </div>

        {draft.mode === 'sensitivity' ? (
          <p className="rounded-lg border border-slate-800 bg-slate-900/50 p-2 text-xs text-slate-400">
            The server perturbs all {capabilities.variables.length} allowlisted variables one at a time and ranks
            their influence. No axis is chosen here.
          </p>
        ) : (
          <div className="space-y-2">
            {draft.axes.slice(0, shape.max || 1).map((axis, index) => {
              const spec = specFor(capabilities, axis.variable)
              return (
                <div key={`${index}-${axis.variable}`} className="rounded-lg border border-slate-800 bg-slate-900/40 p-2">
                  <Field
                    label={index === 0 ? 'Variable' : `Variable ${index + 1}`}
                    hint={
                      spec
                        ? `${spec.label} · allowlisted ${formatNumber(spec.minimum, 2)}–${formatNumber(spec.maximum, 2)} ${spec.unit}${
                            spec.is_observation_only ? ' · observation only' : spec.is_safeguard ? ' · safeguard' : ''
                          }`
                        : undefined
                    }
                  >
                    <select
                      value={axis.variable}
                      onChange={(event) => updateAxis(index, { variable: event.target.value as SearchVariable })}
                      className={FIELD_CLASS}
                    >
                      {capabilities.variables.map((item) => (
                        <option key={item.variable} value={item.variable}>
                          {item.label}
                        </option>
                      ))}
                    </select>
                  </Field>
                  <div className="mt-1.5">
                    <Field label={`Steps (whole range, ${draft.mode === 'combinations' ? '2–7' : '2–25'})`}>
                      <input
                        type="number"
                        min={2}
                        max={draft.mode === 'combinations' ? 7 : 25}
                        value={axis.steps}
                        onChange={(event) =>
                          updateAxis(index, { steps: defaultSteps(draft.mode, parseNumberInput(event.target.value, 2)) })
                        }
                        className={FIELD_CLASS}
                      />
                    </Field>
                  </div>
                </div>
              )
            })}
            {draft.mode === 'combinations' && draft.axes.length === 1 && (
              <button
                type="button"
                onClick={() => updateAxis(1, { variable: 'feed_factor' as SearchVariable, steps: 3 })}
                className="w-full rounded-lg border border-slate-700 px-2 py-1.5 text-xs text-slate-300 transition hover:bg-slate-800"
              >
                Add second variable
              </button>
            )}
          </div>
        )}

        <button
          type="button"
          onClick={() => setAdvanced((open) => !open)}
          aria-expanded={advanced}
          className="flex w-full items-center justify-between rounded-lg border border-slate-800 px-2 py-1.5 text-xs text-slate-400 transition hover:bg-slate-800/60"
        >
          <span>Advanced plan and budgets</span>
          <span aria-hidden="true">{advanced ? '−' : '+'}</span>
        </button>

        {advanced && (
          <div className="space-y-2 rounded-lg border border-slate-800 bg-slate-900/40 p-2">
            <div className="grid grid-cols-2 gap-2">
              <Field label="Duration (s)">
                <input
                  type="number"
                  min={1}
                  value={draft.durationS}
                  onChange={(event) => onDraft({ durationS: parseNumberInput(event.target.value, 0) })}
                  className={FIELD_CLASS}
                />
              </Field>
              <Field label="Time step (s)" hint={`min ${formatNumber(capabilities.limits.min_time_step_s, 3)}`}>
                <input
                  type="number"
                  min={capabilities.limits.min_time_step_s}
                  step="0.05"
                  value={draft.timeStepS}
                  onChange={(event) => onDraft({ timeStepS: parseNumberInput(event.target.value, 0) })}
                  className={FIELD_CLASS}
                />
              </Field>
            </div>

            <Field label="Label">
              <input
                value={draft.label}
                maxLength={120}
                onChange={(event) => onDraft({ label: event.target.value })}
                className={FIELD_CLASS}
              />
            </Field>

            {draft.mode === 'sweep' && (
              <label className="flex items-center gap-2 text-xs text-slate-300">
                <input
                  type="checkbox"
                  checked={draft.refine}
                  onChange={(event) => onDraft({ refine: event.target.checked })}
                />
                Refine the boundary (bisection where monotonic, densify otherwise)
              </label>
            )}

            <div className="grid grid-cols-2 gap-2">
              <Field label="Refinement depth" hint={`configured max ${capabilities.limits.max_refinement_depth}`}>
                <input
                  type="number"
                  min={0}
                  max={capabilities.limits.max_refinement_depth}
                  value={draft.refinementDepth ?? ''}
                  onChange={(event) => onDraft({ refinementDepth: parseOptionalNumberInput(event.target.value) })}
                  placeholder="server default"
                  className={FIELD_CLASS}
                />
              </Field>
              <Field label="Near-limit fraction" hint="0.5–1.0 · where amber starts">
                <input
                  type="number"
                  min={0.5}
                  max={1}
                  step="0.01"
                  value={draft.nearLimitFraction ?? ''}
                  onChange={(event) => onDraft({ nearLimitFraction: parseOptionalNumberInput(event.target.value) })}
                  placeholder="server default"
                  className={FIELD_CLASS}
                />
              </Field>
            </div>

            <div className="grid grid-cols-2 gap-2">
              <Field label="Scenario budget" hint={`configured max ${capabilities.limits.max_scenarios}`}>
                <input
                  type="number"
                  min={1}
                  value={draft.maxScenarios ?? ''}
                  onChange={(event) => onDraft({ maxScenarios: parseOptionalNumberInput(event.target.value) })}
                  placeholder="server default"
                  className={FIELD_CLASS}
                />
              </Field>
              <Field label="Timeout (s)" hint={`configured max ${capabilities.limits.timeout_s}`}>
                <input
                  type="number"
                  min={1}
                  value={draft.timeoutS ?? ''}
                  onChange={(event) => onDraft({ timeoutS: parseOptionalNumberInput(event.target.value) })}
                  placeholder="server default"
                  className={FIELD_CLASS}
                />
              </Field>
            </div>
            <p className="text-[10px] text-slate-500">
              Requesting more than the configured budget is rejected by the server, never silently clamped.
            </p>
          </div>
        )}

        <p className="text-[11px] text-slate-500">
          Planned: {planned > 0 ? `${planned} scenario(s) before refinement` : 'one pass over the allowlist'} · budgets{' '}
          {capabilities.limits.max_scenarios} scenarios / {capabilities.limits.timeout_s}s.
        </p>

        {issues.length > 0 && (
          <ul className="list-disc space-y-0.5 rounded-lg border border-amber-500/30 bg-amber-500/5 py-1.5 pr-2 pl-6 text-[11px] text-amber-200">
            {issues.map((issue) => (
              <li key={issue}>{issue}</li>
            ))}
          </ul>
        )}
      </div>

      <button
        type="button"
        onClick={onRun}
        disabled={running || issues.length > 0}
        className="shrink-0 rounded-lg bg-cyan-500/20 px-3 py-2 text-sm font-medium text-cyan-200 ring-1 ring-cyan-500/40 transition enabled:hover:bg-cyan-500/30 disabled:opacity-40"
      >
        {running ? 'Running search…' : 'Run search'}
      </button>
    </div>
  )
}
