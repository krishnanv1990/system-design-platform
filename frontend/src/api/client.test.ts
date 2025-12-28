import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import axios from 'axios'
import { problemsApi, submissionsApi, testsApi, authApi, assetsApi, chatApi } from './client'
import type { Mock } from 'vitest'

interface MockAxios {
  create: Mock
  get: Mock
  post: Mock
  delete: Mock
  interceptors: {
    request: { use: Mock }
    response: { use: Mock }
  }
}

// Mock axios
vi.mock('axios', () => {
  const mockAxiosInstance: MockAxios = {
    create: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
  }
  mockAxiosInstance.create.mockReturnValue(mockAxiosInstance)
  return { default: mockAxiosInstance }
})

const mockAxios = axios as unknown as MockAxios

describe('API Client', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('problemsApi', () => {
    it('list - fetches problems list', async () => {
      const mockProblems = [
        { id: 1, title: 'URL Shortener', difficulty: 'medium' },
        { id: 2, title: 'Chat App', difficulty: 'hard' },
      ]
      mockAxios.get.mockResolvedValueOnce({ data: mockProblems })

      const result = await problemsApi.list()

      expect(mockAxios.get).toHaveBeenCalledWith('/problems', { params: undefined })
      expect(result).toEqual(mockProblems)
    })

    it('list - fetches with params', async () => {
      mockAxios.get.mockResolvedValueOnce({ data: [] })

      await problemsApi.list({ skip: 10, limit: 5, difficulty: 'hard' })

      expect(mockAxios.get).toHaveBeenCalledWith('/problems', {
        params: { skip: 10, limit: 5, difficulty: 'hard' },
      })
    })

    it('get - fetches single problem', async () => {
      const mockProblem = { id: 1, title: 'URL Shortener' }
      mockAxios.get.mockResolvedValueOnce({ data: mockProblem })

      const result = await problemsApi.get(1)

      expect(mockAxios.get).toHaveBeenCalledWith('/problems/1')
      expect(result).toEqual(mockProblem)
    })

    it('create - creates new problem', async () => {
      const newProblem = { title: 'New Problem', difficulty: 'easy' as const }
      mockAxios.post.mockResolvedValueOnce({ data: { id: 3, ...newProblem } })

      const result = await problemsApi.create(newProblem)

      expect(mockAxios.post).toHaveBeenCalledWith('/problems', newProblem)
      expect(result.id).toBe(3)
    })
  })

  describe('submissionsApi', () => {
    it('create - creates new submission', async () => {
      const submission = { problem_id: 1, design_text: 'My design' }
      mockAxios.post.mockResolvedValueOnce({ data: { id: 100, ...submission } })

      const result = await submissionsApi.create(submission)

      expect(mockAxios.post).toHaveBeenCalledWith('/submissions', submission)
      expect(result.id).toBe(100)
    })

    it('get - fetches submission details', async () => {
      const mockSubmission = { id: 100, status: 'completed' }
      mockAxios.get.mockResolvedValueOnce({ data: mockSubmission })

      const result = await submissionsApi.get(100)

      expect(mockAxios.get).toHaveBeenCalledWith('/submissions/100')
      expect(result).toEqual(mockSubmission)
    })

    it('validate - validates submission', async () => {
      const validationRequest = { problem_id: 1, design_text: 'design' }
      const validationResponse = { is_valid: true, errors: [], warnings: [] }
      mockAxios.post.mockResolvedValueOnce({ data: validationResponse })

      const result = await submissionsApi.validate(validationRequest)

      expect(mockAxios.post).toHaveBeenCalledWith('/submissions/validate', validationRequest)
      expect(result.is_valid).toBe(true)
    })

    it('delete - deletes submission', async () => {
      mockAxios.delete.mockResolvedValueOnce({})

      await submissionsApi.delete(100)

      expect(mockAxios.delete).toHaveBeenCalledWith('/submissions/100')
    })

    it('getDeploymentStatus - fetches deployment status', async () => {
      const mockStatus = { deployment_id: 'dep-123', status: 'running' }
      mockAxios.get.mockResolvedValueOnce({ data: mockStatus })

      const result = await submissionsApi.getDeploymentStatus(100)

      expect(mockAxios.get).toHaveBeenCalledWith('/submissions/100/deployment')
      expect(result).toEqual(mockStatus)
    })

    it('teardown - tears down deployment', async () => {
      mockAxios.post.mockResolvedValueOnce({ data: { success: true } })

      const result = await submissionsApi.teardown(100)

      expect(mockAxios.post).toHaveBeenCalledWith('/submissions/100/teardown')
      expect(result.success).toBe(true)
    })
  })

  describe('testsApi', () => {
    it('getSubmissionTests - fetches tests for submission', async () => {
      const mockTests = [{ id: 1, test_name: 'Test 1' }]
      mockAxios.get.mockResolvedValueOnce({ data: mockTests })

      const result = await testsApi.getSubmissionTests(100)

      expect(mockAxios.get).toHaveBeenCalledWith('/tests/submission/100', {
        params: { test_type: undefined },
      })
      expect(result).toEqual(mockTests)
    })

    it('getTestSummary - fetches test summary', async () => {
      const mockSummary = { total: 10, passed: 8, failed: 2 }
      mockAxios.get.mockResolvedValueOnce({ data: mockSummary })

      const result = await testsApi.getTestSummary(100)

      expect(mockAxios.get).toHaveBeenCalledWith('/tests/submission/100/summary')
      expect(result).toEqual(mockSummary)
    })
  })

  describe('authApi', () => {
    it('getCurrentUser - fetches current user', async () => {
      const mockUser = { id: 1, email: 'test@example.com' }
      mockAxios.get.mockResolvedValueOnce({ data: mockUser })

      const result = await authApi.getCurrentUser()

      expect(mockAxios.get).toHaveBeenCalledWith('/auth/me')
      expect(result).toEqual(mockUser)
    })

    it('getDemoStatus - fetches demo status', async () => {
      const mockStatus = { demo_mode: true, message: 'Demo mode active' }
      mockAxios.get.mockResolvedValueOnce({ data: mockStatus })

      const result = await authApi.getDemoStatus()

      expect(mockAxios.get).toHaveBeenCalledWith('/auth/demo-status')
      expect(result.demo_mode).toBe(true)
    })

    it('downloadUserData - downloads user data export', async () => {
      const mockExport = {
        user: {
          id: 1,
          email: 'test@example.com',
          name: 'Test User',
          avatar_url: null,
          created_at: '2024-01-01T00:00:00Z',
          linked_providers: ['google'],
        },
        submissions: [
          {
            id: 1,
            problem_id: 1,
            problem_title: 'URL Shortener',
            status: 'completed',
            created_at: '2024-01-01T00:00:00Z',
            design_text: 'My design',
            schema_input: {},
            api_spec_input: {},
          },
        ],
        test_results: [],
        exported_at: '2024-01-01T00:00:00Z',
      }
      mockAxios.get.mockResolvedValueOnce({ data: mockExport })

      const result = await authApi.downloadUserData()

      expect(mockAxios.get).toHaveBeenCalledWith('/auth/download-data')
      expect(result.user.email).toBe('test@example.com')
      expect(result.submissions).toHaveLength(1)
      expect(result.exported_at).toBeDefined()
    })

    it('deleteAccount - deletes user account', async () => {
      const mockResponse = { message: 'Account deleted successfully' }
      mockAxios.delete.mockResolvedValueOnce({ data: mockResponse })

      const result = await authApi.deleteAccount()

      expect(mockAxios.delete).toHaveBeenCalledWith('/auth/delete-account')
      expect(result.message).toContain('deleted')
    })
  })

  describe('assetsApi', () => {
    it('getSubmissionAssets - fetches assets for submission', async () => {
      const mockAssets = { service_name: 'my-service', region: 'us-central1' }
      mockAxios.get.mockResolvedValueOnce({ data: mockAssets })

      const result = await assetsApi.getSubmissionAssets(100)

      expect(mockAxios.get).toHaveBeenCalledWith('/assets/submission/100')
      expect(result).toEqual(mockAssets)
    })

    it('getSubmissionCode - fetches generated code', async () => {
      const mockCode = { code: 'def main(): pass' }
      mockAxios.get.mockResolvedValueOnce({ data: mockCode })

      const result = await assetsApi.getSubmissionCode(100)

      expect(mockAxios.get).toHaveBeenCalledWith('/assets/submission/100/code')
      expect(result).toEqual(mockCode)
    })
  })

  describe('chatApi', () => {
    it('sendMessage - sends chat message', async () => {
      const request = {
        problem_id: 1,
        message: 'How do I design this?',
        conversation_history: [],
      }
      const response = {
        response: 'Here is my suggestion...',
        is_on_track: true,
        demo_mode: false,
      }
      mockAxios.post.mockResolvedValueOnce({ data: response })

      const result = await chatApi.sendMessage(request)

      expect(mockAxios.post).toHaveBeenCalledWith('/chat/', request)
      expect(result.response).toBe('Here is my suggestion...')
    })

    it('sendMessage - sends message with difficulty level', async () => {
      const request = {
        problem_id: 1,
        message: 'How do I design this at L7 level?',
        conversation_history: [],
        difficulty_level: 'hard' as const,
      }
      const response = {
        response: 'For L7 level, you need global distribution...',
        is_on_track: true,
        demo_mode: false,
      }
      mockAxios.post.mockResolvedValueOnce({ data: response })

      const result = await chatApi.sendMessage(request)

      expect(mockAxios.post).toHaveBeenCalledWith('/chat/', request)
      expect(result.response).toContain('L7')
    })

    it('generateSummary - generates design summary', async () => {
      const request = {
        problem_id: 1,
        difficulty_level: 'medium' as const,
        conversation_history: [
          { role: 'user' as const, content: 'How should I design this?' },
          { role: 'assistant' as const, content: 'Start with KGS...' },
        ],
      }
      const response = {
        summary: 'This design demonstrates a solid understanding...',
        key_components: ['KGS', 'Redis Cache', 'Load Balancer'],
        strengths: ['Good use of KGS', 'Proper caching'],
        areas_for_improvement: ['Consider adding analytics'],
        overall_score: 85,
        difficulty_level: 'medium',
        level_info: {
          level: 'L6',
          title: 'Staff Engineer',
          description: 'Production-ready design',
        },
        demo_mode: false,
      }
      mockAxios.post.mockResolvedValueOnce({ data: response })

      const result = await chatApi.generateSummary(request)

      expect(mockAxios.post).toHaveBeenCalledWith('/chat/generate-summary', request)
      expect(result.summary).toContain('solid understanding')
      expect(result.key_components).toContain('KGS')
      expect(result.overall_score).toBe(85)
      expect(result.level_info.level).toBe('L6')
    })

    it('generateSummary - handles different difficulty levels', async () => {
      const easyRequest = {
        problem_id: 1,
        difficulty_level: 'easy' as const,
        conversation_history: [],
      }
      const easyResponse = {
        summary: 'Basic implementation',
        key_components: ['KGS'],
        strengths: ['Working solution'],
        areas_for_improvement: ['Add caching'],
        overall_score: 70,
        difficulty_level: 'easy',
        level_info: {
          level: 'L5',
          title: 'Senior Software Engineer',
          description: 'Core functionality',
        },
        demo_mode: true,
      }
      mockAxios.post.mockResolvedValueOnce({ data: easyResponse })

      const result = await chatApi.generateSummary(easyRequest)

      expect(result.difficulty_level).toBe('easy')
      expect(result.level_info.level).toBe('L5')
    })

    it('getLevelRequirements - fetches level requirements', async () => {
      const response = {
        problem_id: 1,
        problem_title: 'URL Shortener',
        difficulty: 'medium',
        level_info: {
          level: 'L6',
          title: 'Staff Engineer',
          description: 'Production-ready design',
        },
        requirements: '**L6 (Staff SWE) URL Shortener Requirements:**...',
      }
      mockAxios.get.mockResolvedValueOnce({ data: response })

      const result = await chatApi.getLevelRequirements(1, 'medium')

      expect(mockAxios.get).toHaveBeenCalledWith('/chat/level-requirements/1', {
        params: { difficulty: 'medium' },
      })
      expect(result.level_info.level).toBe('L6')
      expect(result.requirements).toContain('L6')
    })

    it('getLevelRequirements - defaults to medium difficulty', async () => {
      const response = {
        problem_id: 1,
        problem_title: 'URL Shortener',
        difficulty: 'medium',
        level_info: { level: 'L6', title: 'Staff Engineer', description: '' },
        requirements: 'Medium level requirements',
      }
      mockAxios.get.mockResolvedValueOnce({ data: response })

      await chatApi.getLevelRequirements(1)

      expect(mockAxios.get).toHaveBeenCalledWith('/chat/level-requirements/1', {
        params: { difficulty: 'medium' },
      })
    })

    it('getLevelRequirements - fetches L5 requirements for easy', async () => {
      const response = {
        problem_id: 1,
        problem_title: 'URL Shortener',
        difficulty: 'easy',
        level_info: {
          level: 'L5',
          title: 'Senior Software Engineer',
          description: 'Core functionality',
        },
        requirements: '**L5 (Senior SWE) Requirements:**...',
      }
      mockAxios.get.mockResolvedValueOnce({ data: response })

      const result = await chatApi.getLevelRequirements(1, 'easy')

      expect(result.level_info.level).toBe('L5')
    })

    it('getLevelRequirements - fetches L7 requirements for hard', async () => {
      const response = {
        problem_id: 1,
        problem_title: 'URL Shortener',
        difficulty: 'hard',
        level_info: {
          level: 'L7',
          title: 'Principal Engineer',
          description: 'Global-scale architecture',
        },
        requirements: '**L7 (Principal SWE) Requirements:**...',
      }
      mockAxios.get.mockResolvedValueOnce({ data: response })

      const result = await chatApi.getLevelRequirements(1, 'hard')

      expect(result.level_info.level).toBe('L7')
    })
  })
})
