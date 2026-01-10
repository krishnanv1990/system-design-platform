/**
 * Hit Detection Utility Tests
 */

import { describe, it, expect } from 'vitest'
import {
  pointToLineSegmentDistance,
  isPointNearArrow,
  isPointInRectangle,
  isPointInEllipse,
  isPointInDiamond,
  isPointInElement,
} from '../hitDetection'
import type { ArrowElement, RectangleElement, EllipseElement } from '@/types/canvas'

describe('pointToLineSegmentDistance', () => {
  it('should return 0 for a point on the line', () => {
    const distance = pointToLineSegmentDistance(
      { x: 50, y: 50 },
      { x: 0, y: 0 },
      { x: 100, y: 100 }
    )
    expect(distance).toBeCloseTo(0, 5)
  })

  it('should return correct distance for a point perpendicular to line', () => {
    // Point at (50, 60), line from (0, 50) to (100, 50)
    // Distance should be 10
    const distance = pointToLineSegmentDistance(
      { x: 50, y: 60 },
      { x: 0, y: 50 },
      { x: 100, y: 50 }
    )
    expect(distance).toBeCloseTo(10, 5)
  })

  it('should return distance to start point when projection is before segment', () => {
    // Point at (-10, 0), line from (0, 0) to (100, 0)
    // Closest point is (0, 0), distance is 10
    const distance = pointToLineSegmentDistance(
      { x: -10, y: 0 },
      { x: 0, y: 0 },
      { x: 100, y: 0 }
    )
    expect(distance).toBeCloseTo(10, 5)
  })

  it('should return distance to end point when projection is after segment', () => {
    // Point at (110, 0), line from (0, 0) to (100, 0)
    // Closest point is (100, 0), distance is 10
    const distance = pointToLineSegmentDistance(
      { x: 110, y: 0 },
      { x: 0, y: 0 },
      { x: 100, y: 0 }
    )
    expect(distance).toBeCloseTo(10, 5)
  })

  it('should handle zero-length line segment', () => {
    const distance = pointToLineSegmentDistance(
      { x: 10, y: 10 },
      { x: 0, y: 0 },
      { x: 0, y: 0 }
    )
    expect(distance).toBeCloseTo(Math.sqrt(200), 5)
  })

  it('should handle diagonal lines', () => {
    // Point at (0, 100), line from (0, 0) to (100, 100)
    // The perpendicular distance to the line is 100/sqrt(2) ≈ 70.71
    const distance = pointToLineSegmentDistance(
      { x: 0, y: 100 },
      { x: 0, y: 0 },
      { x: 100, y: 100 }
    )
    expect(distance).toBeCloseTo(70.71, 1)
  })
})

describe('isPointNearArrow', () => {
  const createArrow = (x: number, y: number, endX: number, endY: number): ArrowElement => ({
    id: 'test-arrow',
    type: 'arrow',
    x,
    y,
    endX,
    endY,
    width: 0,
    height: 0,
    fill: 'transparent',
    stroke: '#000',
    strokeWidth: 2,
    lineStyle: 'solid',
    zIndex: 0,
  })

  it('should return true for point near the middle of the arrow', () => {
    const arrow = createArrow(0, 0, 100, 0)
    expect(isPointNearArrow({ x: 50, y: 5 }, arrow, 10)).toBe(true)
  })

  it('should return true for point near the start of the arrow', () => {
    const arrow = createArrow(0, 0, 100, 0)
    expect(isPointNearArrow({ x: 5, y: 5 }, arrow, 10)).toBe(true)
  })

  it('should return true for point near the end of the arrow', () => {
    const arrow = createArrow(0, 0, 100, 0)
    expect(isPointNearArrow({ x: 95, y: 5 }, arrow, 10)).toBe(true)
  })

  it('should return false for point far from the arrow', () => {
    const arrow = createArrow(0, 0, 100, 0)
    expect(isPointNearArrow({ x: 50, y: 50 }, arrow, 10)).toBe(false)
  })

  it('should respect custom tolerance', () => {
    const arrow = createArrow(0, 0, 100, 0)
    expect(isPointNearArrow({ x: 50, y: 15 }, arrow, 10)).toBe(false)
    expect(isPointNearArrow({ x: 50, y: 15 }, arrow, 20)).toBe(true)
  })

  it('should work with diagonal arrows', () => {
    const arrow = createArrow(0, 0, 100, 100)
    // Point on the line should be detected
    expect(isPointNearArrow({ x: 50, y: 50 }, arrow, 10)).toBe(true)
    // Point perpendicular to line at midpoint
    expect(isPointNearArrow({ x: 55, y: 45 }, arrow, 10)).toBe(true)
  })
})

