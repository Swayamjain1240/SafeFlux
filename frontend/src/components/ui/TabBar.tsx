export interface TabItem<T extends string> {
  id: T
  label: string
}

/**
 * Viewport-safe panel switcher (Part 6). Used instead of stacking panels
 * vertically, which is how the one-viewport rule is honoured on tablet and
 * mobile: one primary panel at a time, with every panel still reachable.
 *
 * Visual transformation: the switcher reads as part of the instrument panel —
 * a recessed track with one accent-lit active tab — rather than a button row.
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
      className="flex shrink-0 gap-1 overflow-x-auto rounded-md border border-edge bg-panel/80 p-1"
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
              'flex-1 rounded px-3 py-1.5 text-xs font-medium whitespace-nowrap transition',
              isActive
                ? 'bg-accent/12 text-accent ring-1 ring-accent/30'
                : 'text-slate-400 hover:bg-surface-2/70 hover:text-slate-100',
            ].join(' ')}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}
