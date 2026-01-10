/**
 * Results page
 * Shows submission status and test results with error analysis
 */

import { useState, useEffect } from "react"
import { useParams, Link } from "react-router-dom"
import {
  ArrowLeft,
  CheckCircle,
  XCircle,
  AlertCircle,
  Clock,
  Loader2,
  ExternalLink,
  Trash2,
  Server,
  AlertTriangle,
  Code,
  Cloud,
  FileCode,
  ChevronDown,
  ChevronUp,
  Copy,
  Check,
} from "lucide-react"
import { submissionsApi, testsApi, assetsApi } from "@/api/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { Progress } from "@/components/ui/progress"
import { Skeleton } from "@/components/ui/skeleton"
import TestResultCard from "@/components/TestResultCard"
import TestScenarioDetails from "@/components/TestScenarioDetails"
import DeployedComponentsCard from "@/components/DeployedComponentsCard"
import { cn } from "@/lib/utils"
import type { SubmissionDetail, TestSummary, SubmissionStatus, TestResult } from "@/types"

interface DeploymentStatus {
  submission_id: number
  deployment_id: string
  namespace: string
  deployment_mode: string
  endpoint_url: string
  deployed_at: string
  scheduled_cleanup_at: string
  time_remaining_seconds: number
  time_remaining_minutes: number
  is_cleaned_up: boolean
}

interface GCPAssets {
  submission_id: number
  user_email: string
  status: string
  created_at: string
  service_name: string | null
  endpoint_url: string | null
  region: string
  container_image: string | null
  console_links: {
    cloud_run_service?: string
    cloud_run_logs?: string
    cloud_run_revisions?: string
    cloud_build_history?: string
    container_registry?: string
    cloud_storage_source?: string
  }
  generated_code: string | null
}

const statusConfig: Record<
  SubmissionStatus,
  {
    label: string
    variant: "default" | "secondary" | "destructive" | "success" | "warning"
    icon: React.ElementType
    iconClass: string
  }
> = {
  pending: {
    label: "Pending",
    variant: "secondary",
    icon: Clock,
    iconClass: "text-muted-foreground",
  },
  validating: {
    label: "Validating Design...",
    variant: "default",
    icon: Loader2,
    iconClass: "text-primary animate-spin",
  },
  validation_failed: {
    label: "Validation Failed",
    variant: "destructive",
    icon: XCircle,
    iconClass: "text-destructive",
  },
  generating_infra: {
    label: "Generating Infrastructure...",
    variant: "default",
    icon: Loader2,
    iconClass: "text-primary animate-spin",
  },
  deploying: {
    label: "Deploying to GCP...",
    variant: "default",
    icon: Loader2,
    iconClass: "text-primary animate-spin",
  },
  deploy_failed: {
    label: "Deployment Failed",
    variant: "destructive",
    icon: XCircle,
    iconClass: "text-destructive",
  },
  testing: {
    label: "Running Tests...",
    variant: "warning",
    icon: Loader2,
    iconClass: "text-warning animate-spin",
  },
  completed: {
    label: "Completed",
    variant: "success",
    icon: CheckCircle,
    iconClass: "text-success",
  },
  failed: {
    label: "Failed",
    variant: "destructive",
    icon: XCircle,
    iconClass: "text-destructive",
  },
}

function ResultsSkeleton() {
  return (
    <div className="max-w-5xl mx-auto space-y-6">
      <div className="flex items-center justify-between">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-6 w-24" />
      </div>
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32" />
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-4">
          {[1, 2, 3, 4].map((i) => (
            <Skeleton key={i} className="h-20" />
          ))}
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <Skeleton className="h-6 w-32" />
        </CardHeader>
        <CardContent className="space-y-4">
          {[1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-24" />
          ))}
        </CardContent>
      </Card>
    </div>
  )
}

