/**
 * Hook for persisting form data to localStorage and warning on unsaved changes
 */

import { useState, useEffect, useCallback, useRef } from 'react'

interface UseFormPersistenceOptions<T> {
  key: string
  initialValue: T
  debounceMs?: number
}

interface UseFormPersistenceReturn<T> {
  value: T
  setValue: (value: T | ((prev: T) => T)) => void
  isDirty: boolean
  clearStorage: () => void
  lastSaved: Date | null
}

export function useFormPersistence<T>({
  key,
  initialValue,
  debounceMs = 1000,
}: UseFormPersistenceOptions<T>): UseFormPersistenceReturn<T> {
  // Load initial value from localStorage or use provided initial value
  const [value, setValueInternal] = useState<T>(() => {
    try {
      const stored = localStorage.getItem(key)
      if (stored) {
        const parsed = JSON.parse(stored)
        return parsed.value as T
      }
    } catch {
      // Invalid stored data, use initial value
    }
    return initialValue
  })

  const [isDirty, setIsDirty] = useState(false)
  const [lastSaved, setLastSaved] = useState<Date | null>(null)
  const saveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const initialValueRef = useRef(initialValue)

  // Save to localStorage with debounce
  const saveToStorage = useCallback(
    (newValue: T) => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current)
      }

      saveTimeoutRef.current = setTimeout(() => {
        try {
          localStorage.setItem(
            key,
            JSON.stringify({
              value: newValue,
              savedAt: new Date().toISOString(),
            })
          )
          setLastSaved(new Date())
        } catch (e) {
          console.error('Failed to save to localStorage:', e)
        }
      }, debounceMs)
    },
    [key, debounceMs]
  )

  // Set value and mark as dirty
  const setValue = useCallback(
    (newValue: T | ((prev: T) => T)) => {
      setValueInternal((prev) => {
        const resolved = typeof newValue === 'function'
          ? (newValue as (prev: T) => T)(prev)
          : newValue
        setIsDirty(JSON.stringify(resolved) !== JSON.stringify(initialValueRef.current))
        saveToStorage(resolved)
        return resolved
      })
    },
    [saveToStorage]
  )

  // Clear storage
  const clearStorage = useCallback(() => {
    localStorage.removeItem(key)
    setIsDirty(false)
    setLastSaved(null)
  }, [key])

  // Warn before leaving if dirty
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        e.preventDefault()
        e.returnValue = 'You have unsaved changes. Are you sure you want to leave?'
        return e.returnValue
      }
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [isDirty])

  // Cleanup timeout on unmount
  useEffect(() => {
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current)
      }
    }
  }, [])

  return {
    value,
    setValue,
    isDirty,
    clearStorage,
    lastSaved,
  }
}

/**
 * Hook to detect and warn about unsaved changes when navigating
 */
export function useUnsavedChangesWarning(isDirty: boolean, message?: string) {
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      if (isDirty) {
        const msg = message || 'You have unsaved changes. Are you sure you want to leave?'
        e.preventDefault()
        e.returnValue = msg
        return msg
      }
    }

    window.addEventListener('beforeunload', handleBeforeUnload)
    return () => window.removeEventListener('beforeunload', handleBeforeUnload)
  }, [isDirty, message])
}
