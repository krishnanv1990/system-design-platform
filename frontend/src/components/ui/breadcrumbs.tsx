/**
 * Breadcrumb navigation component
 */

import { ChevronRight, Home } from 'lucide-react'
import { Link, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'

interface BreadcrumbItem {
  label: string
  href?: string
}

interface BreadcrumbsProps {
  items?: BreadcrumbItem[]
  className?: string
}

// Auto-generate breadcrumbs from current route
function useAutoBreadcrumbs(): BreadcrumbItem[] {
  const location = useLocation()
  const pathnames = location.pathname.split('/').filter((x) => x)

  const breadcrumbs: BreadcrumbItem[] = []

  let currentPath = ''
  for (const segment of pathnames) {
    currentPath += `/${segment}`

    // Convert path segments to readable labels
    let label = segment
    if (segment === 'problems') {
      label = 'Problems'
    } else if (segment === 'submit') {
      label = 'Submit Solution'
    } else if (segment === 'results') {
      label = 'Results'
    } else if (segment === 'admin') {
      label = 'Admin'
    } else if (segment === 'submissions') {
      label = 'Submissions'
    } else if (/^\d+$/.test(segment)) {
      // It's an ID, skip adding label but keep path
      continue
    }

    breadcrumbs.push({
      label,
      href: currentPath,
    })
  }

  return breadcrumbs
}

export function Breadcrumbs({ items, className }: BreadcrumbsProps) {
  const autoBreadcrumbs = useAutoBreadcrumbs()
  const breadcrumbItems = items || autoBreadcrumbs

  if (breadcrumbItems.length === 0) {
    return null
  }

  return (
    <nav aria-label="Breadcrumb" className={cn('mb-4', className)}>
      <ol className="flex items-center gap-1 text-sm text-muted-foreground">
        <li>
          <Link
            to="/"
            className="flex items-center gap-1 hover:text-foreground transition-colors p-1 rounded hover:bg-muted"
            aria-label="Home"
          >
            <Home className="h-4 w-4" />
          </Link>
        </li>

        {breadcrumbItems.map((item, index) => {
          const isLast = index === breadcrumbItems.length - 1
          return (
            <li key={item.href || index} className="flex items-center gap-1">
              <ChevronRight className="h-4 w-4 text-muted-foreground/50" aria-hidden="true" />
              {isLast || !item.href ? (
                <span className={cn('px-1', isLast && 'text-foreground font-medium')} aria-current={isLast ? 'page' : undefined}>
                  {item.label}
                </span>
              ) : (
                <Link
                  to={item.href}
                  className="hover:text-foreground transition-colors px-1 py-0.5 rounded hover:bg-muted"
                >
                  {item.label}
                </Link>
              )}
            </li>
          )
        })}
      </ol>
    </nav>
  )
}
