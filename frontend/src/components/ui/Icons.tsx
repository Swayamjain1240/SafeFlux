/**
 * Inline stroke icons (visual transformation).
 *
 * Deliberately dependency-free: one consistent 24px grid, 1.6 stroke, no
 * filled shapes, so the shell reads as engineering software rather than a
 * marketing template. Every icon is decorative (`aria-hidden`) — labels always
 * carry the meaning.
 */

import type { ReactNode, SVGProps } from 'react'

type IconProps = SVGProps<SVGSVGElement>

function Base({ children, ...props }: IconProps & { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.6}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      {...props}
    >
      {children}
    </svg>
  )
}

export function IconDashboard(props: IconProps) {
  return (
    <Base {...props}>
      <rect x="3" y="3" width="8" height="8" rx="1.5" />
      <rect x="13" y="3" width="8" height="5" rx="1.5" />
      <rect x="13" y="10" width="8" height="11" rx="1.5" />
      <rect x="3" y="13" width="8" height="8" rx="1.5" />
    </Base>
  )
}

export function IconPlant(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M4 20h16" />
      <path d="M6 20V9.5A2.5 2.5 0 0 1 8.5 7h4A2.5 2.5 0 0 1 15 9.5V20" />
      <path d="M15 12h2.5A2.5 2.5 0 0 1 20 14.5V20" />
      <path d="M9 7V4.5" />
    </Base>
  )
}

export function IconMonitor(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M3 12h3.5l2-5 3 10 2.5-7 1.5 2H21" />
    </Base>
  )
}

export function IconAnalyze(props: IconProps) {
  return (
    <Base {...props}>
      <circle cx="10.5" cy="10.5" r="6.5" />
      <path d="m20 20-4.7-4.7" />
      <path d="M10.5 7.5v6M7.5 10.5h6" />
    </Base>
  )
}

export function IconHistory(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M3.5 12a8.5 8.5 0 1 0 2.6-6.1" />
      <path d="M3.5 4.5V9H8" />
      <path d="M12 8v4.5l3 1.8" />
    </Base>
  )
}

export function IconReport(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M7 3.5h7.5L19 8v12.5H7z" />
      <path d="M14.5 3.5V8H19" />
      <path d="M9.5 12.5h7M9.5 16h7" />
    </Base>
  )
}

export function IconShield(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M12 3 5.5 5.6v5.6c0 4.4 2.8 7.6 6.5 8.8 3.7-1.2 6.5-4.4 6.5-8.8V5.6L12 3Z" />
      <path d="m9.2 11.8 2 2 3.6-3.8" />
    </Base>
  )
}

export function IconAlert(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M12 4 2.8 19.5h18.4L12 4Z" />
      <path d="M12 10v4.5" />
      <path d="M12 17.4h.01" />
    </Base>
  )
}

export function IconPulse(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M3 12.5h4l1.8-4.5 3.4 9 2.4-6 1.4 3h5" />
    </Base>
  )
}

export function IconSignOut(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M9 4.5H6.5A1.5 1.5 0 0 0 5 6v12a1.5 1.5 0 0 0 1.5 1.5H9" />
      <path d="M15 8.5 18.5 12 15 15.5" />
      <path d="M18.5 12H10" />
    </Base>
  )
}

export function IconDownload(props: IconProps) {
  return (
    <Base {...props}>
      <path d="M12 4v10.5" />
      <path d="m7.5 10.5 4.5 4.5 4.5-4.5" />
      <path d="M5 19.5h14" />
    </Base>
  )
}

export function IconChevronRight(props: IconProps) {
  return (
    <Base {...props}>
      <path d="m9 5.5 6.5 6.5L9 18.5" />
    </Base>
  )
}
