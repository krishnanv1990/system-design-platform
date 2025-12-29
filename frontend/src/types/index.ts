/**
 * TypeScript type definitions for the System Design Platform
 *
 * Supports difficulty levels mapped to engineering levels:
 * - easy: L5 SWE (Senior Software Engineer)
 * - medium: L6 SWE (Staff Engineer)
 * - hard: L7 SWE (Principal Engineer)
 */

// User types
export interface User {
  id: number
  email: string
  name: string | null
  display_name?: string | null
  avatar_url: string | null
  created_at: string
  // OAuth provider IDs (optional, may not be present in all responses)
  google_id?: string | null
  facebook_id?: string | null
  linkedin_id?: string | null
  github_id?: string | null
  // Ban status (optional, may not be present in all responses)
  is_banned?: boolean
  ban_reason?: string | null
}

// Difficulty level types
export type DifficultyLevel = 'easy' | 'medium' | 'hard'

export interface DifficultyLevelInfo {
  level: string  // L5, L6, L7
  title: string  // Senior Software Engineer, Staff Engineer, Principal Engineer
  description: string
}

export interface DifficultyRequirements {
  focus_areas: string[]
  expected_components: string[]
  evaluation_criteria: string[]
  scale_requirements?: string
  additional_considerations?: string[]
}

// Problem types
export interface Problem {
  id: number
  title: string
  description: string
  difficulty: DifficultyLevel
  difficulty_requirements?: Record<DifficultyLevel, DifficultyRequirements> | null
  difficulty_info?: DifficultyLevelInfo | null
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
  difficulty: DifficultyLevel
  difficulty_info?: DifficultyLevelInfo | null
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

// Design Summary types
export interface DesignSummaryRequest {
  problem_id: number
  difficulty_level: DifficultyLevel
  conversation_history: ChatMessage[]
  current_schema?: Record<string, unknown>
  current_api_spec?: Record<string, unknown>
  current_diagram?: Record<string, unknown>
}

export interface DesignSummaryResponse {
  summary: string
  key_components: string[]
  strengths: string[]
  areas_for_improvement: string[]
  overall_score: number | null
  difficulty_level: DifficultyLevel
  level_info: DifficultyLevelInfo
  demo_mode: boolean
}

// Chat types
export interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatRequest {
  problem_id: number
  message: string
  conversation_history: ChatMessage[]
  current_schema?: Record<string, unknown>
  current_api_spec?: Record<string, unknown>
  current_diagram?: Record<string, unknown>
  difficulty_level?: DifficultyLevel
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

export interface LevelRequirementsResponse {
  problem_id: number
  problem_title: string
  difficulty: DifficultyLevel
  level_info: DifficultyLevelInfo
  requirements: string
}
