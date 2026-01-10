/**
 * Snap Utility Tests
 */

import { describe, it, expect } from 'vitest'
import { snapToGrid, snapPointToGrid, getSnapLines, snapToElements } from '../snap'
import type { CanvasElement, RectangleElement } from '@/types/canvas'

const createRectangle = (
  id: string,
  x: number,
  y: number,
  width: number = 80,
  height: number = 60
): RectangleElement => ({
  id,
  type: 'rectangle',
  x,
  y,
  width,
  height,
  fill: '#fff',
  stroke: '#000',
  strokeWidth: 2,
  zIndex: 0,
})

describe('snapToGrid', () => {
  it('should snap value to nearest grid point', () => {
    expect(snapToGrid(23, 20)).toBe(20)
    expect(snapToGrid(37, 20)).toBe(40)
  })

  it('should round up when exactly at half grid', () => {
    expect(snapToGrid(30, 20)).toBe(40)
  })

  it('should return exact value when on grid', () => {
    expect(snapToGrid(40, 20)).toBe(40)
    expect(snapToGrid(0, 20)).toBe(0)
  })

  it('should handle negative values', () => {
    expect(snapToGrid(-23, 20)).toBe(-20)
    expect(snapToGrid(-37, 20)).toBe(-40)
  })

  it('should handle zero', () => {
    expect(snapToGrid(0, 20)).toBe(0)
  })

  it('should handle different grid sizes', () => {
    expect(snapToGrid(17, 10)).toBe(20)
    expect(snapToGrid(17, 5)).toBe(15)
    expect(snapToGrid(17, 25)).toBe(25)
  })

  it('should not snap when disabled', () => {
    expect(snapToGrid(23, 20, false)).toBe(23)
    expect(snapToGrid(37, 20, false)).toBe(37)
  })
})

describe('snapPointToGrid', () => {
  it('should snap both x and y coordinates', () => {
    const result = snapPointToGrid({ x: 23, y: 37 }, 20)
    expect(result).toEqual({ x: 20, y: 40 })
  })

  it('should maintain independent snap for each axis', () => {
    const result = snapPointToGrid({ x: 5, y: 35 }, 20)
    expect(result).toEqual({ x: 0, y: 40 })
  })

  it('should handle negative coordinates', () => {
    const result = snapPointToGrid({ x: -23, y: -37 }, 20)
    expect(result).toEqual({ x: -20, y: -40 })
  })

  it('should not snap when disabled', () => {
    const result = snapPointToGrid({ x: 23, y: 37 }, 20, false)
    expect(result).toEqual({ x: 23, y: 37 })
  })
})

describe('getSnapLines', () => {
  it('should return empty arrays when no other elements nearby', () => {
    const movingElement = createRectangle('1', 0, 0)
    const otherElement = createRectangle('2', 500, 500)
    const lines = getSnapLines(movingElement, [movingElement, otherElement], 10)

    expect(lines.horizontal).toHaveLength(0)
    expect(lines.vertical).toHaveLength(0)
  })

  it('should find vertical snap lines when elements align', () => {
    const movingElement = createRectangle('1', 100, 100, 80, 60)
    const otherElement = createRectangle('2', 100, 300, 80, 60)  // Same x position
    const lines = getSnapLines(movingElement, [movingElement, otherElement], 10)

    // Both elements have x=100, center=140, right=180
    expect(lines.vertical).toContain(100)
  })

  it('should find horizontal snap lines when elements align', () => {
    const movingElement = createRectangle('1', 100, 100, 80, 60)
    const otherElement = createRectangle('2', 300, 100, 80, 60)  // Same y position
    const lines = getSnapLines(movingElement, [movingElement, otherElement], 10)

    // Both elements have y=100
    expect(lines.horizontal).toContain(100)
  })

  it('should not include the moving element in results', () => {
    const movingElement = createRectangle('1', 100, 100, 80, 60)
    const lines = getSnapLines(movingElement, [movingElement], 10)

    expect(lines.horizontal).toHaveLength(0)
    expect(lines.vertical).toHaveLength(0)
  })

  it('should detect center alignment', () => {
    const movingElement = createRectangle('1', 100, 100, 80, 60)  // center at 140
    const otherElement = createRectangle('2', 100, 300, 80, 60)  // center at 140
    const lines = getSnapLines(movingElement, [movingElement, otherElement], 10)

    expect(lines.vertical).toContain(140) // Both have center at x=140
  })
})

describe('snapToElements', () => {
  it('should snap to element left edge when within threshold', () => {
    const movingElement = createRectangle('1', 0, 0, 80, 60)
    const targetElement = createRectangle('2', 100, 100, 80, 60)
    const result = snapToElements(
      { x: 105, y: 200 },
      movingElement,
      [movingElement, targetElement],
      10
    )
    expect(result.x).toBe(100) // Snaps to left edge of target
  })

  it('should not snap when outside threshold', () => {
    const movingElement = createRectangle('1', 0, 0, 80, 60)
    const targetElement = createRectangle('2', 100, 100, 80, 60)
    const result = snapToElements(
      { x: 120, y: 200 },
      movingElement,
      [movingElement, targetElement],
      5
    )
    expect(result.x).toBe(120)
    expect(result.y).toBe(200)
  })

  it('should return original point when no elements nearby', () => {
    const movingElement = createRectangle('1', 0, 0, 80, 60)
    const targetElement = createRectangle('2', 500, 500, 80, 60)
    const result = snapToElements(
      { x: 50, y: 50 },
      movingElement,
      [movingElement, targetElement],
      10
    )
    expect(result).toEqual({ x: 50, y: 50 })
  })

  it('should not snap to itself', () => {
    const movingElement = createRectangle('1', 100, 100, 80, 60)
    const result = snapToElements(
      { x: 105, y: 105 },
      movingElement,
      [movingElement],
      10
    )
    expect(result.x).toBe(105)
    expect(result.y).toBe(105)
  })

  it('should snap to top edge', () => {
    const movingElement = createRectangle('1', 0, 0, 80, 60)
    const targetElement = createRectangle('2', 200, 100, 80, 60)
    const result = snapToElements(
      { x: 50, y: 105 },
      movingElement,
      [movingElement, targetElement],
      10
    )
    expect(result.y).toBe(100)
  })

  it('should snap to right edge', () => {
    const movingElement = createRectangle('1', 0, 0, 80, 60)
    const targetElement = createRectangle('2', 100, 100, 80, 60) // right edge at 180
    const result = snapToElements(
      { x: 95, y: 200 }, // right edge would be at 175, close to 180
      movingElement,
      [movingElement, targetElement],
      10
    )
    // Should snap right edge to target's right edge (100 + 80 = 180)
    // So x = 180 - 80 = 100
    expect(result.x).toBe(100)
  })

  it('should snap to center alignment', () => {
    const movingElement = createRectangle('1', 0, 0, 80, 60) // center at x=40
    const targetElement = createRectangle('2', 100, 200, 80, 60) // center at x=140
    const result = snapToElements(
      { x: 95, y: 300 }, // center would be at 135, close to 140
      movingElement,
      [movingElement, targetElement],
      10
    )
    // Should snap center to 140, so x = 140 - 40 = 100
    expect(result.x).toBe(100)
  })
})
