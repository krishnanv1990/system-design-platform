/**
 * Admin Usage Dashboard
 * Displays aggregated usage costs and activity logs for all users
 */

import { useState, useEffect } from "react"
import { Link } from "react-router-dom"
import {
  ArrowLeft,
  RefreshCw,
  DollarSign,
  Activity,
  Users,
  Clock,
  Cpu,
  Database,
  Network,
  Zap,
  MessageSquare,
  AlertTriangle,
  TrendingUp,
  BarChart3,
  Server,
  Cloud,
} from "lucide-react"
import { adminApi, assetsApi, AdminUsageResponse, AdminActivityResponse, AdminGCPResources, StorageInfo } from "@/api/client"
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

export default function AdminUsageDashboard() {
  const [usage, setUsage] = useState<AdminUsageResponse | null>(null)
  const [activity, setActivity] = useState<AdminActivityResponse | null>(null)
  const [gcpResources, setGcpResources] = useState<AdminGCPResources | null>(null)
  const [storage, setStorage] = useState<StorageInfo | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [days, setDays] = useState(30)

  const loadData = async () => {
    try {
      const [usageData, activityData, gcpData, storageData] = await Promise.all([
        adminApi.getUsage(days),
        adminApi.getActivity(Math.min(days, 90)),
        assetsApi.getAdminGCPResources().catch(() => null),
        assetsApi.getAdminStorage().catch(() => null),
      ])
      setUsage(usageData)
      setActivity(activityData)
      setGcpResources(gcpData)
      setStorage(storageData)
      setError(null)
    } catch (err: any) {
      if (err.response?.status === 403) {
        setError("Admin privileges required to view this dashboard")
      } else {
        setError(err.response?.data?.detail || "Failed to load usage data")
      }
      console.error("Error loading admin usage data:", err)
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
      <div className="max-w-7xl mx-auto space-y-6">
        <DashboardSkeleton />
      </div>
    )
  }

  if (error) {
    return (
      <div className="max-w-7xl mx-auto">
        <div className="flex flex-col items-center justify-center py-12">
          <AlertTriangle className="h-12 w-12 text-destructive mb-4" />
          <p className="text-destructive font-medium mb-4">{error}</p>
          <Button asChild variant="outline">
            <Link to="/admin">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Admin
            </Link>
          </Button>
        </div>
      </div>
    )
  }

  // Sort actions by count for the bar chart
  const sortedActions = Object.entries(activity?.by_action || {})
    .sort(([, a], [, b]) => b - a)
    .slice(0, 10)

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold">Admin Usage Dashboard</h1>
          <p className="mt-1 text-sm text-muted-foreground">
            Aggregated usage costs and activity for all users
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
      <div className="grid gap-4 md:grid-cols-4">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <DollarSign className="h-4 w-4 text-green-600" />
              <p className="text-sm text-muted-foreground">Total Revenue</p>
            </div>
            <p className="text-2xl font-bold mt-1 text-green-600">
              {formatCost(usage?.total_cost_usd || 0)}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Users className="h-4 w-4 text-blue-600" />
              <p className="text-sm text-muted-foreground">Total Users</p>
            </div>
            <p className="text-2xl font-bold mt-1 text-blue-600">
              {usage?.total_users || 0}
            </p>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-2">
              <Activity className="h-4 w-4 text-purple-600" />
              <p className="text-sm text-muted-foreground">Total Actions</p>
            </div>
            <p className="text-2xl font-bold mt-1 text-purple-600">
              {formatNumber(usage?.total_actions || 0)}
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
      <Tabs defaultValue="overview">
        <TabsList>
          <TabsTrigger value="overview">
            <TrendingUp className="h-4 w-4 mr-2" />
            Overview
          </TabsTrigger>
          <TabsTrigger value="infrastructure">
            <Server className="h-4 w-4 mr-2" />
            Infrastructure
          </TabsTrigger>
          <TabsTrigger value="users">
            <Users className="h-4 w-4 mr-2" />
            By User
          </TabsTrigger>
          <TabsTrigger value="activity">
            <BarChart3 className="h-4 w-4 mr-2" />
            Activity
          </TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          {/* Cost by Category */}
          <Card>
            <CardHeader>
              <CardTitle>Cost by Category</CardTitle>
              <CardDescription>Platform-wide usage breakdown</CardDescription>
            </CardHeader>
            <CardContent>
              {(usage?.by_category || []).length === 0 ? (
                <p className="text-muted-foreground text-center py-8">
                  No usage data for this period
                </p>
              ) : (
                <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                  {(usage?.by_category || []).map((category) => {
                    const Icon = categoryIcons[category.category] || DollarSign
                    return (
                      <div
                        key={category.category}
                        className="flex items-center justify-between p-4 bg-muted/50 rounded-lg"
                      >
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-background rounded-lg">
                            <Icon className="h-5 w-5 text-muted-foreground" />
                          </div>
                          <div>
                            <p className="font-medium">
                              {formatCategory(category.category)}
                            </p>
                            <p className="text-sm text-muted-foreground">
                              {formatNumber(category.total_quantity)} {category.unit}
                            </p>
                          </div>
                        </div>
                        <Badge variant="secondary" className="text-lg px-3 py-1">
                          {formatCost(category.total_cost_usd)}
                        </Badge>
                      </div>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>

          {/* Action Distribution */}
          <Card>
            <CardHeader>
              <CardTitle>Top Actions</CardTitle>
              <CardDescription>Most common user actions</CardDescription>
            </CardHeader>
            <CardContent>
              {sortedActions.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">
                  No activity data for this period
                </p>
              ) : (
                <div className="space-y-3">
                  {sortedActions.map(([action, count]) => {
                    const maxCount = sortedActions[0]?.[1] || 1
                    const percentage = (count / maxCount) * 100
                    return (
                      <div key={action} className="space-y-1">
                        <div className="flex items-center justify-between text-sm">
                          <span className="font-medium">{formatAction(action)}</span>
                          <span className="text-muted-foreground">
                            {formatNumber(count)}
                          </span>
                        </div>
                        <div className="h-2 bg-muted rounded-full overflow-hidden">
                          <div
                            className="h-full bg-primary rounded-full transition-all"
                            style={{ width: `${percentage}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="infrastructure" className="space-y-4">
          {/* GCP Infrastructure Summary */}
          <div className="grid gap-4 md:grid-cols-3">
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2">
                  <Users className="h-4 w-4 text-blue-600" />
                  <p className="text-sm text-muted-foreground">Users with Deployments</p>
                </div>
                <p className="text-2xl font-bold mt-1 text-blue-600">
                  {gcpResources?.total_users || 0}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2">
                  <Server className="h-4 w-4 text-green-600" />
                  <p className="text-sm text-muted-foreground">Active Services</p>
                </div>
                <p className="text-2xl font-bold mt-1 text-green-600">
                  {gcpResources?.total_active_services || 0}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="flex items-center gap-2">
                  <Cloud className="h-4 w-4 text-purple-600" />
                  <p className="text-sm text-muted-foreground">Total Cluster Nodes</p>
                </div>
                <p className="text-2xl font-bold mt-1 text-purple-600">
                  {gcpResources?.total_cluster_nodes || 0}
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Resources by User */}
          <Card>
            <CardHeader>
              <CardTitle>Cloud Run Services by User</CardTitle>
              <CardDescription>Active distributed consensus deployments</CardDescription>
            </CardHeader>
            <CardContent>
              {!gcpResources || gcpResources.resources_by_user.length === 0 ? (
                <p className="text-muted-foreground text-center py-8">
                  No active GCP resources
                </p>
              ) : (
                <div className="space-y-6">
                  {gcpResources.resources_by_user.map((userRes) => (
                    <div key={userRes.user_id} className="border rounded-lg p-4 space-y-3">
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-3">
                          <div className="p-2 bg-blue-500/10 rounded-lg">
                            <Users className="h-5 w-5 text-blue-500" />
                          </div>
                          <div>
                            <p className="font-medium">{userRes.user_email}</p>
                            <p className="text-sm text-muted-foreground">
                              {userRes.active_cloud_run_services} service(s), {userRes.total_cluster_nodes} node(s)
                            </p>
                          </div>
                        </div>
                      </div>

                      {/* User's submissions */}
                      <div className="pl-11 space-y-2">
                        {userRes.distributed_submissions.map((sub) => {
                          const hasNodes = sub.cluster_node_urls.length > 0
                          return (
                            <div
                              key={sub.submission_id}
                              className="p-3 bg-muted/50 rounded-lg"
                            >
                              <div className="flex items-center justify-between">
                                <div className="flex items-center gap-2">
                                  <Server className={`h-4 w-4 ${hasNodes ? "text-green-500" : "text-muted-foreground"}`} />
                                  <span className="text-sm font-medium">
                                    Submission #{sub.submission_id}
                                  </span>
                                  <Badge variant="outline" className="text-xs">
                                    {sub.language}
                                  </Badge>
                                </div>
                                <Badge variant={hasNodes ? "default" : "secondary"}>
                                  {sub.status}
                                </Badge>
                              </div>
                              {hasNodes && (
                                <div className="mt-2 space-y-1">
                                  {sub.cluster_node_urls.map((url, idx) => (
                                    <div key={idx} className="flex items-center gap-2 text-xs text-muted-foreground">
                                      <Cloud className="h-3 w-3" />
                                      <code className="bg-background px-1 rounded">{url}</code>
                                    </div>
                                  ))}
                                </div>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    </div>
                  ))}
                </div>
              )}
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
                  <>Total storage: {storage.total_size_formatted} ({storage.images.length} images)</>
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
                  {storage.images.slice(0, 20).map((image, idx) => (
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
                            {image.tags && image.tags.length > 0 && (
                              <span> · Tags: {image.tags.join(", ")}</span>
                            )}
                          </p>
                        </div>
                      </div>
                      <Badge variant="secondary">{image.size_formatted}</Badge>
                    </div>
                  ))}
                  {storage.images.length > 20 && (
                    <p className="text-xs text-muted-foreground text-center">
                      +{storage.images.length - 20} more images
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

        <TabsContent value="users" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Usage by User</CardTitle>
              <CardDescription>
                Top users by cost ({(usage?.by_user || []).length} users shown)
              </CardDescription>
            </CardHeader>
            <CardContent>
              {(usage?.by_user || []).length === 0 ? (
                <p className="text-muted-foreground text-center py-8">
                  No user data for this period
                </p>
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b">
                        <th className="text-left py-3 px-2 font-medium">User</th>
                        <th className="text-right py-3 px-2 font-medium">Cost</th>
                        <th className="text-right py-3 px-2 font-medium">Actions</th>
                        <th className="text-right py-3 px-2 font-medium">Input Tokens</th>
                        <th className="text-right py-3 px-2 font-medium">Output Tokens</th>
                      </tr>
                    </thead>
                    <tbody>
                      {(usage?.by_user || []).map((user, index) => (
                        <tr
                          key={user.user_id}
                          className={`border-b last:border-0 ${
                            index < 3 ? "bg-muted/30" : ""
                          }`}
                        >
                          <td className="py-3 px-2">
                            <div>
                              <p className="font-medium">{user.email}</p>
                              {user.name && (
                                <p className="text-sm text-muted-foreground">
                                  {user.name}
                                </p>
                              )}
                            </div>
                          </td>
                          <td className="text-right py-3 px-2">
                            <Badge
                              variant={user.total_cost_usd > 1 ? "default" : "secondary"}
                            >
                              {formatCost(user.total_cost_usd)}
                            </Badge>
                          </td>
                          <td className="text-right py-3 px-2 text-muted-foreground">
                            {formatNumber(user.total_actions)}
                          </td>
                          <td className="text-right py-3 px-2 text-muted-foreground">
                            {formatNumber(user.ai_input_tokens)}
                          </td>
                          <td className="text-right py-3 px-2 text-muted-foreground">
                            {formatNumber(user.ai_output_tokens)}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="activity" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Recent Activity</CardTitle>
              <CardDescription>
                Latest actions across all users ({activity?.total_actions || 0} total,{" "}
                {activity?.total_users || 0} active users)
              </CardDescription>
            </CardHeader>
            <CardContent>
              {(activity?.recent_items || []).length === 0 ? (
                <p className="text-muted-foreground text-center py-8">
                  No activity in this period
                </p>
              ) : (
                <div className="space-y-2 max-h-[600px] overflow-y-auto">
                  {(activity?.recent_items || []).map((item) => (
                    <div
                      key={item.id}
                      className="flex items-center justify-between py-3 border-b last:border-0"
                    >
                      <div className="flex items-center gap-3">
                        <Activity className="h-4 w-4 text-muted-foreground" />
                        <div>
                          <p className="text-sm font-medium">
                            {formatAction(item.action)}
                          </p>
                          <p className="text-xs text-muted-foreground">
                            {item.request_path || "N/A"}
                            {item.details?.user_id !== undefined && (
                              <span className="ml-2">
                                (User: {String(item.details.user_id)})
                              </span>
                            )}
                          </p>
                        </div>
                      </div>
                      <div className="text-right">
                        <Badge
                          variant={
                            item.response_status && item.response_status >= 400
                              ? "destructive"
                              : item.response_status && item.response_status >= 200
                              ? "secondary"
                              : "outline"
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
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
