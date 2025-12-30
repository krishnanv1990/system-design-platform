/**
 * Admin User Management
 * View all users, filter by status, and manage bans
 */

import { useState, useEffect } from "react"
import { Link } from "react-router-dom"
import {
  ArrowLeft,
  Users,
  Shield,
  ShieldOff,
  RefreshCw,
  AlertTriangle,
  Search,
  Filter,
} from "lucide-react"
import { adminApi, AdminUser } from "@/api/client"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { useConfirm } from "@/components/ui/confirm-dialog"

type FilterOption = "all" | "active" | "banned" | "admin"

function AdminUserManagementSkeleton() {
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

export default function AdminUserManagement() {
  const [users, setUsers] = useState<AdminUser[]>([])
  const [filteredUsers, setFilteredUsers] = useState<AdminUser[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [refreshing, setRefreshing] = useState(false)
  const [filter, setFilter] = useState<FilterOption>("all")
  const [searchQuery, setSearchQuery] = useState("")
  const [actionLoading, setActionLoading] = useState<number | null>(null)
  const confirm = useConfirm()

  const loadData = async () => {
    try {
      const data = await adminApi.listUsers()
      setUsers(data)
      setError(null)
    } catch (err: any) {
      if (err.response?.status === 403) {
        setError("Admin access required. Please contact the administrator.")
      } else {
        setError("Failed to load users.")
      }
      console.error("Failed to load users:", err)
    } finally {
      setLoading(false)
      setRefreshing(false)
    }
  }

  useEffect(() => {
    loadData()
  }, [])

  useEffect(() => {
    let result = users

    // Apply filter
    switch (filter) {
      case "active":
        result = result.filter((u) => !u.is_banned)
        break
      case "banned":
        result = result.filter((u) => u.is_banned)
        break
      case "admin":
        result = result.filter((u) => u.is_admin)
        break
    }

    // Apply search
    if (searchQuery.trim()) {
      const query = searchQuery.toLowerCase()
      result = result.filter(
        (u) =>
          u.email.toLowerCase().includes(query) ||
          u.name?.toLowerCase().includes(query) ||
          u.display_name?.toLowerCase().includes(query)
      )
    }

    setFilteredUsers(result)
  }, [users, filter, searchQuery])

  const handleRefresh = () => {
    setRefreshing(true)
    loadData()
  }

  const handleUnban = async (user: AdminUser) => {
    const confirmed = await confirm({
      title: "Unban User",
      message: `Are you sure you want to unban ${user.email}? They will be able to use the platform again.`,
      confirmLabel: "Unban",
      cancelLabel: "Cancel",
    })

    if (!confirmed) return

    setActionLoading(user.id)
    try {
      await adminApi.unbanUser({ user_id: user.id, reason: "Unbanned by admin" })
      await loadData()
    } catch (err: any) {
      console.error("Failed to unban user:", err)
      setError(err.response?.data?.detail || "Failed to unban user")
    } finally {
      setActionLoading(null)
    }
  }

  const handleBan = async (user: AdminUser) => {
    const reason = window.prompt(`Enter reason for banning ${user.email}:`)
    if (!reason) return

    const confirmed = await confirm({
      title: "Ban User",
      message: `Are you sure you want to ban ${user.email}? Reason: ${reason}`,
      confirmLabel: "Ban",
      cancelLabel: "Cancel",
      type: "danger",
    })

    if (!confirmed) return

    setActionLoading(user.id)
    try {
      await adminApi.banUser(user.id, reason)
      await loadData()
    } catch (err: any) {
      console.error("Failed to ban user:", err)
      setError(err.response?.data?.detail || "Failed to ban user")
    } finally {
      setActionLoading(null)
    }
  }

  const formatDate = (dateStr: string) => {
    return new Date(dateStr).toLocaleString()
  }

  // Calculate stats
  const stats = {
    total: users.length,
    active: users.filter((u) => !u.is_banned).length,
    banned: users.filter((u) => u.is_banned).length,
    admins: users.filter((u) => u.is_admin).length,
  }

  if (loading) {
    return <AdminUserManagementSkeleton />
  }

  if (error) {
    return (
      <div className="max-w-6xl mx-auto">
        <div className="flex flex-col items-center justify-center py-12">
          <AlertTriangle className="h-12 w-12 text-destructive mb-4" />
          <p className="text-destructive font-medium mb-4">{error}</p>
          <Button asChild variant="outline">
            <Link to="/dashboard">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to dashboard
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
          <Link to="/dashboard">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back to dashboard
          </Link>
        </Button>
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold flex items-center gap-2">
            <Users className="h-6 w-6" />
            User Management
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

      {/* Stats Cards */}
      <div className="grid gap-4 md:grid-cols-4">
        <Card
          className={`cursor-pointer transition-colors ${
            filter === "all" ? "ring-2 ring-primary" : ""
          }`}
          onClick={() => setFilter("all")}
        >
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-blue-100 dark:bg-blue-900/30 rounded-lg">
                <Users className="h-6 w-6 text-blue-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Total Users</p>
                <p className="text-2xl font-bold">{stats.total}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card
          className={`cursor-pointer transition-colors ${
            filter === "active" ? "ring-2 ring-primary" : ""
          }`}
          onClick={() => setFilter("active")}
        >
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-green-100 dark:bg-green-900/30 rounded-lg">
                <Shield className="h-6 w-6 text-green-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Active Users</p>
                <p className="text-2xl font-bold">{stats.active}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card
          className={`cursor-pointer transition-colors ${
            filter === "banned" ? "ring-2 ring-primary" : ""
          }`}
          onClick={() => setFilter("banned")}
        >
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-red-100 dark:bg-red-900/30 rounded-lg">
                <ShieldOff className="h-6 w-6 text-red-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Banned Users</p>
                <p className="text-2xl font-bold">{stats.banned}</p>
              </div>
            </div>
          </CardContent>
        </Card>

        <Card
          className={`cursor-pointer transition-colors ${
            filter === "admin" ? "ring-2 ring-primary" : ""
          }`}
          onClick={() => setFilter("admin")}
        >
          <CardContent className="pt-6">
            <div className="flex items-center gap-4">
              <div className="p-3 bg-purple-100 dark:bg-purple-900/30 rounded-lg">
                <Shield className="h-6 w-6 text-purple-600" />
              </div>
              <div>
                <p className="text-sm text-muted-foreground">Admins</p>
                <p className="text-2xl font-bold">{stats.admins}</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Search and Filters */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex gap-4 items-center">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <input
                type="text"
                placeholder="Search by email or name..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div className="flex items-center gap-2">
              <Filter className="h-4 w-4 text-muted-foreground" />
              <select
                value={filter}
                onChange={(e) => setFilter(e.target.value as FilterOption)}
                className="px-3 py-2 border rounded-md bg-background focus:outline-none focus:ring-2 focus:ring-primary"
              >
                <option value="all">All Users</option>
                <option value="active">Active Only</option>
                <option value="banned">Banned Only</option>
                <option value="admin">Admins Only</option>
              </select>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Users Table */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">
            Users ({filteredUsers.length})
          </CardTitle>
        </CardHeader>
        <CardContent>
          {filteredUsers.length === 0 ? (
            <p className="text-center text-muted-foreground py-8">
              No users found
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left py-3 px-2 font-medium">ID</th>
                    <th className="text-left py-3 px-2 font-medium">Email</th>
                    <th className="text-left py-3 px-2 font-medium">Name</th>
                    <th className="text-left py-3 px-2 font-medium">Status</th>
                    <th className="text-left py-3 px-2 font-medium">Created</th>
                    <th className="text-left py-3 px-2 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredUsers.map((user) => (
                    <tr key={user.id} className="border-b hover:bg-muted/50">
                      <td className="py-3 px-2">#{user.id}</td>
                      <td className="py-3 px-2">
                        <span
                          className="truncate max-w-[200px] block"
                          title={user.email}
                        >
                          {user.email}
                        </span>
                      </td>
                      <td className="py-3 px-2">
                        {user.display_name || user.name || "-"}
                      </td>
                      <td className="py-3 px-2">
                        <div className="flex gap-1">
                          {user.is_admin && (
                            <Badge variant="secondary">Admin</Badge>
                          )}
                          {user.is_banned ? (
                            <Badge variant="destructive" title={user.ban_reason || undefined}>
                              Banned
                            </Badge>
                          ) : (
                            <Badge variant="success">Active</Badge>
                          )}
                        </div>
                      </td>
                      <td className="py-3 px-2 text-muted-foreground">
                        {formatDate(user.created_at)}
                      </td>
                      <td className="py-3 px-2">
                        <div className="flex gap-2">
                          {user.is_banned ? (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleUnban(user)}
                              disabled={actionLoading === user.id}
                            >
                              {actionLoading === user.id ? (
                                <RefreshCw className="h-3 w-3 animate-spin" />
                              ) : (
                                "Unban"
                              )}
                            </Button>
                          ) : (
                            !user.is_admin && (
                              <Button
                                variant="destructive"
                                size="sm"
                                onClick={() => handleBan(user)}
                                disabled={actionLoading === user.id}
                              >
                                {actionLoading === user.id ? (
                                  <RefreshCw className="h-3 w-3 animate-spin" />
                                ) : (
                                  "Ban"
                                )}
                              </Button>
                            )
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Banned Users Details */}
      {stats.banned > 0 && filter === "banned" && (
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Ban Details</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {filteredUsers.map((user) => (
                <div
                  key={user.id}
                  className="p-4 border rounded-lg bg-muted/30"
                >
                  <div className="flex justify-between items-start">
                    <div>
                      <p className="font-medium">{user.email}</p>
                      <p className="text-sm text-muted-foreground">
                        Banned on: {user.banned_at ? formatDate(user.banned_at) : "Unknown"}
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleUnban(user)}
                      disabled={actionLoading === user.id}
                    >
                      {actionLoading === user.id ? (
                        <RefreshCw className="h-3 w-3 animate-spin mr-1" />
                      ) : null}
                      Unban
                    </Button>
                  </div>
                  {user.ban_reason && (
                    <p className="mt-2 text-sm p-2 bg-destructive/10 rounded border border-destructive/20">
                      <strong>Reason:</strong> {user.ban_reason}
                    </p>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
