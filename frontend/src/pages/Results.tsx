/**
 * Results page
 * Shows submission status and test results
 */

import { useState, useEffect } from 'react'
import { useParams, Link } from 'react-router-dom'
import { submissionsApi, testsApi } from '../api/client'
import { SubmissionDetail, TestSummary, SubmissionStatus } from '../types'
import TestResultCard from '../components/TestResultCard'

const statusLabels: Record<SubmissionStatus, string> = {
  pending: 'Pending',
  validating: 'Validating Design...',
  validation_failed: 'Validation Failed',
  generating_infra: 'Generating Infrastructure...',
  deploying: 'Deploying to GCP...',
  deploy_failed: 'Deployment Failed',
  testing: 'Running Tests...',
  completed: 'Completed',
  failed: 'Failed',
}

const statusColors: Record<SubmissionStatus, string> = {
  pending: 'bg-gray-100 text-gray-800',
  validating: 'bg-blue-100 text-blue-800',
  validation_failed: 'bg-red-100 text-red-800',
  generating_infra: 'bg-blue-100 text-blue-800',
  deploying: 'bg-blue-100 text-blue-800',
  deploy_failed: 'bg-red-100 text-red-800',
  testing: 'bg-yellow-100 text-yellow-800',
  completed: 'bg-green-100 text-green-800',
  failed: 'bg-red-100 text-red-800',
}

