import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import TestResultCard from './TestResultCard'
import type { TestResult } from '@/types'

const createMockResult = (overrides: Partial<TestResult> = {}): TestResult => ({
  id: 1,
  submission_id: 1,
  test_type: 'functional',
  test_name: 'Test API endpoint',
  status: 'passed',
  details: null,
  duration_ms: 150,
  chaos_scenario: null,
  created_at: '2024-01-15T10:00:00Z',
  ...overrides,
})

describe('TestResultCard', () => {
  it('renders test name', () => {
    render(<TestResultCard result={createMockResult()} />)
    expect(screen.getByText('Test API endpoint')).toBeInTheDocument()
  })

  it('shows passed status with correct styling', () => {
    render(<TestResultCard result={createMockResult({ status: 'passed' })} />)
    expect(screen.getByText('Passed')).toBeInTheDocument()
  })

  it('shows failed status with correct styling', () => {
    render(<TestResultCard result={createMockResult({ status: 'failed' })} />)
    expect(screen.getByText('Failed')).toBeInTheDocument()
  })

  it('shows running status with spinner', () => {
    render(<TestResultCard result={createMockResult({ status: 'running' })} />)
    expect(screen.getByText('Running')).toBeInTheDocument()
  })

  it('shows pending status', () => {
    render(<TestResultCard result={createMockResult({ status: 'pending' })} />)
    expect(screen.getByText('Pending')).toBeInTheDocument()
  })

  it('shows error status', () => {
    render(<TestResultCard result={createMockResult({ status: 'error' })} />)
    expect(screen.getByText('Error')).toBeInTheDocument()
  })

  it('shows skipped status', () => {
    render(<TestResultCard result={createMockResult({ status: 'skipped' })} />)
    expect(screen.getByText('Skipped')).toBeInTheDocument()
  })

  it('displays duration when available', () => {
    render(<TestResultCard result={createMockResult({ duration_ms: 250 })} />)
    expect(screen.getByText('250ms')).toBeInTheDocument()
  })

  it('displays chaos scenario when available', () => {
    render(<TestResultCard result={createMockResult({ chaos_scenario: 'network_partition' })} />)
    expect(screen.getByText(/network_partition/i)).toBeInTheDocument()
  })

  it('toggles details view when details exist', () => {
    render(
      <TestResultCard
        result={createMockResult({
          details: { response: { status: 200 } },
        })}
      />
    )

    // Initially hidden
    expect(screen.queryByText(/"status": 200/)).not.toBeInTheDocument()

    // Click to show
    fireEvent.click(screen.getByText(/View Raw Details/i))
    expect(screen.getByText(/"status": 200/)).toBeInTheDocument()

    // Click to hide
    fireEvent.click(screen.getByText(/Hide/i))
    expect(screen.queryByText(/"status": 200/)).not.toBeInTheDocument()
  })

  it('shows error analysis when available and test failed', () => {
    render(
      <TestResultCard
        result={createMockResult({
          status: 'failed',
          error_analysis: {
            category: 'user_solution',
            confidence: 0.85,
            explanation: 'The API endpoint is not returning the expected response',
            suggestions: ['Check your response format', 'Verify status codes'],
            status: 'completed',
          },
        })}
      />
    )

    expect(screen.getByText(/Root Cause Analysis/i)).toBeInTheDocument()
    expect(screen.getByText(/Solution Issue/i)).toBeInTheDocument()
  })

  it('does not show error analysis for passed tests', () => {
    render(
      <TestResultCard
        result={createMockResult({
          status: 'passed',
          error_analysis: {
            category: 'user_solution',
            confidence: 0.85,
            explanation: 'Some explanation',
            suggestions: [],
            status: 'completed',
          },
        })}
      />
    )

    expect(screen.queryByText(/Root Cause Analysis/i)).not.toBeInTheDocument()
  })

  it('respects showAnalysis prop', () => {
    render(
      <TestResultCard
        result={createMockResult({
          status: 'failed',
          error_analysis: {
            category: 'user_solution',
            confidence: 0.85,
            explanation: 'Test explanation',
            suggestions: [],
            status: 'completed',
          },
        })}
        showAnalysis={false}
      />
    )

    expect(screen.queryByText(/Root Cause Analysis/i)).not.toBeInTheDocument()
  })
})
