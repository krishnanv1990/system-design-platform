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
    const token = searchParams.get('token')
    const error = searchParams.get('error')

    if (error) {
      console.error('Authentication error:', error)
      navigate('/login?error=' + encodeURIComponent(error))
      return
    }

    if (token) {
      login(token)
      navigate('/problems')
    } else {
      navigate('/login')
    }
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
