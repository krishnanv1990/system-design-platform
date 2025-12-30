/**
 * Tests for DistributedProblemDetail page
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import DistributedProblemDetail from './DistributedProblemDetail'
import { distributedProblemsApi, distributedSubmissionsApi } from '@/api/client'

// Mock the API
vi.mock('@/api/client', () => ({
  distributedProblemsApi: {
    get: vi.fn(),
    getTemplate: vi.fn(),
    getSavedCode: vi.fn(),
    saveCode: vi.fn(),
  },
  distributedSubmissionsApi: {
    submit: vi.fn(),
  },
}))

// Mock the toast
vi.mock('@/hooks/useToast', () => ({
  useToast: () => ({
    toast: vi.fn(),
  }),
}))

// Mock CodeEditor
vi.mock('@/components/CodeEditor', () => ({
  default: ({ value, onChange }: { value: string; onChange: (v: string) => void }) => (
    <textarea
      data-testid="code-editor"
      value={value}
      onChange={(e) => onChange(e.target.value)}
    />
  ),
}))

const mockProblem = {
  id: 1,
  title: 'Implement Raft Consensus',
  description: 'Implement the Raft consensus algorithm.',
  difficulty: 'hard',
  problem_type: 'distributed_consensus',
  grpc_proto: 'syntax = "proto3";\n\nservice RaftService { }',
  supported_languages: ['python', 'go', 'java', 'cpp', 'rust'],
  cluster_size: 3,
  language_templates: {
    python: {
      language: 'python',
      template: '# Python template\nclass RaftNode:\n    pass',
      build_command: 'pip install -r requirements.txt',
      run_command: 'python server.py',
    },
    go: {
      language: 'go',
      template: '// Go template\npackage main',
      build_command: 'go build',
      run_command: './server',
    },
  },
  test_scenarios: [
    { name: 'Leader Election', description: 'Verify leader election', test_type: 'functional' },
    { name: 'Log Replication', description: 'Verify log replication', test_type: 'functional' },
    { name: 'Network Partition', description: 'Test network partition', test_type: 'chaos' },
  ],
  hints: ['Use randomized timeouts', 'Reset timer on valid AppendEntries'],
  tags: ['distributed-systems', 'consensus', 'raft'],
  created_at: '2025-01-01T00:00:00Z',
}

const renderWithRouter = (problemId: string = '1') => {
  return render(
    <MemoryRouter initialEntries={[`/distributed/${problemId}`]}>
      <Routes>
        <Route path="/distributed/:id" element={<DistributedProblemDetail />} />
        <Route path="/distributed/submissions/:id" element={<div>Submission Results</div>} />
        <Route path="/distributed" element={<div>Problem List</div>} />
      </Routes>
    </MemoryRouter>
  )
}

describe('DistributedProblemDetail', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(distributedProblemsApi.getSavedCode).mockResolvedValue(null)
  })

  it('renders loading skeleton initially', () => {
    vi.mocked(distributedProblemsApi.get).mockImplementation(
      () => new Promise(() => {})
    )

    renderWithRouter()

    // Should show loading state
    expect(document.querySelector('.animate-pulse')).toBeInTheDocument()
  })

  it('renders problem details after loading', async () => {
    vi.mocked(distributedProblemsApi.get).mockResolvedValue(mockProblem)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('Implement Raft Consensus')).toBeInTheDocument()
      expect(screen.getByText('Implement the Raft consensus algorithm.')).toBeInTheDocument()
    })
  })

  it('displays difficulty and cluster size badges', async () => {
    vi.mocked(distributedProblemsApi.get).mockResolvedValue(mockProblem)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('hard')).toBeInTheDocument()
      expect(screen.getByText('3 nodes')).toBeInTheDocument()
    })
  })

  it('displays gRPC proto in a tab', async () => {
    vi.mocked(distributedProblemsApi.get).mockResolvedValue(mockProblem)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('gRPC Proto')).toBeInTheDocument()
    })

    // Click on proto tab
    const protoTab = screen.getByText('gRPC Proto')
    await userEvent.click(protoTab)

    await waitFor(() => {
      expect(screen.getByText(/syntax = "proto3"/)).toBeInTheDocument()
    })
  })

  it('displays hints in a tab', async () => {
    vi.mocked(distributedProblemsApi.get).mockResolvedValue(mockProblem)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('Hints')).toBeInTheDocument()
    })

    const hintsTab = screen.getByText('Hints')
    await userEvent.click(hintsTab)

    await waitFor(() => {
      expect(screen.getByText('Use randomized timeouts')).toBeInTheDocument()
    })
  })

  it('displays test scenarios', async () => {
    vi.mocked(distributedProblemsApi.get).mockResolvedValue(mockProblem)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('Test Scenarios')).toBeInTheDocument()
      expect(screen.getByText('Leader Election')).toBeInTheDocument()
      expect(screen.getByText('Log Replication')).toBeInTheDocument()
      expect(screen.getByText('Network Partition')).toBeInTheDocument()
    })
  })

  it('displays language selector with all supported languages', async () => {
    vi.mocked(distributedProblemsApi.get).mockResolvedValue(mockProblem)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('Select Language')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Python/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Go/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Java/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /C\+\+/i })).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /Rust/i })).toBeInTheDocument()
    })
  })

  it('switches language when clicking language button', async () => {
    vi.mocked(distributedProblemsApi.get).mockResolvedValue(mockProblem)
    const user = userEvent.setup()

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Go/i })).toBeInTheDocument()
    })

    const goButton = screen.getByRole('button', { name: /Go/i })
    await user.click(goButton)

    // Go button should now be active (default variant)
    expect(goButton).toHaveClass('bg-primary')
  })

  it('shows save button disabled when no changes', async () => {
    vi.mocked(distributedProblemsApi.get).mockResolvedValue(mockProblem)

    renderWithRouter()

    await waitFor(() => {
      const saveButton = screen.getByRole('button', { name: /Save/i })
      expect(saveButton).toBeDisabled()
    })
  })

  it('enables save button when code changes', async () => {
    vi.mocked(distributedProblemsApi.get).mockResolvedValue(mockProblem)
    const user = userEvent.setup()

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByTestId('code-editor')).toBeInTheDocument()
    })

    const editor = screen.getByTestId('code-editor')
    await user.type(editor, 'some new code')

    await waitFor(() => {
      const saveButton = screen.getByRole('button', { name: /Save/i })
      expect(saveButton).not.toBeDisabled()
    })
  })

  it('shows submit button', async () => {
    vi.mocked(distributedProblemsApi.get).mockResolvedValue(mockProblem)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /Submit/i })).toBeInTheDocument()
    })
  })

  it('shows error state when API fails', async () => {
    vi.mocked(distributedProblemsApi.get).mockRejectedValue(new Error('API Error'))

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('Failed to load problem')).toBeInTheDocument()
    })
  })

  it('has back button to return to problem list', async () => {
    vi.mocked(distributedProblemsApi.get).mockResolvedValue(mockProblem)

    renderWithRouter()

    await waitFor(() => {
      expect(screen.getByText('Back to Problems')).toBeInTheDocument()
    })
  })
})
