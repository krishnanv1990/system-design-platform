/**
 * Tests for authentication API functions
 *
 * Tests cover:
 * - OAuth URL generation for all providers
 * - Auth API methods
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// We'll test the authApi by mocking axios and verifying the URLs are correctly generated
describe('authApi', () => {
  beforeEach(() => {
    vi.resetModules()
  })

  afterEach(() => {
    vi.unstubAllEnvs()
  })

  describe('OAuth URL Generation', () => {
    it('generates correct Google OAuth URL without API_URL', async () => {
      vi.stubEnv('VITE_API_URL', '')
      const { authApi } = await import('./client')

      expect(authApi.getGoogleAuthUrl()).toBe('/api/auth/google?source=user')
    })

    it('generates correct Facebook OAuth URL without API_URL', async () => {
      vi.stubEnv('VITE_API_URL', '')
      const { authApi } = await import('./client')

      expect(authApi.getFacebookAuthUrl()).toBe('/api/auth/facebook?source=user')
    })

    it('generates correct LinkedIn OAuth URL without API_URL', async () => {
      vi.stubEnv('VITE_API_URL', '')
      const { authApi } = await import('./client')

      expect(authApi.getLinkedInAuthUrl()).toBe('/api/auth/linkedin?source=user')
    })

    it('generates correct GitHub OAuth URL without API_URL', async () => {
      vi.stubEnv('VITE_API_URL', '')
      const { authApi } = await import('./client')

      expect(authApi.getGitHubAuthUrl()).toBe('/api/auth/github?source=user')
    })

    it('generates correct Google OAuth URL with API_URL', async () => {
      vi.stubEnv('VITE_API_URL', 'http://api.example.com')
      const { authApi } = await import('./client')

      expect(authApi.getGoogleAuthUrl()).toBe('http://api.example.com/api/auth/google?source=user')
    })

    it('generates correct Facebook OAuth URL with API_URL', async () => {
      vi.stubEnv('VITE_API_URL', 'http://api.example.com')
      const { authApi } = await import('./client')

      expect(authApi.getFacebookAuthUrl()).toBe('http://api.example.com/api/auth/facebook?source=user')
    })

    it('generates correct LinkedIn OAuth URL with API_URL', async () => {
      vi.stubEnv('VITE_API_URL', 'http://api.example.com')
      const { authApi } = await import('./client')

      expect(authApi.getLinkedInAuthUrl()).toBe('http://api.example.com/api/auth/linkedin?source=user')
    })

    it('generates correct GitHub OAuth URL with API_URL', async () => {
      vi.stubEnv('VITE_API_URL', 'http://api.example.com')
      const { authApi } = await import('./client')

      expect(authApi.getGitHubAuthUrl()).toBe('http://api.example.com/api/auth/github?source=user')
    })

    it('generates correct OAuth URL with admin source', async () => {
      vi.stubEnv('VITE_API_URL', '')
      const { authApi } = await import('./client')

      expect(authApi.getGoogleAuthUrl('admin')).toBe('/api/auth/google?source=admin')
      expect(authApi.getFacebookAuthUrl('admin')).toBe('/api/auth/facebook?source=admin')
      expect(authApi.getLinkedInAuthUrl('admin')).toBe('/api/auth/linkedin?source=admin')
      expect(authApi.getGitHubAuthUrl('admin')).toBe('/api/auth/github?source=admin')
    })
  })

  describe('getAuthUrl generic method', () => {
    it('generates correct URL for google provider', async () => {
      vi.stubEnv('VITE_API_URL', '')
      const { authApi } = await import('./client')

      expect(authApi.getAuthUrl('google')).toBe('/api/auth/google?source=user')
    })

    it('generates correct URL for facebook provider', async () => {
      vi.stubEnv('VITE_API_URL', '')
      const { authApi } = await import('./client')

      expect(authApi.getAuthUrl('facebook')).toBe('/api/auth/facebook?source=user')
    })

    it('generates correct URL for linkedin provider', async () => {
      vi.stubEnv('VITE_API_URL', '')
      const { authApi } = await import('./client')

      expect(authApi.getAuthUrl('linkedin')).toBe('/api/auth/linkedin?source=user')
    })

    it('generates correct URL for github provider', async () => {
      vi.stubEnv('VITE_API_URL', '')
      const { authApi } = await import('./client')

      expect(authApi.getAuthUrl('github')).toBe('/api/auth/github?source=user')
    })

    it('generates correct URL with API_URL prefix', async () => {
      vi.stubEnv('VITE_API_URL', 'https://api.test.com')
      const { authApi } = await import('./client')

      expect(authApi.getAuthUrl('google')).toBe('https://api.test.com/api/auth/google?source=user')
      expect(authApi.getAuthUrl('facebook')).toBe('https://api.test.com/api/auth/facebook?source=user')
      expect(authApi.getAuthUrl('linkedin')).toBe('https://api.test.com/api/auth/linkedin?source=user')
      expect(authApi.getAuthUrl('github')).toBe('https://api.test.com/api/auth/github?source=user')
    })

    it('generates correct URL with admin source', async () => {
      vi.stubEnv('VITE_API_URL', '')
      const { authApi } = await import('./client')

      expect(authApi.getAuthUrl('google', 'admin')).toBe('/api/auth/google?source=admin')
      expect(authApi.getAuthUrl('facebook', 'admin')).toBe('/api/auth/facebook?source=admin')
      expect(authApi.getAuthUrl('linkedin', 'admin')).toBe('/api/auth/linkedin?source=admin')
      expect(authApi.getAuthUrl('github', 'admin')).toBe('/api/auth/github?source=admin')
    })
  })
})

describe('OAuthProvider type', () => {
  it('exports OAuthProvider type with correct values', async () => {
    const { authApi } = await import('./client')

    // These should not throw type errors
    const google: Parameters<typeof authApi.getAuthUrl>[0] = 'google'
    const facebook: Parameters<typeof authApi.getAuthUrl>[0] = 'facebook'
    const linkedin: Parameters<typeof authApi.getAuthUrl>[0] = 'linkedin'
    const github: Parameters<typeof authApi.getAuthUrl>[0] = 'github'

    expect(google).toBe('google')
    expect(facebook).toBe('facebook')
    expect(linkedin).toBe('linkedin')
    expect(github).toBe('github')
  })
})
