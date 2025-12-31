/**
 * Distributed Submission Results Page
 *
 * Shows build logs, cluster status, and test results for a distributed submission.
 */

import { useState, useEffect, useCallback } from "react"
import { useParams, useNavigate } from "react-router-dom"
import {
  ArrowLeft,
  AlertCircle,
  RefreshCw,
  Server,
  CheckCircle,
  XCircle,
  Loader2,
  Terminal,
  Play,
  Clock,
  Trash2,
} from "lucide-react"
import { distributedSubmissionsApi } from "@/api/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useToast } from "@/hooks/useToast"
import { useConfirm } from "@/components/ui/confirm-dialog"
import type { DistributedSubmission, TestResult, SupportedLanguage } from "@/types"

// Language display info
const languageInfo: Record<SupportedLanguage, { label: string; icon: string }> = {
  python: { label: "Python", icon: "🐍" },
  go: { label: "Go", icon: "🐹" },
  java: { label: "Java", icon: "☕" },
  cpp: { label: "C++", icon: "⚡" },
  rust: { label: "Rust", icon: "🦀" },
}

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

function ResultsSkeleton() {
  return (
    <div className="space-y-6">
      <div className="flex items-center gap-4">
        <Skeleton className="h-10 w-10" />
        <Skeleton className="h-8 w-64" />
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
        <Skeleton className="h-24" />
      </div>
      <Skeleton className="h-[400px]" />
    </div>
  )
}

