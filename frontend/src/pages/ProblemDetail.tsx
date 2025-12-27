/**
 * Problem detail page
 * Shows full problem description and allows starting a submission
 *
 * Supports selecting difficulty level:
 * - Easy (L5): Senior Software Engineer
 * - Medium (L6): Staff Engineer
 * - Hard (L7): Principal Engineer
 */

import { useState, useEffect } from "react"
import { useParams, Link } from "react-router-dom"
import { ArrowLeft, ArrowRight, AlertCircle, Lightbulb, Code, GraduationCap, CheckCircle } from "lucide-react"
import { problemsApi, chatApi, DifficultyLevel } from "@/api/client"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { cn } from "@/lib/utils"
import type { Problem, DifficultyLevelInfo } from "@/types"

// Difficulty level variants for badge styling
const difficultyVariant: Record<string, "success" | "warning" | "destructive"> = {
  easy: "success",
  medium: "warning",
  hard: "destructive",
}

// Engineering level details for each difficulty
const difficultyLevels: Record<DifficultyLevel, DifficultyLevelInfo> = {
  easy: {
    level: "L5",
    title: "Senior Software Engineer",
    description: "Focus on core functionality with basic scalability",
  },
  medium: {
    level: "L6",
    title: "Staff Engineer",
    description: "Production-ready design with high availability",
  },
  hard: {
    level: "L7",
    title: "Principal Engineer",
    description: "Global-scale architecture with advanced optimizations",
  },
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
  const [selectedDifficulty, setSelectedDifficulty] = useState<DifficultyLevel>("medium")
  const [levelRequirements, setLevelRequirements] = useState<string | null>(null)
  const [loadingRequirements, setLoadingRequirements] = useState(false)

  useEffect(() => {
    const loadProblem = async () => {
      if (!id) return
      try {
        const data = await problemsApi.get(parseInt(id))
        setProblem(data)
        // Set default difficulty based on problem
        setSelectedDifficulty(data.difficulty)
      } catch (err) {
        setError("Failed to load problem")
        console.error(err)
      } finally {
        setLoading(false)
      }
    }
    loadProblem()
  }, [id])

  // Load level-specific requirements when difficulty changes
  useEffect(() => {
    const loadRequirements = async () => {
      if (!id) return
      setLoadingRequirements(true)
      try {
        const data = await chatApi.getLevelRequirements(parseInt(id), selectedDifficulty)
        setLevelRequirements(data.requirements)
      } catch (err) {
        console.error("Failed to load requirements:", err)
        setLevelRequirements(null)
      } finally {
        setLoadingRequirements(false)
      }
    }
    loadRequirements()
  }, [id, selectedDifficulty])

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

      {/* Difficulty Level Selector */}
      <Card className="border-primary/30">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <GraduationCap className="h-5 w-5 text-primary" />
            Select Your Level
          </CardTitle>
          <CardDescription>
            Choose the difficulty level that matches your target role
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            {(Object.keys(difficultyLevels) as DifficultyLevel[]).map((level) => {
              const info = difficultyLevels[level]
              const isSelected = selectedDifficulty === level
              return (
                <button
                  key={level}
                  onClick={() => setSelectedDifficulty(level)}
                  className={cn(
                    "relative p-4 rounded-lg border-2 text-left transition-all",
                    isSelected
                      ? "border-primary bg-primary/5"
                      : "border-border hover:border-primary/50"
                  )}
                >
                  {isSelected && (
                    <CheckCircle className="absolute top-2 right-2 h-5 w-5 text-primary" />
                  )}
                  <div className="flex items-center gap-2 mb-2">
                    <Badge variant={difficultyVariant[level]}>{info.level}</Badge>
                    <span className="font-medium capitalize">{level}</span>
                  </div>
                  <p className="text-sm font-medium">{info.title}</p>
                  <p className="text-xs text-muted-foreground mt-1">{info.description}</p>
                </button>
              )
            })}
          </div>

          {/* Level Requirements Preview */}
          {levelRequirements && (
            <div className="mt-6 p-4 bg-muted rounded-lg">
              <h4 className="font-medium mb-2 flex items-center gap-2">
                <Lightbulb className="h-4 w-4 text-yellow-500" />
                {difficultyLevels[selectedDifficulty].level} Requirements Preview
              </h4>
              {loadingRequirements ? (
                <Skeleton className="h-20 w-full" />
              ) : (
                <div className="text-sm text-muted-foreground prose prose-sm dark:prose-invert max-w-none">
                  <div className="whitespace-pre-wrap line-clamp-6">{levelRequirements}</div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Hints */}
      {problem.hints && problem.hints.length > 0 && (
        <Card className="border-amber-500/30 bg-amber-500/5">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <Lightbulb className="h-5 w-5 text-amber-500" />
              Hints
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2">
              {problem.hints.map((hint, i) => (
                <li key={i} className="text-sm text-muted-foreground flex items-start gap-2">
                  <span className="text-amber-500 font-medium">{i + 1}.</span>
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
          <Link to={`/problems/${problem.id}/submit?difficulty=${selectedDifficulty}`}>
            Start Design as {difficultyLevels[selectedDifficulty].level}
            <ArrowRight className="ml-2 h-4 w-4" />
          </Link>
        </Button>
      </div>
    </div>
  )
}
