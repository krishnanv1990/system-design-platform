import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import ProblemList from './ProblemList'

// Mock the API client
const mockList = vi.fn()
vi.mock('@/api/client', () => ({
  problemsApi: {
    list: () => mockList(),
  },
}))

const mockProblems = [
  {
    id: 1,
    title: 'Design a URL Shortener',
    description: 'Design a URL shortening service',
    difficulty: 'medium',
    difficulty_info: { level: 'L6', title: 'Staff Engineer' },
    tags: ['distributed-systems', 'caching'],
  },
  {
    id: 2,
    title: 'Design a Rate Limiter',
    description: 'Design a rate limiting service',
    difficulty: 'easy',
    difficulty_info: { level: 'L5', title: 'Senior Engineer' },
    tags: ['algorithms'],
  },
]

const renderWithRouter = () => {
  return render(
    <MemoryRouter>
      <ProblemList />
    </MemoryRouter>
  )
}

describe('ProblemList Page', () => {
  beforeEach(() => {
    mockList.mockReset()
  })

  // ==========================================================================
  // Loading State Tests
  // ==========================================================================

  describe('Loading State', () => {
    it('shows skeleton while loading', () => {
      mockList.mockReturnValue(new Promise(() => {})) // Never resolves
      renderWithRouter()
      // Should show multiple skeleton cards
      const skeletons = document.querySelectorAll('[class*="animate-pulse"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })
  })

  // ==========================================================================
  // Success State Tests
  // ==========================================================================

  describe('Success State', () => {
    it('renders problems list after loading', async () => {
      mockList.mockResolvedValue(mockProblems)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Design a URL Shortener')).toBeInTheDocument()
        expect(screen.getByText('Design a Rate Limiter')).toBeInTheDocument()
      })
    })

    it('displays difficulty badges', async () => {
      mockList.mockResolvedValue(mockProblems)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText(/L6 - medium/i)).toBeInTheDocument()
        expect(screen.getByText(/L5 - easy/i)).toBeInTheDocument()
      })
    })

    it('displays tags for problems', async () => {
      mockList.mockResolvedValue(mockProblems)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('distributed-systems')).toBeInTheDocument()
        expect(screen.getByText('caching')).toBeInTheDocument()
        expect(screen.getByText('algorithms')).toBeInTheDocument()
      })
    })

    it('problem cards link to problem detail pages', async () => {
      mockList.mockResolvedValue(mockProblems)
      renderWithRouter()

      await waitFor(() => {
        const links = screen.getAllByRole('link')
        expect(links[0]).toHaveAttribute('href', '/problems/1')
        expect(links[1]).toHaveAttribute('href', '/problems/2')
      })
    })
  })

  // ==========================================================================
  // Empty State Tests
  // ==========================================================================

  describe('Empty State', () => {
    it('shows empty message when no problems', async () => {
      mockList.mockResolvedValue([])
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('No problems available yet.')).toBeInTheDocument()
      })
    })
  })

  // ==========================================================================
  // Error State Tests
  // ==========================================================================

  describe('Error State', () => {
    it('shows error message when API fails', async () => {
      mockList.mockRejectedValue(new Error('Network error'))
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Failed to load problems')).toBeInTheDocument()
        expect(screen.getByText('Network error')).toBeInTheDocument()
      })
    })

    it('shows API error detail if available', async () => {
      mockList.mockRejectedValue({
        response: { data: { detail: 'Server is down' } },
      })
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Server is down')).toBeInTheDocument()
      })
    })

    it('shows Try Again button on error', async () => {
      mockList.mockRejectedValue(new Error('Network error'))
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /try again/i })).toBeInTheDocument()
      })
    })

    it('Try Again button retries loading', async () => {
      mockList.mockRejectedValueOnce(new Error('Network error'))
      mockList.mockResolvedValueOnce(mockProblems)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Failed to load problems')).toBeInTheDocument()
      })

      const retryButton = screen.getByRole('button', { name: /try again/i })
      fireEvent.click(retryButton)

      await waitFor(() => {
        expect(screen.getByText('Design a URL Shortener')).toBeInTheDocument()
      })
    })
  })

  // ==========================================================================
  // Search/Filter Tests
  // ==========================================================================

  describe('Search Functionality', () => {
    it('renders search input', async () => {
      mockList.mockResolvedValue(mockProblems)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByPlaceholderText(/search problems/i)).toBeInTheDocument()
      })
    })

    it('filters problems by title', async () => {
      mockList.mockResolvedValue(mockProblems)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Design a URL Shortener')).toBeInTheDocument()
      })

      const searchInput = screen.getByPlaceholderText(/search problems/i)
      fireEvent.change(searchInput, { target: { value: 'Rate' } })

      expect(screen.queryByText('Design a URL Shortener')).not.toBeInTheDocument()
      expect(screen.getByText('Design a Rate Limiter')).toBeInTheDocument()
    })

    it('shows no match message when search has no results', async () => {
      mockList.mockResolvedValue(mockProblems)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Design a URL Shortener')).toBeInTheDocument()
      })

      const searchInput = screen.getByPlaceholderText(/search problems/i)
      fireEvent.change(searchInput, { target: { value: 'nonexistent' } })

      expect(screen.getByText('No problems match your search.')).toBeInTheDocument()
    })
  })

  // ==========================================================================
  // Header Tests
  // ==========================================================================

  describe('Page Header', () => {
    it('renders page title', async () => {
      mockList.mockResolvedValue(mockProblems)
      renderWithRouter()

      expect(screen.getByText('System Design Problems')).toBeInTheDocument()
    })

    it('renders page description', async () => {
      mockList.mockResolvedValue(mockProblems)
      renderWithRouter()

      expect(screen.getByText(/Choose a problem to practice/i)).toBeInTheDocument()
    })
  })
})
