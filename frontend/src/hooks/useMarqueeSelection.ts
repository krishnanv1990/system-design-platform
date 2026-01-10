/**
 * useMarqueeSelection Hook
 * Handles box/marquee selection for selecting multiple elements
 */

import { useState, useCallback } from 'react'
import type { CanvasElement, MarqueeState, Bounds } from '@/types/canvas'

export interface UseMarqueeSelectionReturn {
  marquee: MarqueeState
  isSelecting: boolean
  startMarquee: (x: number, y: number) => void
  updateMarquee: (x: number, y: number) => void
  endMarquee: () => string[]
  getMarqueeBounds: () => Bounds | null
  getElementsInMarquee: (elements: CanvasElement[]) => string[]
}

const initialMarquee: MarqueeState = {
  isSelecting: false,
  startX: 0,
  startY: 0,
  endX: 0,
  endY: 0,
}

/**
 * Check if an element is inside the marquee bounds
 */
function isElementInBounds(element: CanvasElement, bounds: Bounds): boolean {
  // Handle arrow elements
  if (element.type === 'arrow') {
    const arrowMinX = Math.min(element.x, element.endX)
    const arrowMaxX = Math.max(element.x, element.endX)
    const arrowMinY = Math.min(element.y, element.endY)
    const arrowMaxY = Math.max(element.y, element.endY)

    // Check if arrow overlaps with bounds
    return (
      arrowMinX < bounds.x + bounds.width &&
      arrowMaxX > bounds.x &&
      arrowMinY < bounds.y + bounds.height &&
      arrowMaxY > bounds.y
    )
  }

  // For regular elements, check if any part of the element is inside bounds
  const elementRight = element.x + element.width
  const elementBottom = element.y + element.height
  const boundsRight = bounds.x + bounds.width
  const boundsBottom = bounds.y + bounds.height

  // Check for overlap (not just fully contained)
  return (
    element.x < boundsRight &&
    elementRight > bounds.x &&
    element.y < boundsBottom &&
    elementBottom > bounds.y
  )
}

export function useMarqueeSelection(): UseMarqueeSelectionReturn {
  const [marquee, setMarquee] = useState<MarqueeState>(initialMarquee)

  const startMarquee = useCallback((x: number, y: number) => {
    setMarquee({
      isSelecting: true,
      startX: x,
      startY: y,
      endX: x,
      endY: y,
    })
  }, [])

  const updateMarquee = useCallback((x: number, y: number) => {
    setMarquee((prev) => {
      if (!prev.isSelecting) return prev
      return {
        ...prev,
        endX: x,
        endY: y,
      }
    })
  }, [])

  const getMarqueeBounds = useCallback((): Bounds | null => {
    if (!marquee.isSelecting) return null

    const x = Math.min(marquee.startX, marquee.endX)
    const y = Math.min(marquee.startY, marquee.endY)
    const width = Math.abs(marquee.endX - marquee.startX)
    const height = Math.abs(marquee.endY - marquee.startY)

    return { x, y, width, height }
  }, [marquee])

  const getElementsInMarquee = useCallback(
    (elements: CanvasElement[]): string[] => {
      const bounds = getMarqueeBounds()
      if (!bounds || bounds.width < 5 || bounds.height < 5) {
        return []
      }

      return elements.filter((el) => isElementInBounds(el, bounds)).map((el) => el.id)
    },
    [getMarqueeBounds]
  )

  const endMarquee = useCallback((): string[] => {
    // Note: caller needs to provide elements to get the selected IDs
    setMarquee(initialMarquee)
    return []
  }, [])

  return {
    marquee,
    isSelecting: marquee.isSelecting,
    startMarquee,
    updateMarquee,
    endMarquee,
    getMarqueeBounds,
    getElementsInMarquee,
  }
}
