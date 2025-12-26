/**
 * Authentication context and provider
 * Manages user authentication state across the application
 */

import { createContext, useContext, useState, useEffect, ReactNode } from 'react'
import { User } from '../types'
import { authApi } from '../api/client'

interface AuthContextType {
  user: User | null
  loading: boolean
  login: (token: string) => void
  logout: () => void
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

/**
 * Auth provider component
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)

  // Check for existing token on mount
  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('token')
      if (token) {
        try {
          const userData = await authApi.getCurrentUser()
          setUser(userData)
        } catch (error) {
          localStorage.removeItem('token')
        }
      }
      setLoading(false)
    }
    checkAuth()
  }, [])

  const login = (token: string) => {
    localStorage.setItem('token', token)
    // Fetch user data after login
    authApi.getCurrentUser().then(setUser)
  }

  const logout = async () => {
    try {
      await authApi.logout()
    } catch {
      // Ignore logout errors
    }
    localStorage.removeItem('token')
    setUser(null)
  }

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

/**
 * Hook to access auth context
 */
export function useAuth() {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
