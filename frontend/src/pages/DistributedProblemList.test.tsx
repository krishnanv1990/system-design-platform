/**
 * Tests for DistributedProblemList page
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import DistributedProblemList from './DistributedProblemList'
import { distributedProblemsApi } from '@/api/client'
import type { DistributedProblemListItem } from '@/types'

// Mock the API
vi.mock('@/api/client', () => ({
  distributedProblemsApi: {
    list: vi.fn(),
  },
}))

const mockProblems: DistributedProblemListItem[] = [
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
    title: 'Implement Paxos Consensus',
    description: 'Implement the Paxos consensus algorithm',
    difficulty: 'hard',
    problem_type: 'distributed_consensus',
    supported_languages: ['python', 'go', 'java', 'cpp', 'rust'],
    cluster_size: 3,
    tags: ['distributed-systems', 'consensus', 'paxos'],
    created_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 3,
    title: 'Implement Two-Phase Commit',
    description: 'Implement the Two-Phase Commit protocol',
    difficulty: 'medium',
    problem_type: 'distributed_consensus',
    supported_languages: ['python', 'go', 'java', 'cpp', 'rust'],
    cluster_size: 3,
    tags: ['distributed-systems', 'transactions', '2pc'],
    created_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 4,
    title: 'Implement Chandy-Lamport Snapshot',
    description: 'Implement the Chandy-Lamport snapshot algorithm',
    difficulty: 'medium',
    problem_type: 'distributed_consensus',
    supported_languages: ['python', 'go', 'java', 'cpp', 'rust'],
    cluster_size: 3,
    tags: ['distributed-systems', 'snapshots', 'chandy-lamport'],
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
      expect(screen.getByText('Implement Paxos Consensus')).toBeInTheDocument()
      expect(screen.getByText('Implement Two-Phase Commit')).toBeInTheDocument()
      expect(screen.getByText('Implement Chandy-Lamport Snapshot')).toBeInTheDocument()
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
      // All 4 problems have 3 node clusters
      const clusterBadges = screen.getAllByText('3 node cluster')
      expect(clusterBadges.length).toBe(4)
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
      expect(screen.getByText('Implement Paxos Consensus')).toBeInTheDocument()
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
      const mediumBadges = screen.getAllByText('medium')
      expect(hardBadges.length).toBe(2)  // Raft and Paxos are hard
      expect(mediumBadges.length).toBe(2)  // 2PC and Chandy-Lamport are medium
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
      expect(screen.getAllByText('distributed-systems').length).toBe(4)  // All 4 problems
      expect(screen.getAllByText('raft').length).toBe(1)
      expect(screen.getAllByText('paxos').length).toBe(1)
      expect(screen.getAllByText('2pc').length).toBe(1)
      expect(screen.getAllByText('chandy-lamport').length).toBe(1)
    })
  })
})
