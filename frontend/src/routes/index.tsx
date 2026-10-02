import { Route, Routes } from 'react-router-dom'
import AppLayout from '../layouts/AppLayout'
import PublicLayout from '../layouts/PublicLayout'
import ComingSoon from '../pages/ComingSoon'
import DashboardPage from '../pages/DashboardPage'
import LandingPage from '../pages/LandingPage'
import LoginPage from '../pages/LoginPage'
import NotFoundPage from '../pages/NotFoundPage'
import SignupPage from '../pages/SignupPage'
import ProtectedRoute from './ProtectedRoute'

/** Route table mirrors docs/ARCHITECTURE.md §4 (public vs protected). */
export default function AppRoutes() {
  return (
    <Routes>
      <Route element={<PublicLayout />}>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/signup" element={<SignupPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>

      <Route element={<ProtectedRoute />}>
        <Route element={<AppLayout />}>
          <Route path="/dashboard" element={<DashboardPage />} />
          <Route path="/plant" element={<ComingSoon title="Plant setup" part={3} />} />
          <Route path="/monitor" element={<ComingSoon title="Live monitoring" part={5} />} />
          <Route path="/analysis/new" element={<ComingSoon title="New analysis" part={7} />} />
          <Route
            path="/analysis/:id/live"
            element={<ComingSoon title="Live autonomous investigation" part={8} />}
          />
          <Route
            path="/analysis/:id/failures/:failureId"
            element={<ComingSoon title="Failure detail" part={7} />}
          />
          <Route
            path="/analysis/:id/investigation"
            element={<ComingSoon title="Root-cause investigation" part={9} />}
          />
          <Route
            path="/analysis/:id/safeguards"
            element={<ComingSoon title="Safeguard verification" part={9} />}
          />
          <Route
            path="/analysis/:id/reverify"
            element={<ComingSoon title="Re-verification" part={9} />}
          />
          <Route path="/history" element={<ComingSoon title="Analysis history" part={6} />} />
          <Route path="/reports/:id" element={<ComingSoon title="Engineering report" part={9} />} />
        </Route>
      </Route>
    </Routes>
  )
}
