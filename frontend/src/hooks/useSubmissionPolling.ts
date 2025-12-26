import { useEffect, useRef, useState, useCallback } from "react"
import { submissionsApi, testsApi } from "@/api/client"
import type { SubmissionDetail, TestSummary } from "@/types"

interface UseSubmissionPollingOptions {
  onSubmissionUpdate?: (submission: SubmissionDetail) => void
  onTestsUpdate?: (tests: TestSummary) => void
  enabled?: boolean
  intervalMs?: number
  stopOnComplete?: boolean
}

interface UseSubmissionPollingReturn {
  submission: SubmissionDetail | null
  testSummary: TestSummary | null
  isPolling: boolean
  error: Error | null
  refresh: () => Promise<void>
}

const TERMINAL_STATUSES = [
  "completed",
  "failed",
  "validation_failed",
  "deploy_failed",
]

export function useSubmissionPolling(
  submissionId: number | null,
  options: UseSubmissionPollingOptions = {}
): UseSubmissionPollingReturn {
  const {
    onSubmissionUpdate,
    onTestsUpdate,
    enabled = true,
    intervalMs = 5000,
    stopOnComplete = true,
  } = options

  const [submission, setSubmission] = useState<SubmissionDetail | null>(null)
  const [testSummary, setTestSummary] = useState<TestSummary | null>(null)
  const [isPolling, setIsPolling] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null)
  const isFetchingRef = useRef(false)

  const fetchData = useCallback(async () => {
    if (!submissionId || isFetchingRef.current) return

    isFetchingRef.current = true

    try {
      // Fetch submission
      const sub = await submissionsApi.get(submissionId)
      setSubmission(sub)
      onSubmissionUpdate?.(sub)

      // Fetch test results if testing or completed
      if (["testing", "completed"].includes(sub.status)) {
        try {
          const tests = await testsApi.getTestSummary(submissionId)
          setTestSummary(tests)
          onTestsUpdate?.(tests)
        } catch {
          // Tests may not be ready yet
        }
      }

      setError(null)

      // Check if we should stop polling
      if (stopOnComplete && TERMINAL_STATUSES.includes(sub.status)) {
        setIsPolling(false)
        if (intervalRef.current) {
          clearInterval(intervalRef.current)
          intervalRef.current = null
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Failed to fetch submission"))
    } finally {
      isFetchingRef.current = false
    }
  }, [submissionId, onSubmissionUpdate, onTestsUpdate, stopOnComplete])

  // Start/stop polling
  useEffect(() => {
    if (!submissionId || !enabled) {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
      setIsPolling(false)
      return
    }

    // Initial fetch
    fetchData()

    // Set up polling interval
    setIsPolling(true)
    intervalRef.current = setInterval(fetchData, intervalMs)

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
        intervalRef.current = null
      }
    }
  }, [submissionId, enabled, intervalMs, fetchData])

  const refresh = useCallback(async () => {
    await fetchData()
  }, [fetchData])

  return {
    submission,
    testSummary,
    isPolling,
    error,
    refresh,
  }
}
