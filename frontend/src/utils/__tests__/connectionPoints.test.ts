/**
 * Connection Points Utility Tests
 */

import { describe, it, expect } from 'vitest'
import {
  getConnectionPoints,
  getConnectionPoint,
  findNearestConnectionPoint,
  updateConnectedArrows,
} from '../connectionPoints'
import type { CanvasElement, RectangleElement, ArrowElement } from '@/types/canvas'

const createRectangle = (
  id: string,
  x: number,
  y: number,
  width: number = 100,
  height: number = 80
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

const createArrow = (
  id: string,
  x: number,
  y: number,
  endX: number,
  endY: number
): ArrowElement => ({
  id,
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

describe('getConnectionPoints', () => {
  it('should return 4 connection points for rectangle', () => {
    const element = createRectangle('1', 100, 100, 100, 80)
    const points = getConnectionPoints(element)
    expect(points).toHaveLength(4)
  })

  it('should calculate correct positions for top, right, bottom, left', () => {
    const element = createRectangle('1', 100, 100, 100, 80)
    const points = getConnectionPoints(element)

    const top = points.find(p => p.position === 'top')!
    const right = points.find(p => p.position === 'right')!
    const bottom = points.find(p => p.position === 'bottom')!
    const left = points.find(p => p.position === 'left')!

    expect(top.x).toBe(150) // x + width/2
    expect(top.y).toBe(100) // y

    expect(right.x).toBe(200) // x + width
    expect(right.y).toBe(140) // y + height/2

    expect(bottom.x).toBe(150) // x + width/2
    expect(bottom.y).toBe(180) // y + height

    expect(left.x).toBe(100) // x
    expect(left.y).toBe(140) // y + height/2
  })

  it('should return empty array for arrow elements', () => {
    const arrow = createArrow('1', 100, 100, 200, 200)
    const points = getConnectionPoints(arrow)
    expect(points).toHaveLength(0)
  })

  it('should include element ID in point IDs', () => {
    const element = createRectangle('rect-1', 100, 100)
    const points = getConnectionPoints(element)
    points.forEach(point => {
      expect(point.id).toContain('rect-1')
    })
  })
})

describe('getConnectionPoint', () => {
  const element = createRectangle('1', 100, 100, 100, 80)

  it('should return correct point for top position', () => {
    const point = getConnectionPoint(element, 'top')
    expect(point).toEqual({ x: 150, y: 100 })
  })

  it('should return correct point for right position', () => {
    const point = getConnectionPoint(element, 'right')
    expect(point).toEqual({ x: 200, y: 140 })
  })

  it('should return correct point for bottom position', () => {
    const point = getConnectionPoint(element, 'bottom')
    expect(point).toEqual({ x: 150, y: 180 })
  })

  it('should return correct point for left position', () => {
    const point = getConnectionPoint(element, 'left')
    expect(point).toEqual({ x: 100, y: 140 })
  })
})

describe('findNearestConnectionPoint', () => {
  const elements: CanvasElement[] = [
    createRectangle('rect1', 100, 100, 100, 80),
    createRectangle('rect2', 300, 100, 100, 80),
  ]

  it('should find nearest connection point within threshold', () => {
    // Point near the right edge of rect1 (at x=200, y=140)
    const result = findNearestConnectionPoint({ x: 195, y: 142 }, elements)
    expect(result).not.toBeNull()
    expect(result?.element.id).toBe('rect1')
    expect(result?.connectionPoint.position).toBe('right')
  })

  it('should return null when no points within threshold', () => {
    const result = findNearestConnectionPoint({ x: 500, y: 500 }, elements)
    expect(result).toBeNull()
  })

  it('should exclude specified element IDs', () => {
    // Point near rect1's right edge
    const result = findNearestConnectionPoint(
      { x: 195, y: 142 },
      elements,
      'rect1' // Exclude rect1
    )
    expect(result).toBeNull()
  })

  it('should find the closest point among multiple options', () => {
    // Point equidistant between rect1 right (200, 140) and rect2 left (300, 140)
    // But closer to rect1
    const result = findNearestConnectionPoint({ x: 210, y: 140 }, elements)
    expect(result?.element.id).toBe('rect1')
  })
})

describe('updateConnectedArrows', () => {
  it('should update arrow start position when connected element moves', () => {
    const rect = createRectangle('rect1', 200, 200, 100, 80) // Moved from 100,100
    const arrow: ArrowElement = {
      ...createArrow('arrow1', 150, 100, 500, 300),
      startConnection: {
        elementId: 'rect1',
        point: 'top',
      },
    }

    const elements: CanvasElement[] = [rect, arrow]
    const result = updateConnectedArrows(elements, 'rect1')

    const updatedArrow = result.find(e => e.id === 'arrow1') as ArrowElement
    // Top connection point of rect at new position (200+50, 200) = (250, 200)
    expect(updatedArrow.x).toBe(250)
    expect(updatedArrow.y).toBe(200)
  })

  it('should update arrow end position when connected element moves', () => {
    const rect = createRectangle('rect1', 200, 200, 100, 80)
    const arrow: ArrowElement = {
      ...createArrow('arrow1', 0, 0, 150, 100),
      endConnection: {
        elementId: 'rect1',
        point: 'left',
      },
    }

    const elements: CanvasElement[] = [rect, arrow]
    const result = updateConnectedArrows(elements, 'rect1')

    const updatedArrow = result.find(e => e.id === 'arrow1') as ArrowElement
    // Left connection point of rect at new position (200, 200+40) = (200, 240)
    expect(updatedArrow.endX).toBe(200)
    expect(updatedArrow.endY).toBe(240)
  })

  it('should not update unconnected arrows when an element moves', () => {
    const rect1 = createRectangle('rect1', 100, 100)
    const rect2 = createRectangle('rect2', 300, 300)
    const arrow = createArrow('arrow1', 50, 50, 400, 400) // Not connected to anything

    const elements: CanvasElement[] = [rect1, rect2, arrow]
    const result = updateConnectedArrows(elements, 'rect2')

    // Unconnected arrow should remain unchanged
    const updatedArrow = result.find(e => e.id === 'arrow1') as ArrowElement
    expect(updatedArrow.x).toBe(50)
    expect(updatedArrow.y).toBe(50)
    expect(updatedArrow.endX).toBe(400)
    expect(updatedArrow.endY).toBe(400)
  })

  it('should update both endpoints when arrow is connected and any connected element moves', () => {
    const rect1 = createRectangle('rect1', 100, 100) // right point at (200, 140)
    const rect2 = createRectangle('rect2', 300, 300) // left point at (300, 340)
    const arrow: ArrowElement = {
      ...createArrow('arrow1', 150, 140, 300, 340),
      startConnection: { elementId: 'rect1', point: 'right' },
      endConnection: { elementId: 'rect2', point: 'left' },
    }

    const elements: CanvasElement[] = [rect1, rect2, arrow]
    const result = updateConnectedArrows(elements, 'rect2')

    // Both endpoints get recalculated based on current element positions
    const updatedArrow = result.find(e => e.id === 'arrow1') as ArrowElement
    expect(updatedArrow.x).toBe(200) // rect1 right point: 100 + 100 = 200
    expect(updatedArrow.y).toBe(140) // rect1 right point: 100 + 80/2 = 140
    expect(updatedArrow.endX).toBe(300) // rect2 left point: 300
    expect(updatedArrow.endY).toBe(340) // rect2 left point: 300 + 80/2 = 340
  })

  it('should return elements unchanged when no connections exist', () => {
    const rect = createRectangle('rect1', 100, 100)
    const arrow = createArrow('arrow1', 0, 0, 50, 50)

    const elements: CanvasElement[] = [rect, arrow]
    const result = updateConnectedArrows(elements, 'rect1')

    expect(result).toEqual(elements)
  })
})
