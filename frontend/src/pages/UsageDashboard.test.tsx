import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import UsageDashboard from './UsageDashboard'
import { userApi } from '@/api/client'

// Mock the API
vi.mock('@/api/client', () => ({
  userApi: {
    getUsage: vi.fn(),
    getActivity: vi.fn(),
  },
}))

const mockUsageData = {
  total_cost_usd: 12.50,
  start_date: '2024-01-01T00:00:00Z',
  end_date: '2024-01-31T23:59:59Z',
  by_category: [
    { category: 'ai_input_tokens', total_quantity: 100000, unit: 'tokens', total_cost_usd: 0.30 },
    { category: 'ai_output_tokens', total_quantity: 50000, unit: 'tokens', total_cost_usd: 0.75 },
  ],
  recent_items: [
    {
      id: 1,
      category: 'ai_input_tokens',
      quantity: 1000,
      unit: 'tokens',
      unit_cost_usd: 0.000003,
      total_cost_usd: 0.003,
      details: null,
      created_at: '2024-01-15T10:00:00Z',
    },
  ],
}

const mockActivityData = {
  total_count: 25,
  items: [
    {
      id: 1,
      action: 'login',
      resource_type: null,
      resource_id: null,
      details: null,
      request_path: '/api/auth/google',
      request_method: 'POST',
      response_status: 200,
      duration_ms: 150,
      created_at: '2024-01-15T10:00:00Z',
    },
  ],
}

describe('UsageDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders loading state initially', () => {
    vi.mocked(userApi.getUsage).mockReturnValue(new Promise(() => {}))
    vi.mocked(userApi.getActivity).mockReturnValue(new Promise(() => {}))

    render(
      <BrowserRouter>
        <UsageDashboard />
      </BrowserRouter>
    )

    // Should show skeletons while loading
    expect(document.querySelector('.animate-pulse')).toBeInTheDocument()
  })

  it('renders usage dashboard with data', async () => {
    vi.mocked(userApi.getUsage).mockResolvedValue(mockUsageData)
    vi.mocked(userApi.getActivity).mockResolvedValue(mockActivityData)

    render(
      <BrowserRouter>
        <UsageDashboard />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Usage Dashboard')).toBeInTheDocument()
    })

    // Check summary cards
    expect(screen.getByText('$12.50')).toBeInTheDocument()
    expect(screen.getByText('25')).toBeInTheDocument() // Total actions
  })

  it('displays cost categories', async () => {
    vi.mocked(userApi.getUsage).mockResolvedValue(mockUsageData)
    vi.mocked(userApi.getActivity).mockResolvedValue(mockActivityData)

    render(
      <BrowserRouter>
        <UsageDashboard />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Cost by Category')).toBeInTheDocument()
    })

    // Check categories appear (may be multiple due to chart and list)
    expect(screen.getAllByText('Ai Input Tokens').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Ai Output Tokens').length).toBeGreaterThan(0)
  })

  it('handles API error gracefully', async () => {
    vi.mocked(userApi.getUsage).mockRejectedValue({
      response: { data: { detail: 'Failed to load usage data' } },
    })
    vi.mocked(userApi.getActivity).mockRejectedValue({
      response: { data: { detail: 'Failed to load activity' } },
    })

    render(
      <BrowserRouter>
        <UsageDashboard />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Failed to load usage data')).toBeInTheDocument()
    })
  })

  it('shows empty state when no data', async () => {
    vi.mocked(userApi.getUsage).mockResolvedValue({
      ...mockUsageData,
      by_category: [],
      recent_items: [],
    })
    vi.mocked(userApi.getActivity).mockResolvedValue({
      total_count: 0,
      items: [],
    })

    render(
      <BrowserRouter>
        <UsageDashboard />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('No usage data for this period')).toBeInTheDocument()
    })
  })
})
