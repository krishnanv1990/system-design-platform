import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'
import AdminUsageDashboard from './AdminUsageDashboard'
import { adminApi } from '@/api/client'

// Mock the API
vi.mock('@/api/client', () => ({
  adminApi: {
    getUsage: vi.fn(),
    getActivity: vi.fn(),
  },
}))

const mockAdminUsageData = {
  total_cost_usd: 150.00,
  total_actions: 5000,
  total_users: 25,
  start_date: '2024-01-01T00:00:00Z',
  end_date: '2024-01-31T23:59:59Z',
  by_category: [
    { category: 'ai_input_tokens', total_quantity: 1000000, unit: 'tokens', total_cost_usd: 3.00 },
    { category: 'ai_output_tokens', total_quantity: 500000, unit: 'tokens', total_cost_usd: 7.50 },
  ],
  by_user: [
    {
      user_id: 1,
      email: 'user1@example.com',
      name: 'User One',
      total_cost_usd: 50.00,
      total_actions: 1000,
      ai_input_tokens: 300000,
      ai_output_tokens: 150000,
    },
    {
      user_id: 2,
      email: 'user2@example.com',
      name: 'User Two',
      total_cost_usd: 30.00,
      total_actions: 800,
      ai_input_tokens: 200000,
      ai_output_tokens: 100000,
    },
  ],
}

const mockAdminActivityData = {
  total_actions: 5000,
  total_users: 25,
  start_date: '2024-01-01T00:00:00Z',
  end_date: '2024-01-31T23:59:59Z',
  by_action: {
    login: 500,
    chat_message: 2000,
    create_submission: 300,
    view_problem: 1500,
  },
  recent_items: [
    {
      id: 1,
      action: 'login',
      resource_type: null,
      resource_id: null,
      details: { user_id: 1 },
      request_path: '/api/auth/google',
      request_method: 'POST',
      response_status: 200,
      duration_ms: 150,
      created_at: '2024-01-15T10:00:00Z',
    },
  ],
}

describe('AdminUsageDashboard', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders loading state initially', () => {
    vi.mocked(adminApi.getUsage).mockReturnValue(new Promise(() => {}))
    vi.mocked(adminApi.getActivity).mockReturnValue(new Promise(() => {}))

    render(
      <BrowserRouter>
        <AdminUsageDashboard />
      </BrowserRouter>
    )

    // Should show skeletons while loading
    expect(document.querySelector('.animate-pulse')).toBeInTheDocument()
  })

  it('renders admin dashboard with data', async () => {
    vi.mocked(adminApi.getUsage).mockResolvedValue(mockAdminUsageData)
    vi.mocked(adminApi.getActivity).mockResolvedValue(mockAdminActivityData)

    render(
      <BrowserRouter>
        <AdminUsageDashboard />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Admin Usage Dashboard')).toBeInTheDocument()
    })

    // Check summary cards
    expect(screen.getByText('$150.00')).toBeInTheDocument()
    // Total users shown on card
    expect(screen.getAllByText('25').length).toBeGreaterThan(0)
  })

  it('displays tabs for navigation', async () => {
    vi.mocked(adminApi.getUsage).mockResolvedValue(mockAdminUsageData)
    vi.mocked(adminApi.getActivity).mockResolvedValue(mockAdminActivityData)

    render(
      <BrowserRouter>
        <AdminUsageDashboard />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Admin Usage Dashboard')).toBeInTheDocument()
    })

    // Check that tabs exist
    expect(screen.getByRole('tab', { name: /Overview/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /By User/i })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: /Activity/i })).toBeInTheDocument()
  })

  it('handles 403 error for non-admin users', async () => {
    vi.mocked(adminApi.getUsage).mockRejectedValue({
      response: { status: 403, data: { detail: 'Admin privileges required' } },
    })
    vi.mocked(adminApi.getActivity).mockRejectedValue({
      response: { status: 403, data: { detail: 'Admin privileges required' } },
    })

    render(
      <BrowserRouter>
        <AdminUsageDashboard />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Admin privileges required to view this dashboard')).toBeInTheDocument()
    })
  })

  it('shows action distribution chart', async () => {
    vi.mocked(adminApi.getUsage).mockResolvedValue(mockAdminUsageData)
    vi.mocked(adminApi.getActivity).mockResolvedValue(mockAdminActivityData)

    render(
      <BrowserRouter>
        <AdminUsageDashboard />
      </BrowserRouter>
    )

    await waitFor(() => {
      expect(screen.getByText('Top Actions')).toBeInTheDocument()
    })

    expect(screen.getByText('Chat Message')).toBeInTheDocument()
    expect(screen.getByText('View Problem')).toBeInTheDocument()
  })
})
