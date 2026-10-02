import { Suspense } from 'react'
import { AuthProvider } from './auth/AuthProvider'
import { ErrorBoundary } from './components/ErrorBoundary'
import { LoadingFallback } from './components/LoadingFallback'
import AppRoutes from './routes'

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <Suspense fallback={<LoadingFallback />}>
          <AppRoutes />
        </Suspense>
      </AuthProvider>
    </ErrorBoundary>
  )
}
