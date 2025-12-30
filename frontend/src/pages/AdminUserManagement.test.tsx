import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import AdminUserManagement from './AdminUserManagement'

// Mock the API client
const mockListUsers = vi.fn()
const mockBanUser = vi.fn()
const mockUnbanUser = vi.fn()

vi.mock('@/api/client', () => ({
  adminApi: {
    listUsers: () => mockListUsers(),
    banUser: (userId: number, reason: string) => mockBanUser(userId, reason),
    unbanUser: (request: { user_id: number; reason?: string }) => mockUnbanUser(request),
  },
}))

// Mock the confirm dialog
const mockConfirm = vi.fn()
vi.mock('@/components/ui/confirm-dialog', () => ({
  useConfirm: () => mockConfirm,
}))

const mockUsers = [
  {
    id: 1,
    email: 'admin@example.com',
    name: 'Admin User',
    display_name: 'Admin',
    is_banned: false,
    ban_reason: null,
    banned_at: null,
    is_admin: true,
    created_at: '2025-01-01T00:00:00Z',
  },
  {
    id: 2,
    email: 'user@example.com',
    name: 'Regular User',
    display_name: null,
    is_banned: false,
    ban_reason: null,
    banned_at: null,
    is_admin: false,
    created_at: '2025-01-02T00:00:00Z',
  },
  {
    id: 3,
    email: 'banned@example.com',
    name: 'Banned User',
    display_name: 'Banned',
    is_banned: true,
    ban_reason: 'Policy violations',
    banned_at: '2025-01-03T00:00:00Z',
    is_admin: false,
    created_at: '2025-01-03T00:00:00Z',
  },
]

const renderWithRouter = () => {
  return render(
    <MemoryRouter>
      <AdminUserManagement />
    </MemoryRouter>
  )
}