export default function DistributedSubmissionResults() {
  const { id } = useParams<{ id: string }>()
  const navigate = useNavigate()
  const { toast } = useToast()
  const confirm = useConfirm()

  const [submission, setSubmission] = useState<DistributedSubmission | null>(null)
  const [buildLogs, setBuildLogs] = useState<string>("")
  const [testResults, setTestResults] = useState<TestResult[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [tearingDown, setTearingDown] = useState(false)

  // Load submission details
  const loadSubmission = useCallback(async () => {
    if (!id) return
    try {
      const data = await distributedSubmissionsApi.get(parseInt(id))
      setSubmission(data)

      // Load build logs if available
      if (data.build_logs || data.status === "building" || data.status === "build_failed") {
        try {
          const logs = await distributedSubmissionsApi.getBuildLogs(parseInt(id))
          setBuildLogs(logs)
        } catch {
          setBuildLogs(data.build_logs || "")
        }
      }

      // Load test results if completed or testing
      if (data.status === "testing" || data.status === "completed" || data.status === "failed") {
        try {
          const results = await distributedSubmissionsApi.getTestResults(parseInt(id))
          setTestResults(results)
        } catch {
          // Ignore errors loading test results
        }
      }

      return data
    } catch (err: any) {
      console.error("Failed to load submission:", err)
      const message = err.response?.data?.detail || err.message || "Failed to load submission"
      setError(message)
      return null
    }
  }, [id])

  // Initial load
  useEffect(() => {
    const load = async () => {
      setLoading(true)
      await loadSubmission()
      setLoading(false)
    }
    load()
  }, [loadSubmission])

  // Poll for updates while in progress
  useEffect(() => {
    if (!submission) return
    const inProgressStatuses = ["pending", "building", "deploying", "testing"]
    if (!inProgressStatuses.includes(submission.status)) return

    const interval = setInterval(async () => {
      const updated = await loadSubmission()
      if (updated && !inProgressStatuses.includes(updated.status)) {
        clearInterval(interval)
      }
    }, 3000)

    return () => clearInterval(interval)
  }, [submission, loadSubmission])

  // Handle teardown
  const handleTeardown = async () => {
    if (!id) return

    const confirmed = await confirm({
      title: "Tear Down Cluster",
      message: "This will permanently delete all cluster nodes. The cluster cannot be restored after teardown. Are you sure?",
      type: "destructive",
      confirmLabel: "Tear Down",
      cancelLabel: "Cancel",
    })

    if (!confirmed) return

    setTearingDown(true)
    try {
      await distributedSubmissionsApi.teardownCluster(parseInt(id))
      toast({
        title: "Cluster torn down",
        description: "All cluster nodes have been removed successfully.",
      })
      // Reload to show updated status
      await loadSubmission()
    } catch (err: any) {
      toast({
        title: "Teardown failed",
        description: err.response?.data?.detail || "Failed to tear down cluster",
        variant: "destructive",
      })
    } finally {
      setTearingDown(false)
    }
  }

  if (loading) {
    return <ResultsSkeleton />
  }

  if (error || !submission) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="h-12 w-12 text-destructive mb-4" />
        <p className="text-destructive font-medium mb-2">Failed to load submission</p>
        <p className="text-muted-foreground text-sm mb-4">{error}</p>
        <div className="flex gap-2">
          <Button onClick={() => navigate("/distributed")} variant="outline">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Problems
          </Button>
          <Button onClick={loadSubmission} variant="outline">
            <RefreshCw className="mr-2 h-4 w-4" />
            Try Again
          </Button>
        </div>
      </div>
    )
  }

  const inProgress = ["pending", "building", "deploying", "testing"].includes(submission.status)
  const testsPassed = testResults.filter((t) => t.status === "passed").length
  const testsFailed = testResults.filter((t) => t.status === "failed").length

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => navigate(`/distributed/${submission.problem_id}`)}
            className="mb-2"
          >
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to Problem
          </Button>
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Server className="h-6 w-6 text-primary" />
            Submission #{submission.id}
          </h1>
          <div className="flex items-center gap-2 mt-2">
            <Badge variant={statusVariant[submission.status] || "secondary"}>
              {inProgress && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
              {statusLabels[submission.status] || submission.status}
            </Badge>
            <Badge variant="outline">
              {languageInfo[submission.language].icon} {languageInfo[submission.language].label}
            </Badge>
          </div>
        </div>
        <div className="flex gap-2">
          {submission.cluster_node_urls && submission.cluster_node_urls.length > 0 && (
            <Button
              onClick={handleTeardown}
              variant="destructive"
              disabled={tearingDown}
            >
              {tearingDown ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Trash2 className="mr-2 h-4 w-4" />
              )}
              Tear Down Cluster
            </Button>
          )}
          <Button onClick={() => loadSubmission()} variant="outline" disabled={loading}>
            <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Status cards */}
      <div className="grid gap-4 md:grid-cols-3">
        {/* Build Status */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Terminal className="h-4 w-4" />
              Build Status
            </CardTitle>
          </CardHeader>
          <CardContent>
            {submission.status === "build_failed" ? (
              <div className="flex items-center gap-2 text-destructive">
                <XCircle className="h-5 w-5" />
                <span className="font-medium">Failed</span>
              </div>
            ) : submission.status === "building" ? (
              <div className="flex items-center gap-2 text-primary">
                <Loader2 className="h-5 w-5 animate-spin" />
                <span className="font-medium">Building...</span>
              </div>
            ) : submission.status === "pending" ? (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Clock className="h-5 w-5" />
                <span className="font-medium">Queued</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-green-600">
                <CheckCircle className="h-5 w-5" />
                <span className="font-medium">Success</span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Cluster Status */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Server className="h-4 w-4" />
              Cluster
            </CardTitle>
          </CardHeader>
          <CardContent>
            {submission.cluster_node_urls && submission.cluster_node_urls.length > 0 ? (
              <div className="flex items-center gap-2 text-green-600">
                <CheckCircle className="h-5 w-5" />
                <span className="font-medium">
                  {submission.cluster_node_urls.length} nodes running
                </span>
              </div>
            ) : submission.status === "deploying" ? (
              <div className="flex items-center gap-2 text-primary">
                <Loader2 className="h-5 w-5 animate-spin" />
                <span className="font-medium">Deploying...</span>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Clock className="h-5 w-5" />
                <span className="font-medium">Not deployed</span>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Test Results */}
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm flex items-center gap-2">
              <Play className="h-4 w-4" />
              Tests
            </CardTitle>
          </CardHeader>
          <CardContent>
            {submission.status === "testing" ? (
              <div className="flex items-center gap-2 text-primary">
                <Loader2 className="h-5 w-5 animate-spin" />
                <span className="font-medium">Running...</span>
              </div>
            ) : testResults.length > 0 ? (
              <div className="flex items-center gap-4">
                <div className="flex items-center gap-1 text-green-600">
                  <CheckCircle className="h-4 w-4" />
                  <span className="font-medium">{testsPassed}</span>
                </div>
                <div className="flex items-center gap-1 text-destructive">
                  <XCircle className="h-4 w-4" />
                  <span className="font-medium">{testsFailed}</span>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-2 text-muted-foreground">
                <Clock className="h-5 w-5" />
                <span className="font-medium">Pending</span>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Error message */}
      {submission.error_message && (
        <Card className="border-destructive">
          <CardHeader>
            <CardTitle className="text-destructive flex items-center gap-2">
              <AlertCircle className="h-5 w-5" />
              Error
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-destructive">{submission.error_message}</p>
          </CardContent>
        </Card>
      )}

      {/* Tabs for logs and results */}
      <Tabs defaultValue="logs">
        <TabsList>
          <TabsTrigger value="logs" className="flex items-center gap-2">
            <Terminal className="h-4 w-4" />
            Build Logs
          </TabsTrigger>
          <TabsTrigger value="tests" className="flex items-center gap-2">
            <Play className="h-4 w-4" />
            Test Results
          </TabsTrigger>
          <TabsTrigger value="cluster" className="flex items-center gap-2">
            <Server className="h-4 w-4" />
            Cluster Info
          </TabsTrigger>
        </TabsList>

        <TabsContent value="logs" className="mt-4">
          <Card>
            <CardContent className="pt-6">
              {buildLogs ? (
                <pre className="bg-muted p-4 rounded-md overflow-auto text-sm max-h-[500px] font-mono">
                  {buildLogs}
                </pre>
              ) : (
                <p className="text-muted-foreground text-center py-8">
                  No build logs available yet.
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="tests" className="mt-4">
          <Card>
            <CardContent className="pt-6">
              {testResults.length > 0 ? (
                <div className="space-y-3">
                  {testResults.map((test) => (
                    <div
                      key={test.id}
                      className={`p-4 rounded-md border ${
                        test.status === "passed"
                          ? "border-green-200 bg-green-50 dark:bg-green-950/20"
                          : test.status === "failed"
                          ? "border-red-200 bg-red-50 dark:bg-red-950/20"
                          : "border-muted bg-muted/50"
                      }`}
                    >
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          {test.status === "passed" ? (
                            <CheckCircle className="h-5 w-5 text-green-600" />
                          ) : test.status === "failed" ? (
                            <XCircle className="h-5 w-5 text-destructive" />
                          ) : (
                            <Loader2 className="h-5 w-5 text-muted-foreground animate-spin" />
                          )}
                          <div>
                            <p className="font-medium">{test.test_name}</p>
                            <div className="flex items-center gap-2 mt-1">
                              <Badge variant="outline" className="text-xs">
                                {test.test_type}
                              </Badge>
                              {test.duration_ms && (
                                <span className="text-xs text-muted-foreground">
                                  {test.duration_ms}ms
                                </span>
                              )}
                            </div>
                          </div>
                        </div>
                      </div>
                      {test.details && Object.keys(test.details).length > 0 && (
                        <pre className="mt-2 text-xs bg-background p-2 rounded overflow-auto">
                          {JSON.stringify(test.details, null, 2)}
                        </pre>
                      )}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground text-center py-8">
                  No test results available yet.
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="cluster" className="mt-4">
          <Card>
            <CardContent className="pt-6">
              {submission.cluster_node_urls && submission.cluster_node_urls.length > 0 ? (
                <div className="space-y-3">
                  {submission.cluster_node_urls.map((url, index) => (
                    <div
                      key={index}
                      className="flex items-center gap-3 p-3 rounded-md bg-muted/50"
                    >
                      <Server className="h-5 w-5 text-primary" />
                      <div>
                        <p className="font-medium">Node {index + 1}</p>
                        <code className="text-sm text-muted-foreground">{url}</code>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground text-center py-8">
                  Cluster not deployed yet.
                </p>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
