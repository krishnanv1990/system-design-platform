/**
 * Tests for DistributedSubmissionResults page
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import DistributedSubmissionResults from './DistributedSubmissionResults'
import { distributedSubmissionsApi } from '@/api/client'

// Mock the API
vi.mock('@/api/client', () => ({
  distributedSubmissionsApi: {
    get: vi.fn(),
    getBuildLogs: vi.fn(),
    getTestResults: vi.fn(),
  },
}))

const mockSubmission = {
  id: 1,
  problem_id: 1,
  user_id: 1,
  submission_type: 'distributed_consensus',
  language: 'python',
  source_code: '# Python code',
  status: 'completed',
  build_logs: 'Building...\nSuccess!',
  build_artifact_url: 'gs://bucket/artifact',
  cluster_node_urls: [
    'https://node1.run.app',
    'https://node2.run.app',
    'https://node3.run.app',
  ],
  error_message: null,
  created_at: '2025-01-01T00:00:00Z',
}

const mockTestResults = [
  {
    id: 1,
    submission_id: 1,
    test_type: 'functional',
    test_name: 'Leader Election',
    status: 'passed',
    duration_ms: 500,
    details: { leader_id: 'node1' },
    created_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 2,
    submission_id: 1,
    test_type: 'functional',
    test_name: 'Log Replication',
    status: 'passed',
    duration_ms: 750,
    details: { entries_replicated: 5 },
    created_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 3,
    submission_id: 1,
    test_type: 'performance',
    test_name: 'Throughput',
    status: 'passed',
    duration_ms: 5000,
    details: { ops_per_second: 150 },
    created_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 4,
    submission_id: 1,
    test_type: 'chaos',
    test_name: 'Network Partition',
    status: 'failed',
    duration_ms: 2000,
    details: { error: 'Cluster did not recover' },
    created_at: '2025-01-01T00:00:00Z',
  },
]

const renderWithRouter = (submissionId: string = '1') => {
  return render(
    <MemoryRouter initialEntries={[`/distributed/submissions/${submissionId}`]}>
      <Routes>
        <Route path="/distributed/submissions/:id" element={<DistributedSubmissionResults />} />
        <Route path="/distributed/:id" element={<div>Problem Detail</div>} />
        <Route path="/distributed" element={<div>Problem List</div>} />
      </Routes>
    </MemoryRouter>
  )
}

describe('DistributedSubmissionResults', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders loading skeleton initially', () => {
    vi.mocked(distributedSubmissionsApi.get).mockImplementation(
      () => new Promise(() => {})
    )

    renderWithRouter()

    // Should show loading state
    expect(document.querySelector('.animate-pulse')).toBeInTheDocument()
  })

  it('renders submission details after loading', async () => {
    vi.mocked(distributedSubmissionsApi.get).mockResolvedValue(mockSubmission)
    vi.mocked(distributedSubmissionsApi.getBuildLogs).mockResolvedValue(mockSubmission.build_logs)
    vi.mocked(distributedSubmissionsApi.getTestResults).mockResolvedValue(mockTestResults)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('Submission #1')).toBeInTheDocument()
    })
  })

  it('displays status badge for completed submission', async () => {
    vi.mocked(distributedSubmissionsApi.get).mockResolvedValue(mockSubmission)
    vi.mocked(distributedSubmissionsApi.getBuildLogs).mockResolvedValue(mockSubmission.build_logs)
    vi.mocked(distributedSubmissionsApi.getTestResults).mockResolvedValue(mockTestResults)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('Completed')).toBeInTheDocument()
    })
  })

  it('displays language badge', async () => {
    vi.mocked(distributedSubmissionsApi.get).mockResolvedValue(mockSubmission)
    vi.mocked(distributedSubmissionsApi.getBuildLogs).mockResolvedValue(mockSubmission.build_logs)
    vi.mocked(distributedSubmissionsApi.getTestResults).mockResolvedValue(mockTestResults)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText(/Python/)).toBeInTheDocument()
    })
  })

  it('displays build status card', async () => {
    vi.mocked(distributedSubmissionsApi.get).mockResolvedValue(mockSubmission)
    vi.mocked(distributedSubmissionsApi.getBuildLogs).mockResolvedValue(mockSubmission.build_logs)
    vi.mocked(distributedSubmissionsApi.getTestResults).mockResolvedValue(mockTestResults)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('Build Status')).toBeInTheDocument()
      expect(screen.getByText('Success')).toBeInTheDocument()
    })
  })

  it('displays cluster status with node count', async () => {
    vi.mocked(distributedSubmissionsApi.get).mockResolvedValue(mockSubmission)
    vi.mocked(distributedSubmissionsApi.getBuildLogs).mockResolvedValue(mockSubmission.build_logs)
    vi.mocked(distributedSubmissionsApi.getTestResults).mockResolvedValue(mockTestResults)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('Cluster')).toBeInTheDocument()
      expect(screen.getByText('3 nodes running')).toBeInTheDocument()
    })
  })

  it('displays test result counts', async () => {
    vi.mocked(distributedSubmissionsApi.get).mockResolvedValue(mockSubmission)
    vi.mocked(distributedSubmissionsApi.getBuildLogs).mockResolvedValue(mockSubmission.build_logs)
    vi.mocked(distributedSubmissionsApi.getTestResults).mockResolvedValue(mockTestResults)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('Tests')).toBeInTheDocument()
      expect(screen.getByText('3')).toBeInTheDocument() // passed
      expect(screen.getByText('1')).toBeInTheDocument() // failed
    })
  })

  it('displays build logs in tab', async () => {
    vi.mocked(distributedSubmissionsApi.get).mockResolvedValue(mockSubmission)
    vi.mocked(distributedSubmissionsApi.getBuildLogs).mockResolvedValue('Building...\nSuccess!')
    vi.mocked(distributedSubmissionsApi.getTestResults).mockResolvedValue(mockTestResults)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('Build Logs')).toBeInTheDocument()
    })

    // Build logs tab should be default and show logs content
    await waitFor(() => {
      // The logs are in a pre element, look for partial match
      const preElement = document.querySelector('pre')
      expect(preElement).toBeInTheDocument()
    })
  })

  it('displays test results in tab', async () => {
    vi.mocked(distributedSubmissionsApi.get).mockResolvedValue(mockSubmission)
    vi.mocked(distributedSubmissionsApi.getBuildLogs).mockResolvedValue(mockSubmission.build_logs)
    vi.mocked(distributedSubmissionsApi.getTestResults).mockResolvedValue(mockTestResults)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('Test Results')).toBeInTheDocument()
    })
  })

  it('displays cluster info in tab', async () => {
    vi.mocked(distributedSubmissionsApi.get).mockResolvedValue(mockSubmission)
    vi.mocked(distributedSubmissionsApi.getBuildLogs).mockResolvedValue(mockSubmission.build_logs)
    vi.mocked(distributedSubmissionsApi.getTestResults).mockResolvedValue(mockTestResults)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('Cluster Info')).toBeInTheDocument()
    })
  })

  it('shows error message when submission has error', async () => {
    const errorSubmission = {
      ...mockSubmission,
      status: 'failed',
      error_message: 'Build compilation failed',
    }
    vi.mocked(distributedSubmissionsApi.get).mockResolvedValue(errorSubmission)
    vi.mocked(distributedSubmissionsApi.getBuildLogs).mockResolvedValue('')
    vi.mocked(distributedSubmissionsApi.getTestResults).mockResolvedValue([])

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('Error')).toBeInTheDocument()
      expect(screen.getByText('Build compilation failed')).toBeInTheDocument()
    })
  })

  it('shows building status with spinner', async () => {
    const buildingSubmission = {
      ...mockSubmission,
      status: 'building',
      cluster_node_urls: null,
    }
    vi.mocked(distributedSubmissionsApi.get).mockResolvedValue(buildingSubmission)
    vi.mocked(distributedSubmissionsApi.getBuildLogs).mockResolvedValue('Compiling...')
    vi.mocked(distributedSubmissionsApi.getTestResults).mockResolvedValue([])

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('Building')).toBeInTheDocument()
      expect(screen.getByText('Building...')).toBeInTheDocument()
    })
  })

  it('shows deploying status', async () => {
    const deployingSubmission = {
      ...mockSubmission,
      status: 'deploying',
      cluster_node_urls: null,
    }
    vi.mocked(distributedSubmissionsApi.get).mockResolvedValue(deployingSubmission)
    vi.mocked(distributedSubmissionsApi.getBuildLogs).mockResolvedValue('')
    vi.mocked(distributedSubmissionsApi.getTestResults).mockResolvedValue([])

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('Deploying')).toBeInTheDocument()
      expect(screen.getByText('Deploying...')).toBeInTheDocument()
    })
  })

  it('shows testing status', async () => {
    const testingSubmission = {
      ...mockSubmission,
      status: 'testing',
    }
    vi.mocked(distributedSubmissionsApi.get).mockResolvedValue(testingSubmission)
    vi.mocked(distributedSubmissionsApi.getBuildLogs).mockResolvedValue('')
    vi.mocked(distributedSubmissionsApi.getTestResults).mockResolvedValue([])

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('Testing')).toBeInTheDocument()
      expect(screen.getByText('Running...')).toBeInTheDocument()
    })
  })

  it('shows error when API fails', async () => {
    vi.mocked(distributedSubmissionsApi.get).mockRejectedValue(new Error('API Error'))

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('Failed to load submission')).toBeInTheDocument()
    })
  })

  it('has back button to return to problem', async () => {
    vi.mocked(distributedSubmissionsApi.get).mockResolvedValue(mockSubmission)
    vi.mocked(distributedSubmissionsApi.getBuildLogs).mockResolvedValue('')
    vi.mocked(distributedSubmissionsApi.getTestResults).mockResolvedValue([])

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('Back to Problem')).toBeInTheDocument()
    })
  })

  it('has refresh button', async () => {
    vi.mocked(distributedSubmissionsApi.get).mockResolvedValue(mockSubmission)
    vi.mocked(distributedSubmissionsApi.getBuildLogs).mockResolvedValue('')
    vi.mocked(distributedSubmissionsApi.getTestResults).mockResolvedValue([])

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('Refresh')).toBeInTheDocument()
    })
  })
})
