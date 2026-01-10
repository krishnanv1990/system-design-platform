/**
 * useCanvasSelection Hook
 * Manages multi-selection state for canvas elements
 */

import { useState, useCallback, useMemo } from 'react'
import type { CanvasElement } from '@/types/canvas'

export interface UseCanvasSelectionReturn {
  selectedIds: Set<string>
  editingId: string | null
  select: (id: string, additive?: boolean) => void
  selectMultiple: (ids: string[]) => void
  deselect: (id: string) => void
  clearSelection: () => void
  selectAll: (elements: CanvasElement[]) => void
  toggleSelection: (id: string) => void
  isSelected: (id: string) => boolean
  setEditingId: (id: string | null) => void
  getSelectedElements: (elements: CanvasElement[]) => CanvasElement[]
  hasSelection: boolean
  selectionCount: number
}

export function useCanvasSelection(): UseCanvasSelectionReturn {
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set())
  const [editingId, setEditingId] = useState<string | null>(null)

  const select = useCallback((id: string, additive: boolean = false) => {
    setEditingId(null)
    setSelectedIds((prev) => {
      if (additive) {
        const next = new Set(prev)
        next.add(id)
        return next
      }
      return new Set([id])
    })
  }, [])

  const selectMultiple = useCallback((ids: string[]) => {
    setEditingId(null)
    setSelectedIds(new Set(ids))
  }, [])

  const deselect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev)
      next.delete(id)
      return next
    })
  }, [])

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set())
    setEditingId(null)
  }, [])

  const selectAll = useCallback((elements: CanvasElement[]) => {
    setEditingId(null)
    setSelectedIds(new Set(elements.map((el) => el.id)))
  }, [])

  const toggleSelection = useCallback((id: string) => {
    setEditingId(null)
    setSelectedIds((prev) => {
      const next = new Set(prev)
      if (next.has(id)) {
        next.delete(id)
      } else {
        next.add(id)
      }
      return next
    })
  }, [])

  const isSelected = useCallback(
    (id: string) => {
      return selectedIds.has(id)
    },
    [selectedIds]
  )

  const getSelectedElements = useCallback(
    (elements: CanvasElement[]) => {
      return elements.filter((el) => selectedIds.has(el.id))
    },
    [selectedIds]
  )

  const hasSelection = useMemo(() => selectedIds.size > 0, [selectedIds])
  const selectionCount = useMemo(() => selectedIds.size, [selectedIds])

  return {
    selectedIds,
    editingId,
    select,
    selectMultiple,
    deselect,
    clearSelection,
    selectAll,
    toggleSelection,
    isSelected,
    setEditingId,
    getSelectedElements,
    hasSelection,
    selectionCount,
  }
}
