import type { AssessmentRecord } from '../../analysis/assessmentStore'
import type { SafetyFinding, SafetyStatus } from '../../types/telemetry'
import { StatusBadge } from '../ui/StatusBadge'
import { Panel } from '../ui/Panel'
import { IconAlert } from '../ui/Icons'
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
 *
 * Visual transformation: standard instrument panel, mono measurements and a
 * violation count in the header so a critical run is legible at a glance.
 */
export function FindingsPanel({
  record,
  className = '',
}: {
  record: AssessmentRecord | null
  className?: string
}) {
  if (!record) {
    return (
      <Panel title="Recent findings" hint="None yet" className={className}>
        <div className="flex h-full min-h-0 items-center justify-center px-4 py-6 text-center">
          <div>
            <p className="text-sm text-slate-400">No safety findings recorded.</p>
            <p className="mt-1 text-xs text-slate-600">
              Run a scenario in the live monitor — its deterministic verdict appears here.
            </p>
          </div>
        </div>
      </Panel>
    )
  }

  const { findings, status, scenario_id: scenario } = record.safety
  const violations = findings.filter((finding) => finding.status === 'violation').length

  return (
    <Panel
      title="Recent findings"
      hint={record.scenarioLabel ?? scenario ?? 'scenario'}
      className={className}
      bodyClassName="p-0"
      actions={
        <div className="flex items-center gap-1.5">
          {violations > 0 && (
            <span className="inline-flex items-center gap-1 rounded border border-crit/40 bg-crit/10 px-1.5 py-0.5 text-[10px] font-medium text-crit">
              <IconAlert className="h-3 w-3" />
              {violations} violation{violations === 1 ? '' : 's'}
            </span>
          )}
          <StatusBadge label={status.replace('_', ' ')} tone={STATUS_TONE[status]} />
        </div>
      }
    >
      <ul className="min-h-0 flex-1 divide-y divide-edge/60 overflow-y-auto">
        {findings.map((finding) => (
          <li key={finding.type} className="flex items-center justify-between gap-2 px-3 py-2">
            <div className="min-w-0">
              <p className="truncate text-xs font-medium text-slate-200">
                {finding.type.replace('_', ' ')}
              </p>
              <p className="truncate stat-num text-[11px] text-slate-500">{describe(finding)}</p>
            </div>
            <StatusBadge label={finding.status.replace('_', ' ')} tone={STATUS_TONE[finding.status]} />
          </li>
        ))}
      </ul>
    </Panel>
  )
}
