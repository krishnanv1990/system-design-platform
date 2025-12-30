import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './components/AuthContext'
import { ConfirmProvider } from './components/ui/confirm-dialog'
import ErrorBoundary from './components/ErrorBoundary'
import CookieNotice from './components/CookieNotice'
import Layout from './components/Layout'
import ProblemList from './pages/ProblemList'
import ProblemDetail from './pages/ProblemDetail'
import Submission from './pages/Submission'
import Results from './pages/Results'
import AuthCallback from './pages/AuthCallback'
import Login from './pages/Login'
import UsageDashboard from './pages/UsageDashboard'
import TermsOfService from './pages/TermsOfService'
import PrivacyPolicy from './pages/PrivacyPolicy'
import AccountSettings from './pages/AccountSettings'
import NotFound from './pages/NotFound'
import DistributedProblemList from './pages/DistributedProblemList'
import DistributedProblemDetail from './pages/DistributedProblemDetail'
import DistributedSubmissionResults from './pages/DistributedSubmissionResults'

/**
 * Protected route wrapper - redirects to login if not authenticated
 * In demo mode, allows access without authentication
 */
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading, demoMode } = useAuth()

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4" role="status" aria-label="Loading">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
        <p className="text-muted-foreground text-sm">Loading...</p>
      </div>
    )
  }

  // In demo mode or if user is authenticated, allow access
  if (demoMode || user) {
    return <>{children}</>
  }

  return <Navigate to="/login" replace />
}

/**
 * Main application component with routing
 */
function AppRoutes() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/auth/callback" element={<AuthCallback />} />

      {/* Protected routes */}
      <Route path="/" element={<Layout />}>
        <Route index element={<Navigate to="/problems" replace />} />
        <Route
          path="problems"
          element={
            <ProtectedRoute>
              <ProblemList />
            </ProtectedRoute>
          }
        />
        <Route
          path="problems/:id"
          element={
            <ProtectedRoute>
              <ProblemDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="problems/:id/submit"
          element={
            <ProtectedRoute>
              <Submission />
            </ProtectedRoute>
          }
        />
        <Route
          path="submissions/:id/results"
          element={
            <ProtectedRoute>
              <Results />
            </ProtectedRoute>
          }
        />
        <Route
          path="usage"
          element={
            <ProtectedRoute>
              <UsageDashboard />
            </ProtectedRoute>
          }
        />
        {/* Distributed consensus problems */}
        <Route
          path="distributed"
          element={
            <ProtectedRoute>
              <DistributedProblemList />
            </ProtectedRoute>
          }
        />
        <Route
          path="distributed/:id"
          element={
            <ProtectedRoute>
              <DistributedProblemDetail />
            </ProtectedRoute>
          }
        />
        <Route
          path="distributed/submissions/:id"
          element={
            <ProtectedRoute>
              <DistributedSubmissionResults />
            </ProtectedRoute>
          }
        />
        {/* Account settings - protected */}
        <Route
          path="settings"
          element={
            <ProtectedRoute>
              <AccountSettings />
            </ProtectedRoute>
          }
        />
        {/* Legal pages - public but within layout */}
        <Route path="terms" element={<TermsOfService />} />
        <Route path="privacy" element={<PrivacyPolicy />} />

        {/* 404 catch-all within layout */}
        <Route path="*" element={<NotFound />} />
      </Route>

      {/* Global 404 for routes outside layout */}
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <ConfirmProvider>
          <AppRoutes />
          <CookieNotice />
        </ConfirmProvider>
      </AuthProvider>
    </ErrorBoundary>
  )
}
