/**
 * Problem list page
 * Shows all available system design problems
 */

import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { problemsApi } from '../api/client'
import { ProblemListItem } from '../types'

const difficultyColors = {
  easy: 'bg-green-100 text-green-800',
  medium: 'bg-yellow-100 text-yellow-800',
  hard: 'bg-red-100 text-red-800',
}

export default function ProblemList() {
  const [problems, setProblems] = useState<ProblemListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string>('')

  useEffect(() => {
    const loadProblems = async () => {
      try {
        const data = await problemsApi.list()
        setProblems(data)
      } catch (error) {
        console.error('Failed to load problems:', error)
      } finally {
        setLoading(false)
      }
    }
    loadProblems()
  }, [])

  const filteredProblems = problems.filter(
    (p) =>
      p.title.toLowerCase().includes(filter.toLowerCase()) ||
      p.description.toLowerCase().includes(filter.toLowerCase())
  )

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">System Design Problems</h1>
        <p className="mt-1 text-sm text-gray-500">
          Choose a problem to practice your system design skills
        </p>
      </div>

      {/* Search */}
      <div className="mb-6">
        <input
          type="text"
          placeholder="Search problems..."
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="w-full max-w-md px-4 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-primary-500"
        />
      </div>

      {/* Problem list */}
      {filteredProblems.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-gray-500">
            {problems.length === 0
              ? 'No problems available yet.'
              : 'No problems match your search.'}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredProblems.map((problem) => (
            <Link
              key={problem.id}
              to={`/problems/${problem.id}`}
              className="block p-6 bg-white rounded-lg border border-gray-200 hover:border-primary-300 hover:shadow-md transition-all"
            >
              <div className="flex items-center justify-between mb-2">
                <h3 className="text-lg font-semibold text-gray-900">
                  {problem.title}
                </h3>
                <span
                  className={`px-2 py-1 text-xs font-medium rounded-full ${
                    difficultyColors[problem.difficulty]
                  }`}
                >
                  {problem.difficulty}
                </span>
              </div>
              <p className="text-sm text-gray-600 line-clamp-2">
                {problem.description}
              </p>
              {problem.tags && problem.tags.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1">
                  {problem.tags.map((tag) => (
                    <span
                      key={tag}
                      className="px-2 py-0.5 text-xs bg-gray-100 text-gray-600 rounded"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
