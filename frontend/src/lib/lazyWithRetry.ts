/**
 * Utility for lazy loading React components with retry logic
 * Handles chunk loading failures that occur after deployments
 */

import { lazy, ComponentType } from 'react'

/**
 * Detect if an error is a chunk loading failure
 * These occur when cached HTML references old chunk filenames after a deployment
 */
function isChunkLoadError(error: unknown): boolean {
  if (error instanceof Error) {
    const message = error.message.toLowerCase()
    return (
      message.includes('failed to fetch dynamically imported module') ||
      message.includes('loading chunk') ||
      message.includes('loading css chunk') ||
      message.includes('failed to fetch') ||
      message.includes('dynamically imported module')
    )
  }
  return false
}

/**
 * Storage key to track if we've already tried refreshing
 */
const REFRESH_KEY = 'chunk_refresh_attempted'

/**
 * Check if we should try refreshing the page
 */
function shouldRefreshPage(): boolean {
  const lastRefresh = sessionStorage.getItem(REFRESH_KEY)
  if (!lastRefresh) return true

  // Only allow refresh once per 30 seconds to prevent infinite loops
  const lastRefreshTime = parseInt(lastRefresh, 10)
  return Date.now() - lastRefreshTime > 30000
}

/**
 * Mark that we've attempted a refresh
 */
function markRefreshAttempted(): void {
  sessionStorage.setItem(REFRESH_KEY, Date.now().toString())
}

/**
 * Clear the refresh marker (call after successful load)
 */
function clearRefreshMarker(): void {
  sessionStorage.removeItem(REFRESH_KEY)
}

/**
 * Lazy load a component with retry logic
 * On chunk load failure, attempts to reload the page once to get fresh chunks
 *
 * @param importFn - Dynamic import function
 * @param retries - Number of retries before forcing refresh (default: 2)
 * @param delay - Delay between retries in ms (default: 1000)
 */
export function lazyWithRetry<T extends ComponentType<any>>(
  importFn: () => Promise<{ default: T }>,
  retries = 2,
  delay = 1000
): React.LazyExoticComponent<T> {
  return lazy(async () => {
    let lastError: unknown

    for (let attempt = 0; attempt <= retries; attempt++) {
      try {
        const module = await importFn()
        // Success - clear any refresh markers
        clearRefreshMarker()
        return module
      } catch (error) {
        lastError = error
        console.warn(`Chunk load attempt ${attempt + 1} failed:`, error)

        if (attempt < retries) {
          // Wait before retrying with exponential backoff
          await new Promise(resolve => setTimeout(resolve, delay * (attempt + 1)))
        }
      }
    }

    // All retries failed
    if (isChunkLoadError(lastError) && shouldRefreshPage()) {
      console.warn('Chunk load failed after retries, refreshing page to get new chunks...')
      markRefreshAttempted()
      // Force a hard refresh to bypass cache
      window.location.reload()
      // Return a never-resolving promise while page reloads
      return new Promise(() => {})
    }

    // If we've already tried refreshing or it's not a chunk error, throw
    throw lastError
  })
}

/**
 * Wrapper for importing Monaco editor with retry logic
 */
export function lazyLoadMonaco() {
  return lazyWithRetry(
    () => import('@monaco-editor/react').then(mod => ({ default: mod.default })),
    3, // 3 retries for Monaco since it's critical
    1500
  )
}

export default lazyWithRetry
