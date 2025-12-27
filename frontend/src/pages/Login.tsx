/**
 * Login page with Google OAuth
 *
 * UX Features:
 * - Displays authentication errors from URL params
 * - Shows session expiry message when redirected
 * - Accessible form with proper labels
 */

import { useEffect, useState } from "react"
import { useSearchParams, useNavigate } from "react-router-dom"
import { CheckCircle, AlertCircle, Info } from "lucide-react"
import { authApi } from "@/api/client"
import { useAuth } from "@/components/AuthContext"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

// Error message mapping for user-friendly display
const errorMessages: Record<string, { title: string; message: string }> = {
  auth_failed: {
    title: "Authentication Failed",
    message: "We couldn't sign you in. Please try again.",
  },
  access_denied: {
    title: "Access Denied",
    message: "You denied access to your Google account. Please try again if this was a mistake.",
  },
  session_expired: {
    title: "Session Expired",
    message: "Your session has expired. Please sign in again to continue.",
  },
  token_invalid: {
    title: "Invalid Token",
    message: "Your authentication token is invalid. Please sign in again.",
  },
  server_error: {
    title: "Server Error",
    message: "Something went wrong on our end. Please try again later.",
  },
}

export default function Login() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const { user, demoMode } = useAuth()
  const [error, setError] = useState<{ title: string; message: string } | null>(null)
  const [info, setInfo] = useState<string | null>(null)

  // Check for error or info params in URL
  useEffect(() => {
    const errorCode = searchParams.get("error")
    const reason = searchParams.get("reason")

    if (errorCode) {
      const errorInfo = errorMessages[errorCode] || {
        title: "Authentication Error",
        message: errorCode,
      }
      setError(errorInfo)
    }

    if (reason === "session_expired") {
      setInfo("Your session has expired. Please sign in again.")
    }
  }, [searchParams])

  // Redirect if already logged in
  useEffect(() => {
    if (user || demoMode) {
      navigate("/problems", { replace: true })
    }
  }, [user, demoMode, navigate])

  const handleGoogleLogin = () => {
    // Clear any existing errors
    setError(null)
    setInfo(null)
    window.location.href = authApi.getGoogleAuthUrl()
  }

  const features = [
    "Real system design problems from top tech companies",
    "AI-powered validation of your designs",
    "Automatic infrastructure deployment to GCP",
    "Functional, performance, and chaos testing",
    "Detailed feedback and scoring",
  ]

  return (
    <div className="min-h-screen flex items-center justify-center bg-background py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold text-primary">System Design Platform</h1>
          <h2 className="mt-6 text-2xl font-bold">Master System Design Interviews</h2>
          <p className="mt-2 text-sm text-muted-foreground">
            Practice with real-world problems, get AI-powered feedback, and validate your designs
            with actual infrastructure deployment.
          </p>
        </div>

        {/* Error message */}
        {error && (
          <div
            className="flex items-start gap-3 p-4 rounded-lg bg-destructive/10 border border-destructive/30 text-destructive"
            role="alert"
            aria-live="polite"
          >
            <AlertCircle className="h-5 w-5 shrink-0 mt-0.5" aria-hidden="true" />
            <div>
              <p className="font-medium">{error.title}</p>
              <p className="text-sm mt-1 opacity-90">{error.message}</p>
            </div>
          </div>
        )}

        {/* Info message */}
        {info && !error && (
          <div
            className="flex items-start gap-3 p-4 rounded-lg bg-blue-500/10 border border-blue-500/30 text-blue-700 dark:text-blue-300"
            role="status"
            aria-live="polite"
          >
            <Info className="h-5 w-5 shrink-0 mt-0.5" aria-hidden="true" />
            <p className="text-sm">{info}</p>
          </div>
        )}

        <Card>
          <CardHeader className="text-center">
            <CardTitle>Get Started</CardTitle>
            <CardDescription>Sign in to start practicing</CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              onClick={handleGoogleLogin}
              variant="outline"
              className="w-full h-12"
              aria-label="Sign in with Google"
            >
              <svg className="w-5 h-5 mr-3" viewBox="0 0 24 24" aria-hidden="true">
                <path
                  fill="#4285F4"
                  d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                />
                <path
                  fill="#34A853"
                  d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                />
                <path
                  fill="#FBBC05"
                  d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                />
                <path
                  fill="#EA4335"
                  d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                />
              </svg>
              Sign in with Google
            </Button>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-lg">Features</CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-3" aria-label="Platform features">
              {features.map((feature, index) => (
                <li key={index} className="flex items-start gap-3 text-sm text-muted-foreground">
                  <CheckCircle className="h-4 w-4 text-success mt-0.5 flex-shrink-0" aria-hidden="true" />
                  <span>{feature}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
