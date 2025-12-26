/**
 * Main layout component with navigation
 */

import { Outlet, Link, useNavigate } from 'react-router-dom'
import { useAuth } from './AuthContext'

export default function Layout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()

  const handleLogout = () => {
    logout()
    navigate('/login')
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Navigation */}
      <nav className="bg-white shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            {/* Logo and main nav */}
            <div className="flex">
              <Link to="/" className="flex items-center">
                <span className="text-xl font-bold text-primary-600">
                  System Design Platform
                </span>
              </Link>
              <div className="hidden sm:ml-8 sm:flex sm:space-x-8">
                <Link
                  to="/problems"
                  className="inline-flex items-center px-1 pt-1 text-sm font-medium text-gray-900 border-b-2 border-transparent hover:border-primary-500"
                >
                  Problems
                </Link>
              </div>
            </div>

            {/* User menu */}
            <div className="flex items-center">
              {user && (
                <div className="flex items-center space-x-4">
                  {user.avatar_url && (
                    <img
                      src={user.avatar_url}
                      alt={user.name || 'User'}
                      className="w-8 h-8 rounded-full"
                    />
                  )}
                  <span className="text-sm text-gray-700">{user.name || user.email}</span>
                  <button
                    onClick={handleLogout}
                    className="text-sm text-gray-500 hover:text-gray-700"
                  >
                    Logout
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </nav>

      {/* Main content */}
      <main className="max-w-7xl mx-auto py-6 sm:px-6 lg:px-8">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="bg-white border-t mt-auto">
        <div className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8">
          <p className="text-center text-sm text-gray-500">
            System Design Interview Platform - Practice and master system design
          </p>
        </div>
      </footer>
    </div>
  )
}
