/**
 * User Usage Dashboard
 * Displays user's usage costs and activity logs
 */

import { useState, useEffect } from "react"
import { Link } from "react-router-dom"
import {
  ArrowLeft,
  RefreshCw,
  DollarSign,
  Activity,
  Clock,
  Cpu,
  Database,
  Network,
  Zap,
  FileText,
  MessageSquare,
  LogIn,
  LogOut,
  Eye,
  Send,
  AlertTriangle,
  Cloud,
  Server,
  Rocket,
} from "lucide-react"
import { userApi, assetsApi, UsageCostResponse, AuditLogResponse, UserGCPResources, StorageInfo } from "@/api/client"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <Skeleton className="h-8 w-48" />
      <div className="grid gap-4 md:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <Skeleton className="h-96" />
    </div>
  )
}

const categoryIcons: Record<string, typeof DollarSign> = {
  ai_input_tokens: Zap,
  ai_output_tokens: MessageSquare,
  gcp_compute: Cpu,
  gcp_storage: Database,
  gcp_network: Network,
  gcp_database: Database,
}

const actionIcons: Record<string, typeof Activity> = {
  login: LogIn,
  logout: LogOut,
  view_problem: Eye,
  list_problems: FileText,
  create_submission: Send,
  view_submission: Eye,
  list_submissions: FileText,
  validate_submission: FileText,
  chat_message: MessageSquare,
  generate_summary: FileText,
  evaluate_diagram: Eye,
  deploy_start: Rocket,
  deploy_complete: Cloud,
  deploy_failed: AlertTriangle,
  run_tests: Server,
  ai_chat: MessageSquare,
  ai_validate_design: Eye,
  ai_generate_code: FileText,
}

function formatCost(cost: number): string {
  if (cost < 0.01) return "<$0.01"
  return `$${cost.toFixed(2)}`
}

function formatNumber(num: number): string {
  if (num >= 1000000) return `${(num / 1000000).toFixed(1)}M`
  if (num >= 1000) return `${(num / 1000).toFixed(1)}K`
  return num.toFixed(0)
}

function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleString()
}

function formatCategory(category: string): string {
  return category
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

function formatAction(action: string): string {
  return action
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase())
}

