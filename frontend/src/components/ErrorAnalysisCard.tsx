import {
  AlertCircle,
  AlertTriangle,
  Server,
  Code,
  HelpCircle,
  Lightbulb,
  ChevronDown,
  ChevronUp,
} from "lucide-react"
import { useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import type { ErrorAnalysis, ErrorCategory } from "@/types"

interface ErrorAnalysisCardProps {
  analysis: ErrorAnalysis
  className?: string
}

const categoryConfig: Record<
  ErrorCategory,
  {
    icon: React.ElementType
    label: string
    description: string
    variant: "user_solution" | "platform" | "deployment" | "secondary"
    bgClass: string
    borderClass: string
  }
> = {
  user_solution: {
    icon: Code,
    label: "Solution Issue",
    description: "This failure is related to your implementation",
    variant: "user_solution",
    bgClass: "bg-amber-50 dark:bg-amber-950/20",
    borderClass: "border-amber-200 dark:border-amber-800",
  },
  platform: {
    icon: Server,
    label: "Platform Issue",
    description: "This is a testing platform issue, not your fault",
    variant: "platform",
    bgClass: "bg-purple-50 dark:bg-purple-950/20",
    borderClass: "border-purple-200 dark:border-purple-800",
  },
  deployment: {
    icon: AlertTriangle,
    label: "Deployment Issue",
    description: "This is an infrastructure issue, not your fault",
    variant: "deployment",
    bgClass: "bg-blue-50 dark:bg-blue-950/20",
    borderClass: "border-blue-200 dark:border-blue-800",
  },
  unknown: {
    icon: HelpCircle,
    label: "Unknown",
    description: "Could not determine the root cause",
    variant: "secondary",
    bgClass: "bg-gray-50 dark:bg-gray-950/20",
    borderClass: "border-gray-200 dark:border-gray-800",
  },
}

export function ErrorAnalysisCard({
  analysis,
  className,
}: ErrorAnalysisCardProps) {
  const [isExpanded, setIsExpanded] = useState(true)
  const config = categoryConfig[analysis.category] || categoryConfig.unknown
  const Icon = config.icon

  const confidencePercent = Math.round(analysis.confidence * 100)
  const isHighConfidence = analysis.confidence >= 0.7

  return (
    <Card
      className={cn(
        "overflow-hidden transition-all",
        config.bgClass,
        config.borderClass,
        className
      )}
    >
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div
              className={cn(
                "rounded-full p-1.5",
                analysis.category === "user_solution" && "bg-amber-100 dark:bg-amber-900/50",
                analysis.category === "platform" && "bg-purple-100 dark:bg-purple-900/50",
                analysis.category === "deployment" && "bg-blue-100 dark:bg-blue-900/50",
                analysis.category === "unknown" && "bg-gray-100 dark:bg-gray-800"
              )}
            >
              <Icon className="h-4 w-4" />
            </div>
            <div>
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                Root Cause Analysis
                <Badge variant={config.variant} className="ml-1">
                  {config.label}
                </Badge>
              </CardTitle>
              <p className="text-xs text-muted-foreground mt-0.5">
                {config.description}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2">
            {analysis.demo_mode && (
              <Badge variant="outline" className="text-xs">
                Demo
              </Badge>
            )}
            <Badge
              variant={isHighConfidence ? "default" : "secondary"}
              className="text-xs"
            >
              {confidencePercent}% confidence
            </Badge>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIsExpanded(!isExpanded)}
              className="h-8 w-8 p-0"
            >
              {isExpanded ? (
                <ChevronUp className="h-4 w-4" />
              ) : (
                <ChevronDown className="h-4 w-4" />
              )}
            </Button>
          </div>
        </div>
      </CardHeader>

      {isExpanded && (
        <CardContent className="pt-2 space-y-4">
          {/* Explanation */}
          <div className="flex gap-2">
            <AlertCircle className="h-4 w-4 mt-0.5 text-muted-foreground flex-shrink-0" />
            <p className="text-sm">{analysis.explanation}</p>
          </div>

          {/* Suggestions */}
          {analysis.suggestions && analysis.suggestions.length > 0 && (
            <div className="space-y-2">
              <div className="flex items-center gap-2 text-sm font-medium">
                <Lightbulb className="h-4 w-4 text-yellow-500" />
                Suggestions
              </div>
              <ul className="space-y-1.5 ml-6">
                {analysis.suggestions.map((suggestion, index) => (
                  <li
                    key={index}
                    className="text-sm text-muted-foreground flex items-start gap-2"
                  >
                    <span className="text-primary mt-1">•</span>
                    <span>{suggestion}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Technical Details */}
          {analysis.technical_details && (
            <div className="rounded-md bg-muted/50 p-3 text-xs font-mono">
              <div className="grid grid-cols-2 gap-2">
                {analysis.technical_details.error_type && (
                  <div>
                    <span className="text-muted-foreground">Error Type:</span>{" "}
                    <span className="font-medium">
                      {analysis.technical_details.error_type}
                    </span>
                  </div>
                )}
                {analysis.technical_details.affected_component && (
                  <div>
                    <span className="text-muted-foreground">Component:</span>{" "}
                    <span className="font-medium">
                      {analysis.technical_details.affected_component}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
        </CardContent>
      )}
    </Card>
  )
}

export default ErrorAnalysisCard
