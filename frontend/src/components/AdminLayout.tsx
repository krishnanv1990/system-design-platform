/**
 * Admin Layout component with admin-specific navigation
 */

import { useState } from "react"
import { Outlet, Link, useNavigate, useLocation } from "react-router-dom"
import { LogOut, Moon, Sun, User, Menu, X, Home, BarChart3, Activity, Shield } from "lucide-react"
import { useAuth } from "./AuthContext"
import { useTheme } from "@/hooks/useTheme"
import { Button } from "@/components/ui/button"
import { Toaster } from "@/components/ui/toaster"
import { useConfirm } from "@/components/ui/confirm-dialog"
import { cn } from "@/lib/utils"

export default function AdminLayout() {
  const { user, logout } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const { resolvedTheme, setTheme } = useTheme()
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false)

  const confirm = useConfirm()

  const handleLogout = async () => {
    const doLogout = await confirm({
      title: "Confirm Logout",
      message: "Are you sure you want to log out?",
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
    { to: "/dashboard", label: "Dashboard", icon: Home },
    { to: "/usage", label: "Usage & Billing", icon: BarChart3 },
  ]

  return (
    <div className="min-h-screen bg-background flex flex-col">
      {/* Admin Banner */}
      <div className="bg-amber-500 text-amber-950 text-center py-1 text-sm font-medium">
        <Shield className="inline h-4 w-4 mr-1" />
        Admin Portal - Restricted Access
      </div>

      {/* Navigation */}
      <nav className="border-b bg-card" role="navigation" aria-label="Admin navigation">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between h-16">
            {/* Logo and main nav */}
            <div className="flex">
              <Link to="/" className="flex items-center" aria-label="Admin Home">
                <Activity className="h-5 w-5 text-amber-600 mr-2" aria-hidden="true" />
                <span className="text-lg sm:text-xl font-bold text-foreground">
                  <span className="hidden sm:inline">SDP Admin</span>
                  <span className="sm:hidden">Admin</span>
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
                        ? "text-amber-600 bg-amber-50 dark:bg-amber-950"
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
                        className="w-8 h-8 rounded-full ring-2 ring-amber-500"
                      />
                    ) : (
                      <div className="w-8 h-8 rounded-full bg-amber-100 dark:bg-amber-900 flex items-center justify-center">
                        <User className="h-4 w-4 text-amber-600" aria-hidden="true" />
                      </div>
                    )}
                    <div className="hidden md:block">
                      <span className="text-sm font-medium block">
                        {user.name || user.email}
                      </span>
                      <span className="text-xs text-amber-600">Admin</span>
                    </div>
                  </div>
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
                      ? "text-amber-600 bg-amber-50 dark:bg-amber-950"
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
                        className="w-10 h-10 rounded-full ring-2 ring-amber-500"
                      />
                    ) : (
                      <div className="w-10 h-10 rounded-full bg-amber-100 dark:bg-amber-900 flex items-center justify-center">
                        <User className="h-5 w-5 text-amber-600" aria-hidden="true" />
                      </div>
                    )}
                    <div className="ml-3">
                      <p className="text-base font-medium">{user.name || user.email}</p>
                      <p className="text-sm text-amber-600">Admin</p>
                    </div>
                  </div>
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
          <p className="text-sm text-center text-muted-foreground">
            System Design Platform - Admin Portal
          </p>
        </div>
      </footer>

      {/* Toast notifications */}
      <Toaster />
    </div>
  )
}
