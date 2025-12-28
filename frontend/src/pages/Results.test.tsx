import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import Results from './Results'

// Mock the API clients
const mockGetSubmission = vi.fn()
const mockGetTestSummary = vi.fn()
const mockGetDeploymentStatus = vi.fn()
const mockGetSubmissionAssets = vi.fn()

vi.mock('@/api/client', () => ({
  submissionsApi: {
    get: () => mockGetSubmission(),
    getDeploymentStatus: () => mockGetDeploymentStatus(),
    teardown: vi.fn(),
  },
  testsApi: {
    getTestSummary: () => mockGetTestSummary(),
  },
  assetsApi: {
    getSubmissionAssets: () => mockGetSubmissionAssets(),
    getSubmissionCode: vi.fn(),
  },
}))

const mockSubmission = {
  id: 1,
  problem_id: 1,
  user_id: 1,
  status: 'completed',
  created_at: '2025-01-01T00:00:00Z',
  design_text: 'Test design',
  schema_input: {},
  api_spec_input: {},
  error_message: null,
  validation_feedback: null,
}

const mockTestSummary = {
  passed: 5,
  failed: 1,
  errors: 0,
  functional_tests: [],
  performance_tests: [],
  chaos_tests: [],
  has_platform_issues: false,
  issues_by_category: null,
}

const renderWithRouter = (submissionId: string = '1') => {
  return render(
    <MemoryRouter initialEntries={[`/submissions/${submissionId}/results`]}>
      <Routes>
        <Route path="/submissions/:id/results" element={<Results />} />
        <Route path="/problems" element={<div>Problems Page</div>} />
      </Routes>
    </MemoryRouter>
  )
}

describe('Results Page', () => {
  beforeEach(() => {
    mockGetSubmission.mockReset()
    mockGetTestSummary.mockReset()
    mockGetDeploymentStatus.mockReset()
    mockGetSubmissionAssets.mockReset()
  })

  // ==========================================================================
  // Loading State Tests
  // ==========================================================================

  describe('Loading State', () => {
    it('shows skeleton while loading', () => {
      mockGetSubmission.mockReturnValue(new Promise(() => {})) // Never resolves
      renderWithRouter()
      // Should show skeleton cards
      const skeletons = document.querySelectorAll('[class*="animate-pulse"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })
  })

  // ==========================================================================
  // Success State Tests
  // ==========================================================================

  describe('Success State', () => {
    it('renders submission results after loading', async () => {
      mockGetSubmission.mockResolvedValue(mockSubmission)
      mockGetTestSummary.mockResolvedValue(mockTestSummary)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Submission Results')).toBeInTheDocument()
      })
    })

    it('displays completed status badge', async () => {
      mockGetSubmission.mockResolvedValue(mockSubmission)
      mockGetTestSummary.mockResolvedValue(mockTestSummary)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Completed')).toBeInTheDocument()
      })
    })

    it('displays test summary', async () => {
      mockGetSubmission.mockResolvedValue(mockSubmission)
      mockGetTestSummary.mockResolvedValue(mockTestSummary)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Test Results')).toBeInTheDocument()
        expect(screen.getByText('5 passed')).toBeInTheDocument()
        expect(screen.getByText('1 failed')).toBeInTheDocument()
      })
    })
  })

  // ==========================================================================
  // Error State Tests
  // ==========================================================================

  describe('Error State', () => {
    it('shows error when submission fails to load', async () => {
      mockGetSubmission.mockRejectedValue(new Error('Network error'))
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Failed to load submission')).toBeInTheDocument()
        expect(screen.getByText('Network error')).toBeInTheDocument()
      })
    })

    it('shows API error detail if available', async () => {
      mockGetSubmission.mockRejectedValue({
        response: { data: { detail: 'Submission not found' } },
      })
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Submission not found')).toBeInTheDocument()
      })
    })

    it('shows Retry button on error', async () => {
      mockGetSubmission.mockRejectedValue(new Error('Network error'))
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument()
      })
    })

    it('shows Back to problems link on error', async () => {
      mockGetSubmission.mockRejectedValue(new Error('Network error'))
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByRole('link', { name: /back to problems/i })).toBeInTheDocument()
      })
    })
  })

  // ==========================================================================
  // Not Found State Tests
  // ==========================================================================

  describe('Not Found State', () => {
    it('shows not found message when submission API returns null', async () => {
      mockGetSubmission.mockResolvedValue(null)
      renderWithRouter()

      await waitFor(() => {
        // Either shows "not found" or the generic error state
        const notFoundText = screen.queryByText(/not found/i) || screen.queryByText(/failed to load/i)
        expect(notFoundText).toBeInTheDocument()
      })
    })
  })

  // ==========================================================================
  // Status Display Tests
  // ==========================================================================

  describe('Status Display', () => {
    it('shows pending status', async () => {
      mockGetSubmission.mockResolvedValue({ ...mockSubmission, status: 'pending' })
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Submission Results')).toBeInTheDocument()
      })

      // The Pending badge should be visible (there may be multiple due to processing indicator)
      const pendingElements = screen.getAllByText('Pending')
      expect(pendingElements.length).toBeGreaterThan(0)
    })

    it('shows validating status', async () => {
      mockGetSubmission.mockResolvedValue({ ...mockSubmission, status: 'validating' })
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Submission Results')).toBeInTheDocument()
      })

      // The Validating Design badge should be visible (there may be multiple)
      const validatingElements = screen.getAllByText(/Validating Design/i)
      expect(validatingElements.length).toBeGreaterThan(0)
    })

    it('shows failed status with error message', async () => {
      mockGetSubmission.mockResolvedValue({
        ...mockSubmission,
        status: 'failed',
        error_message: 'Deployment failed due to timeout',
      })
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Failed')).toBeInTheDocument()
        expect(screen.getByText('Deployment failed due to timeout')).toBeInTheDocument()
      })
    })
  })

  // ==========================================================================
  // Back Navigation Tests
  // ==========================================================================

  describe('Navigation', () => {
    it('renders back to problems link', async () => {
      mockGetSubmission.mockResolvedValue(mockSubmission)
      mockGetTestSummary.mockResolvedValue(mockTestSummary)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByRole('link', { name: /back to problems/i })).toBeInTheDocument()
      })
    })
  })
})