export default function Results() {
  const { id } = useParams<{ id: string }>()
  const [submission, setSubmission] = useState<SubmissionDetail | null>(null)
  const [testSummary, setTestSummary] = useState<TestSummary | null>(null)
  const [deploymentStatus, setDeploymentStatus] = useState<DeploymentStatus | null>(null)
  const [gcpAssets, setGcpAssets] = useState<GCPAssets | null>(null)
  const [generatedCode, setGeneratedCode] = useState<string | null>(null)
  const [showCode, setShowCode] = useState(false)
  const [loadingCode, setLoadingCode] = useState(false)
  const [copiedCode, setCopiedCode] = useState(false)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState<string | null>(null)
  const [tearingDown, setTearingDown] = useState(false)

  // Clear pending draft from Submission page on mount
  useEffect(() => {
    const pendingDraftKey = sessionStorage.getItem('pending_draft_clear')
    if (pendingDraftKey) {
      localStorage.removeItem(pendingDraftKey)
      sessionStorage.removeItem('pending_draft_clear')
    }
  }, [])

  // Poll for updates while processing
  useEffect(() => {
    if (!id) return

    const loadData = async () => {
      try {
        const sub = await submissionsApi.get(parseInt(id))
        setSubmission(sub)

        // Load test results if testing or completed
        if (["testing", "completed"].includes(sub.status)) {
          try {
            const summary = await testsApi.getTestSummary(parseInt(id))
            setTestSummary(summary)
          } catch {
            // Tests not ready yet
          }
        }

        // Load deployment status if deployed
        if (["deploying", "testing", "completed"].includes(sub.status)) {
          try {
            const depStatus = await submissionsApi.getDeploymentStatus(parseInt(id))
            if (depStatus.deployment) {
              setDeploymentStatus(depStatus.deployment)
            }
          } catch {
            // Deployment status not ready yet
          }

          // Load GCP assets
          try {
            const assets = await assetsApi.getSubmissionAssets(parseInt(id))
            setGcpAssets(assets)
          } catch {
            // Assets not available yet
          }
        }
      } catch (err: any) {
        console.error("Failed to load submission:", err)
        const message = err.response?.data?.detail || err.message || "Failed to load submission"
        setLoadError(message)
      } finally {
        setLoading(false)
      }
    }

    loadData()

    // Poll for updates only when not in terminal state
    const terminalStates = ["completed", "failed", "validation_failed", "deploy_failed"]
    const isTerminal = submission && terminalStates.includes(submission.status)

    if (!isTerminal) {
      const interval = setInterval(loadData, 5000)
      return () => clearInterval(interval)
    }
  }, [id, submission?.status])

  const handleTeardown = async () => {
    if (
      !id ||
      !confirm("Are you sure you want to tear down this deployment? This action cannot be undone.")
    ) {
      return
    }

    setTearingDown(true)
    try {
      await submissionsApi.teardown(parseInt(id))
      setDeploymentStatus((prev) => (prev ? { ...prev, is_cleaned_up: true } : null))
    } catch (err) {
      console.error("Failed to teardown:", err)
    } finally {
      setTearingDown(false)
    }
  }

  const formatTimeRemaining = (minutes: number) => {
    if (minutes < 1) return "Less than 1 minute"
    if (minutes < 60) return `${Math.round(minutes)} minutes`
    const hours = Math.floor(minutes / 60)
    const mins = Math.round(minutes % 60)
    return `${hours}h ${mins}m`
  }

  const handleLoadCode = async () => {
    if (!id) return
    setLoadingCode(true)
    try {
      const codeData = await assetsApi.getSubmissionCode(parseInt(id))
      setGeneratedCode(codeData.code)
      setShowCode(true)
    } catch (err) {
      console.error("Failed to load code:", err)
    } finally {
      setLoadingCode(false)
    }
  }

  const handleCopyCode = async () => {
    if (!generatedCode) return
    try {
      await navigator.clipboard.writeText(generatedCode)
      setCopiedCode(true)
      setTimeout(() => setCopiedCode(false), 2000)
    } catch (err) {
      console.error("Failed to copy:", err)
    }
  }

  const getTestCounts = (tests: TestResult[]) => ({
    total: tests.length,
    passed: tests.filter((t) => t.status === "passed").length,
    failed: tests.filter((t) => t.status === "failed" || t.status === "error").length,
  })

  if (loading) {
    return <ResultsSkeleton />
  }

  if (loadError || !submission) {
    return (
      <div className="flex flex-col items-center justify-center py-12">
        <AlertCircle className="h-12 w-12 text-destructive mb-4" />
        <p className="text-destructive font-medium mb-2">
          {loadError ? "Failed to load submission" : "Submission not found"}
        </p>
        {loadError && (
          <p className="text-muted-foreground text-sm mb-4">{loadError}</p>
        )}
        <div className="flex gap-3">
          <Button variant="outline" onClick={() => window.location.reload()}>
            <Loader2 className="mr-2 h-4 w-4" />
            Retry
          </Button>
          <Button asChild>
            <Link to="/problems">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to problems
            </Link>
          </Button>
        </div>
      </div>
    )
  }

  const config = statusConfig[submission.status]
  const StatusIcon = config.icon

  return (
    <div className="max-w-5xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <Button asChild variant="ghost" size="sm" className="mb-2">
          <Link to="/problems">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to problems
          </Link>
        </Button>
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold">Submission Results</h1>
          <Badge variant={config.variant} className="flex items-center gap-1.5">
            <StatusIcon className={cn("h-3.5 w-3.5", config.iconClass)} />
            {config.label}
          </Badge>
        </div>
      </div>

      {/* Error message */}
      {submission.error_message && (
        <Card className="border-destructive/50 bg-destructive/5">
          <CardHeader className="pb-2">
            <CardTitle className="text-destructive flex items-center gap-2 text-base">
              <AlertCircle className="h-4 w-4" />
              Error
            </CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-destructive/90">{submission.error_message}</p>
          </CardContent>
        </Card>
      )}

      {/* Validation feedback */}
      {submission.validation_feedback?.feedback && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Design Validation Feedback</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid gap-4 md:grid-cols-2">
              {["scalability", "reliability", "data_model", "api_design"].map((key) => {
                const item = (submission.validation_feedback?.feedback as any)?.[key]
                if (!item) return null
                return (
                  <div key={key} className="p-4 bg-muted/50 rounded-lg">
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-sm font-medium capitalize">{key.replace("_", " ")}</p>
                      <Badge variant={item.score >= 70 ? "success" : item.score >= 50 ? "warning" : "destructive"}>
                        {item.score}/100
                      </Badge>
                    </div>
                    <p className="text-xs text-muted-foreground">{item.comments}</p>
                  </div>
                )
              })}
            </div>
            {submission.validation_feedback.feedback.overall && (
              <p className="mt-4 text-sm text-muted-foreground border-t pt-4">
                {submission.validation_feedback.feedback.overall}
              </p>
            )}
          </CardContent>
        </Card>
      )}

      {/* Deployment Status */}
      {deploymentStatus && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Server className="h-4 w-4" />
              Deployment Status
            </CardTitle>
            {!deploymentStatus.is_cleaned_up && (
              <Button
                variant="destructive"
                size="sm"
                onClick={handleTeardown}
                disabled={tearingDown}
              >
                {tearingDown ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : (
                  <Trash2 className="mr-2 h-4 w-4" />
                )}
                {tearingDown ? "Tearing down..." : "Tear Down"}
              </Button>
            )}
          </CardHeader>
          <CardContent>
            {deploymentStatus.is_cleaned_up ? (
              <div className="p-4 bg-muted rounded-lg text-center">
                <p className="text-muted-foreground">Deployment has been cleaned up</p>
              </div>
            ) : (
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
                <div className="p-3 bg-muted/50 rounded-lg">
                  <p className="text-xs text-muted-foreground">Time Remaining</p>
                  <p className="text-lg font-semibold text-warning">
                    {formatTimeRemaining(deploymentStatus.time_remaining_minutes)}
                  </p>
                </div>
                <div className="p-3 bg-muted/50 rounded-lg">
                  <p className="text-xs text-muted-foreground">Deployment Mode</p>
                  <p className="text-lg font-semibold">
                    {deploymentStatus.deployment_mode === "warm_pool"
                      ? "Warm Pool"
                      : deploymentStatus.deployment_mode === "fast"
                      ? "Cloud Run"
                      : "Terraform"}
                  </p>
                </div>
                <div className="p-3 bg-muted/50 rounded-lg">
                  <p className="text-xs text-muted-foreground">Namespace</p>
                  <p
                    className="text-sm font-mono truncate"
                    title={deploymentStatus.namespace}
                  >
                    {deploymentStatus.namespace}
                  </p>
                </div>
                <div className="p-3 bg-muted/50 rounded-lg">
                  <p className="text-xs text-muted-foreground">Cleanup Scheduled</p>
                  <p className="text-sm">
                    {new Date(deploymentStatus.scheduled_cleanup_at).toLocaleTimeString()}
                  </p>
                </div>
              </div>
            )}

            {deploymentStatus.endpoint_url && !deploymentStatus.is_cleaned_up && (
              <div className="mt-4 p-3 bg-primary/5 border border-primary/20 rounded-lg">
                <p className="text-xs text-muted-foreground mb-1">Endpoint URL</p>
                <a
                  href={deploymentStatus.endpoint_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary hover:underline flex items-center gap-1"
                >
                  {deploymentStatus.endpoint_url}
                  <ExternalLink className="h-3 w-3" />
                </a>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Deployed Infrastructure Details */}
      {gcpAssets && (
        <DeployedComponentsCard
          serviceName={gcpAssets.service_name || undefined}
          region={gcpAssets.region}
          endpointUrl={gcpAssets.endpoint_url || undefined}
          containerImage={gcpAssets.container_image || undefined}
          consoleLinks={gcpAssets.console_links}
        />
      )}

      {/* GCP Assets */}
      {gcpAssets && (
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-base flex items-center gap-2">
              <Cloud className="h-4 w-4" />
              GCP Resources
            </CardTitle>
            <Badge variant="secondary">{gcpAssets.region}</Badge>
          </CardHeader>
          <CardContent>
            {/* Resource Links */}
            <div className="grid gap-3 md:grid-cols-2 lg:grid-cols-3 mb-4">
              {gcpAssets.console_links.cloud_run_service && (
                <a
                  href={gcpAssets.console_links.cloud_run_service}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 p-3 bg-muted/50 rounded-lg hover:bg-muted transition-colors"
                >
                  <Server className="h-4 w-4 text-blue-500" />
                  <span className="text-sm">Cloud Run Service</span>
                  <ExternalLink className="h-3 w-3 ml-auto text-muted-foreground" />
                </a>
              )}
              {gcpAssets.console_links.cloud_run_logs && (
                <a
                  href={gcpAssets.console_links.cloud_run_logs}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 p-3 bg-muted/50 rounded-lg hover:bg-muted transition-colors"
                >
                  <FileCode className="h-4 w-4 text-green-500" />
                  <span className="text-sm">Service Logs</span>
                  <ExternalLink className="h-3 w-3 ml-auto text-muted-foreground" />
                </a>
              )}
              {gcpAssets.console_links.cloud_build_history && (
                <a
                  href={gcpAssets.console_links.cloud_build_history}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 p-3 bg-muted/50 rounded-lg hover:bg-muted transition-colors"
                >
                  <Cloud className="h-4 w-4 text-orange-500" />
                  <span className="text-sm">Build History</span>
                  <ExternalLink className="h-3 w-3 ml-auto text-muted-foreground" />
                </a>
              )}
              {gcpAssets.console_links.container_registry && (
                <a
                  href={gcpAssets.console_links.container_registry}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-2 p-3 bg-muted/50 rounded-lg hover:bg-muted transition-colors"
                >
                  <Cloud className="h-4 w-4 text-purple-500" />
                  <span className="text-sm">Container Images</span>
                  <ExternalLink className="h-3 w-3 ml-auto text-muted-foreground" />
                </a>
              )}
            </div>

            {/* Resource Summary */}
            <div className="p-3 bg-muted/30 rounded-lg mb-4">
              <h4 className="text-sm font-medium mb-2">Resource Details</h4>
              <div className="grid gap-2 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Service Name:</span>
                  <span className="font-mono">{gcpAssets.service_name}</span>
                </div>
                {gcpAssets.container_image && (
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Container Image:</span>
                    <span className="font-mono text-xs truncate max-w-[300px]" title={gcpAssets.container_image}>
                      {gcpAssets.container_image.split('/').pop()}
                    </span>
                  </div>
                )}
              </div>
            </div>

            {/* Generated Code Section */}
            <div className="border-t pt-4">
              <div className="flex items-center justify-between mb-2">
                <h4 className="text-sm font-medium flex items-center gap-2">
                  <Code className="h-4 w-4" />
                  Generated Code
                </h4>
                <div className="flex gap-2">
                  {!showCode ? (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={handleLoadCode}
                      disabled={loadingCode}
                    >
                      {loadingCode ? (
                        <Loader2 className="h-3 w-3 animate-spin mr-1" />
                      ) : (
                        <ChevronDown className="h-3 w-3 mr-1" />
                      )}
                      View Code
                    </Button>
                  ) : (
                    <>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleCopyCode}
                      >
                        {copiedCode ? (
                          <Check className="h-3 w-3 mr-1 text-green-500" />
                        ) : (
                          <Copy className="h-3 w-3 mr-1" />
                        )}
                        {copiedCode ? "Copied!" : "Copy"}
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => setShowCode(false)}
                      >
                        <ChevronUp className="h-3 w-3 mr-1" />
                        Hide
                      </Button>
                    </>
                  )}
                </div>
              </div>
              {showCode && generatedCode && (
                <div className="relative">
                  <pre className="p-4 bg-slate-900 text-slate-100 rounded-lg overflow-x-auto text-xs max-h-96 overflow-y-auto">
                    <code>{generatedCode}</code>
                  </pre>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Test Results */}
      {testSummary && (
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <CardTitle className="text-base">Test Results</CardTitle>
              <div className="flex items-center gap-3 text-sm">
                <div className="flex items-center gap-1.5">
                  <CheckCircle className="h-4 w-4 text-success" />
                  <span>{testSummary.passed} passed</span>
                </div>
                <div className="flex items-center gap-1.5">
                  <XCircle className="h-4 w-4 text-destructive" />
                  <span>{testSummary.failed} failed</span>
                </div>
                {testSummary.errors > 0 && (
                  <div className="flex items-center gap-1.5">
                    <AlertCircle className="h-4 w-4 text-warning" />
                    <span>{testSummary.errors} errors</span>
                  </div>
                )}
              </div>
            </div>

            {/* Error Category Breakdown */}
            {testSummary.issues_by_category && (
              <div className="mt-4 flex flex-wrap gap-2">
                {testSummary.issues_by_category.user_solution > 0 && (
                  <Badge variant="user_solution" className="flex items-center gap-1">
                    <Code className="h-3 w-3" />
                    {testSummary.issues_by_category.user_solution} solution issue
                    {testSummary.issues_by_category.user_solution !== 1 ? "s" : ""}
                  </Badge>
                )}
                {testSummary.issues_by_category.platform > 0 && (
                  <Badge variant="platform" className="flex items-center gap-1">
                    <Server className="h-3 w-3" />
                    {testSummary.issues_by_category.platform} platform issue
                    {testSummary.issues_by_category.platform !== 1 ? "s" : ""}
                  </Badge>
                )}
                {testSummary.issues_by_category.deployment > 0 && (
                  <Badge variant="deployment" className="flex items-center gap-1">
                    <AlertTriangle className="h-3 w-3" />
                    {testSummary.issues_by_category.deployment} deployment issue
                    {testSummary.issues_by_category.deployment !== 1 ? "s" : ""}
                  </Badge>
                )}
              </div>
            )}

            {/* Platform Issues Warning */}
            {testSummary.has_platform_issues && (
              <div className="mt-4 p-3 bg-purple-50 dark:bg-purple-950/20 border border-purple-200 dark:border-purple-800 rounded-lg">
                <p className="text-sm text-purple-800 dark:text-purple-200 flex items-center gap-2">
                  <Server className="h-4 w-4" />
                  <span>
                    <strong>Note:</strong> Some test failures are due to platform issues, not your
                    solution. These are marked with a purple badge.
                  </span>
                </p>
              </div>
            )}
          </CardHeader>

          <CardContent className="pt-0">
            <Tabs defaultValue="overview">
              <TabsList className="mb-4">
                <TabsTrigger value="overview">Overview</TabsTrigger>
                <TabsTrigger value="functional">
                  Functional
                  <Badge variant="secondary" className="ml-2">
                    {testSummary.functional_tests.length}
                  </Badge>
                </TabsTrigger>
                <TabsTrigger value="performance">
                  Performance
                  <Badge variant="secondary" className="ml-2">
                    {testSummary.performance_tests.length}
                  </Badge>
                </TabsTrigger>
                <TabsTrigger value="chaos">
                  Chaos
                  <Badge variant="secondary" className="ml-2">
                    {testSummary.chaos_tests.length}
                  </Badge>
                </TabsTrigger>
              </TabsList>

              <TabsContent value="overview">
                <div className="grid gap-4 md:grid-cols-3">
                  {[
                    { name: "Functional Tests", tests: testSummary.functional_tests },
                    { name: "Performance Tests", tests: testSummary.performance_tests },
                    { name: "Chaos Tests", tests: testSummary.chaos_tests },
                  ].map(({ name, tests }) => {
                    const counts = getTestCounts(tests)
                    const passRate = counts.total > 0 ? (counts.passed / counts.total) * 100 : 0
                    return (
                      <Card key={name} className="bg-muted/30">
                        <CardContent className="pt-6">
                          <p className="text-sm text-muted-foreground mb-2">{name}</p>
                          <div className="flex items-end justify-between mb-2">
                            <p className="text-2xl font-bold">
                              {counts.passed}/{counts.total}
                            </p>
                            <Badge
                              variant={
                                passRate === 100
                                  ? "success"
                                  : passRate >= 50
                                  ? "warning"
                                  : "destructive"
                              }
                            >
                              {Math.round(passRate)}%
                            </Badge>
                          </div>
                          <Progress value={passRate} className="h-2" />
                        </CardContent>
                      </Card>
                    )
                  })}
                </div>
              </TabsContent>

              <TabsContent value="functional">
                <TestScenarioDetails
                  type="functional"
                  passedTests={testSummary.functional_tests
                    .filter((t) => t.status === "passed")
                    .map((t) => t.test_name)}
                  failedTests={testSummary.functional_tests
                    .filter((t) => t.status === "failed" || t.status === "error")
                    .map((t) => t.test_name)}
                />
                <div className="space-y-4">
                  {testSummary.functional_tests.length === 0 ? (
                    <p className="text-muted-foreground text-center py-8">
                      No functional tests available
                    </p>
                  ) : (
                    testSummary.functional_tests.map((result) => (
                      <TestResultCard key={result.id} result={result} />
                    ))
                  )}
                </div>
              </TabsContent>

              <TabsContent value="performance">
                <TestScenarioDetails
                  type="performance"
                  passedTests={testSummary.performance_tests
                    .filter((t) => t.status === "passed")
                    .map((t) => t.test_name)}
                  failedTests={testSummary.performance_tests
                    .filter((t) => t.status === "failed" || t.status === "error")
                    .map((t) => t.test_name)}
                />
                <div className="space-y-4">
                  {testSummary.performance_tests.length === 0 ? (
                    <p className="text-muted-foreground text-center py-8">
                      No performance tests available
                    </p>
                  ) : (
                    testSummary.performance_tests.map((result) => (
                      <TestResultCard key={result.id} result={result} />
                    ))
                  )}
                </div>
              </TabsContent>

              <TabsContent value="chaos">
                <TestScenarioDetails
                  type="chaos"
                  passedTests={testSummary.chaos_tests
                    .filter((t) => t.status === "passed")
                    .map((t) => t.test_name)}
                  failedTests={testSummary.chaos_tests
                    .filter((t) => t.status === "failed" || t.status === "error")
                    .map((t) => t.test_name)}
                />
                <div className="space-y-4">
                  {testSummary.chaos_tests.length === 0 ? (
                    <p className="text-muted-foreground text-center py-8">
                      No chaos tests available
                    </p>
                  ) : (
                    testSummary.chaos_tests.map((result) => (
                      <TestResultCard key={result.id} result={result} />
                    ))
                  )}
                </div>
              </TabsContent>
            </Tabs>
          </CardContent>
        </Card>
      )}

      {/* Processing indicator */}
      {!["completed", "failed", "validation_failed", "deploy_failed"].includes(
        submission.status
      ) && (
        <Card className="border-primary/30 bg-primary/5">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3 mb-4">
              <Loader2 className="h-5 w-5 text-primary animate-spin" />
              <p className="font-medium text-primary">
                {submission.validation_feedback?.current_step ||
                  statusConfig[submission.status].label}
              </p>
            </div>
            {submission.validation_feedback?.current_detail && (
              <p className="text-sm text-muted-foreground mb-4 ml-8">
                {submission.validation_feedback.current_detail}
              </p>
            )}
            {/* Progress bar */}
            {submission.validation_feedback?.progress &&
              submission.validation_feedback.progress.length > 0 && (
                <div className="mb-4">
                  <div className="flex justify-between text-xs text-muted-foreground mb-2">
                    <span>Progress</span>
                    <span>
                      {submission.validation_feedback.progress[
                        submission.validation_feedback.progress.length - 1
                      ]?.progress_pct || 0}
                      %
                    </span>
                  </div>
                  <Progress
                    value={
                      submission.validation_feedback.progress[
                        submission.validation_feedback.progress.length - 1
                      ]?.progress_pct || 0
                    }
                  />
                </div>
              )}
            {/* Progress history */}
            {submission.validation_feedback?.progress &&
              submission.validation_feedback.progress.length > 1 && (
                <div className="border-t pt-4">
                  <p className="text-xs font-medium text-muted-foreground mb-2">Activity Log</p>
                  <div className="max-h-32 overflow-y-auto space-y-1">
                    {submission.validation_feedback.progress
                      .slice()
                      .reverse()
                      .map((p: any, i: number) => (
                        <div key={i} className="text-xs flex items-start gap-2">
                          <span className="text-muted-foreground whitespace-nowrap">
                            {new Date(p.timestamp).toLocaleTimeString()}
                          </span>
                          <span className="font-medium">{p.step}:</span>
                          <span className="text-muted-foreground truncate">{p.detail}</span>
                        </div>
                      ))}
                  </div>
                </div>
              )}
          </CardContent>
        </Card>
      )}
    </div>
  )
}
