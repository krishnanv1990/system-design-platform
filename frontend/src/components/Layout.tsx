/**
 * Main layout component with navigation and theme toggle
 *
 * UX Features:
 * - Skip to content link for accessibility
 * - Mobile navigation menu
 * - Logout confirmation
 * - Theme toggle with aria labels
 */

import { useState } from "react"
import { Outlet, Link, useNavigate, useLocation } from "react-router-dom"
import { LogOut, Moon, Sun, User, Cloud, Menu, X, Home, FileText, Settings, BarChart3, Activity } from "lucide-react"
import { useAuth } from "./AuthContext"
import { useTheme } from "@/hooks/useTheme"
import { Button } from "@/components/ui/button"
import { Toaster } from "@/components/ui/toaster"
import { useConfirm } from "@/components/ui/confirm-dialog"
import { cn } from "@/lib/utils"

export default function Layout() {
  const { user, logout, demoMode } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const { resolvedTheme, setTheme } = useTheme()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const confirm = useConfirm()

  const handleLogout = async () => {
    const doLogout = await confirm({
      title: "Confirm Logout",
      message: "Are you sure you want to log out? Any unsaved changes will be lost.",
      type: "warning",
      confirmLabel: "Logout",
    })

    if (doLogout) {
      logout()
      navigate("/login")
    }
  }

  const toggleTheme = () => {
    setTheme(resolvedTheme === "dark" ? "light" : "dark")
  }

  const isActive = (path: string) => location.pathname.startsWith(path)

  const navLinks = [
    { to: "/problems", label: "Problems", icon: FileText },
    { to: "/usage", label: "My Usage", icon: Activity },
    { to: "/admin", label: "Admin", icon: Cloud },
    { to: "/admin/usage", label: "All Usage", icon: BarChart3, adminOnly: true },
  ]

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Skip to main content link for accessibility */}
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:top-4 focus:left-4 focus:z-50 focus:px-4 focus:py-2 focus:bg-primary focus:text-primary-foreground focus:rounded-md"
      >
        Skip to main content
      </a>

      {/* Navigation */}
      <nav className="border-b bg-card" role="navigation" aria-label="Main navigation">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            {/* Logo and main nav */}
            <div className="flex">
              <Link to="/" className="flex items-center" aria-label="Home - System Design Platform">
                <Home className="h-5 w-5 text-primary mr-2 hidden sm:block" aria-hidden="true" />
                <span className="text-lg sm:text-xl font-bold text-primary">
                  <span className="hidden sm:inline">System Design Platform</span>
                  <span className="sm:hidden">SDP</span>
                </span>
              </Link>

              {/* Desktop navigation */}
              <div className="hidden sm:ml-8 sm:flex sm:space-x-4">
                {navLinks.map((link) => (
                  <Link
                    key={link.to}
                    to={link.to}
                    className={cn(
                      "inline-flex items-center px-3 py-2 text-sm font-medium rounded-md transition-colors",
                      isActive(link.to)
                        ? "text-primary bg-primary/10"
                        : "text-foreground/80 hover:text-foreground hover:bg-muted"
                    )}
                    aria-current={isActive(link.to) ? "page" : undefined}
                  >
                    <link.icon className="h-4 w-4 mr-1.5" aria-hidden="true" />
                    {link.label}
                  </Link>
                ))}
              </div>
            </div>

            {/* User menu and theme toggle */}
            <div className="flex items-center gap-2">
              {/* Theme toggle */}
              <Button
                variant="ghost"
                size="icon"
                onClick={toggleTheme}
                className="h-9 w-9"
                aria-label={`Switch to ${resolvedTheme === "dark" ? "light" : "dark"} theme`}
              >
                {resolvedTheme === "dark" ? (
                  <Sun className="h-4 w-4" aria-hidden="true" />
                ) : (
                  <Moon className="h-4 w-4" aria-hidden="true" />
                )}
              </Button>

              {/* User info and logout - desktop */}
              {user && (
                <div className="hidden sm:flex items-center gap-3">
                  <div className="flex items-center gap-2">
                    {user.avatar_url ? (
                      <img
                        src={user.avatar_url}
                        alt=""
                        className="w-8 h-8 rounded-full ring-2 ring-border"
                      />
                    ) : (
                      <div className="w-8 h-8 rounded-full bg-muted flex items-center justify-center">
                        <User className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                      </div>
                    )}
                    <div className="hidden md:block">
                      <span className="text-sm font-medium block">
                        {user.name || user.email}
                      </span>
                      {demoMode && (
                        <span className="text-xs text-muted-foreground">Demo Mode</span>
                      )}
                    </div>
                  </div>
                  <Button
                    asChild
                    variant="ghost"
                    size="sm"
                    aria-label="Account Settings"
                  >
                    <Link to="/settings">
                      <Settings className="h-4 w-4" aria-hidden="true" />
                    </Link>
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={handleLogout}
                    aria-label="Logout"
                  >
                    <LogOut className="h-4 w-4 mr-2" aria-hidden="true" />
                    <span className="hidden lg:inline">Logout</span>
                  </Button>
                </div>
              )}

              {/* Mobile menu button */}
              <Button
                variant="ghost"
                size="icon"
                className="sm:hidden h-9 w-9"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
                aria-expanded={mobileMenuOpen}
                aria-controls="mobile-menu"
                aria-label={mobileMenuOpen ? "Close menu" : "Open menu"}
              >
                {mobileMenuOpen ? (
                  <X className="h-5 w-5" aria-hidden="true" />
                ) : (
                  <Menu className="h-5 w-5" aria-hidden="true" />
                )}
              </Button>
            </div>
          </div>
        </div>

        {/* Mobile menu */}
        {mobileMenuOpen && (
          <div
            id="mobile-menu"
            className="sm:hidden border-t bg-card animate-in slide-in-from-top-2"
          >
            <div className="px-4 py-3 space-y-1">
              {navLinks.map((link) => (
                <Link
                  key={link.to}
                  to={link.to}
                  onClick={() => setMobileMenuOpen(false)}
                  className={cn(
                    "flex items-center px-3 py-2 text-base font-medium rounded-md transition-colors",
                    isActive(link.to)
                      ? "text-primary bg-primary/10"
                      : "text-foreground/80 hover:text-foreground hover:bg-muted"
                  )}
                  aria-current={isActive(link.to) ? "page" : undefined}
                >
                  <link.icon className="h-5 w-5 mr-3" aria-hidden="true" />
                  {link.label}
                </Link>
              ))}

              {/* User info in mobile menu */}
              {user && (
                <div className="pt-4 mt-4 border-t">
                  <div className="flex items-center px-3 py-2">
                    {user.avatar_url ? (
                      <img
                        src={user.avatar_url}
                        alt=""
                        className="w-10 h-10 rounded-full ring-2 ring-border"
                      />
                    ) : (
                      <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
                        <User className="h-5 w-5 text-muted-foreground" aria-hidden="true" />
                      </div>
                    )}
                    <div className="ml-3">
                      <p className="text-base font-medium">{user.name || user.email}</p>
                      {demoMode && (
                        <p className="text-sm text-muted-foreground">Demo Mode</p>
                      )}
                    </div>
                  </div>
                  <Link
                    to="/settings"
                    onClick={() => setMobileMenuOpen(false)}
                    className="flex items-center w-full px-3 py-2 text-base font-medium text-foreground/80 hover:text-foreground hover:bg-muted rounded-md transition-colors"
                  >
                    <Settings className="h-5 w-5 mr-3" aria-hidden="true" />
                    Account Settings
                  </Link>
                  <button
                    onClick={() => {
                      setMobileMenuOpen(false)
                      handleLogout()
                    }}
                    className="flex items-center w-full px-3 py-2 text-base font-medium text-destructive hover:bg-destructive/10 rounded-md transition-colors"
                  >
                    <LogOut className="h-5 w-5 mr-3" aria-hidden="true" />
                    Logout
                  </button>
                </div>
              )}
            </div>
          </div>
        )}
      </nav>

      {/* Main content */}
      <main
        id="main-content"
        className="flex-1 max-w-7xl w-full mx-auto py-6 px-4 sm:px-6 lg:px-8"
        role="main"
      >
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="border-t bg-card" role="contentinfo">
        <div className="max-w-7xl mx-auto py-4 px-4 sm:px-6 lg:px-8">
          <div className="flex flex-col sm:flex-row items-center justify-between gap-2">
            <p className="text-sm text-muted-foreground">
              System Design Interview Platform - Practice and master system design
            </p>
            <div className="flex items-center gap-4 text-sm text-muted-foreground">
              <Link to="/terms" className="hover:text-primary hover:underline">
                Terms
              </Link>
              <Link to="/privacy" className="hover:text-primary hover:underline">
                Privacy
              </Link>
            </div>
          </div>
        </div>
      </footer>

      {/* Toast notifications */}
      <Toaster />
    </div>
  )
}
