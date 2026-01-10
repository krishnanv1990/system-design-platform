/**
 * Z-Order Utility Tests
 */

import { describe, it, expect } from 'vitest'
import {
  sortByZIndex,
  getMaxZIndex,
  getMinZIndex,
  bringToFront,
  sendToBack,
  bringForward,
  sendBackward,
  normalizeZIndices,
  assignZIndex,
  assignZIndicesToMultiple,
} from '../zOrder'
import type { RectangleElement } from '@/types/canvas'

const createRect = (id: string, zIndex: number): RectangleElement => ({
  id,
  type: 'rectangle',
  x: 0,
  y: 0,
  width: 100,
  height: 100,
  fill: '#fff',
  stroke: '#000',
  strokeWidth: 2,
  zIndex,
})

describe('sortByZIndex', () => {
  it('should sort elements by z-index in ascending order', () => {
    const elements = [
      createRect('c', 3),
      createRect('a', 1),
      createRect('b', 2),
    ]
    const sorted = sortByZIndex(elements)
    expect(sorted[0].id).toBe('a')
    expect(sorted[1].id).toBe('b')
    expect(sorted[2].id).toBe('c')
  })

  it('should handle elements without z-index', () => {
    const elements = [
      { ...createRect('a', 0), zIndex: undefined },
      createRect('b', 1),
    ]
    const sorted = sortByZIndex(elements as RectangleElement[])
    expect(sorted[0].id).toBe('a')
    expect(sorted[1].id).toBe('b')
  })

  it('should not modify original array', () => {
    const elements = [createRect('b', 2), createRect('a', 1)]
    const sorted = sortByZIndex(elements)
    expect(elements[0].id).toBe('b')
    expect(sorted[0].id).toBe('a')
  })
})

describe('getMaxZIndex', () => {
  it('should return highest z-index', () => {
    const elements = [
      createRect('a', 1),
      createRect('b', 5),
      createRect('c', 3),
    ]
    expect(getMaxZIndex(elements)).toBe(5)
  })

  it('should return 0 for empty array', () => {
    expect(getMaxZIndex([])).toBe(0)
  })
})

describe('getMinZIndex', () => {
  it('should return lowest z-index', () => {
    const elements = [
      createRect('a', 2),
      createRect('b', 5),
      createRect('c', 3),
    ]
    expect(getMinZIndex(elements)).toBe(2)
  })

  it('should return 0 for empty array', () => {
    expect(getMinZIndex([])).toBe(0)
  })
})

describe('bringToFront', () => {
  it('should bring element to highest z-index', () => {
    const elements = [
      createRect('a', 1),
      createRect('b', 2),
      createRect('c', 3),
    ]
    const result = bringToFront(elements, new Set(['a']))
    const movedElement = result.find(e => e.id === 'a')!
    expect(movedElement.zIndex).toBe(4)
  })

  it('should bring multiple elements to front', () => {
    const elements = [
      createRect('a', 1),
      createRect('b', 2),
      createRect('c', 3),
    ]
    const result = bringToFront(elements, new Set(['a', 'b']))
    const aElement = result.find(e => e.id === 'a')!
    const bElement = result.find(e => e.id === 'b')!
    expect(aElement.zIndex).toBeGreaterThan(3)
    expect(bElement.zIndex).toBeGreaterThan(3)
  })
})

describe('sendToBack', () => {
  it('should send element to lowest z-index', () => {
    const elements = [
      createRect('a', 1),
      createRect('b', 2),
      createRect('c', 3),
    ]
    const result = sendToBack(elements, new Set(['c']))
    const movedElement = result.find(e => e.id === 'c')!
    expect(movedElement.zIndex).toBeLessThan(1)
  })

  it('should send multiple elements to back', () => {
    const elements = [
      createRect('a', 1),
      createRect('b', 2),
      createRect('c', 3),
    ]
    const result = sendToBack(elements, new Set(['b', 'c']))
    const bElement = result.find(e => e.id === 'b')!
    const cElement = result.find(e => e.id === 'c')!
    expect(bElement.zIndex).toBeLessThan(1)
    expect(cElement.zIndex).toBeLessThan(1)
  })
})

describe('bringForward', () => {
  it('should swap z-index with next element', () => {
    const elements = [
      createRect('a', 1),
      createRect('b', 2),
      createRect('c', 3),
    ]
    const result = bringForward(elements, new Set(['a']))
    const aElement = result.find(e => e.id === 'a')!
    const bElement = result.find(e => e.id === 'b')!
    expect(aElement.zIndex).toBe(2)
    expect(bElement.zIndex).toBe(1)
  })

  it('should not move element already at top', () => {
    const elements = [
      createRect('a', 1),
      createRect('b', 2),
    ]
    const result = bringForward(elements, new Set(['b']))
    const bElement = result.find(e => e.id === 'b')!
    expect(bElement.zIndex).toBe(2)
  })
})

