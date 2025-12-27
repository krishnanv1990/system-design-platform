/**
 * Problem list page
 * Shows all available system design problems
 *
 * Displays difficulty levels mapped to engineering levels:
 * - Easy (L5): Senior Software Engineer
 * - Medium (L6): Staff Engineer
 * - Hard (L7): Principal Engineer
 */

import { useState, useEffect } from "react"
import { Link } from "react-router-dom"
import { Search } from "lucide-react"
import { problemsApi } from "@/api/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import type { ProblemListItem } from "@/types"

// Difficulty level variants for badge styling
const difficultyVariant: Record<string, "success" | "warning" | "destructive"> = {
  easy: "success",
  medium: "warning",
  hard: "destructive",
}

// Engineering level labels for each difficulty
const levelLabels: Record<string, string> = {
  easy: "L5",
  medium: "L6",
  hard: "L7",
}

function ProblemListSkeleton() {
  return (
    <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <Card key={i}>
          <CardHeader className="space-y-2">
            <div className="flex items-center justify-between">
              <Skeleton className="h-6 w-3/4" />
              <Skeleton className="h-5 w-16" />
            </div>
          </CardHeader>
          <CardContent>
            <Skeleton className="h-4 w-full mb-2" />
            <Skeleton className="h-4 w-2/3" />
            <div className="mt-4 flex gap-2">
              <Skeleton className="h-5 w-16" />
              <Skeleton className="h-5 w-20" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  )
}

export default function ProblemList() {
  const [problems, setProblems] = useState<ProblemListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [filter, setFilter] = useState<string>("")

  useEffect(() => {
    const loadProblems = async () => {
      try {
        const data = await problemsApi.list()
        setProblems(data)
      } catch (error) {
        console.error("Failed to load problems:", error)
      } finally {
        setLoading(false)
      }
    }
    loadProblems()
  }, [])

  const filteredProblems = problems.filter(
    (p) =>
      p.title.toLowerCase().includes(filter.toLowerCase()) ||
      p.description.toLowerCase().includes(filter.toLowerCase())
  )

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold">System Design Problems</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Choose a problem to practice your system design skills
        </p>
      </div>

      {/* Search */}
      <div className="mb-6">
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            placeholder="Search problems..."
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            className="w-full pl-10 pr-4 py-2 border rounded-lg bg-background focus:outline-none focus:ring-2 focus:ring-primary"
          />
        </div>
      </div>

      {/* Problem list */}
      {loading ? (
        <ProblemListSkeleton />
      ) : filteredProblems.length === 0 ? (
        <div className="text-center py-12">
          <p className="text-muted-foreground">
            {problems.length === 0
              ? "No problems available yet."
              : "No problems match your search."}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredProblems.map((problem) => (
            <Link key={problem.id} to={`/problems/${problem.id}`}>
              <Card className="h-full transition-all hover:border-primary/50 hover:shadow-md">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{problem.title}</CardTitle>
                    <Badge
                      variant={difficultyVariant[problem.difficulty]}
                      title={problem.difficulty_info?.title || ""}
                    >
                      {levelLabels[problem.difficulty] || problem.difficulty} - {problem.difficulty}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground line-clamp-2">
                    {problem.description}
                  </p>
                  {problem.tags && problem.tags.length > 0 && (
                    <div className="mt-3 flex flex-wrap gap-1">
                      {problem.tags.map((tag) => (
                        <Badge key={tag} variant="secondary" className="text-xs">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>
      )}
    </div>
  )
}
