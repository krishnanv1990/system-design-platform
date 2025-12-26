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

const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000'

/**
 * Create axios instance with default config
 */
const createApiClient = (): AxiosInstance => {
  const client = axios.create({
    baseURL: `${API_URL}/api`,
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
 * Authentication API
 */
export const authApi = {
  getGoogleAuthUrl: () => `${API_URL}/api/auth/google`,

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

export default api
