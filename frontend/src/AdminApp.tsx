/**
 * Admin Application
 * Separate admin UI for platform administrators
 */

import { Routes, Route, Navigate } from 'react-router-dom'
import { AuthProvider, useAuth } from './components/AuthContext'
import { ConfirmProvider } from './components/ui/confirm-dialog'
import ErrorBoundary from './components/ErrorBoundary'
import AdminLayout from './components/AdminLayout'
import AdminDashboard from './pages/AdminDashboard'
import AdminUsageDashboard from './pages/AdminUsageDashboard'
import AuthCallback from './pages/AuthCallback'
import Login from './pages/Login'
import NotFound from './pages/NotFound'

/**
 * Admin route wrapper - requires admin privileges
 */
function AdminRoute({ children }: { children: React.ReactNode }) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4" role="status" aria-label="Loading">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary"></div>
        <p className="text-muted-foreground text-sm">Loading...</p>
      </div>
    )
  }

  // Require authentication for admin
  if (!user) {
    return <Navigate to="/login" replace />
  }

  // Check if user is admin
  if (!user.is_admin) {
    return (
      <div className="flex flex-col items-center justify-center min-h-screen gap-4">
        <h1 className="text-2xl font-bold text-destructive">Access Denied</h1>
        <p className="text-muted-foreground">You do not have admin privileges.</p>
      </div>
    )
  }

  return <>{children}</>
}

/**
 * Admin application routes
 */
function AdminRoutes() {
  return (
    <Routes>
      {/* Public routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/auth/callback" element={<AuthCallback />} />

      {/* Admin routes */}
      <Route path="/" element={<AdminLayout />}>
        <Route index element={<Navigate to="/dashboard" replace />} />
        <Route
          path="dashboard"
          element={
            <AdminRoute>
              <AdminDashboard />
            </AdminRoute>
          }
        />
        <Route
          path="usage"
          element={
            <AdminRoute>
              <AdminUsageDashboard />
            </AdminRoute>
          }
        />
        <Route path="*" element={<NotFound />} />
      </Route>
    </Routes>
  )
}

export default function AdminApp() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <ConfirmProvider>
          <AdminRoutes />
        </ConfirmProvider>
      </AuthProvider>
    </ErrorBoundary>
  )
}
