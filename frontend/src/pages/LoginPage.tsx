import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { ErrorPanel } from '../components/ErrorPanel'
import { FormField } from '../components/FormField'
import { validateLogin } from '../utils/validation'

export default function LoginPage() {
  const { signIn, status } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({})
  const [submitError, setSubmitError] = useState<unknown>(null)
  const [submitting, setSubmitting] = useState(false)

  if (status === 'authenticated') {
    return <Navigate to="/dashboard" replace />
  }

  async function handleSubmit(event: FormEvent) {
    event.preventDefault()
    const validation = validateLogin({ email, password })
    setErrors(validation)
    if (Object.keys(validation).length > 0) return

    setSubmitting(true)
    setSubmitError(null)
    try {
      await signIn(email.trim(), password)
      const from = (location.state as { from?: string } | null)?.from ?? '/dashboard'
      navigate(from, { replace: true })
    } catch (error) {
      setSubmitError(error)
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="flex h-full items-center justify-center px-4 py-6">
      <div className="w-full max-w-sm rounded-2xl border border-slate-800 bg-slate-900/60 p-6 shadow-xl">
        <h1 className="text-lg font-semibold text-white">Welcome back</h1>
        <p className="mt-1 text-xs text-slate-500">
          Sign in to review analyses, failures and evidence.
        </p>

        <form onSubmit={handleSubmit} noValidate className="mt-5 space-y-4">
          <FormField
            id="login-email"
            label="Email"
            type="email"
            value={email}
            onChange={setEmail}
            error={errors.email}
            autoComplete="email"
            placeholder="engineer@plant.example"
            required
          />
          <FormField
            id="login-password"
            label="Password"
            type="password"
            value={password}
            onChange={setPassword}
            error={errors.password}
            autoComplete="current-password"
            placeholder="••••••••"
            required
          />

          {submitError !== null && <ErrorPanel error={submitError} title="Sign-in failed" />}

          <button
            type="submit"
            disabled={submitting}
            className="w-full rounded-lg bg-cyan-500 px-4 py-2.5 text-sm font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? 'Signing in…' : 'Log in'}
          </button>
        </form>

        <p className="mt-4 text-center text-xs text-slate-500">
          No account?{' '}
          <Link to="/signup" className="text-cyan-400 hover:underline">
            Create one
          </Link>
        </p>

        <p className="mt-4 border-t border-slate-800 pt-3 text-center text-[11px] leading-relaxed text-slate-600">
          Sessions are held in a secure, HttpOnly cookie and expire automatically.
        </p>
      </div>
    </div>
  )
}
