/**
 * Submission page
 * Allows users to submit their system design solution
 */

import { useState, useEffect } from "react"
import { useParams, useNavigate } from "react-router-dom"
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
} from "lucide-react"
import { problemsApi, submissionsApi } from "@/api/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import SchemaEditor from "@/components/SchemaEditor"
import ApiSpecEditor from "@/components/ApiSpecEditor"
import DesignEditor from "@/components/DesignEditor"
import { cn } from "@/lib/utils"
import type { Problem, ValidationResponse } from "@/types"

type Step = "schema" | "api" | "design" | "review"

const steps: { id: Step; label: string }[] = [
  { id: "schema", label: "Database Schema" },
  { id: "api", label: "API Specification" },
  { id: "design", label: "System Design" },
  { id: "review", label: "Review & Submit" },
]

function SubmissionSkeleton() {
  return (
    <div className="max-w-5xl mx-auto space-y-6">
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

export default function Submission() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()

  const [problem, setProblem] = useState<Problem | null>(null)
  const [loading, setLoading] = useState(true)
  const [step, setStep] = useState<Step>("schema")
  const [submitting, setSubmitting] = useState(false)
  const [validating, setValidating] = useState(false)
  const [validation, setValidation] = useState<ValidationResponse | null>(null)

  // Form data
  const [schemaInput, setSchemaInput] = useState("")
  const [apiSpecInput, setApiSpecInput] = useState("")
  const [designText, setDesignText] = useState("")

  const currentStepIndex = steps.findIndex((s) => s.id === step)
  const progressPercent = ((currentStepIndex + 1) / steps.length) * 100

  useEffect(() => {
    const loadProblem = async () => {
      if (!id) return
      try {
        const data = await problemsApi.get(parseInt(id))
        setProblem(data)
      } catch (err) {
        console.error("Failed to load problem:", err)
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
        schema_input: JSON.parse(schemaInput || "{}"),
        api_spec_input: JSON.parse(apiSpecInput || "{}"),
        design_text: designText,
      })
      setValidation(result)
    } catch (err) {
      console.error("Validation failed:", err)
      setValidation({
        is_valid: false,
        errors: ["Validation request failed. Please check your JSON syntax."],
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
        schema_input: JSON.parse(schemaInput || "{}"),
        api_spec_input: JSON.parse(apiSpecInput || "{}"),
        design_text: designText,
      })
      navigate(`/submissions/${submission.id}/results`)
    } catch (err) {
      console.error("Submission failed:", err)
    } finally {
      setSubmitting(false)
    }
  }

  const goToStep = (targetStep: Step) => {
    setStep(targetStep)
  }

  const goNext = () => {
    if (currentStepIndex < steps.length - 1) {
      setStep(steps[currentStepIndex + 1].id)
    }
  }

  const goPrev = () => {
    if (currentStepIndex > 0) {
      setStep(steps[currentStepIndex - 1].id)
    }
  }

  if (loading) {
    return <SubmissionSkeleton />
  }

  if (!problem) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="h-12 w-12 text-destructive mb-4" />
        <p className="text-destructive font-medium">Problem not found</p>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-bold">{problem.title}</h1>
        <p className="text-sm text-muted-foreground">Submit your system design solution</p>
      </div>

      {/* Progress */}
      <div className="space-y-2">
        <div className="flex justify-between text-sm text-muted-foreground">
          <span>
            Step {currentStepIndex + 1} of {steps.length}
          </span>
          <span>{Math.round(progressPercent)}% complete</span>
        </div>
        <Progress value={progressPercent} className="h-2" />
      </div>

      {/* Progress steps */}
      <div className="flex items-center justify-between">
        {steps.map((s, i) => {
          const isComplete = currentStepIndex > i
          const isCurrent = currentStepIndex === i
          return (
            <div key={s.id} className={cn("flex items-center", i < steps.length - 1 && "flex-1")}>
              <button
                onClick={() => goToStep(s.id)}
                className={cn(
                  "flex items-center justify-center w-10 h-10 rounded-full font-medium transition-colors",
                  isCurrent && "bg-primary text-primary-foreground",
                  isComplete && "bg-success text-success-foreground",
                  !isCurrent && !isComplete && "bg-muted text-muted-foreground"
                )}
              >
                {isComplete ? <Check className="h-5 w-5" /> : i + 1}
              </button>
              <span
                className={cn(
                  "ml-2 text-sm hidden sm:inline",
                  isCurrent && "text-primary font-medium",
                  !isCurrent && "text-muted-foreground"
                )}
              >
                {s.label}
              </span>
              {i < steps.length - 1 && (
                <div
                  className={cn(
                    "flex-1 h-0.5 mx-4",
                    isComplete ? "bg-success" : "bg-muted"
                  )}
                />
              )}
            </div>
          )
        })}
      </div>

      {/* Step content - wrapped in form to prevent accidental submissions */}
      <form onSubmit={(e) => e.preventDefault()}>
        <Card>
          <CardContent className="pt-6">
            {step === "schema" && <SchemaEditor value={schemaInput} onChange={setSchemaInput} />}
            {step === "api" && <ApiSpecEditor value={apiSpecInput} onChange={setApiSpecInput} />}
            {step === "design" && (
              <DesignEditor
                value={designText}
                onChange={setDesignText}
                problemId={problem?.id}
                currentSchema={schemaInput}
                currentApiSpec={apiSpecInput}
              />
            )}
          {step === "review" && (
            <div className="space-y-6">
              <div>
                <h3 className="font-medium mb-3 flex items-center gap-2">
                  <span className="p-1.5 rounded-md bg-gradient-to-br from-blue-500 to-blue-600">
                    <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 7v10c0 2.21 3.582 4 8 4s8-1.79 8-4V7M4 7c0 2.21 3.582 4 8 4s8-1.79 8-4M4 7c0-2.21 3.582-4 8-4s8 1.79 8 4" />
                    </svg>
                  </span>
                  Data Storage Schema
                </h3>
                <SchemaEditor value={schemaInput} onChange={() => {}} readOnly />
              </div>
              <div>
                <h3 className="font-medium mb-3 flex items-center gap-2">
                  <span className="p-1.5 rounded-md bg-gradient-to-br from-emerald-500 to-green-600">
                    <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 9l3 3-3 3m5 0h3M5 20h14a2 2 0 002-2V6a2 2 0 00-2-2H5a2 2 0 00-2 2v12a2 2 0 002 2z" />
                    </svg>
                  </span>
                  API Specification
                </h3>
                <pre className="p-4 bg-muted rounded-lg text-sm overflow-x-auto border">
                  {apiSpecInput || "Not provided"}
                </pre>
              </div>
              <div>
                <h3 className="font-medium mb-3 flex items-center gap-2">
                  <span className="p-1.5 rounded-md bg-gradient-to-br from-purple-500 to-violet-600">
                    <svg className="h-4 w-4 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
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
                          <CheckCircle className="h-5 w-5" />
                          Validation Passed
                        </>
                      ) : (
                        <>
                          <XCircle className="h-5 w-5" />
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
                          <XCircle className="h-4 w-4" />
                          Errors
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
                          <AlertTriangle className="h-4 w-4" />
                          Warnings
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
                          <Lightbulb className="h-4 w-4" />
                          Suggestions
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
      <div className="flex justify-between">
        <Button variant="ghost" onClick={goPrev} disabled={step === "schema"}>
          <ChevronLeft className="mr-2 h-4 w-4" />
          Previous
        </Button>
        <div className="flex gap-3">
          {step === "review" && (
            <>
              <Button variant="outline" onClick={handleValidate} disabled={validating}>
                {validating && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {validating ? "Validating..." : "Validate"}
              </Button>
              <Button onClick={handleSubmit} disabled={submitting}>
                {submitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {submitting ? "Submitting..." : "Submit Solution"}
              </Button>
            </>
          )}
          {step !== "review" && (
            <Button onClick={goNext}>
              Next
              <ChevronRight className="ml-2 h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  )
}
