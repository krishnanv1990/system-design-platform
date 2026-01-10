/**
 * Snap Utilities
 * Functions for snapping elements to grid and other elements
 */

import type { Point, CanvasElement, Bounds } from '@/types/canvas'
import { CANVAS_CONFIG } from '@/config/canvas'

/**
 * Snap a single value to the nearest grid point
 */
export function snapToGrid(
  value: number,
  gridSize: number = CANVAS_CONFIG.GRID_SIZE,
  enabled: boolean = true
): number {
  if (!enabled) return value
  return Math.round(value / gridSize) * gridSize
}

/**
 * Snap a point to the nearest grid intersection
 */
export function snapPointToGrid(
  point: Point,
  gridSize: number = CANVAS_CONFIG.GRID_SIZE,
  enabled: boolean = true
): Point {
  return {
    x: snapToGrid(point.x, gridSize, enabled),
    y: snapToGrid(point.y, gridSize, enabled),
  }
}

/**
 * Get the bounds of an element
 */
export function getElementBounds(element: CanvasElement): Bounds {
  if (element.type === 'arrow') {
    const minX = Math.min(element.x, element.endX)
    const minY = Math.min(element.y, element.endY)
    const maxX = Math.max(element.x, element.endX)
    const maxY = Math.max(element.y, element.endY)
    return {
      x: minX,
      y: minY,
      width: maxX - minX,
      height: maxY - minY,
    }
  }
  return {
    x: element.x,
    y: element.y,
    width: element.width,
    height: element.height,
  }
}

/**
 * Get snap lines from other elements
 */
export function getSnapLines(
  movingElement: CanvasElement,
  allElements: CanvasElement[],
  threshold: number = CANVAS_CONFIG.SNAP_THRESHOLD
): { vertical: number[]; horizontal: number[] } {
  const vertical: number[] = []
  const horizontal: number[] = []
  const movingBounds = getElementBounds(movingElement)

  allElements.forEach((el) => {
    if (el.id === movingElement.id) return
    const bounds = getElementBounds(el)

    // Vertical snap points (left, center, right)
    const vPoints = [bounds.x, bounds.x + bounds.width / 2, bounds.x + bounds.width]
    const movingVPoints = [
      movingBounds.x,
      movingBounds.x + movingBounds.width / 2,
      movingBounds.x + movingBounds.width,
    ]

    vPoints.forEach((vp) => {
      movingVPoints.forEach((mvp) => {
        if (Math.abs(vp - mvp) < threshold) {
          vertical.push(vp)
        }
      })
    })

    // Horizontal snap points (top, center, bottom)
    const hPoints = [bounds.y, bounds.y + bounds.height / 2, bounds.y + bounds.height]
    const movingHPoints = [
      movingBounds.y,
      movingBounds.y + movingBounds.height / 2,
      movingBounds.y + movingBounds.height,
    ]

    hPoints.forEach((hp) => {
      movingHPoints.forEach((mhp) => {
        if (Math.abs(hp - mhp) < threshold) {
          horizontal.push(hp)
        }
      })
    })
  })

  return {
    vertical: [...new Set(vertical)],
    horizontal: [...new Set(horizontal)],
  }
}

/**
 * Snap element position to other elements
 */
export function snapToElements(
  position: Point,
  element: CanvasElement,
  allElements: CanvasElement[],
  threshold: number = CANVAS_CONFIG.SNAP_THRESHOLD
): Point {
  const bounds = getElementBounds(element)
  let snappedX = position.x
  let snappedY = position.y

  allElements.forEach((el) => {
    if (el.id === element.id) return
    const otherBounds = getElementBounds(el)

    // Left edge to left edge
    if (Math.abs(position.x - otherBounds.x) < threshold) {
      snappedX = otherBounds.x
    }
    // Right edge to right edge
    if (Math.abs(position.x + bounds.width - (otherBounds.x + otherBounds.width)) < threshold) {
      snappedX = otherBounds.x + otherBounds.width - bounds.width
    }
    // Left edge to right edge
    if (Math.abs(position.x - (otherBounds.x + otherBounds.width)) < threshold) {
      snappedX = otherBounds.x + otherBounds.width
    }
    // Right edge to left edge
    if (Math.abs(position.x + bounds.width - otherBounds.x) < threshold) {
      snappedX = otherBounds.x - bounds.width
    }
    // Center to center (horizontal)
    const centerX = position.x + bounds.width / 2
    const otherCenterX = otherBounds.x + otherBounds.width / 2
    if (Math.abs(centerX - otherCenterX) < threshold) {
      snappedX = otherCenterX - bounds.width / 2
    }

    // Top edge to top edge
    if (Math.abs(position.y - otherBounds.y) < threshold) {
      snappedY = otherBounds.y
    }
    // Bottom edge to bottom edge
    if (Math.abs(position.y + bounds.height - (otherBounds.y + otherBounds.height)) < threshold) {
      snappedY = otherBounds.y + otherBounds.height - bounds.height
    }
    // Top edge to bottom edge
    if (Math.abs(position.y - (otherBounds.y + otherBounds.height)) < threshold) {
      snappedY = otherBounds.y + otherBounds.height
    }
    // Bottom edge to top edge
    if (Math.abs(position.y + bounds.height - otherBounds.y) < threshold) {
      snappedY = otherBounds.y - bounds.height
    }
    // Center to center (vertical)
    const centerY = position.y + bounds.height / 2
    const otherCenterY = otherBounds.y + otherBounds.height / 2
    if (Math.abs(centerY - otherCenterY) < threshold) {
      snappedY = otherCenterY - bounds.height / 2
    }
  })

  return { x: snappedX, y: snappedY }
}
