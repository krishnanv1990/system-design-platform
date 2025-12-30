/**
 * Admin Dashboard
 * Shows all deployed GCP assets across all candidates
 */

import { useState, useEffect } from "react"
import { Link } from "react-router-dom"
import {
  ArrowLeft,
  Cloud,
  Server,
  Users,
  Clock,
  ExternalLink,
  RefreshCw,
  AlertTriangle,
  CheckCircle,
  XCircle,
  DollarSign,
  Trash2,
  Loader2,
} from "lucide-react"
import { assetsApi, adminApi } from "@/api/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"

interface GCPAsset {
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
  }
}

interface AdminAssetsSummary {
  total_submissions: number
  active_deployments: number
  total_cost_estimate: string
  assets: GCPAsset[]
}

function AdminSkeleton() {
  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <Skeleton className="h-8 w-48" />
      <div className="grid gap-4 md:grid-cols-4">
        {[1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-24" />
        ))}
      </div>
      <Skeleton className="h-64" />
    </div>
  )
}

const statusColors: Record<string, string> = {
  completed: "text-green-600",
  testing: "text-yellow-600",
  deploying: "text-blue-600",
  failed: "text-red-600",
  deploy_failed: "text-red-600",
  pending: "text-gray-600",
}

const statusIcons: Record<string, React.ElementType> = {
  completed: CheckCircle,
  testing: Clock,
  deploying: RefreshCw,
  failed: XCircle,
  deploy_failed: XCircle,
  pending: Clock,
}