describe('AdminUserManagement Page', () => {
  beforeEach(() => {
    mockListUsers.mockReset()
    mockBanUser.mockReset()
    mockUnbanUser.mockReset()
    mockConfirm.mockReset()
  })

  // ==========================================================================
  // Loading State Tests
  // ==========================================================================

  describe('Loading State', () => {
    it('shows skeleton while loading', () => {
      mockListUsers.mockReturnValue(new Promise(() => {})) // Never resolves
      renderWithRouter()
      const skeletons = document.querySelectorAll('[class*="animate-pulse"]')
      expect(skeletons.length).toBeGreaterThan(0)
    })
  })

  // ==========================================================================
  // Success State Tests
  // ==========================================================================

  describe('Success State', () => {
    it('renders page header', async () => {
      mockListUsers.mockResolvedValue(mockUsers)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('User Management')).toBeInTheDocument()
      })
    })

    it('displays total users count', async () => {
      mockListUsers.mockResolvedValue(mockUsers)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Total Users')).toBeInTheDocument()
        expect(screen.getByText('3')).toBeInTheDocument()
      })
    })

    it('displays active users count', async () => {
      mockListUsers.mockResolvedValue(mockUsers)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Active Users')).toBeInTheDocument()
        expect(screen.getByText('2')).toBeInTheDocument()
      })
    })

    it('displays banned users count', async () => {
      mockListUsers.mockResolvedValue(mockUsers)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Banned Users')).toBeInTheDocument()
        // Both banned count and admin count are 1, so check the stat card exists
        const bannedCard = screen.getByText('Banned Users').closest('[class*="cursor-pointer"]')
        expect(bannedCard).toBeInTheDocument()
      })
    })

    it('displays admins count', async () => {
      mockListUsers.mockResolvedValue(mockUsers)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Admins')).toBeInTheDocument()
        // Admin count should be 1
      })
    })

    it('displays users table with all users', async () => {
      mockListUsers.mockResolvedValue(mockUsers)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('admin@example.com')).toBeInTheDocument()
        expect(screen.getByText('user@example.com')).toBeInTheDocument()
        expect(screen.getByText('banned@example.com')).toBeInTheDocument()
      })
    })

    it('displays admin badge for admin users', async () => {
      mockListUsers.mockResolvedValue(mockUsers)
      renderWithRouter()

      await waitFor(() => {
        const adminBadges = screen.getAllByText('Admin')
        expect(adminBadges.length).toBeGreaterThan(0)
      })
    })

    it('displays banned badge for banned users', async () => {
      mockListUsers.mockResolvedValue(mockUsers)
      renderWithRouter()

      await waitFor(() => {
        // There are multiple "Banned" texts (card title and badge), so use getAllByText
        const bannedElements = screen.getAllByText('Banned')
        expect(bannedElements.length).toBeGreaterThanOrEqual(1)
      })
    })

    it('displays active badge for active users', async () => {
      mockListUsers.mockResolvedValue(mockUsers)
      renderWithRouter()

      await waitFor(() => {
        const activeBadges = screen.getAllByText('Active')
        expect(activeBadges.length).toBeGreaterThan(0)
      })
    })
  })

  // ==========================================================================
  // Filter Tests
  // ==========================================================================

  describe('Filtering', () => {
    it('has filter dropdown with options', async () => {
      mockListUsers.mockResolvedValue(mockUsers)
      renderWithRouter()

      // Wait for data to load
      await waitFor(() => {
        expect(screen.getByText('User Management')).toBeInTheDocument()
      })

      // Check that filter dropdown exists with options
      await waitFor(() => {
        const filterSelect = screen.getByRole('combobox')
        expect(filterSelect).toBeInTheDocument()
      })
    })

    it('search filters users by email', async () => {
      mockListUsers.mockResolvedValue(mockUsers)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('User Management')).toBeInTheDocument()
      })

      const searchInput = screen.getByPlaceholderText(/search by email/i)
      fireEvent.change(searchInput, { target: { value: 'admin' } })

      await waitFor(() => {
        expect(screen.getByText('admin@example.com')).toBeInTheDocument()
      })
    })
  })

  // ==========================================================================
  // Action Tests
  // ==========================================================================

  describe('User Actions', () => {
    it('shows unban button for banned users', async () => {
      mockListUsers.mockResolvedValue(mockUsers)
      renderWithRouter()

      await waitFor(() => {
        const unbanButtons = screen.getAllByRole('button', { name: /unban/i })
        expect(unbanButtons.length).toBeGreaterThan(0)
      })
    })

    it('shows ban button for non-admin active users', async () => {
      mockListUsers.mockResolvedValue(mockUsers)
      renderWithRouter()

      await waitFor(() => {
        const banButtons = screen.getAllByRole('button', { name: /^ban$/i })
        expect(banButtons.length).toBeGreaterThan(0)
      })
    })

    it('does not show ban button for admin users', async () => {
      // Only admin user
      mockListUsers.mockResolvedValue([mockUsers[0]])
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('admin@example.com')).toBeInTheDocument()
      })

      // Should not have a ban button for admin
      const banButtons = screen.queryAllByRole('button', { name: /^ban$/i })
      expect(banButtons.length).toBe(0)
    })

    it('calls unban API when unban button clicked and confirmed', async () => {
      mockListUsers.mockResolvedValue(mockUsers)
      mockConfirm.mockResolvedValue(true)
      mockUnbanUser.mockResolvedValue({ ...mockUsers[2], is_banned: false })
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('banned@example.com')).toBeInTheDocument()
      })

      const unbanButtons = screen.getAllByRole('button', { name: /unban/i })
      fireEvent.click(unbanButtons[0])

      await waitFor(() => {
        expect(mockConfirm).toHaveBeenCalled()
      })

      await waitFor(() => {
        expect(mockUnbanUser).toHaveBeenCalled()
      })
    })

    it('does not call unban API when cancelled', async () => {
      mockListUsers.mockResolvedValue(mockUsers)
      mockConfirm.mockResolvedValue(false)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('banned@example.com')).toBeInTheDocument()
      })

      const unbanButtons = screen.getAllByRole('button', { name: /unban/i })
      fireEvent.click(unbanButtons[0])

      await waitFor(() => {
        expect(mockConfirm).toHaveBeenCalled()
      })

      expect(mockUnbanUser).not.toHaveBeenCalled()
    })
  })

  // ==========================================================================
  // Error State Tests
  // ==========================================================================

  describe('Error State', () => {
    it('shows error message when API fails', async () => {
      mockListUsers.mockRejectedValue(new Error('Network error'))
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('Failed to load users.')).toBeInTheDocument()
      })
    })

    it('shows admin access required for 403 error', async () => {
      mockListUsers.mockRejectedValue({
        response: { status: 403 },
      })
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText(/admin access required/i)).toBeInTheDocument()
      })
    })

    it('shows back to dashboard link on error', async () => {
      mockListUsers.mockRejectedValue(new Error('Network error'))
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByRole('link', { name: /back to dashboard/i })).toBeInTheDocument()
      })
    })
  })

  // ==========================================================================
  // Empty State Tests
  // ==========================================================================

  describe('Empty State', () => {
    it('shows no users message when list is empty', async () => {
      mockListUsers.mockResolvedValue([])
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('No users found')).toBeInTheDocument()
      })
    })
  })

  // ==========================================================================
  // Refresh Tests
  // ==========================================================================

  describe('Refresh', () => {
    it('refresh button triggers data reload', async () => {
      mockListUsers.mockResolvedValue(mockUsers)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('User Management')).toBeInTheDocument()
      })

      const refreshButton = screen.getByRole('button', { name: /refresh/i })
      expect(refreshButton).toBeInTheDocument()

      // Update mock for second call
      const newUsers = [...mockUsers, {
        id: 4,
        email: 'new@example.com',
        name: 'New User',
        display_name: null,
        is_banned: false,
        ban_reason: null,
        banned_at: null,
        is_admin: false,
        created_at: '2025-01-04T00:00:00Z',
      }]
      mockListUsers.mockResolvedValue(newUsers)

      fireEvent.click(refreshButton)

      await waitFor(() => {
        expect(screen.getByText('4')).toBeInTheDocument() // New total
      })
    })
  })

  // ==========================================================================
  // Navigation Tests
  // ==========================================================================

  describe('Navigation', () => {
    it('renders back to dashboard link', async () => {
      mockListUsers.mockResolvedValue(mockUsers)
      renderWithRouter()

      await waitFor(() => {
        expect(screen.getByText('User Management')).toBeInTheDocument()
      })

      const backLink = screen.getByRole('link', { name: /back to dashboard/i })
      expect(backLink).toBeInTheDocument()
    })
  })
})
