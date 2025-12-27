/**
 * Tests for CookieNotice component
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import CookieNotice, { useAnalyticsConsent } from './CookieNotice'
import { renderHook, waitFor } from '@testing-library/react'

// Wrapper for router context
const renderWithRouter = (component: React.ReactNode) => {
  return render(<BrowserRouter>{component}</BrowserRouter>)
}

describe('CookieNotice', () => {
  beforeEach(() => {
    // Clear localStorage before each test
    localStorage.clear()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.runOnlyPendingTimers()
    vi.useRealTimers()
  })

  describe('Display behavior', () => {
    it('does not render immediately', () => {
      renderWithRouter(<CookieNotice />)
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('renders after delay when no consent stored', () => {
      renderWithRouter(<CookieNotice />)

      // Advance timers past the delay
      act(() => {
        vi.advanceTimersByTime(600)
      })

      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    it('does not render when consent already given', () => {
      localStorage.setItem('cookie-consent-accepted', 'true')
      renderWithRouter(<CookieNotice />)

      act(() => {
        vi.advanceTimersByTime(600)
      })

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })

    it('does not render when essential-only consent given', () => {
      localStorage.setItem('cookie-consent-accepted', 'essential-only')
      renderWithRouter(<CookieNotice />)

      act(() => {
        vi.advanceTimersByTime(600)
      })

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  describe('Content', () => {
    it('displays cookie information text', () => {
      renderWithRouter(<CookieNotice />)

      act(() => {
        vi.advanceTimersByTime(600)
      })

      expect(screen.getByText(/We use cookies to enhance your experience/)).toBeInTheDocument()
    })

    it('contains link to Privacy Policy', () => {
      renderWithRouter(<CookieNotice />)

      act(() => {
        vi.advanceTimersByTime(600)
      })

      const privacyLink = screen.getByRole('link', { name: /Privacy Policy/i })
      expect(privacyLink).toBeInTheDocument()
      expect(privacyLink).toHaveAttribute('href', '/privacy')
    })

    it('has Accept All button', () => {
      renderWithRouter(<CookieNotice />)

      act(() => {
        vi.advanceTimersByTime(600)
      })

      expect(screen.getByRole('button', { name: /Accept All/i })).toBeInTheDocument()
    })

    it('has Essential Only button', () => {
      renderWithRouter(<CookieNotice />)

      act(() => {
        vi.advanceTimersByTime(600)
      })

      expect(screen.getByRole('button', { name: /Essential Only/i })).toBeInTheDocument()
    })
  })

  describe('User interactions', () => {
    it('hides banner and saves consent when Accept All clicked', () => {
      renderWithRouter(<CookieNotice />)

      act(() => {
        vi.advanceTimersByTime(600)
      })

      expect(screen.getByRole('dialog')).toBeInTheDocument()

      act(() => {
        fireEvent.click(screen.getByRole('button', { name: /Accept All/i }))
      })

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(localStorage.getItem('cookie-consent-accepted')).toBe('true')
    })

    it('hides banner and saves essential-only when Essential Only clicked', () => {
      renderWithRouter(<CookieNotice />)

      act(() => {
        vi.advanceTimersByTime(600)
      })

      expect(screen.getByRole('dialog')).toBeInTheDocument()

      act(() => {
        fireEvent.click(screen.getByRole('button', { name: /Essential Only/i }))
      })

      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
      expect(localStorage.getItem('cookie-consent-accepted')).toBe('essential-only')
    })
  })

  describe('Accessibility', () => {
    it('has proper dialog role', () => {
      renderWithRouter(<CookieNotice />)

      act(() => {
        vi.advanceTimersByTime(600)
      })

      expect(screen.getByRole('dialog')).toHaveAttribute('aria-label', 'Cookie consent')
    })
  })
})

describe('useAnalyticsConsent', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('returns false when no consent stored', () => {
    const { result } = renderHook(() => useAnalyticsConsent())
    // Initial state before useEffect runs
    expect(result.current).toBe(false)
  })

  it('returns true when full consent given', async () => {
    localStorage.setItem('cookie-consent-accepted', 'true')
    const { result } = renderHook(() => useAnalyticsConsent())

    // Wait for the useEffect to run
    await waitFor(() => {
      expect(result.current).toBe(true)
    })
  })

  it('returns false when essential-only consent given', async () => {
    localStorage.setItem('cookie-consent-accepted', 'essential-only')
    const { result } = renderHook(() => useAnalyticsConsent())

    // Wait for the useEffect to run, but result should still be false
    await waitFor(() => {
      // After useEffect, essential-only means no analytics consent
      expect(result.current).toBe(false)
    })
  })
})
