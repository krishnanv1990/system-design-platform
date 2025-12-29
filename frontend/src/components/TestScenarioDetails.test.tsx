/**
 * Tests for TestScenarioDetails component
 *
 * Tests the display of test scenario details including:
 * - Collapsible sections
 * - Pass/fail summaries
 * - Test result lists
 * - Different test types (functional, performance, chaos)
 */

import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import TestScenarioDetails from './TestScenarioDetails'

describe('TestScenarioDetails', () => {
  describe('Functional Tests', () => {
    it('renders functional test scenarios title', () => {
      render(<TestScenarioDetails type="functional" />)
      expect(screen.getByText('Functional Test Scenarios')).toBeInTheDocument()
    })

    it('renders functional test description', () => {
      render(<TestScenarioDetails type="functional" />)
      expect(screen.getByText('Tests core API functionality, validation, and data integrity')).toBeInTheDocument()
    })

    it('displays functional test icon (Shield)', () => {
      const { container } = render(<TestScenarioDetails type="functional" />)
      // Shield icon for functional tests
      expect(container.querySelector('.h-4.w-4.text-blue-500')).toBeInTheDocument()
    })
  })

  describe('Performance Tests', () => {
    it('renders performance test scenarios title', () => {
      render(<TestScenarioDetails type="performance" />)
      expect(screen.getByText('Performance Test Scenarios')).toBeInTheDocument()
    })

    it('renders performance test description', () => {
      render(<TestScenarioDetails type="performance" />)
      expect(screen.getByText('Tests system performance under various load conditions')).toBeInTheDocument()
    })

    it('displays performance test icon (Zap)', () => {
      const { container } = render(<TestScenarioDetails type="performance" />)
      // Zap icon for performance tests
      expect(container.querySelector('.h-4.w-4.text-yellow-500')).toBeInTheDocument()
    })
  })

  describe('Chaos Tests', () => {
    it('renders chaos test scenarios title', () => {
      render(<TestScenarioDetails type="chaos" />)
      expect(screen.getByText('Chaos Test Scenarios')).toBeInTheDocument()
    })

    it('renders chaos test description', () => {
      render(<TestScenarioDetails type="chaos" />)
      expect(screen.getByText('Tests system resilience to failures and degraded conditions')).toBeInTheDocument()
    })

    it('displays chaos test icon (AlertTriangle)', () => {
      const { container } = render(<TestScenarioDetails type="chaos" />)
      // AlertTriangle icon for chaos tests
      expect(container.querySelector('.h-4.w-4.text-red-500')).toBeInTheDocument()
    })
  })

  describe('Pass/Fail Summary', () => {
    it('displays passed test count', () => {
      render(
        <TestScenarioDetails
          type="functional"
          passedTests={['Test 1', 'Test 2', 'Test 3']}
          failedTests={[]}
        />
      )
      // Find the passed count
      expect(screen.getByText('3')).toBeInTheDocument()
    })

    it('displays failed test count', () => {
      render(
        <TestScenarioDetails
          type="functional"
          passedTests={[]}
          failedTests={['Test 1', 'Test 2']}
        />
      )
      // Find the failed count
      expect(screen.getByText('2')).toBeInTheDocument()
    })

    it('displays pass rate percentage', () => {
      render(
        <TestScenarioDetails
          type="functional"
          passedTests={['Test 1', 'Test 2', 'Test 3']}
          failedTests={['Test 4']}
        />
      )
      // 3/4 = 75%
      expect(screen.getByText('(75%)')).toBeInTheDocument()
    })

    it('displays 100% pass rate with green color', () => {
      render(
        <TestScenarioDetails
          type="functional"
          passedTests={['Test 1', 'Test 2']}
          failedTests={[]}
        />
      )
      expect(screen.getByText('(100%)')).toBeInTheDocument()
      expect(screen.getByText('(100%)')).toHaveClass('text-green-600')
    })

    it('displays medium pass rate with yellow color', () => {
      render(
        <TestScenarioDetails
          type="functional"
          passedTests={['Test 1', 'Test 2', 'Test 3']}
          failedTests={['Test 4', 'Test 5']}
        />
      )
      // 3/5 = 60%
      expect(screen.getByText('(60%)')).toBeInTheDocument()
      expect(screen.getByText('(60%)')).toHaveClass('text-yellow-600')
    })

    it('displays low pass rate with red color', () => {
      render(
        <TestScenarioDetails
          type="functional"
          passedTests={['Test 1']}
          failedTests={['Test 2', 'Test 3', 'Test 4', 'Test 5']}
        />
      )
      // 1/5 = 20%
      expect(screen.getByText('(20%)')).toBeInTheDocument()
      expect(screen.getByText('(20%)')).toHaveClass('text-red-600')
    })

    it('does not display summary when no tests provided', () => {
      render(<TestScenarioDetails type="functional" />)
      expect(screen.queryByText('(0%)')).not.toBeInTheDocument()
    })
  })

  describe('Expandable Content', () => {
    it('is collapsed by default', () => {
      render(
        <TestScenarioDetails
          type="functional"
          passedTests={['Test 1']}
        />
      )
      // Actual Test Results should not be visible when collapsed
      expect(screen.queryByText('Actual Test Results')).not.toBeInTheDocument()
    })

    it('expands when clicked', () => {
      render(
        <TestScenarioDetails
          type="functional"
          passedTests={['Test 1']}
        />
      )

      // Click to expand
      fireEvent.click(screen.getByText('Functional Test Scenarios'))

      // Now should see the content
      expect(screen.getByText('Actual Test Results')).toBeInTheDocument()
    })

    it('collapses when clicked again', () => {
      render(
        <TestScenarioDetails
          type="functional"
          passedTests={['Test 1']}
        />
      )

      // Click to expand
      fireEvent.click(screen.getByText('Functional Test Scenarios'))
      expect(screen.getByText('Actual Test Results')).toBeInTheDocument()

      // Click to collapse
      fireEvent.click(screen.getByText('Functional Test Scenarios'))
      expect(screen.queryByText('Actual Test Results')).not.toBeInTheDocument()
    })
  })

  describe('Test Results List', () => {
    it('displays passed tests when expanded', () => {
      render(
        <TestScenarioDetails
          type="functional"
          passedTests={['Create URL succeeded', 'Validate URL passed']}
          failedTests={[]}
        />
      )

      fireEvent.click(screen.getByText('Functional Test Scenarios'))

      expect(screen.getByText('Create URL succeeded')).toBeInTheDocument()
      expect(screen.getByText('Validate URL passed')).toBeInTheDocument()
    })

    it('displays failed tests when expanded', () => {
      render(
        <TestScenarioDetails
          type="functional"
          passedTests={[]}
          failedTests={['Rate limit test failed', 'Edge case failed']}
        />
      )

      fireEvent.click(screen.getByText('Functional Test Scenarios'))

      expect(screen.getByText('Rate limit test failed')).toBeInTheDocument()
      expect(screen.getByText('Edge case failed')).toBeInTheDocument()
    })

    it('shows passed count in header', () => {
      render(
        <TestScenarioDetails
          type="functional"
          passedTests={['Test 1', 'Test 2']}
          failedTests={[]}
        />
      )

      fireEvent.click(screen.getByText('Functional Test Scenarios'))

      expect(screen.getByText('Passed (2)')).toBeInTheDocument()
    })

    it('shows failed count in header', () => {
      render(
        <TestScenarioDetails
          type="functional"
          passedTests={[]}
          failedTests={['Test 1', 'Test 2', 'Test 3']}
        />
      )

      fireEvent.click(screen.getByText('Functional Test Scenarios'))

      expect(screen.getByText('Failed (3)')).toBeInTheDocument()
    })
  })

  describe('Scenario Descriptions', () => {
    it('shows test scenarios covered section', () => {
      render(<TestScenarioDetails type="functional" />)

      fireEvent.click(screen.getByText('Functional Test Scenarios'))

      expect(screen.getByText('Test Scenarios Covered')).toBeInTheDocument()
    })

    it('displays functional scenarios', () => {
      render(<TestScenarioDetails type="functional" />)

      fireEvent.click(screen.getByText('Functional Test Scenarios'))

      expect(screen.getByText('Core CRUD Operations')).toBeInTheDocument()
      expect(screen.getByText('URL Validation')).toBeInTheDocument()
      expect(screen.getByText('URL Expiration')).toBeInTheDocument()
    })

    it('displays performance scenarios', () => {
      render(<TestScenarioDetails type="performance" />)

      fireEvent.click(screen.getByText('Performance Test Scenarios'))

      expect(screen.getByText('Load Testing')).toBeInTheDocument()
      expect(screen.getByText('Latency Benchmarks')).toBeInTheDocument()
      expect(screen.getByText('Throughput Testing')).toBeInTheDocument()
    })

    it('displays chaos scenarios', () => {
      render(<TestScenarioDetails type="chaos" />)

      fireEvent.click(screen.getByText('Chaos Test Scenarios'))

      expect(screen.getByText('Network Failures')).toBeInTheDocument()
      expect(screen.getByText('Database Failures')).toBeInTheDocument()
      expect(screen.getByText('Cache Failures')).toBeInTheDocument()
    })
  })

  describe('Test Status Indicators', () => {
    it('marks matching tests as passed with check icon', () => {
      render(
        <TestScenarioDetails
          type="functional"
          passedTests={['Create short URL with valid input']}
          failedTests={[]}
        />
      )

      fireEvent.click(screen.getByText('Functional Test Scenarios'))

      // The test item in the actual results section should have success styling
      const testItems = screen.getAllByText('Create short URL with valid input')
      // First one is in the actual results section
      expect(testItems[0]).toBeInTheDocument()
    })

    it('marks matching tests as failed with X icon', () => {
      render(
        <TestScenarioDetails
          type="functional"
          passedTests={[]}
          failedTests={['Create short URL with valid input']}
        />
      )

      fireEvent.click(screen.getByText('Functional Test Scenarios'))

      // The test item should be in the failed tests list
      const testItems = screen.getAllByText('Create short URL with valid input')
      // First one is in the actual results section (failed)
      expect(testItems[0]).toBeInTheDocument()
    })
  })

  describe('Edge Cases', () => {
    it('handles empty arrays', () => {
      render(
        <TestScenarioDetails
          type="functional"
          passedTests={[]}
          failedTests={[]}
        />
      )

      expect(screen.getByText('Functional Test Scenarios')).toBeInTheDocument()
    })

    it('handles undefined passedTests', () => {
      render(<TestScenarioDetails type="functional" />)
      expect(screen.getByText('Functional Test Scenarios')).toBeInTheDocument()
    })

    it('handles undefined failedTests', () => {
      render(
        <TestScenarioDetails
          type="functional"
          passedTests={['Test 1']}
        />
      )
      expect(screen.getByText('Functional Test Scenarios')).toBeInTheDocument()
    })

    it('correctly rounds pass rate', () => {
      render(
        <TestScenarioDetails
          type="functional"
          passedTests={['T1']}
          failedTests={['T2', 'T3']}
        />
      )
      // 1/3 = 33.33% -> should round to 33%
      expect(screen.getByText('(33%)')).toBeInTheDocument()
    })
  })
})
