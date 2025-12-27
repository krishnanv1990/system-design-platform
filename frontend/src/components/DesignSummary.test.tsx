/**
 * Tests for DesignSummary component
 *
 * Tests the display of design summary including:
 * - Overall score with color coding
 * - Key components badges
 * - Strengths and areas for improvement
 * - Difficulty level badges (L5/L6/L7)
 * - Demo mode notice
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import DesignSummary from './DesignSummary'
import type { DesignSummaryResponse } from '@/api/client'

const createMockSummary = (overrides: Partial<DesignSummaryResponse> = {}): DesignSummaryResponse => ({
  summary: 'This design demonstrates a solid understanding of URL shortener architecture.',
  key_components: ['Key Generation Service (KGS)', 'Redis Cache', 'Load Balancer'],
  strengths: ['Good use of KGS for unique code generation', 'Proper caching strategy'],
  areas_for_improvement: ['Consider adding analytics tracking', 'Implement rate limiting'],
  overall_score: 85,
  difficulty_level: 'medium',
  level_info: {
    level: 'L6',
    title: 'Staff Engineer',
    description: 'Production-ready design with high availability',
  },
  demo_mode: false,
  ...overrides,
})

describe('DesignSummary', () => {
  describe('Header and Level Info', () => {
    it('renders design summary title', () => {
      const summary = createMockSummary()
      render(<DesignSummary summary={summary} />)

      expect(screen.getByText('Design Summary')).toBeInTheDocument()
    })

    it('displays the difficulty level badge', () => {
      const summary = createMockSummary()
      render(<DesignSummary summary={summary} />)

      expect(screen.getByText('L6')).toBeInTheDocument()
    })

    it('displays the level title', () => {
      const summary = createMockSummary()
      render(<DesignSummary summary={summary} />)

      expect(screen.getByText('Staff Engineer')).toBeInTheDocument()
    })

    it('displays L5 for easy difficulty', () => {
      const summary = createMockSummary({
        difficulty_level: 'easy',
        level_info: {
          level: 'L5',
          title: 'Senior Software Engineer',
          description: 'Core functionality',
        },
      })
      render(<DesignSummary summary={summary} />)

      expect(screen.getByText('L5')).toBeInTheDocument()
      expect(screen.getByText('Senior Software Engineer')).toBeInTheDocument()
    })

    it('displays L7 for hard difficulty', () => {
      const summary = createMockSummary({
        difficulty_level: 'hard',
        level_info: {
          level: 'L7',
          title: 'Principal Engineer',
          description: 'Global-scale architecture',
        },
      })
      render(<DesignSummary summary={summary} />)

      expect(screen.getByText('L7')).toBeInTheDocument()
      expect(screen.getByText('Principal Engineer')).toBeInTheDocument()
    })

    it('shows level in description', () => {
      const summary = createMockSummary()
      render(<DesignSummary summary={summary} />)

      expect(screen.getByText(/Your completed system design at L6 level/)).toBeInTheDocument()
    })
  })

  describe('Overall Score', () => {
    it('renders the overall score', () => {
      const summary = createMockSummary({ overall_score: 85 })
      render(<DesignSummary summary={summary} />)

      expect(screen.getByText('Overall Score')).toBeInTheDocument()
      expect(screen.getByText('85')).toBeInTheDocument()
      expect(screen.getByText('/100')).toBeInTheDocument()
    })

    it('applies green color for high scores (>= 80)', () => {
      const summary = createMockSummary({ overall_score: 85 })
      render(<DesignSummary summary={summary} />)

      const scoreElement = screen.getByText('85')
      expect(scoreElement.closest('div')).toHaveClass('text-green-600')
    })

    it('applies yellow color for medium scores (60-79)', () => {
      const summary = createMockSummary({ overall_score: 70 })
      render(<DesignSummary summary={summary} />)

      const scoreElement = screen.getByText('70')
      expect(scoreElement.closest('div')).toHaveClass('text-yellow-600')
    })

    it('applies red color for low scores (< 60)', () => {
      const summary = createMockSummary({ overall_score: 45 })
      render(<DesignSummary summary={summary} />)

      const scoreElement = screen.getByText('45')
      expect(scoreElement.closest('div')).toHaveClass('text-red-600')
    })

    it('does not render score section when overall_score is null', () => {
      const summary = createMockSummary({ overall_score: null })
      render(<DesignSummary summary={summary} />)

      expect(screen.queryByText('Overall Score')).not.toBeInTheDocument()
    })
  })

  describe('Summary Text', () => {
    it('renders the design overview section', () => {
      const summary = createMockSummary()
      render(<DesignSummary summary={summary} />)

      expect(screen.getByText('Design Overview')).toBeInTheDocument()
    })

    it('renders the summary text', () => {
      const summary = createMockSummary({
        summary: 'This is a test summary with **bold** text.',
      })
      render(<DesignSummary summary={summary} />)

      // Check that summary content is rendered
      expect(screen.getByText(/This is a test summary/)).toBeInTheDocument()
    })

    it('converts bold markdown to HTML', () => {
      const summary = createMockSummary({
        summary: 'Text with **bold** content',
      })
      const { container } = render(<DesignSummary summary={summary} />)

      // Check that strong tags are rendered
      const strongElements = container.querySelectorAll('strong')
      expect(strongElements.length).toBeGreaterThan(0)
    })
  })

  describe('Key Components', () => {
    it('renders key components section when components exist', () => {
      const summary = createMockSummary({
        key_components: ['KGS', 'Redis', 'Load Balancer'],
      })
      render(<DesignSummary summary={summary} />)

      expect(screen.getByText('Key Components')).toBeInTheDocument()
    })

    it('renders all key components as badges', () => {
      const components = ['KGS', 'Redis Cache', 'Load Balancer']
      const summary = createMockSummary({ key_components: components })
      render(<DesignSummary summary={summary} />)

      components.forEach(component => {
        expect(screen.getByText(component)).toBeInTheDocument()
      })
    })

    it('does not render key components section when array is empty', () => {
      const summary = createMockSummary({ key_components: [] })
      render(<DesignSummary summary={summary} />)

      expect(screen.queryByText('Key Components')).not.toBeInTheDocument()
    })
  })

  describe('Strengths', () => {
    it('renders strengths section when strengths exist', () => {
      const summary = createMockSummary({
        strengths: ['Good architecture', 'Clean design'],
      })
      render(<DesignSummary summary={summary} />)

      expect(screen.getByText('Strengths')).toBeInTheDocument()
    })

    it('renders all strengths as list items', () => {
      const strengths = ['Good use of KGS', 'Proper caching strategy', 'Clean API design']
      const summary = createMockSummary({ strengths })
      render(<DesignSummary summary={summary} />)

      strengths.forEach(strength => {
        expect(screen.getByText(strength)).toBeInTheDocument()
      })
    })

    it('does not render strengths section when array is empty', () => {
      const summary = createMockSummary({ strengths: [] })
      render(<DesignSummary summary={summary} />)

      expect(screen.queryByText('Strengths')).not.toBeInTheDocument()
    })
  })

  describe('Areas for Improvement', () => {
    it('renders areas for improvement section when items exist', () => {
      const summary = createMockSummary({
        areas_for_improvement: ['Add caching', 'Implement rate limiting'],
      })
      render(<DesignSummary summary={summary} />)

      expect(screen.getByText('Areas for Improvement')).toBeInTheDocument()
    })

    it('renders all areas for improvement as list items', () => {
      const areas = ['Consider adding analytics', 'Implement rate limiting', 'Add monitoring']
      const summary = createMockSummary({ areas_for_improvement: areas })
      render(<DesignSummary summary={summary} />)

      areas.forEach(area => {
        expect(screen.getByText(area)).toBeInTheDocument()
      })
    })

    it('does not render areas section when array is empty', () => {
      const summary = createMockSummary({ areas_for_improvement: [] })
      render(<DesignSummary summary={summary} />)

      expect(screen.queryByText('Areas for Improvement')).not.toBeInTheDocument()
    })
  })

  describe('Diagram Preview', () => {
    it('renders diagram section when diagramData is provided', () => {
      const summary = createMockSummary()
      render(<DesignSummary summary={summary} diagramData='{"elements": []}' />)

      expect(screen.getByText('Your Diagram')).toBeInTheDocument()
    })

    it('does not render diagram section when diagramData is not provided', () => {
      const summary = createMockSummary()
      render(<DesignSummary summary={summary} />)

      expect(screen.queryByText('Your Diagram')).not.toBeInTheDocument()
    })

    it('renders diagram placeholder text', () => {
      const summary = createMockSummary()
      render(<DesignSummary summary={summary} diagramData='{"elements": []}' />)

      expect(screen.getByText('[Diagram preview would be rendered here]')).toBeInTheDocument()
    })
  })

  describe('Demo Mode', () => {
    it('renders demo mode notice when demo_mode is true', () => {
      const summary = createMockSummary({ demo_mode: true })
      render(<DesignSummary summary={summary} />)

      expect(screen.getByText(/This is a demo summary/)).toBeInTheDocument()
    })

    it('does not render demo mode notice when demo_mode is false', () => {
      const summary = createMockSummary({ demo_mode: false })
      render(<DesignSummary summary={summary} />)

      expect(screen.queryByText(/This is a demo summary/)).not.toBeInTheDocument()
    })
  })

  describe('Edge Cases', () => {
    it('renders with minimal data', () => {
      const summary: DesignSummaryResponse = {
        summary: 'Minimal summary',
        key_components: [],
        strengths: [],
        areas_for_improvement: [],
        overall_score: null,
        difficulty_level: 'medium',
        level_info: {
          level: 'L6',
          title: 'Staff Engineer',
          description: '',
        },
        demo_mode: false,
      }
      render(<DesignSummary summary={summary} />)

      expect(screen.getByText('Design Summary')).toBeInTheDocument()
      expect(screen.getByText('Minimal summary')).toBeInTheDocument()
    })

    it('handles score of exactly 80', () => {
      const summary = createMockSummary({ overall_score: 80 })
      render(<DesignSummary summary={summary} />)

      const scoreElement = screen.getByText('80')
      expect(scoreElement.closest('div')).toHaveClass('text-green-600')
    })

    it('handles score of exactly 60', () => {
      const summary = createMockSummary({ overall_score: 60 })
      render(<DesignSummary summary={summary} />)

      const scoreElement = screen.getByText('60')
      expect(scoreElement.closest('div')).toHaveClass('text-yellow-600')
    })

    it('handles perfect score of 100', () => {
      const summary = createMockSummary({ overall_score: 100 })
      render(<DesignSummary summary={summary} />)

      expect(screen.getByText('100')).toBeInTheDocument()
    })

    it('handles zero score', () => {
      const summary = createMockSummary({ overall_score: 0 })
      render(<DesignSummary summary={summary} />)

      // Score of 0 should still show as it's not null
      expect(screen.getByText('Overall Score')).toBeInTheDocument()
    })
  })
})