describe('isPointInRectangle', () => {
  it('should return true for point inside rectangle', () => {
    expect(isPointInRectangle({ x: 50, y: 50 }, 0, 0, 100, 100)).toBe(true)
  })

  it('should return true for point on edge', () => {
    expect(isPointInRectangle({ x: 0, y: 50 }, 0, 0, 100, 100)).toBe(true)
    expect(isPointInRectangle({ x: 100, y: 50 }, 0, 0, 100, 100)).toBe(true)
  })

  it('should return false for point outside rectangle', () => {
    expect(isPointInRectangle({ x: 150, y: 50 }, 0, 0, 100, 100)).toBe(false)
    expect(isPointInRectangle({ x: -10, y: 50 }, 0, 0, 100, 100)).toBe(false)
  })
})

describe('isPointInEllipse', () => {
  it('should return true for point inside ellipse', () => {
    expect(isPointInEllipse({ x: 50, y: 50 }, 50, 50, 30, 20)).toBe(true)
  })

  it('should return true for point on edge', () => {
    expect(isPointInEllipse({ x: 80, y: 50 }, 50, 50, 30, 20)).toBe(true)
  })

  it('should return false for point outside ellipse', () => {
    expect(isPointInEllipse({ x: 100, y: 100 }, 50, 50, 30, 20)).toBe(false)
  })

  it('should handle circle (equal radii)', () => {
    expect(isPointInEllipse({ x: 50, y: 50 }, 50, 50, 25, 25)).toBe(true)
    expect(isPointInEllipse({ x: 75, y: 50 }, 50, 50, 25, 25)).toBe(true)
    expect(isPointInEllipse({ x: 80, y: 50 }, 50, 50, 25, 25)).toBe(false)
  })
})

describe('isPointInDiamond', () => {
  it('should return true for point at center', () => {
    expect(isPointInDiamond({ x: 50, y: 50 }, 0, 0, 100, 100)).toBe(true)
  })

  it('should return true for point inside diamond', () => {
    expect(isPointInDiamond({ x: 50, y: 25 }, 0, 0, 100, 100)).toBe(true)
  })

  it('should return false for point in corner (outside diamond)', () => {
    // Point at (10, 10) is inside bounding box but outside diamond
    expect(isPointInDiamond({ x: 10, y: 10 }, 0, 0, 100, 100)).toBe(false)
  })
})

describe('isPointInElement', () => {
  it('should detect point in rectangle element', () => {
    const rect: RectangleElement = {
      id: 'rect',
      type: 'rectangle',
      x: 0,
      y: 0,
      width: 100,
      height: 100,
      fill: '#fff',
      stroke: '#000',
      strokeWidth: 2,
      cornerRadius: 0,
      zIndex: 0,
    }
    expect(isPointInElement({ x: 50, y: 50 }, rect)).toBe(true)
    expect(isPointInElement({ x: 150, y: 50 }, rect)).toBe(false)
  })

  it('should detect point near arrow element', () => {
    const arrow: ArrowElement = {
      id: 'arrow',
      type: 'arrow',
      x: 0,
      y: 0,
      endX: 100,
      endY: 0,
      width: 0,
      height: 0,
      fill: 'transparent',
      stroke: '#000',
      strokeWidth: 2,
      lineStyle: 'solid',
      zIndex: 0,
    }
    expect(isPointInElement({ x: 50, y: 5 }, arrow, 10)).toBe(true)
    expect(isPointInElement({ x: 50, y: 50 }, arrow, 10)).toBe(false)
  })

  it('should detect point in ellipse element', () => {
    const ellipse: EllipseElement = {
      id: 'ellipse',
      type: 'ellipse',
      x: 0,
      y: 0,
      width: 100,
      height: 60,
      fill: '#fff',
      stroke: '#000',
      strokeWidth: 2,
      zIndex: 0,
    }
    expect(isPointInElement({ x: 50, y: 30 }, ellipse)).toBe(true)
    expect(isPointInElement({ x: 5, y: 5 }, ellipse)).toBe(false)
  })
})
