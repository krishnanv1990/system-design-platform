import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Login from './Login'

// Mock the auth context
vi.mock('@/components/AuthContext', () => ({
  useAuth: () => ({
    user: null,
    demoMode: false,
    loading: false,
  }),
}))

// Mock the API client
vi.mock('@/api/client', () => ({
  authApi: {
    getGoogleAuthUrl: () => 'http://test.com/auth/google',
  },
}))

const renderWithRouter = (initialEntries: string[] = ['/login']) => {
  return render(
    <MemoryRouter initialEntries={initialEntries}>
      <Login />
    </MemoryRouter>
  )
}

describe('Login Page', () => {
  it('renders login page with title', () => {
    renderWithRouter()
    expect(screen.getByText('System Design Platform')).toBeInTheDocument()
    expect(screen.getByText('Master System Design Interviews')).toBeInTheDocument()
  })

  it('renders Google sign-in button', () => {
    renderWithRouter()
    expect(screen.getByRole('button', { name: /sign in with google/i })).toBeInTheDocument()
  })

  it('renders features list', () => {
    renderWithRouter()
    expect(screen.getByText(/Real system design problems/i)).toBeInTheDocument()
    expect(screen.getByText(/AI-powered validation/i)).toBeInTheDocument()
  })

  it('displays error message from URL params', () => {
    renderWithRouter(['/login?error=auth_failed'])
    expect(screen.getByText('Authentication Failed')).toBeInTheDocument()
    expect(screen.getByText(/couldn't sign you in/i)).toBeInTheDocument()
  })

  it('displays access denied error', () => {
    renderWithRouter(['/login?error=access_denied'])
    expect(screen.getByText('Access Denied')).toBeInTheDocument()
  })

  it('displays session expired error', () => {
    renderWithRouter(['/login?error=session_expired'])
    expect(screen.getByText('Session Expired')).toBeInTheDocument()
  })

  it('displays server error', () => {
    renderWithRouter(['/login?error=server_error'])
    expect(screen.getByText('Server Error')).toBeInTheDocument()
  })

  it('displays custom error for unknown error codes', () => {
    renderWithRouter(['/login?error=unknown_error'])
    expect(screen.getByText('Authentication Error')).toBeInTheDocument()
    expect(screen.getByText('unknown_error')).toBeInTheDocument()
  })

  it('displays info message for session expired reason', () => {
    renderWithRouter(['/login?reason=session_expired'])
    expect(screen.getByText(/session has expired/i)).toBeInTheDocument()
  })

  it('error message has proper accessibility attributes', () => {
    renderWithRouter(['/login?error=auth_failed'])
    const alert = screen.getByRole('alert')
    expect(alert).toHaveAttribute('aria-live', 'polite')
  })

  it('features list has proper accessibility', () => {
    renderWithRouter()
    expect(screen.getByRole('list', { name: /platform features/i })).toBeInTheDocument()
  })
})
