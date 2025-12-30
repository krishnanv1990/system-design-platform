/**
 * Tests for Layout component
 */

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Layout from './Layout'

// Mock AuthContext
vi.mock('./AuthContext', () => ({
  useAuth: () => ({
    user: { id: 1, name: 'Test User', email: 'test@example.com', avatar_url: null },
    logout: vi.fn(),
    demoMode: false,
  }),
}))

// Mock useTheme
vi.mock('@/hooks/useTheme', () => ({
  useTheme: () => ({
    resolvedTheme: 'light',
    setTheme: vi.fn(),
  }),
}))

// Mock confirm dialog
vi.mock('@/components/ui/confirm-dialog', () => ({
  useConfirm: () => vi.fn().mockResolvedValue(false),
}))

describe('Layout', () => {
  it('renders navigation with correct tab labels', () => {
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>
    )

    // Check that the renamed tabs are present
    expect(screen.getByText('System Design')).toBeInTheDocument()
    expect(screen.getByText('Coding Problems')).toBeInTheDocument()
    expect(screen.getByText('My Usage')).toBeInTheDocument()
  })

  it('renders the platform title', () => {
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>
    )

    expect(screen.getByText('System Design Platform')).toBeInTheDocument()
  })

  it('renders navigation links with correct paths', () => {
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>
    )

    // Use getAllByRole to handle multiple matches (desktop and mobile nav)
    const systemDesignLinks = screen.getAllByRole('link', { name: /^System Design$/i })
    const codingProblemsLinks = screen.getAllByRole('link', { name: /Coding Problems/i })
    const usageLinks = screen.getAllByRole('link', { name: /My Usage/i })

    // Check that the first (desktop) link has correct path
    expect(systemDesignLinks[0]).toHaveAttribute('href', '/problems')
    expect(codingProblemsLinks[0]).toHaveAttribute('href', '/distributed')
    expect(usageLinks[0]).toHaveAttribute('href', '/usage')
  })

  it('renders footer with terms and privacy links', () => {
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>
    )

    expect(screen.getByRole('link', { name: 'Terms' })).toHaveAttribute('href', '/terms')
    expect(screen.getByRole('link', { name: 'Privacy' })).toHaveAttribute('href', '/privacy')
  })

  it('renders theme toggle button', () => {
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>
    )

    expect(screen.getByRole('button', { name: /Switch to dark theme/i })).toBeInTheDocument()
  })

  it('renders user info when user is logged in', () => {
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>
    )

    expect(screen.getByText('Test User')).toBeInTheDocument()
  })

  it('renders skip to content link for accessibility', () => {
    render(
      <MemoryRouter>
        <Layout />
      </MemoryRouter>
    )

    expect(screen.getByText('Skip to main content')).toBeInTheDocument()
  })
})
