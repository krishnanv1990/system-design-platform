/**
 * Login page with multiple OAuth providers
 *
 * Supports authentication via:
 * - Google
 * - Facebook
 * - LinkedIn
 * - GitHub
 *
 * UX Features:
 * - Displays authentication errors from URL params
 * - Shows session expiry message when redirected
 * - Accessible form with proper labels
 * - Provider buttons with brand colors
 */

import { useEffect, useState } from "react"
import { useSearchParams, useNavigate } from "react-router-dom"
import { CheckCircle, AlertCircle, Info } from "lucide-react"
import { authApi, OAuthProvider } from "@/api/client"
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
    message: "You denied access to your account. Please try again if this was a mistake.",
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

/**
 * OAuth Provider Button Configuration
 * Each provider has its own branding colors and icon
 */
interface ProviderConfig {
  name: string
  icon: React.ReactNode
  className: string
  ariaLabel: string
}

const providerConfigs: Record<OAuthProvider, ProviderConfig> = {
  google: {
    name: "Google",
    icon: (
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
    ),
    className: "bg-white hover:bg-gray-50 text-gray-700 border border-gray-300",
    ariaLabel: "Sign in with Google",
  },
  facebook: {
    name: "Facebook",
    icon: (
      <svg className="w-5 h-5 mr-3" viewBox="0 0 24 24" fill="white" aria-hidden="true">
        <path d="M24 12.073c0-6.627-5.373-12-12-12s-12 5.373-12 12c0 5.99 4.388 10.954 10.125 11.854v-8.385H7.078v-3.47h3.047V9.43c0-3.007 1.792-4.669 4.533-4.669 1.312 0 2.686.235 2.686.235v2.953H15.83c-1.491 0-1.956.925-1.956 1.874v2.25h3.328l-.532 3.47h-2.796v8.385C19.612 23.027 24 18.062 24 12.073z" />
      </svg>
    ),
    className: "bg-[#1877F2] hover:bg-[#166FE5] text-white",
    ariaLabel: "Sign in with Facebook",
  },
  linkedin: {
    name: "LinkedIn",
    icon: (
      <svg className="w-5 h-5 mr-3" viewBox="0 0 24 24" fill="white" aria-hidden="true">
        <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
      </svg>
    ),
    className: "bg-[#0A66C2] hover:bg-[#004182] text-white",
    ariaLabel: "Sign in with LinkedIn",
  },
  github: {
    name: "GitHub",
    icon: (
      <svg className="w-5 h-5 mr-3" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
        <path d="M12 0c-6.626 0-12 5.373-12 12 0 5.302 3.438 9.8 8.207 11.387.599.111.793-.261.793-.577v-2.234c-3.338.726-4.033-1.416-4.033-1.416-.546-1.387-1.333-1.756-1.333-1.756-1.089-.745.083-.729.083-.729 1.205.084 1.839 1.237 1.839 1.237 1.07 1.834 2.807 1.304 3.492.997.107-.775.418-1.305.762-1.604-2.665-.305-5.467-1.334-5.467-5.931 0-1.311.469-2.381 1.236-3.221-.124-.303-.535-1.524.117-3.176 0 0 1.008-.322 3.301 1.23.957-.266 1.983-.399 3.003-.404 1.02.005 2.047.138 3.006.404 2.291-1.552 3.297-1.23 3.297-1.23.653 1.653.242 2.874.118 3.176.77.84 1.235 1.911 1.235 3.221 0 4.609-2.807 5.624-5.479 5.921.43.372.823 1.102.823 2.222v3.293c0 .319.192.694.801.576 4.765-1.589 8.199-6.086 8.199-11.386 0-6.627-5.373-12-12-12z" />
      </svg>
    ),
    className: "bg-[#24292F] hover:bg-[#1B1F23] text-white",
    ariaLabel: "Sign in with GitHub",
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

  /**
   * Handle OAuth login for any provider
   */
  const handleOAuthLogin = (provider: OAuthProvider) => {
    // Clear any existing errors
    setError(null)
    setInfo(null)
    window.location.href = authApi.getAuthUrl(provider)
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
        {/* Header */}
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

        {/* Sign in card with OAuth buttons */}
        <Card>
          <CardHeader className="text-center">
            <CardTitle>Get Started</CardTitle>
            <CardDescription>Sign in with your preferred account</CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            {/* Google - Primary option */}
            <Button
              onClick={() => handleOAuthLogin("google")}
              variant="outline"
              className={`w-full h-12 ${providerConfigs.google.className}`}
              aria-label={providerConfigs.google.ariaLabel}
            >
              {providerConfigs.google.icon}
              Sign in with Google
            </Button>

            {/* Divider */}
            <div className="relative my-4">
              <div className="absolute inset-0 flex items-center">
                <span className="w-full border-t" />
              </div>
              <div className="relative flex justify-center text-xs uppercase">
                <span className="bg-background px-2 text-muted-foreground">Or continue with</span>
              </div>
            </div>

            {/* Other providers */}
            <div className="grid grid-cols-3 gap-3">
              {/* Facebook */}
              <Button
                onClick={() => handleOAuthLogin("facebook")}
                variant="outline"
                className={`h-12 ${providerConfigs.facebook.className}`}
                aria-label={providerConfigs.facebook.ariaLabel}
                title="Sign in with Facebook"
              >
                {providerConfigs.facebook.icon}
                <span className="sr-only">Facebook</span>
              </Button>

              {/* LinkedIn */}
              <Button
                onClick={() => handleOAuthLogin("linkedin")}
                variant="outline"
                className={`h-12 ${providerConfigs.linkedin.className}`}
                aria-label={providerConfigs.linkedin.ariaLabel}
                title="Sign in with LinkedIn"
              >
                {providerConfigs.linkedin.icon}
                <span className="sr-only">LinkedIn</span>
              </Button>

              {/* GitHub */}
              <Button
                onClick={() => handleOAuthLogin("github")}
                variant="outline"
                className={`h-12 ${providerConfigs.github.className}`}
                aria-label={providerConfigs.github.ariaLabel}
                title="Sign in with GitHub"
              >
                {providerConfigs.github.icon}
                <span className="sr-only">GitHub</span>
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Features card */}
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
