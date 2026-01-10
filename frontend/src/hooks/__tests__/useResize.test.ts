/**
 * useResize Hook Tests
 */

import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useResize } from '../useResize'
import type { RectangleElement } from '@/types/canvas'

const createRectangle = (
  x: number,
  y: number,
  width: number,
  height: number
): RectangleElement => ({
  id: 'test-element',
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

describe('useResize', () => {
  it('should initialize with isResizing false', () => {
    const { result } = renderHook(() => useResize())
    expect(result.current.isResizing).toBe(false)
    expect(result.current.resizeState.handle).toBeNull()
  })

  it('should start resize correctly', () => {
    const { result } = renderHook(() => useResize())
    const element = createRectangle(100, 100, 200, 150)

    act(() => {
      result.current.startResize(element, 'se', 300, 250)
    })

    expect(result.current.isResizing).toBe(true)
    expect(result.current.resizeState.handle).toBe('se')
    expect(result.current.resizeState.startWidth).toBe(200)
    expect(result.current.resizeState.startHeight).toBe(150)
  })

  it('should resize from SE handle correctly', () => {
    const { result } = renderHook(() => useResize())
    const element = createRectangle(100, 100, 200, 150)

    act(() => {
      result.current.startResize(element, 'se', 300, 250)
    })

    const updates = result.current.updateResize(350, 300, element)

    expect(updates).not.toBeNull()
    expect(updates!.width).toBe(250) // 200 + 50
    expect(updates!.height).toBe(200) // 150 + 50
    expect(updates!.x).toBe(100) // Unchanged
    expect(updates!.y).toBe(100) // Unchanged
  })

  it('should resize from NW handle correctly (moves origin)', () => {
    const { result } = renderHook(() => useResize())
    const element = createRectangle(100, 100, 200, 150)

    act(() => {
      result.current.startResize(element, 'nw', 100, 100)
    })

    const updates = result.current.updateResize(80, 80, element)

    expect(updates).not.toBeNull()
    expect(updates!.x).toBe(80) // Moved left
    expect(updates!.y).toBe(80) // Moved up
    expect(updates!.width).toBe(220) // 200 + 20
    expect(updates!.height).toBe(170) // 150 + 20
  })

  it('should resize from N handle (vertical only)', () => {
    const { result } = renderHook(() => useResize())
    const element = createRectangle(100, 100, 200, 150)

    act(() => {
      result.current.startResize(element, 'n', 200, 100)
    })

    const updates = result.current.updateResize(250, 80, element)

    expect(updates).not.toBeNull()
    expect(updates!.width).toBe(200) // Unchanged
    expect(updates!.height).toBe(170) // 150 + 20
    expect(updates!.y).toBe(80) // Moved up
  })

  it('should resize from E handle (horizontal only)', () => {
    const { result } = renderHook(() => useResize())
    const element = createRectangle(100, 100, 200, 150)

    act(() => {
      result.current.startResize(element, 'e', 300, 175)
    })

    const updates = result.current.updateResize(350, 200, element)

    expect(updates).not.toBeNull()
    expect(updates!.width).toBe(250) // 200 + 50
    expect(updates!.height).toBe(150) // Unchanged
  })

  it('should enforce minimum size constraints', () => {
    const { result } = renderHook(() => useResize())
    const element = createRectangle(100, 100, 200, 150)

    act(() => {
      result.current.startResize(element, 'se', 300, 250)
    })

    // Try to resize to very small
    const updates = result.current.updateResize(105, 105, element)

    expect(updates).not.toBeNull()
    expect(updates!.width).toBeGreaterThanOrEqual(20) // Min size
    expect(updates!.height).toBeGreaterThanOrEqual(20) // Min size
  })

  it('should reset state on endResize', () => {
    const { result } = renderHook(() => useResize())
    const element = createRectangle(100, 100, 200, 150)

    act(() => {
      result.current.startResize(element, 'se', 300, 250)
    })

    expect(result.current.isResizing).toBe(true)

    act(() => {
      result.current.endResize()
    })

    expect(result.current.isResizing).toBe(false)
    expect(result.current.resizeState.handle).toBeNull()
  })

  it('should detect correct handle at position', () => {
    const { result } = renderHook(() => useResize())
    const element = createRectangle(100, 100, 200, 150)

    // Test SE corner (at 300, 250)
    expect(result.current.getHandleAtPosition(element, 300, 250)).toBe('se')

    // Test NW corner (at 100, 100)
    expect(result.current.getHandleAtPosition(element, 100, 100)).toBe('nw')

    // Test center (no handle)
    expect(result.current.getHandleAtPosition(element, 200, 175)).toBeNull()
  })

  it('should return correct cursor for each handle', () => {
    const { result } = renderHook(() => useResize())

    expect(result.current.getHandleCursor('nw')).toBe('nw-resize')
    expect(result.current.getHandleCursor('ne')).toBe('ne-resize')
    expect(result.current.getHandleCursor('sw')).toBe('sw-resize')
    expect(result.current.getHandleCursor('se')).toBe('se-resize')
    expect(result.current.getHandleCursor('n')).toBe('n-resize')
    expect(result.current.getHandleCursor('s')).toBe('s-resize')
    expect(result.current.getHandleCursor('e')).toBe('e-resize')
    expect(result.current.getHandleCursor('w')).toBe('w-resize')
  })

  it('should return null handle for arrow elements', () => {
    const { result } = renderHook(() => useResize())
    const arrow = {
      id: 'arrow-1',
      type: 'arrow' as const,
      x: 100,
      y: 100,
      endX: 200,
      endY: 200,
      width: 0,
      height: 0,
      fill: 'transparent',
      stroke: '#000',
      strokeWidth: 2,
      lineStyle: 'solid' as const,
      zIndex: 0,
    }

    expect(result.current.getHandleAtPosition(arrow as any, 100, 100)).toBeNull()
  })
})
