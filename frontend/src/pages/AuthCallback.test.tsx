/**
 * Tests for AuthCallback component
 *
 * Tests cover:
 * - Token handling from URL params
 * - Error handling from URL params
 * - Navigation after authentication
 * - Loading state display
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import AuthCallback from './AuthCallback'

// Mock navigate function
const mockNavigate = vi.fn()

// Mock useSearchParams
let mockSearchParams = new URLSearchParams()

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    useSearchParams: () => [mockSearchParams],
  }
})

// Mock login function
const mockLogin = vi.fn()

vi.mock('@/components/AuthContext', () => ({
  useAuth: () => ({
    login: mockLogin,
  }),
}))

const renderWithRouter = (searchParams: string = '') => {
  mockSearchParams = new URLSearchParams(searchParams)
  return render(
    <MemoryRouter initialEntries={[`/auth/callback${searchParams ? '?' + searchParams : ''}`]}>
      <AuthCallback />
    </MemoryRouter>
  )
}

describe('AuthCallback', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  // ==========================================================================
  // Loading State Tests
  // ==========================================================================

  describe('Loading State', () => {
    it('displays loading spinner', () => {
      renderWithRouter('token=test-token')
      expect(screen.getByText('Completing authentication...')).toBeInTheDocument()
    })

    it('has spinning animation element', () => {
      renderWithRouter('token=test-token')
      const spinner = document.querySelector('.animate-spin')
      expect(spinner).toBeInTheDocument()
    })
  })

  // ==========================================================================
  // Token Handling Tests
  // ==========================================================================

  describe('Token Handling', () => {
    it('calls login with token from URL', async () => {
      mockLogin.mockResolvedValueOnce(undefined)
      renderWithRouter('token=valid-jwt-token')

      await waitFor(() => {
        expect(mockLogin).toHaveBeenCalledWith('valid-jwt-token')
      })
    })

    it('navigates to problems page on successful login', async () => {
      mockLogin.mockResolvedValueOnce(undefined)
      renderWithRouter('token=valid-jwt-token')

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/problems')
      })
    })

    it('clears old token from localStorage before login', async () => {
      localStorage.setItem('token', 'old-token')
      mockLogin.mockResolvedValueOnce(undefined)
      renderWithRouter('token=new-token')

      await waitFor(() => {
        expect(localStorage.getItem('token')).toBeNull()
      })
    })

    it('handles missing token', async () => {
      renderWithRouter('')

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/login?error=no_token')
      })
    })

    it('handles login failure', async () => {
      mockLogin.mockRejectedValueOnce(new Error('Login failed'))
      renderWithRouter('token=invalid-token')

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/login?error=auth_failed')
      })
    })
  })

  // ==========================================================================
  // Error Handling Tests
  // ==========================================================================

  describe('Error Handling', () => {
    it('redirects to login with error from URL', async () => {
      renderWithRouter('error=auth_failed')

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/login?error=auth_failed')
      })
    })

    it('handles access_denied error', async () => {
      renderWithRouter('error=access_denied')

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/login?error=access_denied')
      })
    })

    it('handles server_error', async () => {
      renderWithRouter('error=server_error')

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/login?error=server_error')
      })
    })

    it('encodes error message in URL', async () => {
      renderWithRouter('error=error with spaces')

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/login?error=error%20with%20spaces')
      })
    })

    it('prioritizes error over token', async () => {
      renderWithRouter('token=test-token&error=auth_failed')

      await waitFor(() => {
        expect(mockNavigate).toHaveBeenCalledWith('/login?error=auth_failed')
        expect(mockLogin).not.toHaveBeenCalled()
      })
    })
  })

  // ==========================================================================
  // Accessibility Tests
  // ==========================================================================

  describe('Accessibility', () => {
    it('has centered layout for loading state', () => {
      renderWithRouter('token=test-token')
      const container = document.querySelector('.min-h-screen')
      expect(container).toHaveClass('flex', 'items-center', 'justify-center')
    })

    it('displays descriptive loading text', () => {
      renderWithRouter('token=test-token')
      expect(screen.getByText('Completing authentication...')).toBeInTheDocument()
    })
  })
})

describe('AuthCallback Integration', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  it('completes full OAuth flow with valid token', async () => {
    mockLogin.mockResolvedValueOnce(undefined)
    renderWithRouter('token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test')

    await waitFor(() => {
      expect(mockLogin).toHaveBeenCalledWith('eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test')
      expect(mockNavigate).toHaveBeenCalledWith('/problems')
    })
  })

  it('handles OAuth provider denial', async () => {
    renderWithRouter('error=access_denied')

    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith('/login?error=access_denied')
    })
  })
})
