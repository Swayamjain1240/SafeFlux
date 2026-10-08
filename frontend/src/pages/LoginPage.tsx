import { useState, type FormEvent } from 'react'
import { Link, Navigate, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { AuthShell } from '../components/auth/AuthShell'
import { ErrorPanel } from '../components/ErrorPanel'
import { FormField } from '../components/FormField'
import { Logo } from '../components/Logo'
import { IconChevronRight } from '../components/ui/Icons'
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
    <AuthShell>
      <div className="w-full max-w-sm">
        <div className="mb-5 flex items-center gap-3 lg:hidden">
          <Logo />
        </div>

        <div className="panel p-5 sm:p-6">
          <p className="text-[10px] font-semibold tracking-[0.24em] text-accent/80 uppercase">
            Workspace access
          </p>
          <h1 className="mt-1 text-lg font-semibold tracking-tight text-white">Welcome back</h1>
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
              className="inline-flex w-full items-center justify-center gap-2 rounded-md bg-accent px-4 py-2.5 text-sm font-semibold text-void transition enabled:hover:bg-accent-soft disabled:cursor-not-allowed disabled:opacity-60"
            >
              {submitting ? 'Signing in…' : 'Log in'}
              {!submitting && <IconChevronRight className="h-4 w-4" />}
            </button>
          </form>

          <p className="mt-4 text-center text-xs text-slate-500">
            No account?{' '}
            <Link to="/signup" className="text-accent hover:underline">
              Create one
            </Link>
          </p>
        </div>

        <p className="mt-4 text-center text-[11px] leading-relaxed text-slate-600">
          Sessions are held in a secure, HttpOnly cookie and expire automatically.
        </p>
      </div>
    </AuthShell>
  )
}
