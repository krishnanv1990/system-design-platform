/**
 * Alignment Utility Tests
 */

import { describe, it, expect } from 'vitest'
import {
  calculateBounds,
  alignLeft,
  alignRight,
  alignCenterHorizontal,
  alignTop,
  alignBottom,
  alignCenterVertical,
  distributeHorizontally,
  distributeVertically,
  moveElements,
} from '../alignment'
import type { CanvasElement, RectangleElement, ArrowElement } from '@/types/canvas'

const createRectangle = (id: string, x: number, y: number, width: number, height: number): RectangleElement => ({
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

describe('calculateBounds', () => {
  it('should return zero bounds for empty array', () => {
    const bounds = calculateBounds([])
    expect(bounds).toEqual({ x: 0, y: 0, width: 0, height: 0 })
  })

  it('should calculate bounds for single element', () => {
    const elements = [createRectangle('1', 100, 50, 80, 60)]
    const bounds = calculateBounds(elements)
    expect(bounds).toEqual({ x: 100, y: 50, width: 80, height: 60 })
  })

  it('should calculate bounds for multiple elements', () => {
    const elements = [
      createRectangle('1', 100, 50, 80, 60),
      createRectangle('2', 300, 200, 100, 80),
    ]
    const bounds = calculateBounds(elements)
    expect(bounds.x).toBe(100)
    expect(bounds.y).toBe(50)
    expect(bounds.width).toBe(300) // 400 - 100
    expect(bounds.height).toBe(230) // 280 - 50
  })

  it('should handle arrow elements correctly', () => {
    const elements: CanvasElement[] = [
      {
        id: '1',
        type: 'arrow',
        x: 100,
        y: 100,
        endX: 300,
        endY: 50,
        width: 0,
        height: 0,
        fill: 'transparent',
        stroke: '#000',
        strokeWidth: 2,
        lineStyle: 'solid',
        zIndex: 0,
      } as ArrowElement,
    ]
    const bounds = calculateBounds(elements)
    expect(bounds.x).toBe(100)
    expect(bounds.y).toBe(50)
    expect(bounds.width).toBe(200)
    expect(bounds.height).toBe(50)
  })
})

describe('alignLeft', () => {
  it('should return single element unchanged', () => {
    const elements = [createRectangle('1', 100, 50, 80, 60)]
    const result = alignLeft(elements)
    expect(result[0].x).toBe(100)
  })

  it('should align elements to leftmost edge', () => {
    const elements = [
      createRectangle('1', 100, 50, 80, 60),
      createRectangle('2', 300, 200, 100, 80),
    ]
    const result = alignLeft(elements)
    expect(result[0].x).toBe(100)
    expect(result[1].x).toBe(100)
  })
})

describe('alignRight', () => {
  it('should align elements to rightmost edge', () => {
    const elements = [
      createRectangle('1', 100, 50, 80, 60),
      createRectangle('2', 300, 200, 100, 80),
    ]
    const result = alignRight(elements)
    // Rightmost edge is 300 + 100 = 400
    expect(result[0].x).toBe(400 - 80) // 320
    expect(result[1].x).toBe(400 - 100) // 300
  })
})

describe('alignCenterHorizontal', () => {
  it('should align elements to horizontal center', () => {
    const elements = [
      createRectangle('1', 100, 50, 80, 60),
      createRectangle('2', 300, 200, 100, 80),
    ]
    const result = alignCenterHorizontal(elements)
    // Bounds: x=100, width=300, center=250
    const expectedCenterX = 250
    expect(result[0].x).toBe(expectedCenterX - 40) // 210
    expect(result[1].x).toBe(expectedCenterX - 50) // 200
  })
})

describe('alignTop', () => {
  it('should align elements to top edge', () => {
    const elements = [
      createRectangle('1', 100, 50, 80, 60),
      createRectangle('2', 300, 200, 100, 80),
    ]
    const result = alignTop(elements)
    expect(result[0].y).toBe(50)
    expect(result[1].y).toBe(50)
  })
})

describe('alignBottom', () => {
  it('should align elements to bottom edge', () => {
    const elements = [
      createRectangle('1', 100, 50, 80, 60),
      createRectangle('2', 300, 200, 100, 80),
    ]
    const result = alignBottom(elements)
    // Bottom edge is 200 + 80 = 280
    expect(result[0].y).toBe(280 - 60) // 220
    expect(result[1].y).toBe(280 - 80) // 200
  })
})

describe('alignCenterVertical', () => {
  it('should align elements to vertical center', () => {
    const elements = [
      createRectangle('1', 100, 50, 80, 60),
      createRectangle('2', 300, 200, 100, 80),
    ]
    const result = alignCenterVertical(elements)
    // Bounds: y=50, height=230, center=165
    const expectedCenterY = 165
    expect(result[0].y).toBe(expectedCenterY - 30) // 135
    expect(result[1].y).toBe(expectedCenterY - 40) // 125
  })
})

describe('distributeHorizontally', () => {
  it('should return elements unchanged when less than 3', () => {
    const elements = [
      createRectangle('1', 100, 50, 80, 60),
      createRectangle('2', 300, 200, 100, 80),
    ]
    const result = distributeHorizontally(elements)
    expect(result).toEqual(elements)
  })

  it('should distribute elements with equal spacing', () => {
    const elements = [
      createRectangle('1', 100, 50, 50, 60),
      createRectangle('2', 200, 50, 50, 60),
      createRectangle('3', 400, 50, 50, 60),
    ]
    const result = distributeHorizontally(elements)
    // Total width = 350 (from 100 to 450), element widths = 150, gaps = 200/2 = 100
    // Sorted by x: element1, element2, element3
    expect(result[0].x).toBe(100) // First stays at bounds.x
    expect(result[2].x).toBe(400) // Last calculated from gap
  })
})

describe('distributeVertically', () => {
  it('should return elements unchanged when less than 3', () => {
    const elements = [
      createRectangle('1', 100, 50, 80, 60),
    ]
    const result = distributeVertically(elements)
    expect(result).toEqual(elements)
  })

  it('should distribute elements with equal vertical spacing', () => {
    const elements = [
      createRectangle('1', 100, 100, 50, 50),
      createRectangle('2', 100, 200, 50, 50),
      createRectangle('3', 100, 400, 50, 50),
    ]
    const result = distributeVertically(elements)
    expect(result[0].y).toBe(100) // First stays at bounds.y
  })
})

describe('moveElements', () => {
  it('should move selected elements by delta', () => {
    const elements = [
      createRectangle('1', 100, 50, 80, 60),
      createRectangle('2', 300, 200, 100, 80),
    ]
    const result = moveElements(elements, new Set(['1']), 10, 20)
    expect(result[0].x).toBe(110)
    expect(result[0].y).toBe(70)
    expect(result[1].x).toBe(300) // Unchanged
    expect(result[1].y).toBe(200)
  })

  it('should move arrow elements correctly', () => {
    const elements: CanvasElement[] = [
      {
        id: '1',
        type: 'arrow',
        x: 100,
        y: 100,
        endX: 300,
        endY: 200,
        width: 0,
        height: 0,
        fill: 'transparent',
        stroke: '#000',
        strokeWidth: 2,
        lineStyle: 'solid',
        zIndex: 0,
      } as ArrowElement,
    ]
    const result = moveElements(elements, new Set(['1']), 50, 30)
    const arrow = result[0] as ArrowElement
    expect(arrow.x).toBe(150)
    expect(arrow.y).toBe(130)
    expect(arrow.endX).toBe(350)
    expect(arrow.endY).toBe(230)
  })
})
