/**
 * Hit Detection Utilities
 * Functions for detecting if a point is within elements
 */

import type { Point, CanvasElement, ArrowElement } from '@/types/canvas'
import { CANVAS_CONFIG } from '@/config/canvas'

/**
 * Calculate the shortest distance from a point to a line segment
 * Uses the parametric line formula to find the closest point on the segment
 */
export function pointToLineSegmentDistance(
  point: Point,
  lineStart: Point,
  lineEnd: Point
): number {
  const dx = lineEnd.x - lineStart.x
  const dy = lineEnd.y - lineStart.y
  const lengthSquared = dx * dx + dy * dy

  // If the line segment has zero length, return distance to the point
  if (lengthSquared === 0) {
    return Math.hypot(point.x - lineStart.x, point.y - lineStart.y)
  }

  // Calculate parameter t for the projection of the point onto the line
  // t = 0 means closest point is lineStart, t = 1 means closest point is lineEnd
  // Clamp t to [0, 1] to stay within the segment
  const t = Math.max(0, Math.min(1, (
    (point.x - lineStart.x) * dx + (point.y - lineStart.y) * dy
  ) / lengthSquared))

  // Calculate the closest point on the segment
  const closestX = lineStart.x + t * dx
  const closestY = lineStart.y + t * dy

  // Return distance from point to closest point
  return Math.hypot(point.x - closestX, point.y - closestY)
}

/**
 * Check if a point is near an arrow (line segment)
 */
export function isPointNearArrow(
  point: Point,
  arrow: ArrowElement,
  tolerance: number = CANVAS_CONFIG.ARROW_HIT_TOLERANCE ?? 10
): boolean {
  const distance = pointToLineSegmentDistance(
    point,
    { x: arrow.x, y: arrow.y },
    { x: arrow.endX, y: arrow.endY }
  )
  return distance <= tolerance
}

/**
 * Check if a point is inside a rectangle
 */
export function isPointInRectangle(
  point: Point,
  x: number,
  y: number,
  width: number,
  height: number
): boolean {
  return (
    point.x >= x &&
    point.x <= x + width &&
    point.y >= y &&
    point.y <= y + height
  )
}

/**
 * Check if a point is inside an ellipse
 */
export function isPointInEllipse(
  point: Point,
  cx: number,
  cy: number,
  rx: number,
  ry: number
): boolean {
  // Normalized distance from center
  const dx = (point.x - cx) / rx
  const dy = (point.y - cy) / ry
  return dx * dx + dy * dy <= 1
}

/**
 * Check if a point is inside a diamond (rhombus)
 */
export function isPointInDiamond(
  point: Point,
  x: number,
  y: number,
  width: number,
  height: number
): boolean {
  const cx = x + width / 2
  const cy = y + height / 2

  // Diamond check using Manhattan distance normalized by half-dimensions
  const dx = Math.abs(point.x - cx) / (width / 2)
  const dy = Math.abs(point.y - cy) / (height / 2)
  return dx + dy <= 1
}

/**
 * Check if a point is inside a hexagon
 */
export function isPointInHexagon(
  point: Point,
  x: number,
  y: number,
  width: number,
  height: number
): boolean {
  const cx = x + width / 2
  const cy = y + height / 2
  const inset = width * 0.25

  // First check bounding box
  if (!isPointInRectangle(point, x, y, width, height)) {
    return false
  }

  // Check against the angled edges
  // Left edge: from (x, cy) to (x + inset, y)
  if (point.x < x + inset) {
    const edgeX = x + (point.y < cy
      ? inset * (cy - point.y) / (cy - y)
      : inset * (point.y - cy) / (y + height - cy))
    if (point.x < x + edgeX * 0 + (cy - Math.abs(point.y - cy)) / (height / 2) * inset) {
      // Simplified: use bounding box with some margin
      const relY = Math.abs(point.y - cy) / (height / 2)
      if (point.x < x + inset * (1 - relY)) {
        return false
      }
    }
  }

  // Right edge similar check
  if (point.x > x + width - inset) {
    const relY = Math.abs(point.y - cy) / (height / 2)
    if (point.x > x + width - inset * (1 - relY)) {
      return false
    }
  }

  return true
}

/**
 * Get the element at a given point, checking from top to bottom (z-order)
 * Returns the topmost element that contains the point
 */
export function getElementAtPoint(
  point: Point,
  elements: CanvasElement[],
  arrowTolerance: number = 10
): CanvasElement | null {
  // Iterate in reverse to check topmost elements first
  for (let i = elements.length - 1; i >= 0; i--) {
    const element = elements[i]

    if (isPointInElement(point, element, arrowTolerance)) {
      return element
    }
  }

  return null
}

/**
 * Check if a point is inside any type of element
 */
export function isPointInElement(
  point: Point,
  element: CanvasElement,
  arrowTolerance: number = 10
): boolean {
  switch (element.type) {
    case 'arrow':
      return isPointNearArrow(point, element as ArrowElement, arrowTolerance)

    case 'ellipse':
      return isPointInEllipse(
        point,
        element.x + element.width / 2,
        element.y + element.height / 2,
        element.width / 2,
        element.height / 2
      )

    case 'diamond':
      return isPointInDiamond(point, element.x, element.y, element.width, element.height)

    case 'hexagon':
      return isPointInHexagon(point, element.x, element.y, element.width, element.height)

    // Rectangle, text, image, icons all use bounding box
    default:
      return isPointInRectangle(point, element.x, element.y, element.width, element.height)
  }
}
