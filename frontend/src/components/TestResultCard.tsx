/**
 * Test result display card
 * Shows individual test results with status and details
 */

import { TestResult, TestStatus } from '../types'

interface TestResultCardProps {
  result: TestResult
}

const statusColors: Record<TestStatus, string> = {
  pending: 'bg-gray-100 text-gray-800',
  running: 'bg-blue-100 text-blue-800',
  passed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
  error: 'bg-orange-100 text-orange-800',
  skipped: 'bg-gray-100 text-gray-600',
}

const statusIcons: Record<TestStatus, string> = {
  pending: '...',
  running: '...',
  passed: '(+)',
  failed: '(x)',
  error: '(!)',
  skipped: '(-)',
}

export default function TestResultCard({ result }: TestResultCardProps) {
  const statusColor = statusColors[result.status] || statusColors.pending
  const statusIcon = statusIcons[result.status] || ''

  return (
    <div className="border rounded-lg p-4 bg-white">
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-medium text-gray-900">{result.test_name}</h4>
        <span
          className={`px-2 py-1 text-xs font-medium rounded-full ${statusColor}`}
        >
          {statusIcon} {result.status.toUpperCase()}
        </span>
      </div>

      {result.chaos_scenario && (
        <p className="text-sm text-gray-500 mb-2">
          Scenario: {result.chaos_scenario}
        </p>
      )}

      {result.duration_ms !== null && (
        <p className="text-sm text-gray-500">
          Duration: {result.duration_ms}ms
        </p>
      )}

      {result.details && (
        <details className="mt-3">
          <summary className="text-sm text-primary-600 cursor-pointer hover:text-primary-700">
            View Details
          </summary>
          <pre className="mt-2 p-3 bg-gray-50 rounded text-xs overflow-x-auto">
            {JSON.stringify(result.details, null, 2)}
          </pre>
        </details>
      )}
    </div>
  )
}
