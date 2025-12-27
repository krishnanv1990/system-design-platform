/**
 * Design Summary Component
 *
 * Displays the final design summary after completing a chat session.
 * Shows key components, strengths, areas for improvement, and overall score.
 */

import { CheckCircle, XCircle, Lightbulb, Award, GraduationCap } from "lucide-react"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Progress } from "@/components/ui/progress"
import type { DesignSummaryResponse } from "@/api/client"

interface DesignSummaryProps {
  summary: DesignSummaryResponse
  diagramData?: string
}

// Difficulty level variants for badge styling
const difficultyVariant: Record<string, "success" | "warning" | "destructive"> = {
  easy: "success",
  medium: "warning",
  hard: "destructive",
}

export default function DesignSummary({ summary, diagramData }: DesignSummaryProps) {
  const scoreColor = summary.overall_score
    ? summary.overall_score >= 80
      ? "text-green-600"
      : summary.overall_score >= 60
        ? "text-yellow-600"
        : "text-red-600"
    : "text-muted-foreground"

  return (
    <div className="space-y-6">
      {/* Header with Level Info */}
      <Card className="border-primary/30 bg-primary/5">
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle className="text-xl flex items-center gap-2">
                <GraduationCap className="h-6 w-6 text-primary" />
                Design Summary
              </CardTitle>
              <CardDescription className="mt-1">
                Your completed system design at {summary.level_info.level} level
              </CardDescription>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={difficultyVariant[summary.difficulty_level]}>
                {summary.level_info.level}
              </Badge>
              <span className="text-sm text-muted-foreground">
                {summary.level_info.title}
              </span>
            </div>
          </div>
        </CardHeader>
      </Card>

      {/* Overall Score */}
      {summary.overall_score !== null && (
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-lg flex items-center gap-2">
              <Award className="h-5 w-5 text-primary" />
              Overall Score
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <div className={`text-4xl font-bold ${scoreColor}`}>
                {summary.overall_score}
                <span className="text-lg text-muted-foreground">/100</span>
              </div>
              <Progress value={summary.overall_score} className="flex-1" />
            </div>
          </CardContent>
        </Card>
      )}

      {/* Summary Text */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Design Overview</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <div
              className="whitespace-pre-wrap"
              dangerouslySetInnerHTML={{
                __html: summary.summary.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                  .replace(/\n/g, '<br />')
              }}
            />
          </div>
        </CardContent>
      </Card>

      {/* Key Components */}
      {summary.key_components.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              Key Components
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex flex-wrap gap-2">
              {summary.key_components.map((component, index) => (
                <Badge key={index} variant="secondary" className="text-sm py-1">
                  {component}
                </Badge>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Strengths and Areas for Improvement */}
      <div className="grid md:grid-cols-2 gap-6">
        {/* Strengths */}
        {summary.strengths.length > 0 && (
          <Card className="border-green-500/30 bg-green-500/5">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg flex items-center gap-2 text-green-700 dark:text-green-400">
                <CheckCircle className="h-5 w-5" />
                Strengths
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {summary.strengths.map((strength, index) => (
                  <li key={index} className="text-sm flex items-start gap-2">
                    <CheckCircle className="h-4 w-4 text-green-500 mt-0.5 shrink-0" />
                    <span>{strength}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}

        {/* Areas for Improvement */}
        {summary.areas_for_improvement.length > 0 && (
          <Card className="border-amber-500/30 bg-amber-500/5">
            <CardHeader className="pb-2">
              <CardTitle className="text-lg flex items-center gap-2 text-amber-700 dark:text-amber-400">
                <Lightbulb className="h-5 w-5" />
                Areas for Improvement
              </CardTitle>
            </CardHeader>
            <CardContent>
              <ul className="space-y-2">
                {summary.areas_for_improvement.map((area, index) => (
                  <li key={index} className="text-sm flex items-start gap-2">
                    <XCircle className="h-4 w-4 text-amber-500 mt-0.5 shrink-0" />
                    <span>{area}</span>
                  </li>
                ))}
              </ul>
            </CardContent>
          </Card>
        )}
      </div>

      {/* Diagram Preview (if available) */}
      {diagramData && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Your Diagram</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="border rounded-lg p-4 bg-muted/30">
              <p className="text-sm text-muted-foreground text-center">
                [Diagram preview would be rendered here]
              </p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Demo Mode Notice */}
      {summary.demo_mode && (
        <Card className="border-blue-500/30 bg-blue-500/5">
          <CardContent className="py-3">
            <p className="text-sm text-blue-700 dark:text-blue-300 text-center">
              This is a demo summary. In production, Claude would provide a detailed analysis of your specific design.
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
