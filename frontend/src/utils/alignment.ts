/**
 * Alignment Utilities
 * Functions for aligning and distributing elements
 */

import type { CanvasElement, Bounds } from '@/types/canvas'

/**
 * Calculate bounds of a set of elements
 */
export function calculateBounds(elements: CanvasElement[]): Bounds {
  if (elements.length === 0) {
    return { x: 0, y: 0, width: 0, height: 0 }
  }

  let minX = Infinity
  let minY = Infinity
  let maxX = -Infinity
  let maxY = -Infinity

  elements.forEach((el) => {
    if (el.type === 'arrow') {
      minX = Math.min(minX, el.x, el.endX)
      minY = Math.min(minY, el.y, el.endY)
      maxX = Math.max(maxX, el.x, el.endX)
      maxY = Math.max(maxY, el.y, el.endY)
    } else {
      minX = Math.min(minX, el.x)
      minY = Math.min(minY, el.y)
      maxX = Math.max(maxX, el.x + el.width)
      maxY = Math.max(maxY, el.y + el.height)
    }
  })

  return {
    x: minX,
    y: minY,
    width: maxX - minX,
    height: maxY - minY,
  }
}

/**
 * Align elements to the left
 */
export function alignLeft(elements: CanvasElement[]): CanvasElement[] {
  if (elements.length <= 1) return elements

  const minX = Math.min(...elements.map((el) => el.x))
  return elements.map((el) => ({ ...el, x: minX }))
}

/**
 * Align elements to the right
 */
export function alignRight(elements: CanvasElement[]): CanvasElement[] {
  if (elements.length <= 1) return elements

  const maxRight = Math.max(...elements.map((el) => el.x + el.width))
  return elements.map((el) => ({ ...el, x: maxRight - el.width }))
}

/**
 * Align elements to the horizontal center
 */
export function alignCenterHorizontal(elements: CanvasElement[]): CanvasElement[] {
  if (elements.length <= 1) return elements

  const bounds = calculateBounds(elements)
  const centerX = bounds.x + bounds.width / 2

  return elements.map((el) => ({
    ...el,
    x: centerX - el.width / 2,
  }))
}

/**
 * Align elements to the top
 */
export function alignTop(elements: CanvasElement[]): CanvasElement[] {
  if (elements.length <= 1) return elements

  const minY = Math.min(...elements.map((el) => el.y))
  return elements.map((el) => ({ ...el, y: minY }))
}

/**
 * Align elements to the bottom
 */
export function alignBottom(elements: CanvasElement[]): CanvasElement[] {
  if (elements.length <= 1) return elements

  const maxBottom = Math.max(...elements.map((el) => el.y + el.height))
  return elements.map((el) => ({ ...el, y: maxBottom - el.height }))
}

/**
 * Align elements to the vertical center
 */
export function alignCenterVertical(elements: CanvasElement[]): CanvasElement[] {
  if (elements.length <= 1) return elements

  const bounds = calculateBounds(elements)
  const centerY = bounds.y + bounds.height / 2

  return elements.map((el) => ({
    ...el,
    y: centerY - el.height / 2,
  }))
}

/**
 * Distribute elements horizontally with equal spacing
 */
export function distributeHorizontally(elements: CanvasElement[]): CanvasElement[] {
  if (elements.length <= 2) return elements

  const sorted = [...elements].sort((a, b) => a.x - b.x)
  const bounds = calculateBounds(elements)
  const totalWidth = elements.reduce((sum, el) => sum + el.width, 0)
  const gap = (bounds.width - totalWidth) / (elements.length - 1)

  let currentX = bounds.x

  return sorted.map((el) => {
    const result = { ...el, x: currentX }
    currentX += el.width + gap
    return result
  })
}

/**
 * Distribute elements vertically with equal spacing
 */
export function distributeVertically(elements: CanvasElement[]): CanvasElement[] {
  if (elements.length <= 2) return elements

  const sorted = [...elements].sort((a, b) => a.y - b.y)
  const bounds = calculateBounds(elements)
  const totalHeight = elements.reduce((sum, el) => sum + el.height, 0)
  const gap = (bounds.height - totalHeight) / (elements.length - 1)

  let currentY = bounds.y

  return sorted.map((el) => {
    const result = { ...el, y: currentY }
    currentY += el.height + gap
    return result
  })
}

/**
 * Move elements by a delta
 */
export function moveElements(
  elements: CanvasElement[],
  ids: Set<string>,
  dx: number,
  dy: number
): CanvasElement[] {
  return elements.map((el) => {
    if (!ids.has(el.id)) return el

    if (el.type === 'arrow') {
      return {
        ...el,
        x: el.x + dx,
        y: el.y + dy,
        endX: el.endX + dx,
        endY: el.endY + dy,
      }
    }

    return {
      ...el,
      x: el.x + dx,
      y: el.y + dy,
    }
  })
}
