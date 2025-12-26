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
} from "lucide-react"
import { Card, CardContent, CardHeader } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { ErrorAnalysisCard } from "@/components/ErrorAnalysisCard"
import { cn } from "@/lib/utils"
import type { TestResult, TestStatus } from "@/types"

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

      {/* Error Analysis - show prominently for failed tests */}
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
        <CardContent className={cn(hasAnalysis ? "pt-0" : "pt-2")}>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsExpanded(!isExpanded)}
            className="w-full justify-between text-muted-foreground hover:text-foreground"
          >
            <span className="text-sm">
              {isExpanded ? "Hide" : "View"} Raw Details
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
