/**
 * Test result display card
 * Shows individual test results with status, details, and error analysis
 */

import { useState } from "react"
import {
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  Loader2,
  MinusCircle,
  ChevronDown,
  ChevronUp,
  Timer,
  Wrench,
  FileText,
} from "lucide-react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ErrorAnalysisCard } from "@/components/ErrorAnalysisCard"
import { cn } from "@/lib/utils"
import type { TestResult, TestStatus } from "@/types"

/**
 * Generate a human-readable summary of test failure
 */
function generateFailureSummary(result: TestResult): string {
  const details = result.details as Record<string, unknown> | null

  // Extract common error patterns
  if (details?.error) {
    return String(details.error)
  }
  if (details?.message) {
    return String(details.message)
  }
  if (details?.reason) {
    return String(details.reason)
  }

  // Test type specific summaries
  if (result.test_type === "functional") {
    if (details?.expected && details?.actual) {
      return `Expected ${JSON.stringify(details.expected)}, but got ${JSON.stringify(details.actual)}`
    }
    if (details?.status_code) {
      return `API returned status ${details.status_code} instead of expected success`
    }
    return "The functional test did not produce the expected result"
  }

  if (result.test_type === "performance") {
    if (details?.latency_ms && details?.threshold_ms) {
      return `Response time of ${details.latency_ms}ms exceeded threshold of ${details.threshold_ms}ms`
    }
    if (details?.requests_per_second && details?.target_rps) {
      return `Achieved ${details.requests_per_second} RPS, below target of ${details.target_rps} RPS`
    }
    return "Performance did not meet the required thresholds"
  }

  if (result.test_type === "chaos") {
    if (result.chaos_scenario) {
      return `System failed to recover properly after ${result.chaos_scenario} scenario`
    }
    return "System did not handle the chaos scenario gracefully"
  }

  return "Test failed - see details below for more information"
}

/**
 * Generate actionable items based on test failure
 */
function generateActionableItems(result: TestResult): string[] {
  const items: string[] = []
  const details = result.details as Record<string, unknown> | null

  // Test type specific actions
  if (result.test_type === "functional") {
    if (details?.status_code === 404) {
      items.push("Verify your API endpoint paths match the expected routes")
      items.push("Check that your URL shortening service is correctly deployed")
    } else if (details?.status_code === 500) {
      items.push("Check your application logs for error messages")
      items.push("Verify database connections and configurations")
    } else if (details?.status_code === 401 || details?.status_code === 403) {
      items.push("Check authentication configuration")
      items.push("Verify API keys and permissions are correctly set")
    } else {
      items.push("Review your API implementation against the specification")
      items.push("Ensure your endpoints return the correct response format")
    }
  }

  if (result.test_type === "performance") {
    items.push("Consider adding caching to reduce response times")
    items.push("Review database query performance and add indexes if needed")
    items.push("Check if connection pooling is configured properly")
    items.push("Consider scaling your infrastructure horizontally")
  }

  if (result.test_type === "chaos") {
    items.push("Implement proper health checks and circuit breakers")
    items.push("Add retry logic with exponential backoff")
    items.push("Ensure graceful degradation for downstream failures")
    items.push("Review your error handling and recovery procedures")
  }

  // Add general items if empty
  if (items.length === 0) {
    items.push("Review the test details below for specific error information")
    items.push("Check your implementation against the problem requirements")
  }

  return items
}

interface TestResultCardProps {
  result: TestResult
  showAnalysis?: boolean
}

const statusConfig: Record<
  TestStatus,
  {
    icon: React.ElementType
    label: string
    variant: "success" | "destructive" | "warning" | "secondary" | "default"
    iconClass: string
  }
> = {
  pending: {
    icon: Clock,
    label: "Pending",
    variant: "secondary",
    iconClass: "text-muted-foreground",
  },
  running: {
    icon: Loader2,
    label: "Running",
    variant: "default",
    iconClass: "text-primary animate-spin",
  },
  passed: {
    icon: CheckCircle,
    label: "Passed",
    variant: "success",
    iconClass: "text-success",
  },
  failed: {
    icon: XCircle,
    label: "Failed",
    variant: "destructive",
    iconClass: "text-destructive",
  },
  error: {
    icon: AlertCircle,
    label: "Error",
    variant: "warning",
    iconClass: "text-warning",
  },
  skipped: {
    icon: MinusCircle,
    label: "Skipped",
    variant: "secondary",
    iconClass: "text-muted-foreground",
  },
}

