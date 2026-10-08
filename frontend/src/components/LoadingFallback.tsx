export function LoadingFallback({ label = 'Loading…' }: { label?: string }) {
  return (
    <div className="flex h-full min-h-[40vh] w-full flex-col items-center justify-center gap-3 text-slate-400">
      <span
        aria-hidden="true"
        className="h-5 w-5 animate-spin rounded-full border-2 border-edge-strong border-t-accent"
      />
      <span className="text-xs tracking-[0.18em] uppercase">{label}</span>
    </div>
  )
}
