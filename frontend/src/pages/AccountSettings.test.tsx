/**
 * Tests for Account Settings page
 * Tests user data download and account deletion functionality
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import AccountSettings from './AccountSettings'

// Mock confirm dialog hook
const mockConfirm = vi.fn()
vi.mock('@/components/ui/confirm-dialog', () => ({
  useConfirm: () => mockConfirm,
  ConfirmProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

// Mock navigation
const mockNavigate = vi.fn()
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  }
})

// Mock user data
const mockUser = {
  id: 1,
  email: 'test@example.com',
  name: 'Test User',
  avatar_url: 'https://example.com/avatar.jpg',
  google_id: 'google-123',
  github_id: 'github-456',
  facebook_id: null,
  linkedin_id: null,
  created_at: '2024-01-01T00:00:00Z',
}

// Mock logout function
const mockLogout = vi.fn()

// Create a mutable auth state that tests can modify
const mockAuthState = {
  user: mockUser as typeof mockUser | null,
  demoMode: false,
  loading: false,
}

// Mock auth context
vi.mock('@/components/AuthContext', () => ({
  useAuth: () => ({
    user: mockAuthState.user,
    demoMode: mockAuthState.demoMode,
    loading: mockAuthState.loading,
    logout: mockLogout,
  }),
}))

// Mock API client
const mockDownloadUserData = vi.fn()
const mockDeleteAccount = vi.fn()

vi.mock('@/api/client', () => ({
  authApi: {
    downloadUserData: () => mockDownloadUserData(),
    deleteAccount: () => mockDeleteAccount(),
  },
}))

// Mock URL.createObjectURL and URL.revokeObjectURL
const mockCreateObjectURL = vi.fn(() => 'blob:test-url')
const mockRevokeObjectURL = vi.fn()
Object.defineProperty(URL, 'createObjectURL', { value: mockCreateObjectURL })
Object.defineProperty(URL, 'revokeObjectURL', { value: mockRevokeObjectURL })

// Helper to render with required providers
const renderAccountSettings = () => {
  return render(
    <MemoryRouter>
      <AccountSettings />
    </MemoryRouter>
  )
}

describe('AccountSettings', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Reset auth state to defaults
    mockAuthState.user = mockUser
    mockAuthState.demoMode = false
    mockAuthState.loading = false

    // Default mock behavior for confirm dialog - both confirmations pass
    mockConfirm.mockResolvedValue(true)

    mockDownloadUserData.mockResolvedValue({
      user: mockUser,
      submissions: [],
      test_results: [],
      exported_at: new Date().toISOString(),
    })
    mockDeleteAccount.mockResolvedValue({ message: 'Account deleted' })
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  // ==========================================================================
  // Basic Rendering Tests
  // ==========================================================================

  describe('Page rendering', () => {
    it('renders the page title', () => {
      renderAccountSettings()
      expect(screen.getByRole('heading', { name: /Account Settings/i })).toBeInTheDocument()
    })

    it('renders the page description', () => {
      renderAccountSettings()
      expect(screen.getByText(/Manage your account and data preferences/i)).toBeInTheDocument()
    })

    it('renders back button', () => {
      renderAccountSettings()
      expect(screen.getByRole('link', { name: /Back/i })).toBeInTheDocument()
    })

    it('back button links to problems page', () => {
      renderAccountSettings()
      const backLink = screen.getByRole('link', { name: /Back/i })
      expect(backLink).toHaveAttribute('href', '/problems')
    })
  })

  // ==========================================================================
  // Profile Information Tests
  // ==========================================================================

  describe('Profile Information section', () => {
    it('displays profile information card', () => {
      renderAccountSettings()
      expect(screen.getByRole('heading', { name: /Profile Information/i })).toBeInTheDocument()
    })

    it('displays user name', () => {
      renderAccountSettings()
      expect(screen.getByText('Test User')).toBeInTheDocument()
    })

    it('displays user email', () => {
      renderAccountSettings()
      expect(screen.getByText('test@example.com')).toBeInTheDocument()
    })

    it('displays user avatar when provided', () => {
      renderAccountSettings()
      const avatar = screen.getByAltText(/Test User|Profile/i)
      expect(avatar).toBeInTheDocument()
      expect(avatar).toHaveAttribute('src', 'https://example.com/avatar.jpg')
    })

    it('displays linked OAuth providers', () => {
      renderAccountSettings()
      expect(screen.getByText('Google')).toBeInTheDocument()
      expect(screen.getByText('GitHub')).toBeInTheDocument()
    })

    it('displays account creation date', () => {
      renderAccountSettings()
      expect(screen.getByText(/Account created:/i)).toBeInTheDocument()
    })
  })

  // ==========================================================================
  // Data Management Section Tests
  // ==========================================================================

  describe('Data Management section', () => {
    it('displays data management card', () => {
      renderAccountSettings()
      expect(screen.getByRole('heading', { name: /Data Management/i })).toBeInTheDocument()
    })

    it('displays download data section', () => {
      renderAccountSettings()
      expect(screen.getByText(/Download Your Data/i)).toBeInTheDocument()
    })

    it('displays download button', () => {
      renderAccountSettings()
      expect(screen.getByRole('button', { name: /Download/i })).toBeInTheDocument()
    })

    it('displays data download info list', () => {
      renderAccountSettings()
      expect(screen.getByText(/Account information and profile/i)).toBeInTheDocument()
      expect(screen.getByText(/All design submissions and diagrams/i)).toBeInTheDocument()
      expect(screen.getByText(/Chat history with AI coach/i)).toBeInTheDocument()
      expect(screen.getByText(/Test results and scores/i)).toBeInTheDocument()
    })
  })

  // ==========================================================================
  // Download Data Functionality Tests
  // ==========================================================================

  describe('Download data functionality', () => {
    it('calls downloadUserData API when download button is clicked', async () => {
      renderAccountSettings()
      const downloadButton = screen.getByRole('button', { name: /Download/i })
      fireEvent.click(downloadButton)

      await waitFor(() => {
        expect(mockDownloadUserData).toHaveBeenCalledTimes(1)
      })
    })

    it('shows loading state during download', async () => {
      mockDownloadUserData.mockImplementation(() => new Promise(() => {})) // Never resolves

      renderAccountSettings()
      const downloadButton = screen.getByRole('button', { name: /Download/i })
      fireEvent.click(downloadButton)

      await waitFor(() => {
        expect(screen.getByText(/Downloading.../i)).toBeInTheDocument()
      })
    })

    it('shows success message after successful download', async () => {
      renderAccountSettings()
      const downloadButton = screen.getByRole('button', { name: /Download/i })
      fireEvent.click(downloadButton)

      await waitFor(() => {
        expect(screen.getByText(/Your data has been downloaded successfully/i)).toBeInTheDocument()
      })
    })

    it('shows error message when download fails', async () => {
      mockDownloadUserData.mockRejectedValue(new Error('Download failed'))

      renderAccountSettings()
      const downloadButton = screen.getByRole('button', { name: /Download/i })
      fireEvent.click(downloadButton)

      await waitFor(() => {
        expect(screen.getByText(/Failed to download data/i)).toBeInTheDocument()
      })
    })

    it('creates downloadable JSON file', async () => {
      const appendChildSpy = vi.spyOn(document.body, 'appendChild')
      const removeChildSpy = vi.spyOn(document.body, 'removeChild')

      renderAccountSettings()
      const downloadButton = screen.getByRole('button', { name: /Download/i })
      fireEvent.click(downloadButton)

      await waitFor(() => {
        expect(mockCreateObjectURL).toHaveBeenCalled()
        expect(appendChildSpy).toHaveBeenCalled()
        expect(removeChildSpy).toHaveBeenCalled()
        expect(mockRevokeObjectURL).toHaveBeenCalled()
      })

      appendChildSpy.mockRestore()
      removeChildSpy.mockRestore()
    })
  })

  // ==========================================================================
  // Delete Account Section Tests
  // ==========================================================================

  describe('Delete Account section', () => {
    it('displays delete account card', () => {
      renderAccountSettings()
      expect(screen.getByRole('heading', { name: /Delete Account/i })).toBeInTheDocument()
    })

    it('displays warning about irreversible action', () => {
      renderAccountSettings()
      expect(screen.getByText(/This action is irreversible/i)).toBeInTheDocument()
    })

    it('displays list of data to be deleted', () => {
      renderAccountSettings()
      expect(screen.getByText(/Your user profile and account/i)).toBeInTheDocument()
      expect(screen.getByText(/All submissions and design diagrams/i)).toBeInTheDocument()
      expect(screen.getByText(/Chat history and AI coaching conversations/i)).toBeInTheDocument()
      expect(screen.getByText(/Test results and evaluation scores/i)).toBeInTheDocument()
    })

    it('displays delete button', () => {
      renderAccountSettings()
      expect(screen.getByRole('button', { name: /Delete My Account/i })).toBeInTheDocument()
    })

    it('delete button has destructive styling', () => {
      renderAccountSettings()
      const deleteButton = screen.getByRole('button', { name: /Delete My Account/i })
      // Destructive variant uses specific class names
      expect(deleteButton.className).toContain('destructive')
    })
  })

  // ==========================================================================
  // Delete Account Functionality Tests
  // ==========================================================================

  describe('Delete account functionality', () => {
    it('calls confirm dialog when delete is clicked', async () => {
      renderAccountSettings()
      const deleteButton = screen.getByRole('button', { name: /Delete My Account/i })
      fireEvent.click(deleteButton)

      await waitFor(() => {
        // First confirmation dialog should be called
        expect(mockConfirm).toHaveBeenCalled()
      })
    })

    it('cancels deletion when first dialog is cancelled', async () => {
      // First confirmation returns false (cancelled)
      mockConfirm.mockResolvedValueOnce(false)

      renderAccountSettings()
      const deleteButton = screen.getByRole('button', { name: /Delete My Account/i })
      fireEvent.click(deleteButton)

      await waitFor(() => {
        expect(mockConfirm).toHaveBeenCalled()
        expect(mockDeleteAccount).not.toHaveBeenCalled()
      })
    })

    it('cancels deletion when second dialog is cancelled', async () => {
      // First confirmation returns true, second returns false
      mockConfirm
        .mockResolvedValueOnce(true)
        .mockResolvedValueOnce(false)

      renderAccountSettings()
      const deleteButton = screen.getByRole('button', { name: /Delete My Account/i })
      fireEvent.click(deleteButton)

      await waitFor(() => {
        expect(mockConfirm).toHaveBeenCalledTimes(2)
        expect(mockDeleteAccount).not.toHaveBeenCalled()
      })
    })

    it('shows loading state during deletion', async () => {
      // Both confirmations pass
      mockConfirm.mockResolvedValue(true)
      // Deletion never resolves
      mockDeleteAccount.mockImplementation(() => new Promise(() => {}))

      renderAccountSettings()
      const deleteButton = screen.getByRole('button', { name: /Delete My Account/i })
      fireEvent.click(deleteButton)

      await waitFor(() => {
        expect(screen.getByText(/Deleting Account.../i)).toBeInTheDocument()
      })
    })

    it('calls logout and navigates to login after successful deletion', async () => {
      // Both confirmations pass
      mockConfirm.mockResolvedValue(true)

      renderAccountSettings()
      const deleteButton = screen.getByRole('button', { name: /Delete My Account/i })
      fireEvent.click(deleteButton)

      await waitFor(() => {
        expect(mockDeleteAccount).toHaveBeenCalledTimes(1)
        expect(mockLogout).toHaveBeenCalled()
        expect(mockNavigate).toHaveBeenCalledWith('/login', expect.anything())
      })
    })

    it('shows error message when deletion fails', async () => {
      // Both confirmations pass
      mockConfirm.mockResolvedValue(true)
      mockDeleteAccount.mockRejectedValue(new Error('Deletion failed'))

      renderAccountSettings()
      const deleteButton = screen.getByRole('button', { name: /Delete My Account/i })
      fireEvent.click(deleteButton)

      await waitFor(() => {
        expect(screen.getByText(/Failed to delete account/i)).toBeInTheDocument()
      })
    })

    it('requires two confirmations before deletion', async () => {
      // Both confirmations pass
      mockConfirm.mockResolvedValue(true)

      renderAccountSettings()
      const deleteButton = screen.getByRole('button', { name: /Delete My Account/i })
      fireEvent.click(deleteButton)

      await waitFor(() => {
        // Two confirmations should have been called
        expect(mockConfirm).toHaveBeenCalledTimes(2)
      })
    })
  })

  // ==========================================================================
  // Legal Links Tests
  // ==========================================================================

  describe('Legal links', () => {
    it('displays link to Terms of Service', () => {
      renderAccountSettings()
      expect(screen.getByRole('link', { name: /Terms of Service/i })).toBeInTheDocument()
    })

    it('Terms of Service link points to correct page', () => {
      renderAccountSettings()
      const termsLink = screen.getByRole('link', { name: /Terms of Service/i })
      expect(termsLink).toHaveAttribute('href', '/terms')
    })

    it('displays link to Privacy Policy', () => {
      renderAccountSettings()
      expect(screen.getByRole('link', { name: /Privacy Policy/i })).toBeInTheDocument()
    })

    it('Privacy Policy link points to correct page', () => {
      renderAccountSettings()
      const privacyLink = screen.getByRole('link', { name: /Privacy Policy/i })
      expect(privacyLink).toHaveAttribute('href', '/privacy')
    })

    it('displays support email link', () => {
      renderAccountSettings()
      expect(screen.getByRole('link', { name: /Contact Support/i })).toBeInTheDocument()
    })
  })
})

// ==========================================================================
// Demo Mode Tests
// ==========================================================================

describe('AccountSettings in Demo Mode', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Set demo mode
    mockAuthState.user = mockUser
    mockAuthState.demoMode = true
    mockAuthState.loading = false
  })

  afterEach(() => {
    // Reset back to normal mode
    mockAuthState.demoMode = false
  })

  it('shows demo mode warning', () => {
    renderAccountSettings()
    expect(screen.getByText(/demo mode/i)).toBeInTheDocument()
  })

  it('shows account settings title in demo mode', () => {
    renderAccountSettings()
    expect(screen.getByRole('heading', { name: /Account Settings/i })).toBeInTheDocument()
  })

  it('shows back button in demo mode', () => {
    renderAccountSettings()
    expect(screen.getByRole('link', { name: /Back/i })).toBeInTheDocument()
  })
})

// ==========================================================================
// No User Tests
// ==========================================================================

describe('AccountSettings without user', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    // Set no user state
    mockAuthState.user = null
    mockAuthState.demoMode = false
    mockAuthState.loading = false
  })

  afterEach(() => {
    // Reset back to normal state
    mockAuthState.user = mockUser
  })

  it('redirects to login when no user', () => {
    renderAccountSettings()
    expect(mockNavigate).toHaveBeenCalledWith('/login')
  })
})

// ==========================================================================
// Accessibility Tests
// ==========================================================================

describe('AccountSettings accessibility', () => {
  it('has proper heading hierarchy', () => {
    renderAccountSettings()

    const h1 = screen.getByRole('heading', { level: 1, name: /Account Settings/i })
    expect(h1).toBeInTheDocument()
  })

  it('buttons have accessible names', () => {
    renderAccountSettings()

    expect(screen.getByRole('button', { name: /Download/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Delete My Account/i })).toBeInTheDocument()
  })

  it('links have accessible names', () => {
    renderAccountSettings()

    expect(screen.getByRole('link', { name: /Back/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Terms of Service/i })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Privacy Policy/i })).toBeInTheDocument()
  })
})

// ==========================================================================
// GDPR/CCPA Compliance Tests
// ==========================================================================

describe('AccountSettings GDPR/CCPA compliance', () => {
  it('provides data download capability (Right to Access)', () => {
    renderAccountSettings()
    expect(screen.getByRole('button', { name: /Download/i })).toBeInTheDocument()
  })

  it('provides account deletion capability (Right to Erasure)', () => {
    renderAccountSettings()
    expect(screen.getByRole('button', { name: /Delete My Account/i })).toBeInTheDocument()
  })

  it('displays clear warning before deletion', () => {
    renderAccountSettings()
    expect(screen.getByText(/This action is irreversible/i)).toBeInTheDocument()
  })

  it('requires multiple confirmations for deletion', async () => {
    // Both confirmations pass
    mockConfirm.mockResolvedValue(true)

    renderAccountSettings()
    const deleteButton = screen.getByRole('button', { name: /Delete My Account/i })
    fireEvent.click(deleteButton)

    await waitFor(() => {
      // Two confirmation dialogs should be shown
      expect(mockConfirm).toHaveBeenCalledTimes(2)
    })
  })

  it('lists all data types that will be deleted', () => {
    renderAccountSettings()

    // User profile
    expect(screen.getByText(/Your user profile and account/i)).toBeInTheDocument()
    // Submissions
    expect(screen.getByText(/All submissions and design diagrams/i)).toBeInTheDocument()
    // Chat history
    expect(screen.getByText(/Chat history and AI coaching conversations/i)).toBeInTheDocument()
    // Test results
    expect(screen.getByText(/Test results and evaluation scores/i)).toBeInTheDocument()
  })
})
