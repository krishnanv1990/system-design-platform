/**
 * TypeScript type definitions for the System Design Platform
 */

// User types
export interface User {
  id: number
  email: string
  name: string | null
  avatar_url: string | null
  created_at: string
}

// Problem types
export interface Problem {
  id: number
  title: string
  description: string
  difficulty: 'easy' | 'medium' | 'hard'
  expected_schema: Record<string, unknown> | null
  expected_api_spec: Record<string, unknown> | null
  hints: string[] | null
  tags: string[] | null
  created_at: string
}

export interface ProblemListItem {
  id: number
  title: string
  description: string
  difficulty: 'easy' | 'medium' | 'hard'
  tags: string[] | null
  created_at: string
}

// Submission types
export type SubmissionStatus =
  | 'pending'
  | 'validating'
  | 'validation_failed'
  | 'generating_infra'
  | 'deploying'
  | 'deploy_failed'
  | 'testing'
  | 'completed'
  | 'failed'

export interface Submission {
  id: number
  problem_id: number
  user_id: number
  status: SubmissionStatus
  error_message: string | null
  created_at: string
}

export interface SubmissionDetail extends Submission {
  schema_input: Record<string, unknown> | null
  api_spec_input: Record<string, unknown> | null
  design_text: string | null
  generated_terraform: string | null
  deployment_id: string | null
  namespace: string | null
  validation_feedback: ValidationFeedback | null
  updated_at: string
}

export interface SubmissionCreate {
  problem_id: number
  schema_input?: Record<string, unknown>
  api_spec_input?: Record<string, unknown>
  design_text?: string
}

// Validation types
export interface ProgressStep {
  step: string
  detail: string
  progress_pct: number
  timestamp: string
}

export interface ValidationFeedback {
  is_valid: boolean
  errors: string[]
  warnings: string[]
  suggestions: string[]
  score: number | null
  feedback?: {
    scalability: { score: number; comments: string }
    reliability: { score: number; comments: string }
    data_model: { score: number; comments: string }
    api_design: { score: number; comments: string }
    overall: string
  }
  // Progress tracking fields
  progress?: ProgressStep[]
  current_step?: string
  current_detail?: string
}

export interface ValidationRequest {
  problem_id: number
  schema_input?: Record<string, unknown>
  api_spec_input?: Record<string, unknown>
  design_text?: string
}

export interface ValidationResponse {
  is_valid: boolean
  errors: string[]
  warnings: string[]
  suggestions: string[]
  score: number | null
}

// Test result types
export type TestType = 'functional' | 'performance' | 'chaos'
export type TestStatus = 'pending' | 'running' | 'passed' | 'failed' | 'error' | 'skipped'

// Error analysis types
export type ErrorCategory = 'user_solution' | 'platform' | 'deployment' | 'unknown'
export type AnalysisStatus = 'pending' | 'analyzing' | 'completed' | 'failed' | 'skipped'

export interface ErrorAnalysis {
  category: ErrorCategory
  confidence: number
  explanation: string
  suggestions: string[]
  technical_details?: {
    error_type?: string
    affected_component?: string
  }
  analyzed_at?: string
  status: AnalysisStatus
  demo_mode?: boolean
}

export interface TestResult {
  id: number
  submission_id: number
  test_type: TestType
  test_name: string
  status: TestStatus
  details: Record<string, unknown> | null
  duration_ms: number | null
  chaos_scenario: string | null
  created_at: string
  // Error analysis fields
  error_category?: ErrorCategory
  error_analysis?: ErrorAnalysis
  ai_analysis_status?: AnalysisStatus
}

export interface IssuesByCategory {
  user_solution: number
  platform: number
  deployment: number
  unknown: number
}

export interface TestSummary {
  submission_id: number
  total_tests: number
  passed: number
  failed: number
  errors: number
  skipped: number
  functional_tests: TestResult[]
  performance_tests: TestResult[]
  chaos_tests: TestResult[]
  overall_status: 'passed' | 'failed' | 'partial' | 'pending'
  // Error analysis summary
  issues_by_category?: IssuesByCategory
  has_platform_issues?: boolean
}

// Auth types
export interface TokenResponse {
  access_token: string
  token_type: string
  user: User
}
