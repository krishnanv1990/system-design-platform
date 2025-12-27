/**
 * API client for backend communication
 */

import axios, { AxiosInstance } from 'axios'
import {
  User,
  Problem,
  ProblemListItem,
  Submission,
  SubmissionDetail,
  SubmissionCreate,
  ValidationRequest,
  ValidationResponse,
  TestResult,
  TestSummary,
} from '../types'

// Use relative URL in production (when served from load balancer)
// or explicit URL in development
const API_URL = import.meta.env.VITE_API_URL

/**
 * Create axios instance with default config
 */
const createApiClient = (): AxiosInstance => {
  const client = axios.create({
    baseURL: API_URL ? `${API_URL}/api` : '/api',
    headers: {
      'Content-Type': 'application/json',
    },
  })

  // Add auth token to requests
  client.interceptors.request.use((config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  })

  // Handle auth errors
  client.interceptors.response.use(
    (response) => response,
    (error) => {
      if (error.response?.status === 401) {
        localStorage.removeItem('token')
        window.location.href = '/login'
      }
      return Promise.reject(error)
    }
  )

  return client
}

const api = createApiClient()

/**
 * OAuth provider types
 */
export type OAuthProvider = 'google' | 'facebook' | 'linkedin' | 'github'

/**
 * Authentication API
 * Supports multiple OAuth providers: Google, Facebook, LinkedIn, GitHub
 */
export const authApi = {
  /**
   * Get OAuth URL for the specified provider
   */
  getAuthUrl: (provider: OAuthProvider): string => {
    const baseUrl = API_URL ? `${API_URL}/api/auth` : '/api/auth'
    return `${baseUrl}/${provider}`
  },

  // Legacy method for backward compatibility
  getGoogleAuthUrl: () => API_URL ? `${API_URL}/api/auth/google` : '/api/auth/google',

  // Convenience methods for each provider
  getFacebookAuthUrl: () => API_URL ? `${API_URL}/api/auth/facebook` : '/api/auth/facebook',
  getLinkedInAuthUrl: () => API_URL ? `${API_URL}/api/auth/linkedin` : '/api/auth/linkedin',
  getGitHubAuthUrl: () => API_URL ? `${API_URL}/api/auth/github` : '/api/auth/github',

  getCurrentUser: async (): Promise<User> => {
    const response = await api.get('/auth/me')
    return response.data
  },

  logout: async (): Promise<void> => {
    await api.post('/auth/logout')
    localStorage.removeItem('token')
  },

  getDemoStatus: async (): Promise<{ demo_mode: boolean; message: string }> => {
    const response = await api.get('/auth/demo-status')
    return response.data
  },

  getDemoUser: async (): Promise<User> => {
    const response = await api.get('/auth/demo-user')
    return response.data
  },

  /**
   * Get available OAuth providers and their configuration status
   */
  getAvailableProviders: async (): Promise<{ providers: Record<OAuthProvider, boolean> }> => {
    const response = await api.get('/auth/providers')
    return response.data
  },
}

/**
 * Problems API
 */
export const problemsApi = {
  list: async (params?: {
    skip?: number
    limit?: number
    difficulty?: string
    tag?: string
  }): Promise<ProblemListItem[]> => {
    const response = await api.get('/problems', { params })
    return response.data
  },

  get: async (id: number): Promise<Problem> => {
    const response = await api.get(`/problems/${id}`)
    return response.data
  },

  create: async (data: Partial<Problem>): Promise<Problem> => {
    const response = await api.post('/problems', data)
    return response.data
  },
}

/**
 * Submissions API
 */
export const submissionsApi = {
  create: async (data: SubmissionCreate): Promise<Submission> => {
    const response = await api.post('/submissions', data)
    return response.data
  },

  list: async (params?: {
    skip?: number
    limit?: number
    problem_id?: number
  }): Promise<Submission[]> => {
    const response = await api.get('/submissions', { params })
    return response.data
  },

  get: async (id: number): Promise<SubmissionDetail> => {
    const response = await api.get(`/submissions/${id}`)
    return response.data
  },

  validate: async (data: ValidationRequest): Promise<ValidationResponse> => {
    const response = await api.post('/submissions/validate', data)
    return response.data
  },

  delete: async (id: number): Promise<void> => {
    await api.delete(`/submissions/${id}`)
  },

  getDeploymentStatus: async (id: number): Promise<any> => {
    const response = await api.get(`/submissions/${id}/deployment`)
    return response.data
  },

  teardown: async (id: number): Promise<any> => {
    const response = await api.post(`/submissions/${id}/teardown`)
    return response.data
  },

  extendTimeout: async (id: number, additionalMinutes: number = 30): Promise<any> => {
    const response = await api.post(`/submissions/${id}/extend`, null, {
      params: { additional_minutes: additionalMinutes }
    })
    return response.data
  },
}

/**
 * Tests API
 */
export const testsApi = {
  getSubmissionTests: async (
    submissionId: number,
    testType?: string
  ): Promise<TestResult[]> => {
    const response = await api.get(`/tests/submission/${submissionId}`, {
      params: { test_type: testType },
    })
    return response.data
  },

  getTestSummary: async (submissionId: number): Promise<TestSummary> => {
    const response = await api.get(`/tests/submission/${submissionId}/summary`)
    return response.data
  },

  getTestResult: async (testId: number): Promise<TestResult> => {
    const response = await api.get(`/tests/${testId}`)
    return response.data
  },
}

/**
 * GCP Assets API
 */
export const assetsApi = {
  getSubmissionAssets: async (submissionId: number): Promise<any> => {
    const response = await api.get(`/assets/submission/${submissionId}`)
    return response.data
  },

  getSubmissionCode: async (submissionId: number): Promise<any> => {
    const response = await api.get(`/assets/submission/${submissionId}/code`)
    return response.data
  },

  getAllAssets: async (): Promise<any> => {
    const response = await api.get('/assets/admin/all')
    return response.data
  },

  getCleanupCandidates: async (hoursOld: number = 1): Promise<any> => {
    const response = await api.get('/assets/admin/cleanup-candidates', {
      params: { hours_old: hoursOld },
    })
    return response.data
  },
}

/**
 * Chat API - Design coaching chatbot
 */
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatRequest {
  problem_id: number
  message: string
  conversation_history: ChatMessage[]
  current_schema?: any
  current_api_spec?: any
  current_diagram?: any
}

export interface DiagramFeedback {
  strengths: string[]
  weaknesses: string[]
  suggested_improvements: string[]
  is_on_track: boolean
  score?: number
}

export interface ChatResponse {
  response: string
  diagram_feedback?: DiagramFeedback
  suggested_improvements: string[]
  is_on_track: boolean
  demo_mode: boolean
}

export const chatApi = {
  sendMessage: async (request: ChatRequest): Promise<ChatResponse> => {
    const response = await api.post('/chat/', request)
    return response.data
  },

  evaluateDiagram: async (problemId: number, diagramData: any): Promise<any> => {
    const response = await api.post('/chat/evaluate-diagram', null, {
      params: { problem_id: problemId },
      data: diagramData,
    })
    return response.data
  },
}

export default api