export default function Results() {
  const { id } = useParams<{ id: string }>()
  const [submission, setSubmission] = useState<SubmissionDetail | null>(null)
  const [testSummary, setTestSummary] = useState<TestSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'overview' | 'functional' | 'performance' | 'chaos'>('overview')

  // Poll for updates while processing
  useEffect(() => {
    if (!id) return

    const loadData = async () => {
      try {
        const sub = await submissionsApi.get(parseInt(id))
        setSubmission(sub)

        // Load test results if testing or completed
        if (['testing', 'completed'].includes(sub.status)) {
          try {
            const summary = await testsApi.getTestSummary(parseInt(id))
            setTestSummary(summary)
          } catch {
            // Tests not ready yet
          }
        }
      } catch (err) {
        console.error('Failed to load submission:', err)
      } finally {
        setLoading(false)
      }
    }

    loadData()

    // Poll for updates
    const interval = setInterval(() => {
      if (submission && !['completed', 'failed', 'validation_failed', 'deploy_failed'].includes(submission.status)) {
        loadData()
      }
    }, 5000)

    return () => clearInterval(interval)
  }, [id, submission?.status])

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!submission) {
    return (
      <div className="text-center py-12">
        <p className="text-red-500">Submission not found</p>
        <Link to="/problems" className="text-primary-600 hover:underline mt-4 inline-block">
          Back to problems
        </Link>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <Link
          to="/problems"
          className="text-sm text-gray-500 hover:text-gray-700 mb-2 inline-block"
        >
          {'<-'} Back to problems
        </Link>
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">Submission Results</h1>
          <span
            className={`px-3 py-1 text-sm font-medium rounded-full ${
              statusColors[submission.status]
            }`}
          >
            {statusLabels[submission.status]}
          </span>
        </div>
      </div>

      {/* Error message */}
      {submission.error_message && (
        <div className="mb-6 p-4 bg-red-50 border border-red-200 rounded-lg">
          <h3 className="font-medium text-red-800 mb-1">Error</h3>
          <p className="text-sm text-red-700">{submission.error_message}</p>
        </div>
      )}

      {/* Validation feedback */}
      {submission.validation_feedback && (
        <div className="mb-6 p-4 bg-white border rounded-lg">
          <h3 className="font-medium text-gray-900 mb-3">Validation Feedback</h3>
          <div className="grid gap-4 md:grid-cols-2">
            {submission.validation_feedback.feedback && (
              <>
                <div className="p-3 bg-gray-50 rounded">
                  <p className="text-sm font-medium">Scalability</p>
                  <p className="text-lg font-bold text-primary-600">
                    {submission.validation_feedback.feedback.scalability.score}/100
                  </p>
                  <p className="text-xs text-gray-500">
                    {submission.validation_feedback.feedback.scalability.comments}
                  </p>
                </div>
                <div className="p-3 bg-gray-50 rounded">
                  <p className="text-sm font-medium">Reliability</p>
                  <p className="text-lg font-bold text-primary-600">
                    {submission.validation_feedback.feedback.reliability.score}/100
                  </p>
                  <p className="text-xs text-gray-500">
                    {submission.validation_feedback.feedback.reliability.comments}
                  </p>
                </div>
                <div className="p-3 bg-gray-50 rounded">
                  <p className="text-sm font-medium">Data Model</p>
                  <p className="text-lg font-bold text-primary-600">
                    {submission.validation_feedback.feedback.data_model.score}/100
                  </p>
                  <p className="text-xs text-gray-500">
                    {submission.validation_feedback.feedback.data_model.comments}
                  </p>
                </div>
                <div className="p-3 bg-gray-50 rounded">
                  <p className="text-sm font-medium">API Design</p>
                  <p className="text-lg font-bold text-primary-600">
                    {submission.validation_feedback.feedback.api_design.score}/100
                  </p>
                  <p className="text-xs text-gray-500">
                    {submission.validation_feedback.feedback.api_design.comments}
                  </p>
                </div>
              </>
            )}
          </div>
          {submission.validation_feedback.feedback?.overall && (
            <p className="mt-4 text-sm text-gray-700">
              {submission.validation_feedback.feedback.overall}
            </p>
          )}
        </div>
      )}

      {/* Test Results */}
      {testSummary && (
        <div className="bg-white border rounded-lg">
          {/* Test Summary */}
          <div className="p-4 border-b">
            <div className="flex items-center justify-between">
              <h3 className="font-medium text-gray-900">Test Results</h3>
              <div className="flex items-center space-x-4 text-sm">
                <span className="text-green-600">Passed: {testSummary.passed}</span>
                <span className="text-red-600">Failed: {testSummary.failed}</span>
                <span className="text-orange-600">Errors: {testSummary.errors}</span>
                <span className="text-gray-500">Total: {testSummary.total_tests}</span>
              </div>
            </div>
          </div>

          {/* Tabs */}
          <div className="border-b">
            <nav className="flex -mb-px">
              {(['overview', 'functional', 'performance', 'chaos'] as const).map((tab) => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className={`px-4 py-3 text-sm font-medium border-b-2 ${
                    activeTab === tab
                      ? 'border-primary-500 text-primary-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700'
                  }`}
                >
                  {tab.charAt(0).toUpperCase() + tab.slice(1)}
                </button>
              ))}
            </nav>
          </div>

          {/* Tab content */}
          <div className="p-4">
            {activeTab === 'overview' && (
              <div className="grid gap-4 md:grid-cols-3">
                <div className="p-4 bg-gray-50 rounded-lg text-center">
                  <p className="text-sm text-gray-500">Functional Tests</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {testSummary.functional_tests.filter((t) => t.status === 'passed').length}/
                    {testSummary.functional_tests.length}
                  </p>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg text-center">
                  <p className="text-sm text-gray-500">Performance Tests</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {testSummary.performance_tests.filter((t) => t.status === 'passed').length}/
                    {testSummary.performance_tests.length}
                  </p>
                </div>
                <div className="p-4 bg-gray-50 rounded-lg text-center">
                  <p className="text-sm text-gray-500">Chaos Tests</p>
                  <p className="text-2xl font-bold text-gray-900">
                    {testSummary.chaos_tests.filter((t) => t.status === 'passed').length}/
                    {testSummary.chaos_tests.length}
                  </p>
                </div>
              </div>
            )}

            {activeTab === 'functional' && (
              <div className="space-y-4">
                {testSummary.functional_tests.length === 0 ? (
                  <p className="text-gray-500">No functional tests available</p>
                ) : (
                  testSummary.functional_tests.map((result) => (
                    <TestResultCard key={result.id} result={result} />
                  ))
                )}
              </div>
            )}

            {activeTab === 'performance' && (
              <div className="space-y-4">
                {testSummary.performance_tests.length === 0 ? (
                  <p className="text-gray-500">No performance tests available</p>
                ) : (
                  testSummary.performance_tests.map((result) => (
                    <TestResultCard key={result.id} result={result} />
                  ))
                )}
              </div>
            )}

            {activeTab === 'chaos' && (
              <div className="space-y-4">
                {testSummary.chaos_tests.length === 0 ? (
                  <p className="text-gray-500">No chaos tests available</p>
                ) : (
                  testSummary.chaos_tests.map((result) => (
                    <TestResultCard key={result.id} result={result} />
                  ))
                )}
              </div>
            )}
          </div>
        </div>
      )}

      {/* Processing indicator */}
      {!['completed', 'failed', 'validation_failed', 'deploy_failed'].includes(submission.status) && (
        <div className="mt-6 p-4 bg-blue-50 border border-blue-200 rounded-lg flex items-center">
          <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600 mr-3"></div>
          <p className="text-blue-800">
            Your submission is being processed. This page will update automatically.
          </p>
        </div>
      )}
    </div>
  )
}
