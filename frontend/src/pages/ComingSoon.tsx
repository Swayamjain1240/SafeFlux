import { Link } from 'react-router-dom'

/** Viewport-contained placeholder for routes that unlock in a later part. */
export default function ComingSoon({
  title,
  part,
}: {
  title: string
  part: number
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-3 px-4 text-center">
      <span className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-[11px] font-medium tracking-widest text-slate-400 uppercase">
        Part {part} of 10
      </span>
      <h1 className="text-2xl font-semibold text-slate-100">{title}</h1>
      <p className="max-w-md text-sm leading-relaxed text-slate-400">
        This workspace is scaffolded and route-protected. The feature itself arrives with build
        part {part}, after authentication (Part 2) unlocks the workspace.
      </p>
      <Link
        to="/dashboard"
        className="mt-2 rounded-lg border border-slate-700 px-4 py-2 text-sm text-slate-300 transition hover:bg-slate-800"
      >
        Back to dashboard
      </Link>
    </div>
  )
}
