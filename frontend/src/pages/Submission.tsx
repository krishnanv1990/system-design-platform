/**
 * Submission page
 * Allows users to submit their system design solution
 *
 * UX Features:
 * - Auto-saves form data to localStorage
 * - Warns before navigating away with unsaved changes
 * - Inline validation with helpful error messages
 * - Mobile-responsive step indicators
 * - Toast notifications for errors
 * - Breadcrumb navigation
 */

import { useState, useEffect, useCallback, useMemo } from "react"
import { useParams, useNavigate, useBlocker, useSearchParams } from "react-router-dom"
import {
  Check,
  ChevronLeft,
  ChevronRight,
  Loader2,
  AlertCircle,
  CheckCircle,
  XCircle,
  AlertTriangle,
  Lightbulb,
  Save,
  RotateCcw,
  RefreshCw,
} from "lucide-react"
import { problemsApi, submissionsApi, DifficultyLevel } from "@/api/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import { Breadcrumbs } from "@/components/ui/breadcrumbs"
import SchemaEditor from "@/components/SchemaEditor"
import ApiSpecEditor from "@/components/ApiSpecEditor"
import DesignEditor from "@/components/DesignEditor"
import { useToast } from "@/hooks/useToast"
import { cn } from "@/lib/utils"
import type { Problem, ValidationResponse } from "@/types"

type Step = "schema" | "api" | "design" | "review"

const steps: { id: Step; label: string; shortLabel: string }[] = [
  { id: "schema", label: "Database Schema", shortLabel: "Schema" },
  { id: "api", label: "API Specification", shortLabel: "API" },
  { id: "design", label: "System Design", shortLabel: "Design" },
  { id: "review", label: "Review & Submit", shortLabel: "Review" },
]

// Storage key for form data
const getStorageKey = (problemId: string) => `submission_draft_${problemId}`

interface FormData {
  schemaInput: string
  apiSpecInput: string
  designText: string
  lastSaved: string
}

function SubmissionSkeleton() {
  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <Skeleton className="h-6 w-48" />
      <Skeleton className="h-8 w-64" />
      <Skeleton className="h-4 w-48" />
      <div className="flex gap-4">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-10 w-10 rounded-full" />
        ))}
      </div>
      <Card>
        <CardContent className="pt-6">
          <Skeleton className="h-64 w-full" />
        </CardContent>
      </Card>
    </div>
  )
}

interface JsonValidResult {
  valid: true
  data: Record<string, unknown>
}

interface JsonInvalidResult {
  valid: false
  error: string
  line?: number
  column?: number
}

type JsonValidationResult = JsonValidResult | JsonInvalidResult

// Validate JSON and return parsed result or error with details
function validateJson(input: string): JsonValidationResult {
  if (!input || input.trim() === '') {
    return { valid: true, data: {} }
  }

  try {
    const data = JSON.parse(input) as Record<string, unknown>
    return { valid: true, data }
  } catch (e) {
    const error = e as SyntaxError
    const message = error.message

    // Try to extract line/column from error message
    const posMatch = message.match(/position (\d+)/)
    if (posMatch) {
      const position = parseInt(posMatch[1])
      const lines = input.substring(0, position).split('\n')
      const line = lines.length
      const column = lines[lines.length - 1].length + 1
      return {
        valid: false,
        error: `JSON syntax error at line ${line}, column ${column}: ${message.replace(/position \d+/, '').trim()}`,
        line,
        column
      }
    }

    return { valid: false, error: `Invalid JSON: ${message}` }
  }
}

