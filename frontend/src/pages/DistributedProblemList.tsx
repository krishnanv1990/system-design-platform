/**
 * Distributed Consensus Problem List
 *
 * Shows all available distributed consensus problems like Raft and Paxos
 * that users can implement in their choice of programming language.
 */

import { useState, useEffect } from "react"
import { Link } from "react-router-dom"
import { Search, AlertCircle, RefreshCw, Server, Code, History } from "lucide-react"
import { distributedProblemsApi } from "@/api/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"
import type { DistributedProblemListItem, SupportedLanguage } from "@/types"

// Difficulty variants for badge styling
const difficultyVariant: Record<string, "success" | "warning" | "destructive"> = {
  easy: "success",
  medium: "warning",
  hard: "destructive",
}

// Language display names
const languageLabels: Record<SupportedLanguage, string> = {
  python: "Python",
  go: "Go",
  java: "Java",
  cpp: "C++",
  rust: "Rust",
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

export default function DistributedProblemList() {
  const [problems, setProblems] = useState<DistributedProblemListItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [filter, setFilter] = useState<string>("")

  const loadProblems = async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await distributedProblemsApi.list()
      setProblems(data)
    } catch (err: any) {
      console.error("Failed to load distributed problems:", err)
      const message = err.response?.data?.detail || err.message || "Failed to load problems"
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadProblems()
  }, [])

  const filteredProblems = problems.filter(
    (p) =>
      p.title.toLowerCase().includes(filter.toLowerCase()) ||
      p.description.toLowerCase().includes(filter.toLowerCase())
  )

  return (
    <div>
      <div className="mb-6 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Server className="h-6 w-6 text-primary" />
            Distributed Consensus Problems
          </h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Implement distributed consensus algorithms like Raft and Paxos in your preferred language
          </p>
        </div>
        <Link to="/distributed/history">
          <Button variant="outline" size="sm">
            <History className="mr-2 h-4 w-4" />
            View Submissions
          </Button>
        </Link>
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
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-12">
          <AlertCircle className="h-12 w-12 text-destructive mb-4" />
          <p className="text-destructive font-medium mb-2">Failed to load problems</p>
          <p className="text-muted-foreground text-sm mb-4">{error}</p>
          <Button onClick={loadProblems} variant="outline">
            <RefreshCw className="mr-2 h-4 w-4" />
            Try Again
          </Button>
        </div>
      ) : filteredProblems.length === 0 ? (
        <div className="text-center py-12">
          <Server className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
          <p className="text-muted-foreground">
            {problems.length === 0
              ? "No distributed consensus problems available yet."
              : "No problems match your search."}
          </p>
        </div>
      ) : (
        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {filteredProblems.map((problem) => (
            <Link key={problem.id} to={`/distributed/${problem.id}`}>
              <Card className="h-full transition-all hover:border-primary/50 hover:shadow-md">
                <CardHeader className="pb-2">
                  <div className="flex items-center justify-between">
                    <CardTitle className="text-lg">{problem.title}</CardTitle>
                    <Badge variant={difficultyVariant[problem.difficulty]}>
                      {problem.difficulty}
                    </Badge>
                  </div>
                </CardHeader>
                <CardContent>
                  <p className="text-sm text-muted-foreground line-clamp-2 mb-3">
                    {problem.description}
                  </p>

                  {/* Cluster size */}
                  <div className="flex items-center gap-2 text-sm text-muted-foreground mb-3">
                    <Server className="h-4 w-4" />
                    <span>{problem.cluster_size} node cluster</span>
                  </div>

                  {/* Supported languages */}
                  <div className="flex items-center gap-2 mb-3">
                    <Code className="h-4 w-4 text-muted-foreground" />
                    <div className="flex flex-wrap gap-1">
                      {problem.supported_languages.map((lang) => (
                        <Badge key={lang} variant="outline" className="text-xs">
                          {languageLabels[lang]}
                        </Badge>
                      ))}
                    </div>
                  </div>

                  {/* Tags */}
                  {problem.tags && problem.tags.length > 0 && (
                    <div className="flex flex-wrap gap-1">
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
