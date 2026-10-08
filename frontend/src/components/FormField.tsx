interface FormFieldProps {
  id: string
  label: string
  value: string
  onChange: (value: string) => void
  type?: 'text' | 'email' | 'password'
  error?: string
  autoComplete?: string
  placeholder?: string
  maxLength?: number
  required?: boolean
}

/** Labeled, validated input with accessible error wiring (rule 6/7). */
export function FormField({
  id,
  label,
  value,
  onChange,
  type = 'text',
  error,
  autoComplete,
  placeholder,
  maxLength = 128,
  required,
}: FormFieldProps) {
  return (
    <div>
      <label htmlFor={id} className="mb-1 block text-xs font-medium text-slate-400">
        {label}
        {required && <span className="text-accent"> *</span>}
      </label>
      <input
        id={id}
        name={id}
        type={type}
        value={value}
        maxLength={maxLength}
        required={required}
        autoComplete={autoComplete}
        placeholder={placeholder}
        spellCheck={type === 'password' ? false : undefined}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        onChange={(event) => onChange(event.target.value)}
        className={[
          'w-full rounded-md border bg-void/70 px-3 py-2 text-sm text-slate-100 outline-none transition',
          'placeholder:text-slate-600 focus:border-accent/60',
          error ? 'border-crit/70' : 'border-edge-strong',
        ].join(' ')}
      />
      {error && (
        <p id={`${id}-error`} className="mt-1 text-xs text-crit">
          {error}
        </p>
      )}
    </div>
  )
}
