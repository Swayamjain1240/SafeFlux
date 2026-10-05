import type { AssessmentRecord } from '../../analysis/assessmentStore'
import type { SafetyFinding, SafetyStatus } from '../../types/telemetry'
import { StatusBadge } from '../ui/StatusBadge'
import type { Tone } from '../../dashboard/viewState'

const STATUS_TONE: Record<SafetyStatus, Tone> = {
  safe: 'ok',
  near_limit: 'warn',
  safeguard_activated: 'warn',
  violation: 'crit',
}

function describe(finding: SafetyFinding): string {
  const measured = finding.measured_value
  if (measured === null) return `limit ${finding.limit}`
  return `${measured.toFixed(1)} / ${finding.limit} ${finding.type === 'level_pct' ? '%' : ''}`.trim()
}

/**
 * "Recent findings" (Part 6): the deterministic `SafetyFinding` evidence the
 * backend returned for the last run — variable, status, measured value and
 * configured limit. No record yet is an explicit empty state, not a blank box.
 */
export function FindingsPanel({ record, className = '' }: { record: AssessmentRecord | null; className?: string }) {
  if (!record) {
    return (
      <section className={`flex min-h-0 flex-col rounded-xl border border-slate-800 bg-slate-900/60 ${className}`}>
        <Header subtitle="None yet" />
        <div className="flex flex-1 items-center justify-center px-4 py-6 text-center">
          <div>
            <p className="text-sm text-slate-400">No safety findings recorded.</p>
            <p className="mt-1 text-xs text-slate-600">
              Run a scenario in the live monitor — its deterministic verdict appears here.
            </p>
          </div>
        </div>
      </section>
    )
  }

  const { findings, status, scenario_id: scenario } = record.safety

  return (
    <section className={`flex min-h-0 flex-col overflow-hidden rounded-xl border border-slate-800 bg-slate-900/60 ${className}`}>
      <Header
        subtitle={record.scenarioLabel ?? scenario ?? 'scenario'}
        status={status}
      />
      <ul className="min-h-0 flex-1 divide-y divide-slate-800 overflow-y-auto">
        {findings.map((finding) => (
          <li key={finding.type} className="flex items-center justify-between gap-2 px-3 py-2">
            <div className="min-w-0">
              <p className="truncate text-xs font-medium text-slate-200">
                {finding.type.replace('_', ' ')}
              </p>
              <p className="truncate font-mono text-[11px] text-slate-500">{describe(finding)}</p>
            </div>
            <StatusBadge label={finding.status.replace('_', ' ')} tone={STATUS_TONE[finding.status]} />
          </li>
        ))}
      </ul>
    </section>
  )
}

function Header({ subtitle, status }: { subtitle: string; status?: SafetyStatus }) {
  return (
    <div className="flex shrink-0 items-center justify-between gap-2 border-b border-slate-800 px-3 py-2">
      <p className="truncate text-[10px] tracking-wide text-slate-500 uppercase">Recent findings</p>
      <div className="flex min-w-0 items-center gap-2">
        <span className="truncate font-mono text-[11px] text-slate-500">{subtitle}</span>
        {status && (
          <StatusBadge label={status.replace('_', ' ')} tone={STATUS_TONE[status]} />
        )}
      </div>
    </div>
  )
}
