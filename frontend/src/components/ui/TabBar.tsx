export interface TabItem<T extends string> {
  id: T
  label: string
}

/**
 * Viewport-safe panel switcher (Part 6). Used instead of stacking panels
 * vertically, which is how the one-viewport rule is honoured on tablet and
 * mobile: one primary panel at a time, with every panel still reachable.
 */
export function TabBar<T extends string>({
  tabs,
  active,
  onChange,
  label,
}: {
  tabs: readonly TabItem<T>[]
  active: T
  onChange: (id: T) => void
  label: string
}) {
  return (
    <div
      role="tablist"
      aria-label={label}
      className="flex shrink-0 gap-1 overflow-x-auto rounded-lg border border-slate-800 bg-slate-900/60 p-1"
    >
      {tabs.map((tab) => {
        const isActive = tab.id === active
        return (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={isActive}
            onClick={() => onChange(tab.id)}
            className={[
              'flex-1 rounded-md px-3 py-1.5 text-xs font-medium whitespace-nowrap transition',
              isActive
                ? 'bg-cyan-500/15 text-cyan-300 ring-1 ring-cyan-500/30'
                : 'text-slate-400 hover:text-slate-200',
            ].join(' ')}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}
