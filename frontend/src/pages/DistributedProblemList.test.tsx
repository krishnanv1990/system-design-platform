/**
 * Tests for DistributedProblemList page
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import DistributedProblemList from './DistributedProblemList'
import { distributedProblemsApi } from '@/api/client'

// Mock the API
vi.mock('@/api/client', () => ({
  distributedProblemsApi: {
    list: vi.fn(),
  },
}))

const mockProblems = [
  {
    id: 1,
    title: 'Implement Raft Consensus',
    description: 'Implement the Raft consensus algorithm',
    difficulty: 'hard',
    problem_type: 'distributed_consensus',
    supported_languages: ['python', 'go', 'java', 'cpp', 'rust'],
    cluster_size: 3,
    tags: ['distributed-systems', 'consensus', 'raft'],
    created_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 2,
    title: 'Implement Paxos',
    description: 'Implement the Paxos consensus algorithm',
    difficulty: 'hard',
    problem_type: 'distributed_consensus',
    supported_languages: ['python', 'go'],
    cluster_size: 5,
    tags: ['distributed-systems', 'consensus', 'paxos'],
    created_at: '2025-01-01T00:00:00Z',
  },
]

describe('DistributedProblemList', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders loading skeleton initially', () => {
    vi.mocked(distributedProblemsApi.list).mockImplementation(
      () => new Promise(() => {})
    )

    render(
      <MemoryRouter>
        <DistributedProblemList />
      </MemoryRouter>
    )

    expect(screen.getByText('Distributed Consensus Problems')).toBeInTheDocument()
  })

  it('renders problems after loading', async () => {
    vi.mocked(distributedProblemsApi.list).mockResolvedValue(mockProblems)

    render(
      <MemoryRouter>
        <DistributedProblemList />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Implement Raft Consensus')).toBeInTheDocument()
      expect(screen.getByText('Implement Paxos')).toBeInTheDocument()
    })
  })

  it('displays cluster size for each problem', async () => {
    vi.mocked(distributedProblemsApi.list).mockResolvedValue(mockProblems)

    render(
      <MemoryRouter>
        <DistributedProblemList />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('3 node cluster')).toBeInTheDocument()
      expect(screen.getByText('5 node cluster')).toBeInTheDocument()
    })
  })

  it('displays supported languages', async () => {
    vi.mocked(distributedProblemsApi.list).mockResolvedValue(mockProblems)

    render(
      <MemoryRouter>
        <DistributedProblemList />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getAllByText('Python').length).toBeGreaterThan(0)
      expect(screen.getAllByText('Go').length).toBeGreaterThan(0)
    })
  })

  it('filters problems by search', async () => {
    vi.mocked(distributedProblemsApi.list).mockResolvedValue(mockProblems)
    const user = userEvent.setup()

    render(
      <MemoryRouter>
        <DistributedProblemList />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Implement Raft Consensus')).toBeInTheDocument()
    })

    const searchInput = screen.getByPlaceholderText('Search problems...')
    await user.type(searchInput, 'Paxos')

    await waitFor(() => {
      expect(screen.queryByText('Implement Raft Consensus')).not.toBeInTheDocument()
      expect(screen.getByText('Implement Paxos')).toBeInTheDocument()
    })
  })

  it('shows error state when API fails', async () => {
    vi.mocked(distributedProblemsApi.list).mockRejectedValue(new Error('API Error'))

    render(
      <MemoryRouter>
        <DistributedProblemList />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Failed to load problems')).toBeInTheDocument()
    })
  })

  it('shows empty state when no problems', async () => {
    vi.mocked(distributedProblemsApi.list).mockResolvedValue([])

    render(
      <MemoryRouter>
        <DistributedProblemList />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(
        screen.getByText('No distributed consensus problems available yet.')
      ).toBeInTheDocument()
    })
  })

  it('displays difficulty badges', async () => {
    vi.mocked(distributedProblemsApi.list).mockResolvedValue(mockProblems)

    render(
      <MemoryRouter>
        <DistributedProblemList />
      </MemoryRouter>
    )

    await waitFor(() => {
      const hardBadges = screen.getAllByText('hard')
      expect(hardBadges.length).toBe(2)
    })
  })

  it('displays tags for problems', async () => {
    vi.mocked(distributedProblemsApi.list).mockResolvedValue(mockProblems)

    render(
      <MemoryRouter>
        <DistributedProblemList />
      </MemoryRouter>
    )

    await waitFor(() => {
      expect(screen.getAllByText('distributed-systems').length).toBe(2)
      expect(screen.getAllByText('raft').length).toBe(1)
      expect(screen.getAllByText('paxos').length).toBe(1)
    })
  })
})
