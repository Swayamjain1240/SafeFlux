import { lazy, Suspense } from 'react'
import { Route, Routes } from 'react-router-dom'
import AppLayout from '../layouts/AppLayout'
import PublicLayout from '../layouts/PublicLayout'
import AnalysisNewPage from '../pages/AnalysisNewPage'
import DashboardPage from '../pages/DashboardPage'
import LandingPage from '../pages/LandingPage'
import LoginPage from '../pages/LoginPage'
import MonitorPage from '../pages/MonitorPage'
import NotFoundPage from '../pages/NotFoundPage'
import PlantSetupPage from '../pages/PlantSetupPage'
import SignupPage from '../pages/SignupPage'
import ProtectedRoute from './ProtectedRoute'
import { LoadingFallback } from '../components/LoadingFallback'

// Part 9 investigation views are route-level lazy: the dashboard/monitor bundle
// stays small, and these load only when the engineer opens one of them.
const AnalysisLivePage = lazy(() => import('../pages/AnalysisLivePage'))
const FailureDetailPage = lazy(() => import('../pages/FailureDetailPage'))
const InvestigationPage = lazy(() => import('../pages/InvestigationPage'))
const SafeguardsPage = lazy(() => import('../pages/SafeguardsPage'))
const ReverifyPage = lazy(() => import('../pages/ReverifyPage'))
const HistoryPage = lazy(() => import('../pages/HistoryPage'))
const ReportPage = lazy(() => import('../pages/ReportPage'))

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
          <Route path="/plant" element={<PlantSetupPage />} />
          <Route path="/monitor" element={<MonitorPage />} />
          <Route path="/analysis/new" element={<AnalysisNewPage />} />
          <Route
            path="/analysis/:id/live"
            element={
              <Suspense fallback={<LoadingFallback label="Loading live investigation…" />}>
                <AnalysisLivePage />
              </Suspense>
            }
          />
          <Route
            path="/analysis/:id/failures/:failureId"
            element={
              <Suspense fallback={<LoadingFallback label="Loading failure evidence…" />}>
                <FailureDetailPage />
              </Suspense>
            }
          />
          <Route
            path="/analysis/:id/investigation"
            element={
              <Suspense fallback={<LoadingFallback label="Loading investigation…" />}>
                <InvestigationPage />
              </Suspense>
            }
          />
          <Route
            path="/analysis/:id/safeguards"
            element={
              <Suspense fallback={<LoadingFallback label="Loading safeguard verification…" />}>
                <SafeguardsPage />
              </Suspense>
            }
          />
          <Route
            path="/analysis/:id/reverify"
            element={
              <Suspense fallback={<LoadingFallback label="Loading re-verification…" />}>
                <ReverifyPage />
              </Suspense>
            }
          />
          <Route
            path="/history"
            element={
              <Suspense fallback={<LoadingFallback label="Loading history…" />}>
                <HistoryPage />
              </Suspense>
            }
          />
          <Route
            path="/reports/:id"
            element={
              <Suspense fallback={<LoadingFallback label="Loading report…" />}>
                <ReportPage />
              </Suspense>
            }
          />
        </Route>
      </Route>
    </Routes>
  )
}
