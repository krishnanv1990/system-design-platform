/**
 * Custom hook for managing undo/redo history
 * Provides state management with history tracking for undo/redo operations
 */

import { useState, useCallback } from 'react'

interface UseHistoryOptions {
  maxHistorySize?: number
}

interface UseHistoryReturn<T> {
  state: T
  setState: (newState: T | ((prev: T) => T), options?: { skipHistory?: boolean }) => void
  undo: () => void
  redo: () => void
  canUndo: boolean
  canRedo: boolean
  clearHistory: () => void
}

interface HistoryState<T> {
  past: T[]
  present: T
  future: T[]
}

export function useHistory<T>(
  initialState: T,
  options: UseHistoryOptions = {}
): UseHistoryReturn<T> {
  const { maxHistorySize = 50 } = options

  // Combined state with past, present, and future
  const [historyState, setHistoryState] = useState<HistoryState<T>>({
    past: [],
    present: initialState,
    future: [],
  })

  const setState = useCallback(
    (newState: T | ((prev: T) => T), setOptions?: { skipHistory?: boolean }) => {
      setHistoryState((prevState) => {
        const resolved = typeof newState === 'function'
          ? (newState as (prev: T) => T)(prevState.present)
          : newState

        // Skip history tracking if specified
        if (setOptions?.skipHistory) {
          return {
            ...prevState,
            present: resolved,
          }
        }

        // Add current state to past, set new state as present, clear future
        let newPast = [...prevState.past, prevState.present]

        // Limit history size
        if (newPast.length > maxHistorySize - 1) {
          newPast = newPast.slice(-(maxHistorySize - 1))
        }

        return {
          past: newPast,
          present: resolved,
          future: [], // Clear future when making a new change
        }
      })
    },
    [maxHistorySize]
  )

  const undo = useCallback(() => {
    setHistoryState((prevState) => {
      if (prevState.past.length === 0) {
        return prevState
      }

      const newPast = prevState.past.slice(0, -1)
      const previousState = prevState.past[prevState.past.length - 1]
      const newFuture = [prevState.present, ...prevState.future]

      return {
        past: newPast,
        present: previousState,
        future: newFuture,
      }
    })
  }, [])

  const redo = useCallback(() => {
    setHistoryState((prevState) => {
      if (prevState.future.length === 0) {
        return prevState
      }

      const nextState = prevState.future[0]
      const newFuture = prevState.future.slice(1)
      const newPast = [...prevState.past, prevState.present]

      return {
        past: newPast,
        present: nextState,
        future: newFuture,
      }
    })
  }, [])

  const clearHistory = useCallback(() => {
    setHistoryState((prevState) => ({
      past: [],
      present: prevState.present,
      future: [],
    }))
  }, [])

  // Memoized values
  const state = historyState.present
  const canUndo = historyState.past.length > 0
  const canRedo = historyState.future.length > 0

  return {
    state,
    setState,
    undo,
    redo,
    canUndo,
    canRedo,
    clearHistory,
  }
}
