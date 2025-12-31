/**
 * Distributed Submission History Page
 *
 * Shows all past distributed consensus submissions for the current user.
 */

import { useState, useEffect } from "react"
import { Link, useSearchParams } from "react-router-dom"
import {
  AlertCircle,
  RefreshCw,
  Server,
  Clock,
  CheckCircle,
  XCircle,
  Loader2,
  History,
  Code,
} from "lucide-react"
import { distributedSubmissionsApi, distributedProblemsApi } from "@/api/client"
import { Card, CardContent } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Skeleton } from "@/components/ui/skeleton"
import { Button } from "@/components/ui/button"
import type { DistributedSubmission, DistributedProblemListItem, SupportedLanguage } from "@/types"

// Status colors
const statusVariant: Record<string, "default" | "secondary" | "destructive" | "success" | "warning"> = {
  pending: "secondary",
  building: "default",
  build_failed: "destructive",
  deploying: "default",
  deploy_failed: "destructive",
  testing: "warning",
  completed: "success",
  failed: "destructive",
}

const statusLabels: Record<string, string> = {
  pending: "Pending",
  building: "Building",
  build_failed: "Build Failed",
  deploying: "Deploying",
  deploy_failed: "Deploy Failed",
  testing: "Testing",
  completed: "Completed",
  failed: "Failed",
}

// Language display info
const languageInfo: Record<SupportedLanguage, { label: string; icon: string }> = {
  python: { label: "Python", icon: "Python" },
  go: { label: "Go", icon: "Go" },
  java: { label: "Java", icon: "Java" },
  cpp: { label: "C++", icon: "C++" },
  rust: { label: "Rust", icon: "Rust" },
}

function HistorySkeleton() {
  return (
    <div className="space-y-4">
      {[1, 2, 3, 4, 5].map((i) => (
        <Skeleton key={i} className="h-24" />
      ))}
    </div>
  )
}

function formatDate(dateString: string): string {
  const date = new Date(dateString)
  return date.toLocaleDateString("en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  })
}

export default function DistributedSubmissionHistory() {
  const [searchParams] = useSearchParams()
  const problemIdFilter = searchParams.get("problem_id")

  const [submissions, setSubmissions] = useState<DistributedSubmission[]>([])
  const [problems, setProblems] = useState<Record<number, DistributedProblemListItem>>({})
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const loadData = async () => {
    setLoading(true)
    setError(null)
    try {
      // Load submissions
      const submissionData = await distributedSubmissionsApi.list(
        problemIdFilter ? parseInt(problemIdFilter) : undefined
      )
      setSubmissions(submissionData)

      // Load problem info for each unique problem_id
      const problemIds = [...new Set(submissionData.map((s) => s.problem_id))]
      const problemData = await distributedProblemsApi.list()
      const problemMap: Record<number, DistributedProblemListItem> = {}
      for (const problem of problemData) {
        if (problemIds.includes(problem.id)) {
          problemMap[problem.id] = problem
        }
      }
      setProblems(problemMap)
    } catch (err: any) {
      console.error("Failed to load submission history:", err)
      const message = err.response?.data?.detail || err.message || "Failed to load submissions"
      setError(message)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [problemIdFilter])

  const getStatusIcon = (status: string) => {
    if (["pending", "building", "deploying", "testing"].includes(status)) {
      return <Loader2 className="h-5 w-5 animate-spin text-primary" />
    }
    if (status === "completed") {
      return <CheckCircle className="h-5 w-5 text-green-600" />
    }
    return <XCircle className="h-5 w-5 text-destructive" />
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold flex items-center gap-2">
          <History className="h-6 w-6 text-primary" />
          Submission History
        </h1>
        <p className="mt-1 text-sm text-muted-foreground">
          {problemIdFilter
            ? `Showing submissions for problem #${problemIdFilter}`
            : "View all your past distributed consensus submissions"}
        </p>
      </div>

      {/* Actions */}
      <div className="mb-6 flex gap-2">
        {problemIdFilter && (
          <Link to="/distributed/history">
            <Button variant="outline" size="sm">
              Show All Submissions
            </Button>
          </Link>
        )}
        <Button onClick={loadData} variant="outline" size="sm" disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Submission list */}
      {loading ? (
        <HistorySkeleton />
      ) : error ? (
        <div className="flex flex-col items-center justify-center py-12">
          <AlertCircle className="h-12 w-12 text-destructive mb-4" />
          <p className="text-destructive font-medium mb-2">Failed to load submissions</p>
          <p className="text-muted-foreground text-sm mb-4">{error}</p>
          <Button onClick={loadData} variant="outline">
            <RefreshCw className="mr-2 h-4 w-4" />
            Try Again
          </Button>
        </div>
      ) : submissions.length === 0 ? (
        <div className="text-center py-12">
          <Server className="h-16 w-16 text-muted-foreground mx-auto mb-4" />
          <p className="text-muted-foreground mb-4">
            {problemIdFilter
              ? "No submissions found for this problem."
              : "You haven't submitted any distributed consensus solutions yet."}
          </p>
          <Link to="/distributed">
            <Button variant="outline">
              <Code className="mr-2 h-4 w-4" />
              Browse Problems
            </Button>
          </Link>
        </div>
      ) : (
        <div className="space-y-4">
          {submissions.map((submission) => {
            const problem = problems[submission.problem_id]
            return (
              <Link
                key={submission.id}
                to={`/distributed/submissions/${submission.id}`}
              >
                <Card className="transition-all hover:border-primary/50 hover:shadow-md">
                  <CardContent className="p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-4">
                        {getStatusIcon(submission.status)}
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium">
                              Submission #{submission.id}
                            </span>
                            <Badge variant={statusVariant[submission.status] || "secondary"}>
                              {statusLabels[submission.status] || submission.status}
                            </Badge>
                            <Badge variant="outline">
                              {languageInfo[submission.language].label}
                            </Badge>
                          </div>
                          <div className="flex items-center gap-2 mt-1 text-sm text-muted-foreground">
                            {problem && (
                              <>
                                <Server className="h-4 w-4" />
                                <span>{problem.title}</span>
                                <span>·</span>
                              </>
                            )}
                            <Clock className="h-4 w-4" />
                            <span>{formatDate(submission.created_at)}</span>
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        {submission.cluster_node_urls && submission.cluster_node_urls.length > 0 && (
                          <Badge variant="success" className="text-xs">
                            {submission.cluster_node_urls.length} nodes active
                          </Badge>
                        )}
                      </div>
                    </div>
                  </CardContent>
                </Card>
              </Link>
            )
          })}
        </div>
      )}
    </div>
  )
}
