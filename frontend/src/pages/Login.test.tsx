import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Login from './Login'

// Mock window.location
const mockLocation = { href: '' }
Object.defineProperty(window, 'location', {
  value: mockLocation,
  writable: true,
})

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
    getAuthUrl: (provider: string) => `http://test.com/auth/${provider}`,
    getGoogleAuthUrl: () => 'http://test.com/auth/google',
    getFacebookAuthUrl: () => 'http://test.com/auth/facebook',
    getLinkedInAuthUrl: () => 'http://test.com/auth/linkedin',
    getGitHubAuthUrl: () => 'http://test.com/auth/github',
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
  beforeEach(() => {
    mockLocation.href = ''
  })

  // ==========================================================================
  // Basic Rendering Tests
  // ==========================================================================

  it('renders login page with title', () => {
    renderWithRouter()
    expect(screen.getByText('System Design Platform')).toBeInTheDocument()
    expect(screen.getByText('Master System Design Interviews')).toBeInTheDocument()
  })

  it('renders features list', () => {
    renderWithRouter()
    expect(screen.getByText(/Real system design problems/i)).toBeInTheDocument()
    expect(screen.getByText(/AI-powered validation/i)).toBeInTheDocument()
  })

  it('features list has proper accessibility', () => {
    renderWithRouter()
    expect(screen.getByRole('list', { name: /platform features/i })).toBeInTheDocument()
  })

  // ==========================================================================
  // OAuth Provider Button Tests
  // ==========================================================================

  describe('OAuth Provider Buttons', () => {
    it('renders Google sign-in button', () => {
      renderWithRouter()
      expect(screen.getByRole('button', { name: /sign in with google/i })).toBeInTheDocument()
    })

    it('renders Facebook sign-in button', () => {
      renderWithRouter()
      expect(screen.getByRole('button', { name: /sign in with facebook/i })).toBeInTheDocument()
    })

    it('renders LinkedIn sign-in button', () => {
      renderWithRouter()
      expect(screen.getByRole('button', { name: /sign in with linkedin/i })).toBeInTheDocument()
    })

    it('renders GitHub sign-in button', () => {
      renderWithRouter()
      expect(screen.getByRole('button', { name: /sign in with github/i })).toBeInTheDocument()
    })

    it('clicking Google button redirects to Google OAuth', () => {
      renderWithRouter()
      const button = screen.getByRole('button', { name: /sign in with google/i })
      fireEvent.click(button)
      expect(mockLocation.href).toBe('http://test.com/auth/google')
    })

    it('clicking Facebook button redirects to Facebook OAuth', () => {
      renderWithRouter()
      const button = screen.getByRole('button', { name: /sign in with facebook/i })
      fireEvent.click(button)
      expect(mockLocation.href).toBe('http://test.com/auth/facebook')
    })

    it('clicking LinkedIn button redirects to LinkedIn OAuth', () => {
      renderWithRouter()
      const button = screen.getByRole('button', { name: /sign in with linkedin/i })
      fireEvent.click(button)
      expect(mockLocation.href).toBe('http://test.com/auth/linkedin')
    })

    it('clicking GitHub button redirects to GitHub OAuth', () => {
      renderWithRouter()
      const button = screen.getByRole('button', { name: /sign in with github/i })
      fireEvent.click(button)
      expect(mockLocation.href).toBe('http://test.com/auth/github')
    })
  })

  // ==========================================================================
  // Error Handling Tests
  // ==========================================================================

  describe('Error Display', () => {
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

    it('error message has proper accessibility attributes', () => {
      renderWithRouter(['/login?error=auth_failed'])
      const alert = screen.getByRole('alert')
      expect(alert).toHaveAttribute('aria-live', 'polite')
    })
  })

  // ==========================================================================
  // Info Message Tests
  // ==========================================================================

  describe('Info Messages', () => {
    it('displays info message for session expired reason', () => {
      renderWithRouter(['/login?reason=session_expired'])
      expect(screen.getByText(/session has expired/i)).toBeInTheDocument()
    })
  })

  // ==========================================================================
  // Layout Tests
  // ==========================================================================

  describe('Layout', () => {
    it('renders "Or continue with" divider', () => {
      renderWithRouter()
      expect(screen.getByText(/or continue with/i)).toBeInTheDocument()
    })

    it('renders Get Started card with description', () => {
      renderWithRouter()
      expect(screen.getByText('Get Started')).toBeInTheDocument()
      expect(screen.getByText(/sign in with your preferred account/i)).toBeInTheDocument()
    })
  })
})
