export function LoadingFallback({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex h-full min-h-[40vh] w-full items-center justify-center gap-3 text-slate-400">
      <span
        aria-hidden="true"
        className="h-5 w-5 animate-spin rounded-full border-2 border-slate-600 border-t-cyan-400"
      />
      <span className="text-sm">{label}</span>
    </div>
  )
}
