/**
 * Connection Points Utilities
 * Functions for managing element connection points for arrows
 */

import type {
  CanvasElement,
  ArrowElement,
  ConnectionPoint,
  ConnectionPointPosition,
  Point,
} from '@/types/canvas'
import { CANVAS_CONFIG } from '@/config/canvas'

/**
 * Get connection points for an element
 */
export function getConnectionPoints(element: CanvasElement): ConnectionPoint[] {
  // Arrows don't have connection points
  if (element.type === 'arrow') {
    return []
  }

  const { x, y, width, height, id } = element

  return [
    {
      id: `${id}-top`,
      position: 'top',
      x: x + width / 2,
      y: y,
    },
    {
      id: `${id}-right`,
      position: 'right',
      x: x + width,
      y: y + height / 2,
    },
    {
      id: `${id}-bottom`,
      position: 'bottom',
      x: x + width / 2,
      y: y + height,
    },
    {
      id: `${id}-left`,
      position: 'left',
      x: x,
      y: y + height / 2,
    },
  ]
}

/**
 * Get a specific connection point for an element
 */
export function getConnectionPoint(
  element: CanvasElement,
  position: ConnectionPointPosition
): Point {
  const { x, y, width, height } = element

  switch (position) {
    case 'top':
      return { x: x + width / 2, y }
    case 'right':
      return { x: x + width, y: y + height / 2 }
    case 'bottom':
      return { x: x + width / 2, y: y + height }
    case 'left':
      return { x, y: y + height / 2 }
    default:
      return { x: x + width / 2, y: y + height / 2 }
  }
}

/**
 * Find the nearest connection point to a given position
 */
export function findNearestConnectionPoint(
  point: Point,
  elements: CanvasElement[],
  excludeElementId?: string,
  threshold: number = CANVAS_CONFIG.CONNECTION_SNAP_DISTANCE
): { element: CanvasElement; connectionPoint: ConnectionPoint } | null {
  let nearest: { element: CanvasElement; connectionPoint: ConnectionPoint; distance: number } | null =
    null

  for (const element of elements) {
    if (element.id === excludeElementId || element.type === 'arrow') {
      continue
    }

    const connectionPoints = getConnectionPoints(element)

    for (const cp of connectionPoints) {
      const distance = Math.hypot(point.x - cp.x, point.y - cp.y)

      if (distance <= threshold) {
        if (!nearest || distance < nearest.distance) {
          nearest = { element, connectionPoint: cp, distance }
        }
      }
    }
  }

  return nearest ? { element: nearest.element, connectionPoint: nearest.connectionPoint } : null
}

/**
 * Update arrow endpoints based on connected elements
 */
export function updateConnectedArrow(
  arrow: ArrowElement,
  elements: CanvasElement[]
): ArrowElement {
  let updatedArrow = { ...arrow }

  // Update start point if connected
  if (arrow.startConnection) {
    const startElement = elements.find((el) => el.id === arrow.startConnection!.elementId)
    if (startElement) {
      const point = getConnectionPoint(startElement, arrow.startConnection.point)
      updatedArrow = { ...updatedArrow, x: point.x, y: point.y }
    }
  }

  // Update end point if connected
  if (arrow.endConnection) {
    const endElement = elements.find((el) => el.id === arrow.endConnection!.elementId)
    if (endElement) {
      const point = getConnectionPoint(endElement, arrow.endConnection.point)
      updatedArrow = { ...updatedArrow, endX: point.x, endY: point.y }
    }
  }

  return updatedArrow
}

/**
 * Update all connected arrows when an element moves
 */
export function updateConnectedArrows(
  elements: CanvasElement[],
  movedElementId: string
): CanvasElement[] {
  return elements.map((el) => {
    if (el.type !== 'arrow') return el

    const arrow = el as ArrowElement
    const startConnected = arrow.startConnection?.elementId === movedElementId
    const endConnected = arrow.endConnection?.elementId === movedElementId

    if (startConnected || endConnected) {
      return updateConnectedArrow(arrow, elements)
    }

    return el
  })
}

/**
 * Check if an arrow is connected to an element
 */
export function isArrowConnectedTo(arrow: ArrowElement, elementId: string): boolean {
  return (
    arrow.startConnection?.elementId === elementId || arrow.endConnection?.elementId === elementId
  )
}

/**
 * Disconnect arrow from an element
 */
export function disconnectArrowFrom(arrow: ArrowElement, elementId: string): ArrowElement {
  let updatedArrow = { ...arrow }

  if (arrow.startConnection?.elementId === elementId) {
    updatedArrow = { ...updatedArrow, startConnection: undefined }
  }

  if (arrow.endConnection?.elementId === elementId) {
    updatedArrow = { ...updatedArrow, endConnection: undefined }
  }

  return updatedArrow
}

/**
 * Get the best connection point position based on relative positions
 */
export function getBestConnectionPoint(
  fromElement: CanvasElement,
  toElement: CanvasElement
): { from: ConnectionPointPosition; to: ConnectionPointPosition } {
  const fromCenter = {
    x: fromElement.x + fromElement.width / 2,
    y: fromElement.y + fromElement.height / 2,
  }
  const toCenter = {
    x: toElement.x + toElement.width / 2,
    y: toElement.y + toElement.height / 2,
  }

  const dx = toCenter.x - fromCenter.x
  const dy = toCenter.y - fromCenter.y
  const angle = Math.atan2(dy, dx)

  // Determine best exit/entry points based on angle
  let from: ConnectionPointPosition
  let to: ConnectionPointPosition

  if (angle >= -Math.PI / 4 && angle < Math.PI / 4) {
    // Target is to the right
    from = 'right'
    to = 'left'
  } else if (angle >= Math.PI / 4 && angle < (3 * Math.PI) / 4) {
    // Target is below
    from = 'bottom'
    to = 'top'
  } else if (angle >= (3 * Math.PI) / 4 || angle < (-3 * Math.PI) / 4) {
    // Target is to the left
    from = 'left'
    to = 'right'
  } else {
    // Target is above
    from = 'top'
    to = 'bottom'
  }

  return { from, to }
}
