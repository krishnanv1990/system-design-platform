/**
 * useCanvasClipboard Hook
 * Handles copy, cut, and paste operations for canvas elements
 */

import { useState, useCallback } from 'react'
import type { CanvasElement, ClipboardData, Bounds } from '@/types/canvas'
import { calculateBounds } from '@/utils/alignment'

export interface UseCanvasClipboardReturn {
  hasClipboard: boolean
  copy: (elements: CanvasElement[]) => void
  cut: (elements: CanvasElement[]) => string[]
  paste: (offset?: { x: number; y: number }) => CanvasElement[]
  canPaste: boolean
}

/**
 * Generate a unique ID
 */
function generateId(): string {
  return Math.random().toString(36).substring(2, 11)
}

/**
 * Deep clone an element with a new ID
 */
function cloneElement(element: CanvasElement): CanvasElement {
  return {
    ...JSON.parse(JSON.stringify(element)),
    id: generateId(),
  }
}

export function useCanvasClipboard(): UseCanvasClipboardReturn {
  const [clipboard, setClipboard] = useState<ClipboardData | null>(null)

  const copy = useCallback((elements: CanvasElement[]) => {
    if (elements.length === 0) return

    const bounds = calculateBounds(elements)
    const clonedElements = elements.map((el) => ({
      ...JSON.parse(JSON.stringify(el)),
    }))

    setClipboard({
      elements: clonedElements,
      bounds,
    })

    // Also copy to system clipboard as JSON for cross-session paste
    try {
      const clipboardData = JSON.stringify({
        type: 'design-canvas-elements',
        elements: clonedElements,
        bounds,
      })
      navigator.clipboard.writeText(clipboardData).catch(() => {
        // Silently fail if clipboard access is denied
      })
    } catch {
      // Ignore clipboard errors
    }
  }, [])

  const cut = useCallback(
    (elements: CanvasElement[]): string[] => {
      copy(elements)
      // Return IDs of elements to delete
      return elements.map((el) => el.id)
    },
    [copy]
  )

  const paste = useCallback(
    (offset: { x: number; y: number } = { x: 20, y: 20 }): CanvasElement[] => {
      if (!clipboard) return []

      // Clone elements with new IDs and offset positions
      return clipboard.elements.map((el) => {
        const cloned = cloneElement(el)

        // Offset from original position relative to bounds
        const relativeX = el.x - clipboard.bounds.x
        const relativeY = el.y - clipboard.bounds.y

        cloned.x = offset.x + relativeX
        cloned.y = offset.y + relativeY

        // Also offset arrow endpoints
        if (cloned.type === 'arrow') {
          const originalEndXOffset = el.endX - el.x
          const originalEndYOffset = el.endY - el.y
          cloned.endX = cloned.x + originalEndXOffset
          cloned.endY = cloned.y + originalEndYOffset

          // Clear connections since the connected elements might not be pasted
          cloned.startConnection = undefined
          cloned.endConnection = undefined
        }

        return cloned
      })
    },
    [clipboard]
  )

  return {
    hasClipboard: clipboard !== null && clipboard.elements.length > 0,
    copy,
    cut,
    paste,
    canPaste: clipboard !== null && clipboard.elements.length > 0,
  }
}

/**
 * Try to paste from system clipboard
 */
export async function pasteFromSystemClipboard(): Promise<CanvasElement[] | null> {
  try {
    const text = await navigator.clipboard.readText()
    const data = JSON.parse(text)

    if (data.type === 'design-canvas-elements' && Array.isArray(data.elements)) {
      // Clone with new IDs and offset
      return data.elements.map((el: CanvasElement) => ({
        ...el,
        id: generateId(),
        x: el.x + 20,
        y: el.y + 20,
        ...(el.type === 'arrow'
          ? {
              endX: el.endX + 20,
              endY: el.endY + 20,
              startConnection: undefined,
              endConnection: undefined,
            }
          : {}),
      }))
    }
  } catch {
    // Ignore errors - clipboard might not contain valid data
  }

  return null
}
