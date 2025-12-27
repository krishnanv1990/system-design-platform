import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './components/AuthContext'
import Layout from './components/Layout'
import ProblemList from './pages/ProblemList'
import ProblemDetail from './pages/ProblemDetail'
import Submission from './pages/Submission'
import Results from './pages/Results'
import AuthCallback from './pages/AuthCallback'
import Login from './pages/Login'
import AdminDashboard from './pages/AdminDashboard'

/**
 * Protected route wrapper - redirects to login if not authenticated
 * In demo mode, allows access without authentication
 */
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { user, loading, demoMode } = useAuth()

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
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
          path="admin"
          element={
            <ProtectedRoute>
              <AdminDashboard />
            </ProtectedRoute>
          }
        />
      </Route>
    </Routes>
  )
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  )
}
