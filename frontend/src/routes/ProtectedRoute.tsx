import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAuth } from '../auth/context'
import { LoadingFallback } from '../components/LoadingFallback'

/**
 * Frontend route guard — UX only. The backend independently authorizes
 * every protected endpoint (never trust client-side protection).
 */
export default function ProtectedRoute() {
  const { status } = useAuth()
  const location = useLocation()

  if (status === 'loading') {
    return <LoadingFallback label="Checking session…" />
  }

  if (status !== 'authenticated') {
    return (
      <Navigate
        to="/login"
        replace
        state={{ from: location.pathname + location.search }}
      />
    )
  }

  return <Outlet />
}
