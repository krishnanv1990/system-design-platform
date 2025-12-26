/**
 * Submission page
 * Allows users to submit their system design solution
 */

import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { problemsApi, submissionsApi } from '../api/client'
import { Problem, ValidationResponse } from '../types'
import SchemaEditor from '../components/SchemaEditor'
import ApiSpecEditor from '../components/ApiSpecEditor'
import DesignEditor from '../components/DesignEditor'

type Step = 'schema' | 'api' | 'design' | 'review'

export default function Submission() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [problem, setProblem] = useState<Problem | null>(null)
  const [loading, setLoading] = useState(true)
  const [step, setStep] = useState<Step>('schema')
  const [submitting, setSubmitting] = useState(false)
  const [validating, setValidating] = useState(false)
  const [validation, setValidation] = useState<ValidationResponse | null>(null)

  // Form data
  const [schemaInput, setSchemaInput] = useState('')
  const [apiSpecInput, setApiSpecInput] = useState('')
  const [designText, setDesignText] = useState('')

  useEffect(() => {
    const loadProblem = async () => {
      if (!id) return
      try {
        const data = await problemsApi.get(parseInt(id))
        setProblem(data)
      } catch (err) {
        console.error('Failed to load problem:', err)
      } finally {
        setLoading(false)
      }
    }
    loadProblem()
  }, [id])

  const handleValidate = async () => {
    if (!problem) return
    setValidating(true)
    try {
      const result = await submissionsApi.validate({
        problem_id: problem.id,
        schema_input: JSON.parse(schemaInput || '{}'),
        api_spec_input: JSON.parse(apiSpecInput || '{}'),
        design_text: designText,
      })
      setValidation(result)
    } catch (err) {
      console.error('Validation failed:', err)
      setValidation({
        is_valid: false,
        errors: ['Validation request failed. Please check your JSON syntax.'],
        warnings: [],
        suggestions: [],
        score: null,
      })
    } finally {
      setValidating(false)
    }
  }

  const handleSubmit = async () => {
    if (!problem) return
    setSubmitting(true)
    try {
      const submission = await submissionsApi.create({
        problem_id: problem.id,
        schema_input: JSON.parse(schemaInput || '{}'),
        api_spec_input: JSON.parse(apiSpecInput || '{}'),
        design_text: designText,
      })
      navigate(`/submissions/${submission.id}/results`)
    } catch (err) {
      console.error('Submission failed:', err)
      alert('Submission failed. Please try again.')
    } finally {
      setSubmitting(false)
    }
  }

  const steps: { id: Step; label: string }[] = [
    { id: 'schema', label: 'Database Schema' },
    { id: 'api', label: 'API Specification' },
    { id: 'design', label: 'System Design' },
    { id: 'review', label: 'Review & Submit' },
  ]

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  if (!problem) {
    return <div className="text-center py-12 text-red-500">Problem not found</div>
  }

  return (
    <div className="max-w-5xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">{problem.title}</h1>
        <p className="text-sm text-gray-500">Submit your system design solution</p>
      </div>

      {/* Progress steps */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          {steps.map((s, i) => (
            <div
              key={s.id}
              className={`flex items-center ${i < steps.length - 1 ? 'flex-1' : ''}`}
            >
              <button
                onClick={() => setStep(s.id)}
                className={`flex items-center justify-center w-10 h-10 rounded-full font-medium ${
                  step === s.id
                    ? 'bg-primary-600 text-white'
                    : steps.indexOf(steps.find((x) => x.id === step)!) > i
                    ? 'bg-green-500 text-white'
                    : 'bg-gray-200 text-gray-600'
                }`}
              >
                {i + 1}
              </button>
              <span
                className={`ml-2 text-sm ${
                  step === s.id ? 'text-primary-600 font-medium' : 'text-gray-500'
                }`}
              >
                {s.label}
              </span>
              {i < steps.length - 1 && (
                <div className="flex-1 h-0.5 mx-4 bg-gray-200"></div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Step content */}
      <div className="bg-white rounded-lg border p-6 mb-6">
        {step === 'schema' && (
          <SchemaEditor value={schemaInput} onChange={setSchemaInput} />
        )}
        {step === 'api' && (
          <ApiSpecEditor value={apiSpecInput} onChange={setApiSpecInput} />
        )}
        {step === 'design' && (
          <DesignEditor value={designText} onChange={setDesignText} />
        )}
        {step === 'review' && (
          <div className="space-y-6">
            <div>
              <h3 className="font-medium text-gray-900 mb-2">Database Schema</h3>
              <pre className="p-4 bg-gray-50 rounded text-sm overflow-x-auto">
                {schemaInput || 'Not provided'}
              </pre>
            </div>
            <div>
              <h3 className="font-medium text-gray-900 mb-2">API Specification</h3>
              <pre className="p-4 bg-gray-50 rounded text-sm overflow-x-auto">
                {apiSpecInput || 'Not provided'}
              </pre>
            </div>
            <div>
              <h3 className="font-medium text-gray-900 mb-2">System Design</h3>
              <div className="p-4 bg-gray-50 rounded text-sm whitespace-pre-wrap">
                {designText || 'Not provided'}
              </div>
            </div>

            {/* Validation results */}
            {validation && (
              <div
                className={`p-4 rounded-lg ${
                  validation.is_valid
                    ? 'bg-green-50 border border-green-200'
                    : 'bg-red-50 border border-red-200'
                }`}
              >
                <h3
                  className={`font-medium mb-2 ${
                    validation.is_valid ? 'text-green-800' : 'text-red-800'
                  }`}
                >
                  {validation.is_valid ? '[+] Validation Passed' : '[x] Validation Failed'}
                </h3>
                {validation.errors.length > 0 && (
                  <ul className="text-sm text-red-700 list-disc list-inside">
                    {validation.errors.map((e, i) => (
                      <li key={i}>{e}</li>
                    ))}
                  </ul>
                )}
                {validation.warnings.length > 0 && (
                  <ul className="text-sm text-yellow-700 list-disc list-inside mt-2">
                    {validation.warnings.map((w, i) => (
                      <li key={i}>{w}</li>
                    ))}
                  </ul>
                )}
                {validation.suggestions.length > 0 && (
                  <ul className="text-sm text-blue-700 list-disc list-inside mt-2">
                    {validation.suggestions.map((s, i) => (
                      <li key={i}>{s}</li>
                    ))}
                  </ul>
                )}
                {validation.score !== null && (
                  <p className="mt-2 text-sm font-medium">
                    Score: {validation.score}/100
                  </p>
                )}
              </div>
            )}
          </div>
        )}
      </div>

      {/* Navigation buttons */}
      <div className="flex justify-between">
        <button
          onClick={() => {
            const currentIndex = steps.findIndex((s) => s.id === step)
            if (currentIndex > 0) {
              setStep(steps[currentIndex - 1].id)
            }
          }}
          disabled={step === 'schema'}
          className="px-4 py-2 text-gray-600 hover:text-gray-900 disabled:opacity-50"
        >
          Previous
        </button>
        <div className="space-x-4">
          {step === 'review' && (
            <>
              <button
                onClick={handleValidate}
                disabled={validating}
                className="px-4 py-2 border border-primary-600 text-primary-600 rounded-lg hover:bg-primary-50 disabled:opacity-50"
              >
                {validating ? 'Validating...' : 'Validate'}
              </button>
              <button
                onClick={handleSubmit}
                disabled={submitting}
                className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 disabled:opacity-50"
              >
                {submitting ? 'Submitting...' : 'Submit Solution'}
              </button>
            </>
          )}
          {step !== 'review' && (
            <button
              onClick={() => {
                const currentIndex = steps.findIndex((s) => s.id === step)
                if (currentIndex < steps.length - 1) {
                  setStep(steps[currentIndex + 1].id)
                }
              }}
              className="px-6 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700"
            >
              Next
            </button>
          )}
        </div>
      </div>
    </div>
  )
}
