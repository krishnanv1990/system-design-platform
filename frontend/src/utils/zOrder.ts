/**
 * Z-Order Utilities
 * Functions for managing element layering (z-index)
 */

import type { CanvasElement } from '@/types/canvas'

/**
 * Get elements sorted by z-index
 */
export function sortByZIndex(elements: CanvasElement[]): CanvasElement[] {
  return [...elements].sort((a, b) => (a.zIndex ?? 0) - (b.zIndex ?? 0))
}

/**
 * Get the maximum z-index in a list of elements
 */
export function getMaxZIndex(elements: CanvasElement[]): number {
  if (elements.length === 0) return 0
  return Math.max(...elements.map((e) => e.zIndex ?? 0))
}

/**
 * Get the minimum z-index in a list of elements
 */
export function getMinZIndex(elements: CanvasElement[]): number {
  if (elements.length === 0) return 0
  return Math.min(...elements.map((e) => e.zIndex ?? 0))
}

/**
 * Bring elements to the front
 */
export function bringToFront(
  elements: CanvasElement[],
  ids: Set<string>
): CanvasElement[] {
  const maxZ = getMaxZIndex(elements)
  let currentZ = maxZ + 1

  return elements.map((el) => {
    if (ids.has(el.id)) {
      return { ...el, zIndex: currentZ++ }
    }
    return el
  })
}

/**
 * Send elements to the back
 */
export function sendToBack(
  elements: CanvasElement[],
  ids: Set<string>
): CanvasElement[] {
  const minZ = getMinZIndex(elements)
  let currentZ = minZ - ids.size

  return elements.map((el) => {
    if (ids.has(el.id)) {
      return { ...el, zIndex: currentZ++ }
    }
    return el
  })
}

/**
 * Bring elements forward by one layer
 */
export function bringForward(
  elements: CanvasElement[],
  ids: Set<string>
): CanvasElement[] {
  const sorted = sortByZIndex(elements)
  const result = [...sorted]

  // Find elements to move and their indices
  const indicesToMove: number[] = []
  sorted.forEach((el, index) => {
    if (ids.has(el.id)) {
      indicesToMove.push(index)
    }
  })

  // Move each element forward (swap with next non-selected element)
  for (let i = indicesToMove.length - 1; i >= 0; i--) {
    const currentIndex = indicesToMove[i]
    const nextIndex = currentIndex + 1

    if (nextIndex < result.length && !ids.has(result[nextIndex].id)) {
      // Swap z-indices
      const currentZ = result[currentIndex].zIndex ?? currentIndex
      const nextZ = result[nextIndex].zIndex ?? nextIndex

      result[currentIndex] = { ...result[currentIndex], zIndex: nextZ }
      result[nextIndex] = { ...result[nextIndex], zIndex: currentZ }
    }
  }

  return result
}

/**
 * Send elements backward by one layer
 */
export function sendBackward(
  elements: CanvasElement[],
  ids: Set<string>
): CanvasElement[] {
  const sorted = sortByZIndex(elements)
  const result = [...sorted]

  // Find elements to move and their indices
  const indicesToMove: number[] = []
  sorted.forEach((el, index) => {
    if (ids.has(el.id)) {
      indicesToMove.push(index)
    }
  })

  // Move each element backward (swap with previous non-selected element)
  for (let i = 0; i < indicesToMove.length; i++) {
    const currentIndex = indicesToMove[i]
    const prevIndex = currentIndex - 1

    if (prevIndex >= 0 && !ids.has(result[prevIndex].id)) {
      // Swap z-indices
      const currentZ = result[currentIndex].zIndex ?? currentIndex
      const prevZ = result[prevIndex].zIndex ?? prevIndex

      result[currentIndex] = { ...result[currentIndex], zIndex: prevZ }
      result[prevIndex] = { ...result[prevIndex], zIndex: currentZ }
    }
  }

  return result
}

/**
 * Normalize z-indices to be sequential starting from 0
 */
export function normalizeZIndices(elements: CanvasElement[]): CanvasElement[] {
  const sorted = sortByZIndex(elements)
  return sorted.map((el, index) => ({ ...el, zIndex: index }))
}

/**
 * Assign default z-index to new element
 */
export function assignZIndex(
  elements: CanvasElement[],
  newElement: CanvasElement
): CanvasElement {
  const maxZ = getMaxZIndex(elements)
  return { ...newElement, zIndex: maxZ + 1 }
}

/**
 * Assign z-indices to multiple new elements, ensuring they stack on top
 * of existing elements and each other in order
 */
export function assignZIndicesToMultiple(
  existingElements: CanvasElement[],
  newElements: CanvasElement[]
): CanvasElement[] {
  const maxZ = getMaxZIndex(existingElements)
  return newElements.map((el, index) => ({
    ...el,
    zIndex: maxZ + 1 + index,
  }))
}
