/**
 * Account Settings page
 *
 * Allows users to:
 * - View their account information
 * - See linked OAuth providers
 * - Download their data
 * - Delete their account and all data
 */

import { useState } from "react"
import { Link, useNavigate } from "react-router-dom"
import {
  ArrowLeft,
  Settings,
  User,
  Shield,
  Trash2,
  Download,
  AlertTriangle,
  CheckCircle,
  Loader2,
} from "lucide-react"
import { useAuth } from "@/components/AuthContext"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { useConfirm } from "@/components/ui/confirm-dialog"
import { authApi } from "@/api/client"

export default function AccountSettings() {
  const { user, logout, demoMode } = useAuth()
  const navigate = useNavigate()
  const confirm = useConfirm()
  const [deleting, setDeleting] = useState(false)
  const [downloading, setDownloading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [success, setSuccess] = useState<string | null>(null)

  const handleDownloadData = async () => {
    setDownloading(true)
    setError(null)
    setSuccess(null)

    try {
      const data = await authApi.downloadUserData()

      // Create a downloadable JSON file
      const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" })
      const url = URL.createObjectURL(blob)
      const link = document.createElement("a")
      link.href = url
      link.download = `system-design-platform-data-${new Date().toISOString().split("T")[0]}.json`
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      URL.revokeObjectURL(url)

      setSuccess("Your data has been downloaded successfully.")
    } catch (err) {
      setError("Failed to download data. Please try again.")
      console.error("Download error:", err)
    } finally {
      setDownloading(false)
    }
  }

  const handleDeleteAccount = async () => {
    // First confirmation
    const firstConfirm = await confirm({
      title: "Delete Account",
      message:
        "Are you sure you want to delete your account? This will permanently remove all your data including submissions, diagrams, and chat history.",
      type: "danger",
      confirmLabel: "Continue",
    })

    if (!firstConfirm) return

    // Second confirmation for extra safety
    const secondConfirm = await confirm({
      title: "Final Confirmation",
      message:
        "This action is IRREVERSIBLE. All your data will be permanently deleted and cannot be recovered. Type DELETE to confirm.",
      type: "danger",
      confirmLabel: "Delete Everything",
    })

    if (!secondConfirm) return

    setDeleting(true)
    setError(null)

    try {
      await authApi.deleteAccount()
      logout()
      navigate("/login", {
        state: { message: "Your account has been successfully deleted." },
      })
    } catch (err) {
      setError("Failed to delete account. Please try again or contact support.")
      console.error("Delete error:", err)
      setDeleting(false)
    }
  }

  // If in demo mode or no user, show limited view
  if (demoMode) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <div>
          <Button asChild variant="ghost" size="sm" className="mb-4">
            <Link to="/problems">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back
            </Link>
          </Button>
          <div className="flex items-center gap-3 mb-2">
            <Settings className="h-8 w-8 text-primary" />
            <h1 className="text-3xl font-bold">Account Settings</h1>
          </div>
        </div>

        <Card className="border-amber-500/30 bg-amber-500/5">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <AlertTriangle className="h-5 w-5 text-amber-500" />
              <p className="text-muted-foreground">
                Account settings are not available in demo mode. Sign in with a real account to
                access these features.
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  if (!user) {
    navigate("/login")
    return null
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <Button asChild variant="ghost" size="sm" className="mb-4">
          <Link to="/problems">
            <ArrowLeft className="mr-2 h-4 w-4" />
            Back
          </Link>
        </Button>
        <div className="flex items-center gap-3 mb-2">
          <Settings className="h-8 w-8 text-primary" />
          <h1 className="text-3xl font-bold">Account Settings</h1>
        </div>
        <p className="text-muted-foreground">Manage your account and data preferences</p>
      </div>

      {/* Success/Error messages */}
      {success && (
        <Card className="border-green-500/30 bg-green-500/5">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <CheckCircle className="h-5 w-5 text-green-500" />
              <p className="text-green-700 dark:text-green-300">{success}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {error && (
        <Card className="border-destructive/30 bg-destructive/5">
          <CardContent className="pt-6">
            <div className="flex items-center gap-3">
              <AlertTriangle className="h-5 w-5 text-destructive" />
              <p className="text-destructive">{error}</p>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Profile Information */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <User className="h-5 w-5 text-primary" />
            Profile Information
          </CardTitle>
          <CardDescription>Your account details from OAuth provider</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center gap-4">
            {user.avatar_url ? (
              <img
                src={user.avatar_url}
                alt={user.name || "Profile"}
                className="w-16 h-16 rounded-full ring-2 ring-border"
              />
            ) : (
              <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center">
                <User className="h-8 w-8 text-muted-foreground" />
              </div>
            )}
            <div>
              <p className="font-medium text-lg">{user.name || "No name set"}</p>
              <p className="text-muted-foreground">{user.email}</p>
            </div>
          </div>

          <div className="pt-4 border-t">
            <p className="text-sm font-medium mb-2">Linked Accounts</p>
            <div className="flex flex-wrap gap-2">
              {user.google_id && <Badge variant="secondary">Google</Badge>}
              {user.facebook_id && <Badge variant="secondary">Facebook</Badge>}
              {user.linkedin_id && <Badge variant="secondary">LinkedIn</Badge>}
              {user.github_id && <Badge variant="secondary">GitHub</Badge>}
            </div>
          </div>

          <div className="pt-4 border-t">
            <p className="text-sm text-muted-foreground">
              Account created: {new Date(user.created_at).toLocaleDateString()}
            </p>
          </div>
        </CardContent>
      </Card>

      {/* Data Management */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-primary" />
            Data Management
          </CardTitle>
          <CardDescription>Download or delete your data</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Download Data */}
          <div className="flex items-center justify-between p-4 border rounded-lg">
            <div>
              <p className="font-medium">Download Your Data</p>
              <p className="text-sm text-muted-foreground">
                Get a copy of all your submissions, designs, and account data
              </p>
            </div>
            <Button
              variant="outline"
              onClick={handleDownloadData}
              disabled={downloading}
            >
              {downloading ? (
                <>
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  Downloading...
                </>
              ) : (
                <>
                  <Download className="mr-2 h-4 w-4" />
                  Download
                </>
              )}
            </Button>
          </div>

          {/* Data info */}
          <div className="p-4 bg-muted/50 rounded-lg">
            <p className="text-sm text-muted-foreground">
              Your data download includes:
            </p>
            <ul className="text-sm text-muted-foreground mt-2 ml-4 list-disc">
              <li>Account information and profile</li>
              <li>All design submissions and diagrams</li>
              <li>Chat history with AI coach</li>
              <li>Test results and scores</li>
            </ul>
          </div>
        </CardContent>
      </Card>

      {/* Delete Account */}
      <Card className="border-destructive/30">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <Trash2 className="h-5 w-5" />
            Delete Account
          </CardTitle>
          <CardDescription>Permanently delete your account and all data</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="p-4 bg-destructive/5 rounded-lg border border-destructive/20">
            <div className="flex items-start gap-3">
              <AlertTriangle className="h-5 w-5 text-destructive shrink-0 mt-0.5" />
              <div className="text-sm">
                <p className="font-medium text-destructive">Warning: This action is irreversible</p>
                <p className="text-muted-foreground mt-1">
                  Deleting your account will permanently remove:
                </p>
                <ul className="text-muted-foreground mt-2 ml-4 list-disc">
                  <li>Your user profile and account</li>
                  <li>All submissions and design diagrams</li>
                  <li>Chat history and AI coaching conversations</li>
                  <li>Test results and evaluation scores</li>
                </ul>
              </div>
            </div>
          </div>

          <Button
            variant="destructive"
            onClick={handleDeleteAccount}
            disabled={deleting}
            className="w-full"
          >
            {deleting ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Deleting Account...
              </>
            ) : (
              <>
                <Trash2 className="mr-2 h-4 w-4" />
                Delete My Account
              </>
            )}
          </Button>
        </CardContent>
      </Card>

      {/* Legal Links */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap justify-center gap-4 text-sm text-muted-foreground">
            <Link to="/terms" className="hover:text-primary hover:underline">
              Terms of Service
            </Link>
            <span>|</span>
            <Link to="/privacy" className="hover:text-primary hover:underline">
              Privacy Policy
            </Link>
            <span>|</span>
            <a
              href="mailto:support@systemdesignplatform.com"
              className="hover:text-primary hover:underline"
            >
              Contact Support
            </a>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