export default function UsageDashboard() {
  const [usage, setUsage] = useState<UsageCostResponse | null>(null)
  const [activity, setActivity] = useState<AuditLogResponse | null>(null)
  const [gcpResources, setGcpResources] = useState<UserGCPResources | null>(null)
  const [storage, setStorage] = useState<StorageInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [days, setDays] = useState(30)

  const loadData = async () => {
    try {
      const [usageData, activityData, gcpData, storageData] = await Promise.all([
        userApi.getUsage(days),
        userApi.getActivity(Math.min(days, 90)),
        assetsApi.getUserGCPResources().catch(() => null),
        assetsApi.getStorage().catch(() => null),
      ])
      setUsage(usageData)
      setActivity(activityData)
      setGcpResources(gcpData)
      setStorage(storageData)
      setError(null)
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load usage data")
      console.error("Error loading usage data:", err)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [days])

  const handleRefresh = () => {
    setRefreshing(true)
    loadData()
  }

  if (loading) {
    return (
      <div className="max-w-6xl mx-auto space-y-6">
        <DashboardSkeleton />
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col items-center justify-center py-12">
          <AlertTriangle className="h-12 w-12 text-destructive mb-4" />
          <p className="text-destructive font-medium mb-4">{error}</p>
          <Button asChild variant="outline">
            <Link to="/problems">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Problems
            </Link>
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Usage Dashboard</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            View your usage costs and activity logs
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            className="border rounded px-3 py-2 text-sm"
            value={days}
            onChange={(e) => setDays(Number(e.target.value))}
          >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
            <option value={365}>Last year</option>
          </select>
          <Button
            variant="outline"
            size="sm"
            onClick={handleRefresh}
            disabled={refreshing}
          >
            <RefreshCw className={`h-4 w-4 mr-2 ${refreshing ? "animate-spin" : ""}`} />
            Refresh
          </Button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid gap-4 md:grid-cols-5">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">Total Cost</p>
            </div>
            <p className="text-2xl font-bold mt-1">
              {formatCost(usage?.total_cost_usd || 0)}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Cloud className="h-4 w-4 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">GCP Costs</p>
            </div>
            <p className="text-2xl font-bold mt-1">
              {formatCost(
                (usage?.by_category || [])
                  .filter((c) => c.category.startsWith("gcp_"))
                  .reduce((sum, c) => sum + c.total_cost_usd, 0)
              )}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Zap className="h-4 w-4 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">AI Tokens Used</p>
            </div>
            <p className="text-2xl font-bold mt-1">
              {formatNumber(
                (usage?.by_category || [])
                  .filter((c) => c.category.includes("tokens"))
                  .reduce((sum, c) => sum + c.total_quantity, 0)
              )}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">Total Actions</p>
            </div>
            <p className="text-2xl font-bold mt-1">
              {activity?.total_count || 0}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Clock className="h-4 w-4 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">Period</p>
            </div>
            <p className="text-sm font-medium mt-1">
              {usage?.start_date ? new Date(usage.start_date).toLocaleDateString() : "N/A"}
              {" - "}
              {usage?.end_date ? new Date(usage.end_date).toLocaleDateString() : "N/A"}
            </p>
          </CardContent>
        </Card>
      </div>

      {/* Main Content Tabs */}
      <Tabs defaultValue="costs">
        <TabsList>
          <TabsTrigger value="costs">
            <DollarSign className="h-4 w-4 mr-2" />
            Costs
          </TabsTrigger>
          <TabsTrigger value="deployments">
            <Cloud className="h-4 w-4 mr-2" />
            Deployments
          </TabsTrigger>
          <TabsTrigger value="activity">
            <Activity className="h-4 w-4 mr-2" />
            Activity
          </TabsTrigger>
        </TabsList>

        <TabsContent value="costs" className="space-y-4">
          {/* Cost by Category */}
          <Card>
            <CardHeader>
              <CardTitle>Cost by Category</CardTitle>
              <CardDescription>Breakdown of your usage costs</CardDescription>
            </CardHeader>
            <CardContent>
              {(usage?.by_category || []).length === 0 ? (
                <p className="text-muted-foreground text-center py-8">
                  No usage data for this period
                </p>
              ) : (
                <div className="space-y-4">
                  {(usage?.by_category || []).map((category) => {
                    const Icon = categoryIcons[category.category] || DollarSign
                    return (
                      <div
                        key={category.category}
                        className="flex items-center justify-between p-3 bg-muted/50 rounded-lg"
                      >
                        <div className="flex items-center gap-3">
                          <Icon className="h-5 w-5 text-muted-foreground" />
                          <div>
                            <p className="font-medium">
                              {formatCategory(category.category)}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              {formatNumber(category.total_quantity)} {category.unit}
                            </p>
                          </div>
                        </div>
                        <Badge variant="secondary">
                          {formatCost(category.total_cost_usd)}
                        </Badge>
                      </div>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Recent Cost Items */}
          <Card>
            <CardHeader>
              <CardTitle>Recent Charges</CardTitle>
              <CardDescription>Your most recent usage charges</CardDescription>
            </CardHeader>
            <CardContent>
              {(usage?.recent_items || []).length === 0 ? (
                <p className="text-muted-foreground text-center py-8">
                  No charges in this period
                </p>
              ) : (
                <div className="space-y-2">
                  {(usage?.recent_items || []).slice(0, 20).map((item) => {
                    const Icon = categoryIcons[item.category] || DollarSign
                    return (
                      <div
                        key={item.id}
                        className="flex items-center justify-between py-2 border-b last:border-0"
                      >
                        <div className="flex items-center gap-3">
                          <Icon className="h-4 w-4 text-muted-foreground" />
                          <div>
                            <p className="text-sm font-medium">
                              {formatCategory(item.category)}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {formatDate(item.created_at)}
                            </p>
                          </div>
                        </div>
                        <div className="text-right">
                          <p className="text-sm font-medium">
                            {formatCost(item.total_cost_usd)}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {formatNumber(item.quantity)} {item.unit}
                          </p>
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="deployments" className="space-y-4">
          {/* Active Cloud Run Services */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Server className="h-5 w-5" />
                Active Cloud Run Services
              </CardTitle>
              <CardDescription>
                {gcpResources ? (
                  `${gcpResources.active_cloud_run_services} service(s) running across ${gcpResources.total_cluster_nodes} nodes`
                ) : (
                  "Loading..."
                )}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!gcpResources || gcpResources.distributed_submissions.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">
                  No active Cloud Run services. Submit a distributed consensus problem to deploy.
                </p>
              ) : (
                <div className="space-y-4">
                  {gcpResources.distributed_submissions.map((submission) => {
                    const hasActiveNodes = submission.cluster_node_urls.length > 0
                    const statusColor = hasActiveNodes
                      ? "text-green-500"
                      : submission.status.includes("fail")
                      ? "text-red-500"
                      : "text-muted-foreground"

                    return (
                      <div
                        key={submission.submission_id}
                        className="p-4 border rounded-lg space-y-3"
                      >
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-3">
                            <div className={`p-2 rounded-lg ${
                              hasActiveNodes ? "bg-green-500/10" : "bg-muted"
                            }`}>
                              <Server className={`h-5 w-5 ${statusColor}`} />
                            </div>
                            <div>
                              <p className="font-medium">
                                Submission #{submission.submission_id}
                              </p>
                              <p className="text-sm text-muted-foreground">
                                {submission.language.toUpperCase()} · Problem #{submission.problem_id}
                              </p>
                            </div>
                          </div>
                          <div className="text-right">
                            <Badge variant={hasActiveNodes ? "default" : "secondary"}>
                              {submission.status}
                            </Badge>
                            <p className="text-xs text-muted-foreground mt-1">
                              {formatDate(submission.created_at)}
                            </p>
                          </div>
                        </div>

                        {/* Cloud Run nodes */}
                        {hasActiveNodes && (
                          <div className="pl-11 space-y-2">
                            <p className="text-sm font-medium text-muted-foreground">
                              Cloud Run Services ({submission.cluster_node_urls.length} nodes):
                            </p>
                            <div className="space-y-1">
                              {submission.cluster_node_urls.map((url, idx) => (
                                <div key={idx} className="flex items-center gap-2 text-sm">
                                  <Cloud className="h-4 w-4 text-blue-500" />
                                  <code className="text-xs bg-muted px-2 py-1 rounded">
                                    {url}
                                  </code>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Console links */}
                        {Object.keys(submission.console_links).length > 0 && (
                          <div className="pl-11 flex flex-wrap gap-2">
                            {Object.entries(submission.console_links).map(([name, url]) => (
                              <a
                                key={name}
                                href={url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-xs text-blue-500 hover:underline"
                              >
                                {name.replace(/_/g, " ")}
                              </a>
                            ))}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          {/* GCP Cost Breakdown */}
          <Card>
            <CardHeader>
              <CardTitle>GCP Cost Summary</CardTitle>
              <CardDescription>Infrastructure costs by category</CardDescription>
            </CardHeader>
            <CardContent>
              {(() => {
                const gcpCategories = (usage?.by_category || []).filter(
                  (c) => c.category.startsWith("gcp_")
                )
                if (gcpCategories.length === 0) {
                  return (
                    <p className="text-muted-foreground text-center py-8">
                      No GCP cost data for this period
                    </p>
                  )
                }
                return (
                  <div className="space-y-3">
                    {gcpCategories.map((category) => {
                      const Icon = categoryIcons[category.category] || Cloud
                      return (
                        <div
                          key={category.category}
                          className="flex items-center justify-between p-3 bg-muted/50 rounded-lg"
                        >
                          <div className="flex items-center gap-3">
                            <Icon className="h-5 w-5 text-blue-500" />
                            <div>
                              <p className="font-medium text-sm">
                                {formatCategory(category.category)}
                              </p>
                              <p className="text-xs text-muted-foreground">
                                {formatNumber(category.total_quantity)} {category.unit}
                              </p>
                            </div>
                          </div>
                          <Badge variant="secondary">
                            {formatCost(category.total_cost_usd)}
                          </Badge>
                        </div>
                      )
                    })}
                  </div>
                )
              })()}
            </CardContent>
          </Card>

          {/* Container Image Storage */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-5 w-5" />
                Container Image Storage
              </CardTitle>
              <CardDescription>
                {storage ? (
                  <>Total storage: {storage.total_size_formatted}</>
                ) : (
                  "Loading..."
                )}
              </CardDescription>
            </CardHeader>
            <CardContent>
              {!storage || storage.images.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">
                  No container images in storage
                </p>
              ) : (
                <div className="space-y-3">
                  {storage.images.slice(0, 10).map((image, idx) => (
                    <div
                      key={idx}
                      className="flex items-center justify-between p-3 bg-muted/50 rounded-lg"
                    >
                      <div className="flex items-center gap-3">
                        <Database className="h-4 w-4 text-purple-500" />
                        <div>
                          <p className="font-medium text-sm">{image.name}</p>
                          <p className="text-xs text-muted-foreground">
                            {image.upload_time ? formatDate(image.upload_time) : "Unknown date"}
                          </p>
                        </div>
                      </div>
                      <Badge variant="secondary">{image.size_formatted}</Badge>
                    </div>
                  ))}
                  {storage.images.length > 10 && (
                    <p className="text-xs text-muted-foreground text-center">
                      +{storage.images.length - 10} more images
                    </p>
                  )}
                  <a
                    href={storage.artifact_registry_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-sm text-blue-500 hover:underline block text-center"
                  >
                    View in Artifact Registry
                  </a>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="activity" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Activity Log</CardTitle>
              <CardDescription>
                Your recent actions ({activity?.total_count || 0} total)
              </CardDescription>
            </CardHeader>
            <CardContent>
              {(activity?.items || []).length === 0 ? (
                <p className="text-muted-foreground text-center py-8">
                  No activity in this period
                </p>
              ) : (
                <div className="space-y-2">
                  {(activity?.items || []).map((item) => {
                    const Icon = actionIcons[item.action] || Activity
                    return (
                      <div
                        key={item.id}
                        className="flex items-center justify-between py-3 border-b last:border-0"
                      >
                        <div className="flex items-center gap-3">
                          <Icon className="h-4 w-4 text-muted-foreground" />
                          <div>
                            <p className="text-sm font-medium">
                              {formatAction(item.action)}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {item.request_path || "N/A"}
                            </p>
                          </div>
                        </div>
                        <div className="text-right">
                          <Badge
                            variant={
                              item.response_status && item.response_status >= 400
                                ? "destructive"
                                : "secondary"
                            }
                          >
                            {item.response_status || "N/A"}
                          </Badge>
                          <p className="text-xs text-muted-foreground mt-1">
                            {formatDate(item.created_at)}
                          </p>
                          {item.duration_ms && (
                            <p className="text-xs text-muted-foreground">
                              {item.duration_ms}ms
                            </p>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