export default function TestResultCard({
  result,
  showAnalysis = true,
}: TestResultCardProps) {
  const [isExpanded, setIsExpanded] = useState(false)
  const config = statusConfig[result.status] || statusConfig.pending
  const StatusIcon = config.icon

  const hasError = result.status === "failed" || result.status === "error"
  const hasAnalysis = hasError && result.error_analysis && showAnalysis

  // Generate summary and actionable items for failed tests
  const failureSummary = hasError ? generateFailureSummary(result) : null
  const actionableItems = hasError && !hasAnalysis ? generateActionableItems(result) : []

  return (
    <Card
      className={cn(
        "transition-all hover:shadow-md",
        hasError && "border-destructive/50"
      )}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <StatusIcon className={cn("h-5 w-5", config.iconClass)} />
            <div>
              <h4 className="font-medium">{result.test_name}</h4>
              {result.chaos_scenario && (
                <p className="text-xs text-muted-foreground">
                  Scenario: {result.chaos_scenario}
                </p>
              )}
            </div>
          </div>
          <div className="flex items-center gap-2">
            {result.duration_ms !== null && (
              <div className="flex items-center gap-1 text-xs text-muted-foreground">
                <Timer className="h-3 w-3" />
                {result.duration_ms}ms
              </div>
            )}
            <Badge variant={config.variant}>{config.label}</Badge>
          </div>
        </div>
      </CardHeader>

      {/* Failure Summary - show human-readable summary for failed tests without AI analysis */}
      {hasError && failureSummary && !hasAnalysis && (
        <CardContent className="pt-2 pb-2">
          <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 space-y-3">
            {/* Summary */}
            <div className="flex gap-2">
              <FileText className="h-4 w-4 mt-0.5 text-destructive flex-shrink-0" />
              <div>
                <p className="text-sm font-medium text-destructive">What went wrong</p>
                <p className="text-sm mt-1">{failureSummary}</p>
              </div>
            </div>

            {/* Actionable Items */}
            {actionableItems.length > 0 && (
              <div className="space-y-2 pt-2 border-t border-destructive/20">
                <div className="flex items-center gap-2 text-sm font-medium">
                  <Wrench className="h-4 w-4 text-amber-500" />
                  How to fix it
                </div>
                <ul className="space-y-1.5 ml-6">
                  {actionableItems.map((item, index) => (
                    <li
                      key={index}
                      className="text-sm text-muted-foreground flex items-start gap-2"
                    >
                      <span className="text-amber-500 mt-1">•</span>
                      <span>{item}</span>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </CardContent>
      )}

      {/* Error Analysis - show prominently for failed tests with AI analysis */}
      {hasAnalysis && (
        <CardContent className="pt-2 pb-2">
          <ErrorAnalysisCard
            analysis={result.error_analysis!}
            className="border-0 shadow-none"
          />
        </CardContent>
      )}

      {/* Details section */}
      {result.details && (
        <CardContent className={cn((hasAnalysis || (hasError && failureSummary)) ? "pt-0" : "pt-2")}>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="w-full justify-between text-muted-foreground hover:text-foreground"
          >
            <span className="text-sm">
              {isExpanded ? "Hide" : "View"} Technical Details
            </span>
            {isExpanded ? (
              <ChevronUp className="h-4 w-4" />
            ) : (
              <ChevronDown className="h-4 w-4" />
            )}
          </Button>

          {isExpanded && (
            <pre className="mt-2 p-3 bg-muted rounded-md text-xs overflow-x-auto max-h-64 overflow-y-auto">
              {JSON.stringify(result.details, null, 2)}
            </pre>
          )}
        </CardContent>
      )}
    </Card>
  )
}