export default function Submission() {
  const { id } = useParams<{ id: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { toast } = useToast()

  // Get difficulty level from URL query params, default to "medium"
  const difficultyLevel = (searchParams.get("difficulty") as DifficultyLevel) || "medium"

  const [problem, setProblem] = useState<Problem | null>(null)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [step, setStep] = useState<Step>("schema")
  const [submitting, setSubmitting] = useState(false)
  const [validating, setValidating] = useState(false)
  const [validation, setValidation] = useState<ValidationResponse | null>(null)

  // Form data with localStorage persistence
  const [schemaInput, setSchemaInput] = useState("")
  const [apiSpecInput, setApiSpecInput] = useState("")
  const [designText, setDesignText] = useState("")
  const [isDirty, setIsDirty] = useState(false)
  const [lastSaved, setLastSaved] = useState<Date | null>(null)
  const [hasLoadedDraft, setHasLoadedDraft] = useState(false)

  // Inline validation states
  const [schemaError, setSchemaError] = useState<string | null>(null)
  const [apiSpecError, setApiSpecError] = useState<string | null>(null)

  const currentStepIndex = steps.findIndex((s) => s.id === step)
  const progressPercent = ((currentStepIndex + 1) / steps.length) * 100

  // Load saved draft from localStorage
  useEffect(() => {
    if (!id) return

    const storageKey = getStorageKey(id)
    try {
      const saved = localStorage.getItem(storageKey)
      if (saved) {
        const data: FormData = JSON.parse(saved)
        setSchemaInput(data.schemaInput || "")
        setApiSpecInput(data.apiSpecInput || "")
        setDesignText(data.designText || "")
        setLastSaved(data.lastSaved ? new Date(data.lastSaved) : null)
        setHasLoadedDraft(true)
        toast({
          title: "Draft restored",
          description: "Your previous work has been loaded from auto-save.",
        })
      }
    } catch {
      // Invalid stored data, ignore
    }
  }, [id, toast])

  // Auto-save to localStorage with debounce
  useEffect(() => {
    if (!id || !isDirty) return

    const timeoutId = setTimeout(() => {
      const storageKey = getStorageKey(id)
      const data: FormData = {
        schemaInput,
        apiSpecInput,
        designText,
        lastSaved: new Date().toISOString(),
      }
      try {
        localStorage.setItem(storageKey, JSON.stringify(data))
        setLastSaved(new Date())
      } catch {
        console.error("Failed to save draft to localStorage")
      }
    }, 1000)

    return () => clearTimeout(timeoutId)
  }, [id, schemaInput, apiSpecInput, designText, isDirty])

  // Warn before navigating away with unsaved changes
  const blocker = useBlocker(
    ({ currentLocation, nextLocation }) =>
      isDirty && currentLocation.pathname !== nextLocation.pathname
  )

  // Handle blocker state
  useEffect(() => {
    if (blocker.state === "blocked") {
      const confirmed = window.confirm(
        "You have unsaved changes. Are you sure you want to leave?"
      )
      if (confirmed) {
        blocker.proceed()
      } else {
        blocker.reset()
      }
    }
  }, [blocker])

  // Warn on page unload
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault()
        e.returnValue = "You have unsaved changes."
        return e.returnValue
      }
    }
    window.addEventListener("beforeunload", handleBeforeUnload)
    return () => window.removeEventListener("beforeunload", handleBeforeUnload)
  }, [isDirty])

  // Load problem
  useEffect(() => {
    const loadProblem = async () => {
      if (!id) return
      try {
        const data = await problemsApi.get(parseInt(id))
        setProblem(data)
        setLoadError(null)
      } catch (err: any) {
        console.error("Failed to load problem:", err)
        const message = err.response?.data?.detail || err.message || "Failed to load problem"
        setLoadError(message)
        toast({
          variant: "destructive",
          title: "Failed to load problem",
          description: message,
        })
      } finally {
        setLoading(false)
      }
    }
    loadProblem()
  }, [id, toast])

  // Form change handlers that mark as dirty
  const handleSchemaChange = useCallback((value: string) => {
    setSchemaInput(value)
    setIsDirty(true)

    // Validate JSON inline
    const result = validateJson(value)
    setSchemaError(result.valid ? null : result.error)
  }, [])

  const handleApiSpecChange = useCallback((value: string) => {
    setApiSpecInput(value)
    setIsDirty(true)

    // Validate JSON inline
    const result = validateJson(value)
    setApiSpecError(result.valid ? null : result.error)
  }, [])

  const handleDesignChange = useCallback((value: string) => {
    setDesignText(value)
    setIsDirty(true)
  }, [])

  // Clear draft
  const handleClearDraft = useCallback(() => {
    if (!id) return

    if (window.confirm("Are you sure you want to clear all your work? This cannot be undone.")) {
      localStorage.removeItem(getStorageKey(id))
      setSchemaInput("")
      setApiSpecInput("")
      setDesignText("")
      setIsDirty(false)
      setLastSaved(null)
      setValidation(null)
      setSchemaError(null)
      setApiSpecError(null)
      toast({
        title: "Draft cleared",
        description: "All your work has been removed.",
      })
    }
  }, [id, toast])

  // Check if current step has valid data
  const isStepValid = useCallback((stepId: Step): boolean => {
    switch (stepId) {
      case "schema":
        return !schemaError
      case "api":
        return !apiSpecError
      case "design":
        return true // Design step is always valid (optional diagram)
      case "review":
        return !schemaError && !apiSpecError
      default:
        return true
    }
  }, [schemaError, apiSpecError])

  // Validation handler with better error messages
  const handleValidate = async () => {
    if (!problem) return

    // Check for JSON errors first
    if (schemaError || apiSpecError) {
      toast({
        variant: "destructive",
        title: "Invalid JSON",
        description: schemaError || apiSpecError,
      })
      return
    }

    setValidating(true)
    try {
      const schemaResult = validateJson(schemaInput)
      const apiResult = validateJson(apiSpecInput)

      if (!schemaResult.valid) {
        throw new Error(schemaResult.error)
      }
      if (!apiResult.valid) {
        throw new Error(apiResult.error)
      }

      const result = await submissionsApi.validate({
        problem_id: problem.id,
        schema_input: schemaResult.data,
        api_spec_input: apiResult.data,
        design_text: designText,
      })
      setValidation(result)

      if (result.is_valid) {
        toast({
          title: "Validation passed!",
          description: result.score ? `Score: ${result.score}/100` : "Your design looks good.",
        })
      } else {
        toast({
          variant: "destructive",
          title: "Validation failed",
          description: `${result.errors.length} error(s) found. Please review and fix them.`,
        })
      }
    } catch (err: any) {
      console.error("Validation failed:", err)
      const message = err.response?.data?.detail || err.message || "Validation request failed"
      setValidation({
        is_valid: false,
        errors: [message],
        warnings: [],
        suggestions: [],
        score: null,
      })
      toast({
        variant: "destructive",
        title: "Validation failed",
        description: message,
      })
    } finally {
      setValidating(false)
    }
  }

  // Submit handler
  const handleSubmit = async () => {
    if (!problem) return

    // Check for errors first
    if (schemaError || apiSpecError) {
      toast({
        variant: "destructive",
        title: "Cannot submit",
        description: "Please fix the JSON errors before submitting.",
      })
      return
    }

    setSubmitting(true)
    try {
      const schemaResult = validateJson(schemaInput)
      const apiResult = validateJson(apiSpecInput)

      if (!schemaResult.valid) {
        throw new Error(schemaResult.error)
      }
      if (!apiResult.valid) {
        throw new Error(apiResult.error)
      }

      const submission = await submissionsApi.create({
        problem_id: problem.id,
        schema_input: schemaResult.data,
        api_spec_input: apiResult.data,
        design_text: designText,
      })

      // Clear draft on successful submission
      if (id) {
        localStorage.removeItem(getStorageKey(id))
      }
      setIsDirty(false)

      toast({
        title: "Submission created!",
        description: "Redirecting to results page...",
      })

      navigate(`/submissions/${submission.id}/results`)
    } catch (err: any) {
      console.error("Submission failed:", err)
      const message = err.response?.data?.detail || err.message || "Submission failed"
      toast({
        variant: "destructive",
        title: "Submission failed",
        description: message,
      })
    } finally {
      setSubmitting(false)
    }
  }

  const goToStep = (targetStep: Step) => {
    setStep(targetStep)
  }

  const goNext = () => {
    if (currentStepIndex < steps.length - 1) {
      // Validate current step before moving
      if (!isStepValid(step)) {
        toast({
          variant: "destructive",
          title: "Please fix errors",
          description: "Fix the errors in this step before continuing.",
        })
        return
      }
      setStep(steps[currentStepIndex + 1].id)
    }
  }

  const goPrev = () => {
    if (currentStepIndex > 0) {
      setStep(steps[currentStepIndex - 1].id)
    }
  }

  // Breadcrumbs
  const breadcrumbItems = useMemo(() => [
    { label: "Problems", href: "/problems" },
    { label: problem?.title || "Loading...", href: problem ? `/problems/${problem.id}` : undefined },
    { label: "Submit Solution" },
  ], [problem])

  if (loading) {
    return <SubmissionSkeleton />
  }

  if (loadError || !problem) {
    return (
      <div className="max-w-5xl mx-auto">
        <Breadcrumbs items={[{ label: "Problems", href: "/problems" }, { label: "Error" }]} />
        <div className="flex flex-col items-center justify-center py-12">
          <AlertCircle className="h-12 w-12 text-destructive mb-4" />
          <p className="text-destructive font-medium mb-2">
            {loadError || "Problem not found"}
          </p>
          <div className="flex gap-3 mt-4">
            <Button variant="outline" onClick={() => window.location.reload()}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Retry
            </Button>
            <Button onClick={() => navigate("/problems")}>
              Back to Problems
            </Button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Breadcrumbs */}
      <Breadcrumbs items={breadcrumbItems} />

      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-2xl font-bold">{problem.title}</h1>
          <p className="text-sm text-muted-foreground">Submit your system design solution</p>
        </div>

        {/* Auto-save indicator */}
        <div className="flex items-center gap-2 text-sm text-muted-foreground">
          {isDirty && (
            <span className="flex items-center gap-1 text-amber-600 dark:text-amber-400">
              <Save className="h-4 w-4" />
              Unsaved changes
            </span>
          )}
          {lastSaved && !isDirty && (
            <span className="flex items-center gap-1 text-green-600 dark:text-green-400">
              <CheckCircle className="h-4 w-4" />
              Saved {lastSaved.toLocaleTimeString()}
            </span>
          )}
          {hasLoadedDraft && (
            <Button
              variant="ghost"
              size="sm"
              onClick={handleClearDraft}
              className="text-muted-foreground hover:text-destructive"
              title="Clear all saved work"
            >
              <RotateCcw className="h-4 w-4" />
              <span className="sr-only">Clear draft</span>
            </Button>
          )}
        </div>
      </div>

      {/* Progress */}
      <div className="space-y-2">
        <div className="flex justify-between text-sm text-muted-foreground">
          <span>
            Step {currentStepIndex + 1} of {steps.length}
          </span>
          <span>{Math.round(progressPercent)}% complete</span>
        </div>
        <Progress value={progressPercent} className="h-2" aria-label="Form progress" />
      </div>

      {/* Progress steps - mobile responsive */}
      <nav aria-label="Form steps" className="flex items-center justify-between">
        {steps.map((s, i) => {
          const isComplete = currentStepIndex > i
          const isCurrent = currentStepIndex === i
          const hasError = (s.id === "schema" && schemaError) || (s.id === "api" && apiSpecError)

          return (
            <div key={s.id} className={cn("flex items-center", i < steps.length - 1 && "flex-1")}>
              <button
                type="button"
                onClick={() => goToStep(s.id)}
                aria-current={isCurrent ? "step" : undefined}
                aria-label={`${s.label}${isComplete ? " (completed)" : ""}${hasError ? " (has errors)" : ""}`}
                className={cn(
                  "flex items-center justify-center w-10 h-10 rounded-full font-medium transition-colors focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2",
                  isCurrent && "bg-primary text-primary-foreground",
                  isComplete && !hasError && "bg-success text-success-foreground",
                  hasError && "bg-destructive text-destructive-foreground",
                  !isCurrent && !isComplete && !hasError && "bg-muted text-muted-foreground hover:bg-muted/80"
                )}
              >
                {isComplete && !hasError ? (
                  <Check className="h-5 w-5" aria-hidden="true" />
                ) : hasError ? (
                  <XCircle className="h-5 w-5" aria-hidden="true" />
                ) : (
                  i + 1
                )}
              </button>
              {/* Show labels on all screen sizes now */}
              <span
                className={cn(
                  "ml-2 text-xs sm:text-sm",
                  isCurrent && "text-primary font-medium",
                  hasError && "text-destructive",
                  !isCurrent && !hasError && "text-muted-foreground"
                )}
              >
                <span className="hidden sm:inline">{s.label}</span>
                <span className="sm:hidden">{s.shortLabel}</span>
              </span>
              {i < steps.length - 1 && (
                <div
                  className={cn(
                    "flex-1 h-0.5 mx-2 sm:mx-4",
                    isComplete ? "bg-success" : "bg-muted"
                  )}
                  aria-hidden="true"
                />
              )}
            </div>
          )
        })}
      </nav>

      {/* Inline error display for current step */}
      {step === "schema" && schemaError && (
        <div className="flex items-start gap-2 p-3 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive text-sm" role="alert">
          <XCircle className="h-5 w-5 shrink-0 mt-0.5" aria-hidden="true" />
          <div>
            <p className="font-medium">Schema JSON Error</p>
            <p className="mt-1 font-mono text-xs">{schemaError}</p>
          </div>
        </div>
      )}
      {step === "api" && apiSpecError && (
        <div className="flex items-start gap-2 p-3 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive text-sm" role="alert">
          <XCircle className="h-5 w-5 shrink-0 mt-0.5" aria-hidden="true" />
          <div>
            <p className="font-medium">API Spec JSON Error</p>
            <p className="mt-1 font-mono text-xs">{apiSpecError}</p>
          </div>
        </div>
      )}

      {/* Step content */}
      <form onSubmit={(e) => e.preventDefault()}>
        <Card>
          <CardContent className="pt-6">
            {step === "schema" && (
              <SchemaEditor
                value={schemaInput}
                onChange={handleSchemaChange}
              />
            )}
            {step === "api" && (
              <ApiSpecEditor
                value={apiSpecInput}
                onChange={handleApiSpecChange}
              />
            )}
            {step === "design" && (
              <DesignEditor
                value={designText}
                onChange={handleDesignChange}
                problemId={problem?.id}
                currentSchema={schemaInput}
                currentApiSpec={apiSpecInput}
                difficultyLevel={difficultyLevel}
              />
            )}
            {step === "review" && (
              <div className="space-y-6">
                <div>
                  <h3 className="font-medium mb-3 flex items-center gap-2">
                    <span className="p-1.5 rounded-md bg-gradient-to-br from-blue-500 to-blue-600">
                      <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                      </svg>
                    </span>
                    Data Storage Schema
                    {schemaError && (
                      <Badge variant="destructive" className="ml-2">Has Errors</Badge>
                    )}
                  </h3>
                  <SchemaEditor value={schemaInput} onChange={() => {}} readOnly />
                </div>
                <div>
                  <h3 className="font-medium mb-3 flex items-center gap-2">
                    <span className="p-1.5 rounded-md bg-gradient-to-br from-emerald-500 to-green-600">
                      <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                    </span>
                    API Specification
                    {apiSpecError && (
                      <Badge variant="destructive" className="ml-2">Has Errors</Badge>
                    )}
                  </h3>
                  <pre className="p-4 bg-muted rounded-lg text-sm overflow-x-auto border max-h-64">
                    <code>{apiSpecInput || "Not provided"}</code>
                  </pre>
                </div>
                <div>
                  <h3 className="font-medium mb-3 flex items-center gap-2">
                    <span className="p-1.5 rounded-md bg-gradient-to-br from-purple-500 to-violet-600">
                      <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden="true">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                      </svg>
                    </span>
                    System Design
                  </h3>
                  <DesignEditor value={designText} onChange={() => {}} readOnly />
                </div>

                {/* Validation results */}
                {validation && (
                  <Card
                    className={cn(
                      "border-2",
                      validation.is_valid
                        ? "border-success/50 bg-success/5"
                        : "border-destructive/50 bg-destructive/5"
                    )}
                    role="alert"
                  >
                    <CardHeader className="pb-2">
                      <CardTitle
                        className={cn(
                          "text-base flex items-center gap-2",
                          validation.is_valid ? "text-success" : "text-destructive"
                        )}
                      >
                        {validation.is_valid ? (
                          <>
                            <CheckCircle className="h-5 w-5" aria-hidden="true" />
                            Validation Passed
                          </>
                        ) : (
                          <>
                            <XCircle className="h-5 w-5" aria-hidden="true" />
                            Validation Failed
                          </>
                        )}
                        {validation.score !== null && (
                          <Badge variant={validation.score >= 70 ? "success" : "destructive"} className="ml-auto">
                            Score: {validation.score}/100
                          </Badge>
                        )}
                      </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                      {validation.errors.length > 0 && (
                        <div>
                          <p className="text-sm font-medium text-destructive mb-1 flex items-center gap-1">
                            <XCircle className="h-4 w-4" aria-hidden="true" />
                            Errors ({validation.errors.length})
                          </p>
                          <ul className="text-sm text-destructive/90 space-y-1 ml-5">
                            {validation.errors.map((e, i) => (
                              <li key={i} className="list-disc">
                                {e}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {validation.warnings.length > 0 && (
                        <div>
                          <p className="text-sm font-medium text-warning mb-1 flex items-center gap-1">
                            <AlertTriangle className="h-4 w-4" aria-hidden="true" />
                            Warnings ({validation.warnings.length})
                          </p>
                          <ul className="text-sm text-warning/90 space-y-1 ml-5">
                            {validation.warnings.map((w, i) => (
                              <li key={i} className="list-disc">
                                {w}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      {validation.suggestions.length > 0 && (
                        <div>
                          <p className="text-sm font-medium text-primary mb-1 flex items-center gap-1">
                            <Lightbulb className="h-4 w-4" aria-hidden="true" />
                            Suggestions ({validation.suggestions.length})
                          </p>
                          <ul className="text-sm text-primary/90 space-y-1 ml-5">
                            {validation.suggestions.map((s, i) => (
                              <li key={i} className="list-disc">
                                {s}
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                    </CardContent>
                  </Card>
                )}
              </div>
            )}
          </CardContent>
        </Card>
      </form>

      {/* Navigation buttons */}
      <div className="flex flex-col sm:flex-row justify-between gap-4">
        <Button
          variant="ghost"
          onClick={goPrev}
          disabled={step === "schema"}
          className="order-2 sm:order-1"
        >
          <ChevronLeft className="mr-2 h-4 w-4" aria-hidden="true" />
          Previous
        </Button>
        <div className="flex flex-col sm:flex-row gap-3 order-1 sm:order-2">
          {step === "review" && (
            <>
              <Button
                variant="outline"
                onClick={handleValidate}
                disabled={validating || schemaError !== null || apiSpecError !== null}
              >
                {validating && <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />}
                {validating ? "Validating..." : "Validate Design"}
              </Button>
              <Button
                onClick={handleSubmit}
                disabled={submitting || schemaError !== null || apiSpecError !== null}
              >
                {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />}
                {submitting ? "Submitting..." : "Submit Solution"}
              </Button>
            </>
          )}
          {step !== "review" && (
            <Button onClick={goNext}>
              Next
              <ChevronRight className="ml-2 h-4 w-4" aria-hidden="true" />
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
