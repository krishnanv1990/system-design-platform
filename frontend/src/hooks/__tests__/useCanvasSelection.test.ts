/**
 * useCanvasSelection Hook Tests
 */

import { describe, it, expect, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useCanvasSelection } from '../useCanvasSelection'

describe('useCanvasSelection', () => {
  it('should initialize with empty selection', () => {
    const { result } = renderHook(() => useCanvasSelection())
    expect(result.current.selectedIds.size).toBe(0)
    expect(result.current.editingId).toBeNull()
    expect(result.current.hasSelection).toBe(false)
    expect(result.current.selectionCount).toBe(0)
  })

  it('should select single element', () => {
    const { result } = renderHook(() => useCanvasSelection())

    act(() => {
      result.current.select('element-1')
    })

    expect(result.current.selectedIds.has('element-1')).toBe(true)
    expect(result.current.selectionCount).toBe(1)
    expect(result.current.hasSelection).toBe(true)
  })

  it('should replace selection on single select', () => {
    const { result } = renderHook(() => useCanvasSelection())

    act(() => {
      result.current.select('element-1')
    })

    act(() => {
      result.current.select('element-2')
    })

    expect(result.current.selectedIds.has('element-1')).toBe(false)
    expect(result.current.selectedIds.has('element-2')).toBe(true)
    expect(result.current.selectionCount).toBe(1)
  })

  it('should select multiple elements', () => {
    const { result } = renderHook(() => useCanvasSelection())

    act(() => {
      result.current.selectMultiple(['element-1', 'element-2', 'element-3'])
    })

    expect(result.current.selectedIds.size).toBe(3)
    expect(result.current.selectedIds.has('element-1')).toBe(true)
    expect(result.current.selectedIds.has('element-2')).toBe(true)
    expect(result.current.selectedIds.has('element-3')).toBe(true)
  })

  it('should toggle selection', () => {
    const { result } = renderHook(() => useCanvasSelection())

    act(() => {
      result.current.select('element-1')
    })

    act(() => {
      result.current.toggleSelection('element-1')
    })

    expect(result.current.selectedIds.has('element-1')).toBe(false)

    act(() => {
      result.current.toggleSelection('element-1')
    })

    expect(result.current.selectedIds.has('element-1')).toBe(true)
  })

  it('should clear selection', () => {
    const { result } = renderHook(() => useCanvasSelection())

    act(() => {
      result.current.selectMultiple(['element-1', 'element-2'])
    })

    act(() => {
      result.current.clearSelection()
    })

    expect(result.current.selectedIds.size).toBe(0)
    expect(result.current.hasSelection).toBe(false)
  })

  it('should check if element is selected', () => {
    const { result } = renderHook(() => useCanvasSelection())

    act(() => {
      result.current.select('element-1')
    })

    expect(result.current.isSelected('element-1')).toBe(true)
    expect(result.current.isSelected('element-2')).toBe(false)
  })

  it('should set editing ID', () => {
    const { result } = renderHook(() => useCanvasSelection())

    act(() => {
      result.current.setEditingId('element-1')
    })

    expect(result.current.editingId).toBe('element-1')

    act(() => {
      result.current.setEditingId(null)
    })

    expect(result.current.editingId).toBeNull()
  })

  it('should get selected elements from array', () => {
    const { result } = renderHook(() => useCanvasSelection())
    const elements = [
      { id: 'element-1', type: 'rectangle' },
      { id: 'element-2', type: 'ellipse' },
      { id: 'element-3', type: 'text' },
    ]

    act(() => {
      result.current.selectMultiple(['element-1', 'element-3'])
    })

    const selected = result.current.getSelectedElements(elements as any)
    expect(selected).toHaveLength(2)
    expect(selected.map(e => e.id)).toContain('element-1')
    expect(selected.map(e => e.id)).toContain('element-3')
    expect(selected.map(e => e.id)).not.toContain('element-2')
  })
})
