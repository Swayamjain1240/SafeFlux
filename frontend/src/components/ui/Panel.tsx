import type { ReactNode } from 'react'

/**
 * Standard instrument panel (visual transformation).
 *
 * One surface language for the whole product: thin technical border, compact
 * uppercase caption, optional right-side actions. Panels fill their grid cell
 * (`min-h-0`) so the one-viewport contract still holds — content scrolls inside
 * a panel, never the page.
 */
export function Panel({
  title,
  hint,
  actions,
  children,
  className = '',
  bodyClassName = '',
  scroll = false,
  dense = false,
}: {
  title?: string
  hint?: string
  actions?: ReactNode
  children: ReactNode
  className?: string
  bodyClassName?: string
  /** Allow the body to scroll internally when its content can exceed the cell. */
  scroll?: boolean
  /** Tighter padding for stacked instrumentation blocks. */
  dense?: boolean
}) {
  return (
    <section className={`panel flex min-h-0 flex-col ${className}`}>
      {(title || actions) && (
        <header className="flex shrink-0 items-center justify-between gap-2 border-b border-edge/80 px-3 py-2">
          <div className="min-w-0">
            {title && (
              <h2 className="truncate text-[11px] font-semibold tracking-[0.14em] text-slate-400 uppercase">
                {title}
              </h2>
            )}
            {hint && <p className="truncate text-[11px] text-slate-500">{hint}</p>}
          </div>
          {actions && <div className="flex shrink-0 items-center gap-1.5">{actions}</div>}
        </header>
      )}
      <div
        className={[
          'min-h-0 flex-1',
          dense ? 'p-2.5' : 'p-3',
          scroll ? 'overflow-y-auto' : '',
          bodyClassName,
        ]
          .filter(Boolean)
          .join(' ')}
      >
        {children}
      </div>
    </section>
  )
}
