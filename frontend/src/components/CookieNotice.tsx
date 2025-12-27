/**
 * Cookie Notice Component
 *
 * Displays a cookie consent banner at the bottom of the screen.
 * Persists consent in localStorage.
 */

import { useState, useEffect } from "react"
import { Link } from "react-router-dom"
import { Cookie, X } from "lucide-react"
import { Button } from "@/components/ui/button"

const COOKIE_CONSENT_KEY = "cookie-consent-accepted"

export default function CookieNotice() {
  const [showBanner, setShowBanner] = useState(false)

  useEffect(() => {
    // Check if user has already accepted cookies
    const consent = localStorage.getItem(COOKIE_CONSENT_KEY)
    if (!consent) {
      // Slight delay to prevent flash on page load
      const timer = setTimeout(() => setShowBanner(true), 500)
      return () => clearTimeout(timer)
    }
  }, [])

  const handleAccept = () => {
    localStorage.setItem(COOKIE_CONSENT_KEY, "true")
    setShowBanner(false)
  }

  const handleDecline = () => {
    // Even if declined, we set a flag so we don't show the banner again
    localStorage.setItem(COOKIE_CONSENT_KEY, "essential-only")
    setShowBanner(false)
  }

  if (!showBanner) return null

  return (
    <div
      className="fixed bottom-0 left-0 right-0 z-50 bg-card border-t shadow-lg animate-in slide-in-from-bottom-4"
      role="dialog"
      aria-label="Cookie consent"
    >
      <div className="max-w-7xl mx-auto px-4 py-4 sm:px-6 lg:px-8">
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
          {/* Icon and text */}
          <div className="flex items-start gap-3 flex-1">
            <Cookie className="h-5 w-5 text-primary shrink-0 mt-0.5" aria-hidden="true" />
            <div className="text-sm text-muted-foreground">
              <p>
                We use cookies to enhance your experience on our platform. Essential cookies are
                required for the platform to function. Analytics cookies help us improve the
                service.
              </p>
              <p className="mt-1">
                Learn more in our{" "}
                <Link to="/privacy" className="text-primary hover:underline">
                  Privacy Policy
                </Link>
                .
              </p>
            </div>
          </div>

          {/* Buttons */}
          <div className="flex items-center gap-2 shrink-0 w-full sm:w-auto">
            <Button
              variant="outline"
              size="sm"
              onClick={handleDecline}
              className="flex-1 sm:flex-none"
            >
              Essential Only
            </Button>
            <Button
              size="sm"
              onClick={handleAccept}
              className="flex-1 sm:flex-none"
            >
              Accept All
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={handleDecline}
              className="h-8 w-8 sm:hidden"
              aria-label="Close cookie notice"
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
        </div>
      </div>
    </div>
  )
}

/**
 * Hook to check if user has consented to analytics cookies
 */
export function useAnalyticsConsent(): boolean {
  const [hasConsent, setHasConsent] = useState(false)

  useEffect(() => {
    const consent = localStorage.getItem(COOKIE_CONSENT_KEY)
    setHasConsent(consent === "true")
  }, [])

  return hasConsent
}
