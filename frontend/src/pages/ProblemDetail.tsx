/**
 * Problem detail page
 * Shows full problem description and allows starting a submission
 */

import { useState, useEffect } from "react"
import { useParams, Link } from "react-router-dom"
import { ArrowLeft, ArrowRight, AlertCircle, Lightbulb, Code } from "lucide-react"
import { problemsApi } from "@/api/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import type { Problem } from "@/types"

const difficultyVariant: Record<string, "success" | "warning" | "destructive"> = {
  easy: "success",
  medium: "warning",
  hard: "destructive",
}

function ProblemDetailSkeleton() {
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <Skeleton className="h-6 w-32" />
      <div className="flex items-center justify-between">
        <Skeleton className="h-10 w-64" />
        <Skeleton className="h-6 w-20" />
      </div>
      <div className="flex gap-2">
        <Skeleton className="h-5 w-16" />
        <Skeleton className="h-5 w-20" />
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-40" />
        </CardHeader>
        <CardContent className="space-y-2">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-3/4" />
        </CardContent>
      </Card>
    </div>
  )
}

export default function ProblemDetail() {
  const { id } = useParams<{ id: string }>()
  const [problem, setProblem] = useState<Problem | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    const loadProblem = async () => {
      if (!id) return
      try {
        const data = await problemsApi.get(parseInt(id))
        setProblem(data)
      } catch (err) {
        setError("Failed to load problem")
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    loadProblem()
  }, [id])

  if (loading) {
    return <ProblemDetailSkeleton />
  }

  if (error || !problem) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="h-12 w-12 text-destructive mb-4" />
        <p className="text-destructive font-medium mb-4">{error || "Problem not found"}</p>
        <Button asChild variant="outline">
          <Link to="/problems">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to problems
          </Link>
        </Button>
      </div>
    )
  }

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <Button asChild variant="ghost" size="sm" className="mb-2">
          <Link to="/problems">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to problems
          </Link>
        </Button>
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold">{problem.title}</h1>
          <Badge variant={difficultyVariant[problem.difficulty]} className="text-sm">
            {problem.difficulty}
          </Badge>
        </div>
        {problem.tags && problem.tags.length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2">
            {problem.tags.map((tag) => (
              <Badge key={tag} variant="secondary">
                {tag}
              </Badge>
            ))}
          </div>
        )}
      </div>

      {/* Description */}
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Problem Description</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="prose prose-sm dark:prose-invert max-w-none">
            <p className="whitespace-pre-wrap text-muted-foreground">{problem.description}</p>
          </div>
        </CardContent>
      </Card>

      {/* Hints */}
      {problem.hints && problem.hints.length > 0 && (
        <Card className="border-primary/30 bg-primary/5">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Lightbulb className="h-5 w-5 text-primary" />
              Hints
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {problem.hints.map((hint, i) => (
                <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                  <span className="text-primary font-medium">{i + 1}.</span>
                  {hint}
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Expected API Spec */}
      {problem.expected_api_spec && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Code className="h-5 w-5" />
              Expected API Endpoints
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-muted-foreground mb-4">
              Your solution should include the following endpoints (at minimum):
            </p>
            <pre className="p-4 bg-muted rounded-lg text-sm overflow-x-auto">
              {JSON.stringify(problem.expected_api_spec, null, 2)}
            </pre>
          </CardContent>
        </Card>
      )}

      {/* Start button */}
      <div className="flex justify-end">
        <Button asChild size="lg">
          <Link to={`/problems/${problem.id}/submit`}>
            Start Design
            <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </div>
    </div>
  )
}
