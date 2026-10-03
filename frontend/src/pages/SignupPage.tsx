import { useState, type FormEvent } from 'react'
import { Link, Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { ErrorPanel } from '../components/ErrorPanel'
import { FormField } from '../components/FormField'
import { validateSignupStep1, validateSignupStep2 } from '../utils/validation'

const STEP_LABELS = ['Identity', 'Security']

/**
 * Multi-step wizard (one-viewport rule: long form → steps).
 * Step 1: name + email. Step 2: password + confirmation.
 */
export default function SignupPage() {
  const { signUp, status } = useAuth()
  const navigate = useNavigate()

  const [step, setStep] = useState(0)
  const [fullName, setFullName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [errors, setErrors] = useState<Record<string, string>>({})
  const [submitError, setSubmitError] = useState<unknown>(null)
  const [submitting, setSubmitting] = useState(false)

  if (status === 'authenticated') {
    return <Navigate to="/dashboard" replace />
  }

  function handleNext(event: FormEvent) {
    event.preventDefault()
    const validation = validateSignupStep1({ fullName, email })
    setErrors(validation)
    if (Object.keys(validation).length === 0) setStep(1)
  }

  function handleBack() {
    setErrors({})
    setStep(0)
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const validation = validateSignupStep2({ password, confirmPassword })
    setErrors(validation)
    if (Object.keys(validation).length > 0) return

    setSubmitting(true)
    setSubmitError(null)
    try {
      await signUp(fullName.trim(), email.trim(), password)
      navigate('/dashboard', { replace: true })
    } catch (error) {
      setSubmitError(error)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex h-full items-center justify-center px-4 py-6">
      <div className="w-full max-w-sm rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-xl">
        <div className="flex items-center justify-between">
          <h1 className="text-lg font-semibold text-white">Create account</h1>
          <span className="text-xs text-slate-500">
            Step {step + 1} of {STEP_LABELS.length} · {STEP_LABELS[step]}
          </span>
        </div>

        {/* Step indicator */}
        <div className="mt-3 flex gap-2" aria-hidden="true">
          {STEP_LABELS.map((label, index) => (
            <div
              key={label}
              className={`h-1 flex-1 rounded-full ${index <= step ? 'bg-cyan-400' : 'bg-slate-700'}`}
            />
          ))}
        </div>

        {step === 0 ? (
          <form onSubmit={handleNext} noValidate className="mt-5 space-y-4">
            <FormField
              id="signup-name"
              label="Full name"
              value={fullName}
              onChange={setFullName}
              error={errors.fullName}
              autoComplete="name"
              placeholder="Alex Engineer"
              required
            />
            <FormField
              id="signup-email"
              label="Email"
              type="email"
              value={email}
              onChange={setEmail}
              error={errors.email}
              autoComplete="email"
              placeholder="engineer@plant.example"
              required
            />
            <button
              type="submit"
              className="w-full rounded-lg bg-cyan-500 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400"
            >
              Continue
            </button>
          </form>
        ) : (
          <form onSubmit={handleSubmit} noValidate className="mt-5 space-y-4">
            <FormField
              id="signup-password"
              label="Password"
              type="password"
              value={password}
              onChange={setPassword}
              error={errors.password}
              autoComplete="new-password"
              placeholder="At least 8 characters"
              required
            />
            <FormField
              id="signup-confirm"
              label="Confirm password"
              type="password"
              value={confirmPassword}
              onChange={setConfirmPassword}
              error={errors.confirmPassword}
              autoComplete="new-password"
              placeholder="Repeat password"
              required
            />

            {submitError !== null && <ErrorPanel error={submitError} title="Sign-up failed" />}

            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleBack}
                className="flex-1 rounded-lg border border-slate-700 px-4 py-2.5 text-sm text-slate-300 transition hover:bg-slate-800"
              >
                Back
              </button>
              <button
                type="submit"
                disabled={submitting}
                className="flex-1 rounded-lg bg-cyan-500 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {submitting ? 'Creating…' : 'Create account'}
              </button>
            </div>
          </form>
        )}

        <p className="mt-4 text-center text-xs text-slate-500">
          Already registered?{' '}
          <Link to="/login" className="text-cyan-400 hover:underline">
            Log in
          </Link>
        </p>

        <p className="mt-4 border-t border-slate-800 pt-3 text-center text-[11px] leading-relaxed text-slate-600">
          Passwords are hashed server-side with Argon2 and never stored in plain text.
        </p>
      </div>
    </div>
  )
}
