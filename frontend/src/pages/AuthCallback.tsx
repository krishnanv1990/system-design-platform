/**
 * OAuth callback handler
 * Processes the token from Google OAuth redirect
 */

import { useEffect } from 'react'
import { useNavigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../components/AuthContext'

export default function AuthCallback() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { login } = useAuth()

  useEffect(() => {
    const handleAuth = async () => {
      // Clear any old tokens to prevent conflicts
      localStorage.removeItem('token')

      const token = searchParams.get('token')
      const error = searchParams.get('error')

      if (error) {
        console.error('Authentication error:', error)
        navigate('/login?error=' + encodeURIComponent(error))
        return
      }

      if (token) {
        try {
          await login(token)
          navigate('/problems')
        } catch (err) {
          console.error('Login failed:', err)
          navigate('/login?error=auth_failed')
        }
      } else {
        navigate('/login?error=no_token')
      }
    }
    handleAuth()
  }, [searchParams, login, navigate])

  return (
    <div className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600 mx-auto"></div>
        <p className="mt-4 text-gray-600">Completing authentication...</p>
      </div>
    </div>
  )
}
