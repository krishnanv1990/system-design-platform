/**
 * Problem detail page
 * Shows full problem description and allows starting a submission
 */

import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { problemsApi } from '../api/client'
import { Problem } from '../types'

const difficultyColors = {
  easy: 'bg-green-100 text-green-800',
  medium: 'bg-yellow-100 text-yellow-800',
  hard: 'bg-red-100 text-red-800',
}

export default function ProblemDetail() {
  const { id } = useParams<{ id: string }>()
  const [problem, setProblem] = useState<Problem | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadProblem = async () => {
      if (!id) return
      try {
        const data = await problemsApi.get(parseInt(id))
        setProblem(data)
      } catch (err) {
        setError('Failed to load problem')
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    loadProblem()
  }, [id])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (error || !problem) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500">{error || 'Problem not found'}</p>
        <Link to="/problems" className="text-primary-600 hover:underline mt-4 inline-block">
          Back to problems
        </Link>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <Link
          to="/problems"
          className="text-sm text-gray-500 hover:text-gray-700 mb-2 inline-block"
        >
          {'<-'} Back to problems
        </Link>
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold text-gray-900">{problem.title}</h1>
          <span
            className={`px-3 py-1 text-sm font-medium rounded-full ${
              difficultyColors[problem.difficulty]
            }`}
          >
            {problem.difficulty}
          </span>
        </div>
        {problem.tags && problem.tags.length > 0 && (
          <div className="mt-2 flex flex-wrap gap-2">
            {problem.tags.map((tag) => (
              <span
                key={tag}
                className="px-2 py-1 text-xs bg-gray-100 text-gray-600 rounded"
              >
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Description */}
      <div className="bg-white rounded-lg border p-6 mb-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Problem Description</h2>
        <div className="prose prose-sm max-w-none">
          <p className="whitespace-pre-wrap">{problem.description}</p>
        </div>
      </div>

      {/* Hints (if available) */}
      {problem.hints && problem.hints.length > 0 && (
        <div className="bg-blue-50 rounded-lg border border-blue-100 p-6 mb-6">
          <h2 className="text-lg font-semibold text-blue-900 mb-3">Hints</h2>
          <ul className="space-y-2">
            {problem.hints.map((hint, i) => (
              <li key={i} className="text-sm text-blue-800">
                {i + 1}. {hint}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Expected Schema Preview */}
      {problem.expected_api_spec && (
        <div className="bg-gray-50 rounded-lg border p-6 mb-6">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">
            Expected API Endpoints
          </h2>
          <p className="text-sm text-gray-600">
            Your solution should include the following endpoints (at minimum):
          </p>
          <pre className="mt-2 p-4 bg-white rounded border text-sm overflow-x-auto">
            {JSON.stringify(problem.expected_api_spec, null, 2)}
          </pre>
        </div>
      )}

      {/* Start button */}
      <div className="flex justify-end">
        <Link
          to={`/problems/${problem.id}/submit`}
          className="px-6 py-3 bg-primary-600 text-white font-medium rounded-lg hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500"
        >
          Start Design
        </Link>
      </div>
    </div>
  )
}
