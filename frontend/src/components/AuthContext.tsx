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
  demoMode: boolean
  login: (token: string) => Promise<void>
  logout: () => void
  refreshUser: () => Promise<void>
}

const AuthContext = createContext<AuthContextType | undefined>(undefined)

/**
 * Auth provider component
 */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [loading, setLoading] = useState(true)
  const [demoMode, setDemoMode] = useState(false)

  // Check for demo mode and existing token on mount
  useEffect(() => {
    const checkAuth = async () => {
      // Skip auth check if we're on the callback page - let AuthCallback handle it
      if (window.location.hash.includes('/auth/callback')) {
        setLoading(false)
        return
      }

      try {
        // First check if demo mode is enabled
        const demoStatus = await authApi.getDemoStatus()
        setDemoMode(demoStatus.demo_mode)

        if (demoStatus.demo_mode) {
          // In demo mode, get the demo user directly
          const demoUser = await authApi.getDemoUser()
          setUser(demoUser)
          setLoading(false)
          return
        }

        // Normal auth flow
        const token = localStorage.getItem('token')
        if (token) {
          try {
            const userData = await authApi.getCurrentUser()
            setUser(userData)
          } catch (error) {
            localStorage.removeItem('token')
          }
        }
      } catch (error) {
        console.error('Auth check failed:', error)
      }
      setLoading(false)
    }
    checkAuth()
  }, [])

  const login = async (token: string) => {
    localStorage.setItem('token', token)
    // Fetch and wait for user data before completing login
    try {
      const userData = await authApi.getCurrentUser()
      setUser(userData)
    } catch (error) {
      // Remove invalid token and rethrow to let caller handle
      localStorage.removeItem('token')
      throw error
    }
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

  const refreshUser = async () => {
    try {
      if (demoMode) {
        const demoUser = await authApi.getDemoUser()
        setUser(demoUser)
      } else {
        const userData = await authApi.getCurrentUser()
        setUser(userData)
      }
    } catch (error) {
      console.error('Failed to refresh user:', error)
    }
  }

  return (
    <AuthContext.Provider value={{ user, loading, demoMode, login, logout, refreshUser }}>
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