describe('sendBackward', () => {
  it('should swap z-index with previous element', () => {
    const elements = [
      createRect('a', 1),
      createRect('b', 2),
      createRect('c', 3),
    ]
    const result = sendBackward(elements, new Set(['c']))
    const cElement = result.find(e => e.id === 'c')!
    const bElement = result.find(e => e.id === 'b')!
    expect(cElement.zIndex).toBe(2)
    expect(bElement.zIndex).toBe(3)
  })

  it('should not move element already at bottom', () => {
    const elements = [
      createRect('a', 1),
      createRect('b', 2),
    ]
    const result = sendBackward(elements, new Set(['a']))
    const aElement = result.find(e => e.id === 'a')!
    expect(aElement.zIndex).toBe(1)
  })
})

describe('normalizeZIndices', () => {
  it('should normalize z-indices to sequential values starting from 0', () => {
    const elements = [
      createRect('a', 10),
      createRect('b', 50),
      createRect('c', 30),
    ]
    const result = normalizeZIndices(elements)
    expect(result[0].zIndex).toBe(0)
    expect(result[1].zIndex).toBe(1)
    expect(result[2].zIndex).toBe(2)
  })

  it('should maintain original order by z-index', () => {
    const elements = [
      createRect('c', 30),
      createRect('a', 10),
      createRect('b', 50),
    ]
    const result = normalizeZIndices(elements)
    expect(result[0].id).toBe('a')
    expect(result[1].id).toBe('c')
    expect(result[2].id).toBe('b')
  })
})

describe('assignZIndex', () => {
  it('should assign z-index one higher than max', () => {
    const elements = [
      createRect('a', 1),
      createRect('b', 5),
    ]
    const newElement = createRect('c', 0)
    const result = assignZIndex(elements, newElement)
    expect(result.zIndex).toBe(6)
  })

  it('should assign z-index 1 when no existing elements', () => {
    const newElement = createRect('a', 0)
    const result = assignZIndex([], newElement)
    expect(result.zIndex).toBe(1)
  })
})

describe('assignZIndicesToMultiple', () => {
  it('should assign unique z-indices to multiple elements in sequence', () => {
    const existingElements = [
      createRect('a', 1),
      createRect('b', 5),
    ]
    const newElements = [
      createRect('c', 0),
      createRect('d', 0),
      createRect('e', 0),
    ]
    const result = assignZIndicesToMultiple(existingElements, newElements)

    expect(result).toHaveLength(3)
    expect(result[0].zIndex).toBe(6) // maxZ (5) + 1
    expect(result[1].zIndex).toBe(7) // maxZ (5) + 2
    expect(result[2].zIndex).toBe(8) // maxZ (5) + 3
  })

  it('should start from z-index 1 when no existing elements', () => {
    const newElements = [
      createRect('a', 0),
      createRect('b', 0),
    ]
    const result = assignZIndicesToMultiple([], newElements)

    expect(result[0].zIndex).toBe(1)
    expect(result[1].zIndex).toBe(2)
  })

  it('should preserve original element IDs', () => {
    const existingElements = [createRect('existing', 5)]
    const newElements = [
      createRect('new1', 0),
      createRect('new2', 0),
    ]
    const result = assignZIndicesToMultiple(existingElements, newElements)

    expect(result[0].id).toBe('new1')
    expect(result[1].id).toBe('new2')
  })

  it('should preserve other element properties', () => {
    const existingElements = [createRect('existing', 5)]
    const newElement = {
      ...createRect('new', 0),
      width: 200,
      height: 150,
      fill: '#ff0000',
    }
    const result = assignZIndicesToMultiple(existingElements, [newElement])

    expect(result[0].width).toBe(200)
    expect(result[0].height).toBe(150)
    expect(result[0].fill).toBe('#ff0000')
    expect(result[0].zIndex).toBe(6)
  })

  it('should return empty array for empty input', () => {
    const result = assignZIndicesToMultiple([createRect('a', 5)], [])
    expect(result).toHaveLength(0)
  })

  it('should handle single element correctly', () => {
    const existingElements = [createRect('a', 10)]
    const newElements = [createRect('b', 0)]
    const result = assignZIndicesToMultiple(existingElements, newElements)

    expect(result).toHaveLength(1)
    expect(result[0].zIndex).toBe(11)
  })
})
