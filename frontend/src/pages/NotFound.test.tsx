import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import NotFound from './NotFound'

// Store original history
const originalBack = window.history.back

beforeEach(() => {
  window.history.back = vi.fn()
})

const renderWithRouter = () => {
  return render(
    <MemoryRouter>
      <NotFound />
    </MemoryRouter>
  )
}

describe('NotFound Page', () => {
  it('renders 404 heading', () => {
    renderWithRouter()
    expect(screen.getByText('404')).toBeInTheDocument()
  })

  it('renders Page Not Found message', () => {
    renderWithRouter()
    expect(screen.getByText('Page Not Found')).toBeInTheDocument()
  })

  it('renders description text', () => {
    renderWithRouter()
    expect(screen.getByText(/The page you're looking for doesn't exist/)).toBeInTheDocument()
  })

  it('renders Go Back button', () => {
    renderWithRouter()
    expect(screen.getByRole('button', { name: /go back/i })).toBeInTheDocument()
  })

  it('renders Go to Problems link', () => {
    renderWithRouter()
    expect(screen.getByRole('link', { name: /go to problems/i })).toBeInTheDocument()
  })

  it('Go Back button calls history.back()', () => {
    renderWithRouter()
    const goBackButton = screen.getByRole('button', { name: /go back/i })
    fireEvent.click(goBackButton)
    expect(window.history.back).toHaveBeenCalled()
  })

  it('Go to Problems link has correct href', () => {
    renderWithRouter()
    const link = screen.getByRole('link', { name: /go to problems/i })
    expect(link).toHaveAttribute('href', '/problems')
  })
})
