/**
 * Failure sequence (visual transformation, §25).
 *
 * The failure page presents the violation as a *recorded* sequence: the
 * findings the deterministic safety engine actually produced for this case,
 * ordered by their own timestamps. Nothing is inferred, nothing is invented —
 * if the engine recorded two findings, the sequence shows two steps.
 *
 * The ordering is pure and unit-tested. The optional reveal animation is a
 * single GSAP tween that is killed (and the inline styles cleared) when the
 * panel unmounts, and it never runs at all under prefers-reduced-motion.
 */

import gsap from 'gsap'
import type { SafetyFinding } from '../types/analysis'

export type SequenceTone = 'crit' | 'warn' | 'ok' | 'idle'

export interface SequenceStep {
  index: number
  type: string
  label: string
  status: string
  tone: SequenceTone
  timestamp: number | null
  message: string
  measured: string | null
  limit: string | null
}

export function toneForStatus(status: string): SequenceTone {
  const normalised = status.toLowerCase()
  if (normalised.includes('violation') || normalised.includes('shutdown')) return 'crit'
  if (normalised.includes('near') || normalised.includes('safeguard')) return 'warn'
  if (normalised.includes('safe')) return 'ok'
  return 'idle'
}

/** Human label for a finding type, e.g. `high_pressure_alarm` → `High pressure alarm`. */
export function labelForType(type: string): string {
  const spaced = type.replaceAll('_', ' ').trim()
  if (spaced.length === 0) return type
  return spaced.charAt(0).toUpperCase() + spaced.slice(1)
}

function formatNumber(value: number | null | undefined): string | null {
  if (value === null || value === undefined || Number.isNaN(value)) return null
  return value.toFixed(2)
}

/**
 * Findings in the order the safety engine recorded them. Findings without a
 * timestamp keep their original relative order and sort last, so a missing
 * timestamp can never fabricate an ordering.
 */
export function orderFindingSequence(findings: readonly SafetyFinding[]): SafetyFinding[] {
  return findings
    .map((finding, index) => ({ finding, index }))
    .sort((a, b) => {
      const left = a.finding.timestamp_s
      const right = b.finding.timestamp_s
      const leftMissing = left === null || left === undefined
      const rightMissing = right === null || right === undefined
      if (leftMissing && rightMissing) return a.index - b.index
      if (leftMissing) return 1
      if (rightMissing) return -1
      if (left === right) return a.index - b.index
      return left - right
    })
    .map(({ finding }) => finding)
}

export function buildSequenceSteps(findings: readonly SafetyFinding[]): SequenceStep[] {
  return orderFindingSequence(findings).map((finding, index) => ({
    index: index + 1,
    type: finding.type,
    label: labelForType(finding.type),
    status: finding.status,
    tone: toneForStatus(finding.status),
    timestamp: finding.timestamp_s,
    message: finding.message,
    measured: formatNumber(finding.measured_value),
    limit: formatNumber(finding.limit),
  }))
}

/** True when the recorded evidence contains an actual violation. */
export function hasRecordedViolation(findings: readonly SafetyFinding[]): boolean {
  return findings.some((finding) => toneForStatus(finding.status) === 'crit')
}

/**
 * Progressive reveal of the sequence. Returns a cleanup that kills the tween
 * and strips the inline styles GSAP added, so unmounting can never leave an
 * element invisible.
 */
export function revealSequence(nodes: readonly HTMLElement[], reducedMotion: boolean): () => void {
  const visible = nodes.filter((node): node is HTMLElement => Boolean(node))
  if (reducedMotion || visible.length === 0) return () => undefined

  const tween = gsap.fromTo(
    visible,
    { autoAlpha: 0, y: 8 },
    { autoAlpha: 1, y: 0, duration: 0.3, stagger: 0.1, ease: 'power2.out', overwrite: true },
  )

  return () => {
    tween.kill()
    gsap.set(visible, { clearProps: 'all' })
  }
}
