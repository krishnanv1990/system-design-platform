import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { ErrorAnalysisCard } from './ErrorAnalysisCard'
import type { ErrorAnalysis } from '@/types'

const createMockAnalysis = (overrides: Partial<ErrorAnalysis> = {}): ErrorAnalysis => ({
  category: 'user_solution',
  confidence: 0.85,
  explanation: 'The API endpoint is not returning the expected response format.',
  suggestions: ['Check your response structure', 'Verify status codes'],
  status: 'completed',
  ...overrides,
})

describe('ErrorAnalysisCard', () => {
  it('renders the root cause analysis title', () => {
    render(<ErrorAnalysisCard analysis={createMockAnalysis()} />)
    expect(screen.getByText('Root Cause Analysis')).toBeInTheDocument()
  })

  it('displays user_solution category correctly', () => {
    render(<ErrorAnalysisCard analysis={createMockAnalysis({ category: 'user_solution' })} />)
    expect(screen.getByText('Solution Issue')).toBeInTheDocument()
    expect(screen.getByText(/This failure is related to your implementation/i)).toBeInTheDocument()
  })

  it('displays platform category correctly', () => {
    render(<ErrorAnalysisCard analysis={createMockAnalysis({ category: 'platform' })} />)
    expect(screen.getByText('Platform Issue')).toBeInTheDocument()
    expect(screen.getByText(/This is a testing platform issue, not your fault/i)).toBeInTheDocument()
  })

  it('displays deployment category correctly', () => {
    render(<ErrorAnalysisCard analysis={createMockAnalysis({ category: 'deployment' })} />)
    expect(screen.getByText('Deployment Issue')).toBeInTheDocument()
    expect(screen.getByText(/This is an infrastructure issue, not your fault/i)).toBeInTheDocument()
  })

  it('displays unknown category correctly', () => {
    render(<ErrorAnalysisCard analysis={createMockAnalysis({ category: 'unknown' })} />)
    expect(screen.getByText('Unknown')).toBeInTheDocument()
  })

  it('shows confidence percentage', () => {
    render(<ErrorAnalysisCard analysis={createMockAnalysis({ confidence: 0.85 })} />)
    expect(screen.getByText('85% confidence')).toBeInTheDocument()
  })

  it('shows high confidence indicator for >= 70%', () => {
    render(<ErrorAnalysisCard analysis={createMockAnalysis({ confidence: 0.75 })} />)
    const badge = screen.getByText('75% confidence')
    expect(badge).toBeInTheDocument()
  })

  it('shows low confidence indicator for < 70%', () => {
    render(<ErrorAnalysisCard analysis={createMockAnalysis({ confidence: 0.5 })} />)
    const badge = screen.getByText('50% confidence')
    expect(badge).toBeInTheDocument()
  })

  it('displays explanation', () => {
    const explanation = 'The API endpoint is not returning the expected response format.'
    render(<ErrorAnalysisCard analysis={createMockAnalysis({ explanation })} />)
    expect(screen.getByText(explanation)).toBeInTheDocument()
  })

  it('displays suggestions when available', () => {
    const suggestions = ['Fix the response format', 'Add proper error handling']
    render(<ErrorAnalysisCard analysis={createMockAnalysis({ suggestions })} />)

    expect(screen.getByText('Suggestions')).toBeInTheDocument()
    suggestions.forEach((suggestion) => {
      expect(screen.getByText(suggestion)).toBeInTheDocument()
    })
  })

  it('does not show suggestions section when empty', () => {
    render(<ErrorAnalysisCard analysis={createMockAnalysis({ suggestions: [] })} />)
    expect(screen.queryByText('Suggestions')).not.toBeInTheDocument()
  })

  it('displays technical details when available', () => {
    render(
      <ErrorAnalysisCard
        analysis={createMockAnalysis({
          technical_details: {
            error_type: 'ValidationError',
            affected_component: 'API Handler',
          },
        })}
      />
    )

    expect(screen.getByText('Error Type:')).toBeInTheDocument()
    expect(screen.getByText('ValidationError')).toBeInTheDocument()
    expect(screen.getByText('Component:')).toBeInTheDocument()
    expect(screen.getByText('API Handler')).toBeInTheDocument()
  })

  it('shows demo badge when in demo mode', () => {
    render(<ErrorAnalysisCard analysis={createMockAnalysis({ demo_mode: true })} />)
    expect(screen.getByText('Demo')).toBeInTheDocument()
  })

  it('can be collapsed and expanded', () => {
    const explanation = 'Test explanation content'
    render(<ErrorAnalysisCard analysis={createMockAnalysis({ explanation })} />)

    // Initially expanded
    expect(screen.getByText(explanation)).toBeVisible()

    // Find and click the collapse button
    const collapseButton = screen.getByRole('button', { name: '' })
    fireEvent.click(collapseButton)

    // Content should be hidden
    expect(screen.queryByText(explanation)).not.toBeInTheDocument()

    // Click again to expand
    fireEvent.click(collapseButton)
    expect(screen.getByText(explanation)).toBeVisible()
  })

  it('applies custom className', () => {
    const { container } = render(
      <ErrorAnalysisCard analysis={createMockAnalysis()} className="custom-class" />
    )
    expect(container.firstChild).toHaveClass('custom-class')
  })
})