export default function AdminDashboard() {
  const [summary, setSummary] = useState<AdminAssetsSummary | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [deletingIds, setDeletingIds] = useState<Set<number>>(new Set())
  const [deletingAll, setDeletingAll] = useState(false)

  const loadData = async () => {
    try {
      const data = await assetsApi.getAllAssets()
      setSummary(data)
      setError(null)
    } catch (err: any) {
      if (err.response?.status === 403) {
        setError("Admin access required. Please contact the administrator.")
      } else {
        setError("Failed to load GCP assets.")
      }
      console.error("Failed to load assets:", err)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  const handleRefresh = () => {
    setRefreshing(true)
    loadData()
  }

  const handleDelete = async (submissionId: number) => {
    if (!confirm(`Are you sure you want to delete deployment #${submissionId}? This action cannot be undone.`)) {
      return
    }

    setDeletingIds((prev) => new Set(prev).add(submissionId))
    try {
      await adminApi.teardownDeployment(submissionId)
      // Reload data after deletion
      await loadData()
    } catch (err: any) {
      console.error("Failed to delete deployment:", err)
      alert(`Failed to delete deployment: ${err.response?.data?.detail || err.message}`)
    } finally {
      setDeletingIds((prev) => {
        const next = new Set(prev)
        next.delete(submissionId)
        return next
      })
    }
  }

  const handleDeleteAll = async () => {
    if (!confirm("Are you sure you want to delete ALL deployments? This action cannot be undone!")) {
      return
    }

    setDeletingAll(true)
    try {
      const result = await adminApi.teardownAllDeployments()
      alert(`Cleaned up ${result.cleaned_up} deployments. ${result.failed} failed.`)
      await loadData()
    } catch (err: any) {
      console.error("Failed to delete all deployments:", err)
      alert(`Failed to delete all deployments: ${err.response?.data?.detail || err.message}`)
    } finally {
      setDeletingAll(false)
    }
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString()
  }

  if (loading) {
    return <AdminSkeleton />
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
              Back to problems
            </Link>
          </Button>
        </div>
      </div>
    )
  }

  if (!summary) {
    return (
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col items-center justify-center py-12">
          <AlertTriangle className="h-12 w-12 text-warning mb-4" />
          <p className="text-muted-foreground font-medium mb-4">No data available</p>
          <Button asChild variant="outline">
            <Link to="/problems">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to problems
            </Link>
          </Button>
        </div>
      </div>
    )
  }

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <Button asChild variant="ghost" size="sm" className="mb-2">
          <Link to="/problems">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to problems
          </Link>
        </Button>
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Cloud className="h-6 w-6" />
            GCP Admin Dashboard
          </h1>
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
            <div className="flex items-center gap-4">
              <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                <Server className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Total Submissions</p>
                <p className="text-2xl font-bold">{summary.total_submissions}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-lg">
                <CheckCircle className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Active Deployments</p>
                <p className="text-2xl font-bold">{summary.active_deployments}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                <Users className="h-6 w-6 text-purple-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Unique Users</p>
                <p className="text-2xl font-bold">
                  {new Set(summary.assets.map((a) => a.user_email)).size}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-yellow-100 dark:bg-yellow-900/30 rounded-lg">
                <DollarSign className="h-6 w-6 text-yellow-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Est. Cost</p>
                <p className="text-lg font-bold truncate" title={summary.total_cost_estimate}>
                  {summary.total_cost_estimate.split(" ")[0]}
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Assets Table */}
      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle className="text-base">All Deployments</CardTitle>
          {summary.assets.length > 0 && (
            <Button
              variant="destructive"
              size="sm"
              onClick={handleDeleteAll}
              disabled={deletingAll}
            >
              {deletingAll ? (
                <Loader2 className="h-4 w-4 mr-2 animate-spin" />
              ) : (
                <Trash2 className="h-4 w-4 mr-2" />
              )}
              Delete All
            </Button>
          )}
        </CardHeader>
        <CardContent>
          {summary.assets.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              No deployments found
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-3 px-2 font-medium">ID</th>
                    <th className="text-left py-3 px-2 font-medium">User</th>
                    <th className="text-left py-3 px-2 font-medium">Service</th>
                    <th className="text-left py-3 px-2 font-medium">Status</th>
                    <th className="text-left py-3 px-2 font-medium">Created</th>
                    <th className="text-left py-3 px-2 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {summary.assets.map((asset) => {
                    const StatusIcon = statusIcons[asset.status] || Clock
                    return (
                      <tr key={asset.submission_id} className="border-b hover:bg-muted/50">
                        <td className="py-3 px-2">
                          <Link
                            to={`/submissions/${asset.submission_id}/results`}
                            className="text-primary hover:underline"
                          >
                            #{asset.submission_id}
                          </Link>
                        </td>
                        <td className="py-3 px-2">
                          <span className="truncate max-w-[200px] block" title={asset.user_email}>
                            {asset.user_email}
                          </span>
                        </td>
                        <td className="py-3 px-2 font-mono text-xs">
                          {asset.service_name || "-"}
                        </td>
                        <td className="py-3 px-2">
                          <Badge
                            variant={
                              asset.status === "completed"
                                ? "success"
                                : asset.status.includes("failed")
                                ? "destructive"
                                : "secondary"
                            }
                            className="flex items-center gap-1 w-fit"
                          >
                            <StatusIcon className={`h-3 w-3 ${statusColors[asset.status] || ""}`} />
                            {asset.status}
                          </Badge>
                        </td>
                        <td className="py-3 px-2 text-muted-foreground">
                          {formatDate(asset.created_at)}
                        </td>
                        <td className="py-3 px-2">
                          <div className="flex gap-2">
                            {asset.console_links.cloud_run_service && (
                              <a
                                href={asset.console_links.cloud_run_service}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-primary hover:underline flex items-center gap-1"
                              >
                                <Server className="h-3 w-3" />
                                <span className="hidden sm:inline">Console</span>
                              </a>
                            )}
                            {asset.endpoint_url && (
                              <a
                                href={asset.endpoint_url}
                                target="_blank"
                                rel="noopener noreferrer"
                                className="text-primary hover:underline flex items-center gap-1"
                              >
                                <ExternalLink className="h-3 w-3" />
                                <span className="hidden sm:inline">Endpoint</span>
                              </a>
                            )}
                            <Button
                              variant="ghost"
                              size="sm"
                              className="h-6 px-2 text-destructive hover:text-destructive hover:bg-destructive/10"
                              onClick={() => handleDelete(asset.submission_id)}
                              disabled={deletingIds.has(asset.submission_id)}
                            >
                              {deletingIds.has(asset.submission_id) ? (
                                <Loader2 className="h-3 w-3 animate-spin" />
                              ) : (
                                <Trash2 className="h-3 w-3" />
                              )}
                            </Button>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Quick Links */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Quick Links</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid gap-3 md:grid-cols-3">
            <a
              href={`https://console.cloud.google.com/run?project=system-design-platform-prod`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 p-3 bg-muted/50 rounded-lg hover:bg-muted transition-colors"
            >
              <Server className="h-4 w-4 text-blue-500" />
              <span>All Cloud Run Services</span>
              <ExternalLink className="h-3 w-3 ml-auto text-muted-foreground" />
            </a>
            <a
              href={`https://console.cloud.google.com/cloud-build/builds?project=system-design-platform-prod`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 p-3 bg-muted/50 rounded-lg hover:bg-muted transition-colors"
            >
              <Cloud className="h-4 w-4 text-orange-500" />
              <span>Cloud Build History</span>
              <ExternalLink className="h-3 w-3 ml-auto text-muted-foreground" />
            </a>
            <a
              href={`https://console.cloud.google.com/artifacts?project=system-design-platform-prod`}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-2 p-3 bg-muted/50 rounded-lg hover:bg-muted transition-colors"
            >
              <Cloud className="h-4 w-4 text-purple-500" />
              <span>Artifact Registry</span>
              <ExternalLink className="h-3 w-3 ml-auto text-muted-foreground" />
            </a>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
