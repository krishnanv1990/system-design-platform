import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import AdminDashboard from './AdminDashboard'

// Mock the API client
const mockGetAllAssets = vi.fn()
vi.mock('@/api/client', () => ({
  assetsApi: {
    getAllAssets: () => mockGetAllAssets(),
  },
}))

const mockSummary = {
  total_submissions: 10,
  active_deployments: 3,
  total_cost_estimate: '$15.00/hour',
  assets: [
    {
      submission_id: 1,
      user_email: 'user1@example.com',
      status: 'completed',
      created_at: '2025-01-01T00:00:00Z',
      service_name: 'candidate-1',
      endpoint_url: 'https://candidate-1.run.app',
      region: 'us-central1',
      container_image: 'gcr.io/project/image:latest',
      console_links: {
        cloud_run_service: 'https://console.cloud.google.com/run/...',
      },
    },
    {
      submission_id: 2,
      user_email: 'user2@example.com',
      status: 'testing',
      created_at: '2025-01-01T01:00:00Z',
      service_name: 'candidate-2',
      endpoint_url: null,
      region: 'us-central1',
      container_image: null,
      console_links: {},
    },
  ],
}

const renderWithRouter = () => {
  return render(
    <MemoryRouter>
      <AdminDashboard />
    </MemoryRouter>
  )
}

describe('AdminDashboard Page', () => {
  beforeEach(() => {
    mockGetAllAssets.mockReset()
  })

  // ==========================================================================
  // Loading State Tests
  // ==========================================================================

  describe('Loading State', () => {
    it('shows skeleton while loading', () => {
      mockGetAllAssets.mockReturnValue(new Promise(() => {})) // Never resolves
      renderWithRouter()
      const skeletons = document.querySelectorAll('[class*="animate-pulse"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })
  })

  // ==========================================================================
  // Success State Tests
  // ==========================================================================

  describe('Success State', () => {
    it('renders dashboard header', async () => {
      mockGetAllAssets.mockResolvedValue(mockSummary)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('GCP Admin Dashboard')).toBeInTheDocument()
      })
    })

    it('displays total submissions count', async () => {
      mockGetAllAssets.mockResolvedValue(mockSummary)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Total Submissions')).toBeInTheDocument()
        expect(screen.getByText('10')).toBeInTheDocument()
      })
    })

    it('displays active deployments count', async () => {
      mockGetAllAssets.mockResolvedValue(mockSummary)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Active Deployments')).toBeInTheDocument()
        expect(screen.getByText('3')).toBeInTheDocument()
      })
    })

    it('displays cost estimate', async () => {
      mockGetAllAssets.mockResolvedValue(mockSummary)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Est. Cost')).toBeInTheDocument()
        expect(screen.getByText('$15.00/hour')).toBeInTheDocument()
      })
    })

    it('displays unique users count', async () => {
      mockGetAllAssets.mockResolvedValue(mockSummary)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Unique Users')).toBeInTheDocument()
        expect(screen.getByText('2')).toBeInTheDocument()
      })
    })

    it('displays deployments table', async () => {
      mockGetAllAssets.mockResolvedValue(mockSummary)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('All Deployments')).toBeInTheDocument()
        expect(screen.getByText('user1@example.com')).toBeInTheDocument()
        expect(screen.getByText('user2@example.com')).toBeInTheDocument()
      })
    })

    it('displays status badges for each deployment', async () => {
      mockGetAllAssets.mockResolvedValue(mockSummary)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('completed')).toBeInTheDocument()
        expect(screen.getByText('testing')).toBeInTheDocument()
      })
    })

    it('displays quick links section', async () => {
      mockGetAllAssets.mockResolvedValue(mockSummary)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Quick Links')).toBeInTheDocument()
        expect(screen.getByText('All Cloud Run Services')).toBeInTheDocument()
        expect(screen.getByText('Cloud Build History')).toBeInTheDocument()
        expect(screen.getByText('Artifact Registry')).toBeInTheDocument()
      })
    })

    it('refresh button triggers data reload', async () => {
      mockGetAllAssets.mockResolvedValue(mockSummary)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('GCP Admin Dashboard')).toBeInTheDocument()
      })

      const refreshButton = screen.getByRole('button', { name: /refresh/i })
      expect(refreshButton).toBeInTheDocument()

      mockGetAllAssets.mockResolvedValue({ ...mockSummary, total_submissions: 15 })
      fireEvent.click(refreshButton)

      await waitFor(() => {
        expect(screen.getByText('15')).toBeInTheDocument()
      })
    })
  })

  // ==========================================================================
  // Empty State Tests
  // ==========================================================================

  describe('Empty State', () => {
    it('shows no deployments message when assets array is empty', async () => {
      mockGetAllAssets.mockResolvedValue({
        ...mockSummary,
        assets: [],
      })
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('No deployments found')).toBeInTheDocument()
      })
    })
  })

  // ==========================================================================
  // Error State Tests
  // ==========================================================================

  describe('Error State', () => {
    it('shows error message when API fails', async () => {
      mockGetAllAssets.mockRejectedValue(new Error('Network error'))
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Failed to load GCP assets.')).toBeInTheDocument()
      })
    })

    it('shows admin access required for 403 error', async () => {
      mockGetAllAssets.mockRejectedValue({
        response: { status: 403 },
      })
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText(/admin access required/i)).toBeInTheDocument()
      })
    })

    it('shows back to problems link on error', async () => {
      mockGetAllAssets.mockRejectedValue(new Error('Network error'))
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByRole('link', { name: /back to problems/i })).toBeInTheDocument()
      })
    })
  })

  // ==========================================================================
  // Null Summary State Tests
  // ==========================================================================

  describe('Null Summary State', () => {
    it('shows no data available when summary is null', async () => {
      mockGetAllAssets.mockResolvedValue(null)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('No data available')).toBeInTheDocument()
      })
    })

    it('shows back link when no data available', async () => {
      mockGetAllAssets.mockResolvedValue(null)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByRole('link', { name: /back to problems/i })).toBeInTheDocument()
      })
    })
  })

  // ==========================================================================
  // Navigation Tests
  // ==========================================================================

  describe('Navigation', () => {
    it('renders back to problems link', async () => {
      mockGetAllAssets.mockResolvedValue(mockSummary)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('GCP Admin Dashboard')).toBeInTheDocument()
      }, { timeout: 10000 })

      // After dashboard loads, check for back link
      const backLinks = screen.getAllByRole('link', { name: /back to problems/i })
      expect(backLinks.length).toBeGreaterThan(0)
    })
  })
})
