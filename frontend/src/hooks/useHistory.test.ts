import { describe, it, expect } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useHistory } from './useHistory'

describe('useHistory', () => {
  it('initializes with the provided initial state', () => {
    const { result } = renderHook(() => useHistory({ count: 0 }))
    expect(result.current.state).toEqual({ count: 0 })
  })

  it('updates state when setState is called', () => {
    const { result } = renderHook(() => useHistory({ count: 0 }))

    act(() => {
      result.current.setState({ count: 1 })
    })

    expect(result.current.state).toEqual({ count: 1 })
  })

  it('supports function updater for setState', () => {
    const { result } = renderHook(() => useHistory({ count: 0 }))

    act(() => {
      result.current.setState((prev) => ({ count: prev.count + 1 }))
    })

    expect(result.current.state).toEqual({ count: 1 })
  })

  it('can undo to previous state', () => {
    const { result } = renderHook(() => useHistory({ count: 0 }))

    act(() => {
      result.current.setState({ count: 1 })
    })

    act(() => {
      result.current.setState({ count: 2 })
    })

    expect(result.current.state).toEqual({ count: 2 })

    act(() => {
      result.current.undo()
    })

    expect(result.current.state).toEqual({ count: 1 })
  })

  it('can redo to next state after undo', () => {
    const { result } = renderHook(() => useHistory({ count: 0 }))

    act(() => {
      result.current.setState({ count: 1 })
    })

    act(() => {
      result.current.setState({ count: 2 })
    })

    act(() => {
      result.current.undo()
    })

    expect(result.current.state).toEqual({ count: 1 })

    act(() => {
      result.current.redo()
    })

    expect(result.current.state).toEqual({ count: 2 })
  })

  it('cannot undo when at initial state', () => {
    const { result } = renderHook(() => useHistory({ count: 0 }))

    expect(result.current.canUndo).toBe(false)

    act(() => {
      result.current.undo()
    })

    expect(result.current.state).toEqual({ count: 0 })
  })

  it('cannot redo when at latest state', () => {
    const { result } = renderHook(() => useHistory({ count: 0 }))

    act(() => {
      result.current.setState({ count: 1 })
    })

    expect(result.current.canRedo).toBe(false)

    act(() => {
      result.current.redo()
    })

    expect(result.current.state).toEqual({ count: 1 })
  })

  it('reports canUndo correctly', () => {
    const { result } = renderHook(() => useHistory({ count: 0 }))

    expect(result.current.canUndo).toBe(false)

    act(() => {
      result.current.setState({ count: 1 })
    })

    expect(result.current.canUndo).toBe(true)

    act(() => {
      result.current.undo()
    })

    expect(result.current.canUndo).toBe(false)
  })

  it('reports canRedo correctly', () => {
    const { result } = renderHook(() => useHistory({ count: 0 }))

    expect(result.current.canRedo).toBe(false)

    act(() => {
      result.current.setState({ count: 1 })
    })

    expect(result.current.canRedo).toBe(false)

    act(() => {
      result.current.undo()
    })

    expect(result.current.canRedo).toBe(true)

    act(() => {
      result.current.redo()
    })

    expect(result.current.canRedo).toBe(false)
  })

  it('clears future history when making changes after undo', () => {
    const { result } = renderHook(() => useHistory({ count: 0 }))

    act(() => {
      result.current.setState({ count: 1 })
    })

    act(() => {
      result.current.setState({ count: 2 })
    })

    act(() => {
      result.current.setState({ count: 3 })
    })

    // Undo twice to get back to count: 1
    act(() => {
      result.current.undo()
    })

    act(() => {
      result.current.undo()
    })

    expect(result.current.state).toEqual({ count: 1 })

    // Make a new change - this should clear future history
    act(() => {
      result.current.setState({ count: 10 })
    })

    expect(result.current.state).toEqual({ count: 10 })
    expect(result.current.canRedo).toBe(false)

    // Should be able to undo to count: 1
    act(() => {
      result.current.undo()
    })

    expect(result.current.state).toEqual({ count: 1 })
  })

  it('can undo multiple times in sequence', () => {
    const { result } = renderHook(() => useHistory({ count: 0 }))

    act(() => {
      result.current.setState({ count: 1 })
    })

    act(() => {
      result.current.setState({ count: 2 })
    })

    act(() => {
      result.current.setState({ count: 3 })
    })

    act(() => {
      result.current.undo()
    })

    expect(result.current.state).toEqual({ count: 2 })

    act(() => {
      result.current.undo()
    })

    expect(result.current.state).toEqual({ count: 1 })

    act(() => {
      result.current.undo()
    })

    expect(result.current.state).toEqual({ count: 0 })
  })

  it('can redo multiple times in sequence', () => {
    const { result } = renderHook(() => useHistory({ count: 0 }))

    act(() => {
      result.current.setState({ count: 1 })
    })

    act(() => {
      result.current.setState({ count: 2 })
    })

    act(() => {
      result.current.setState({ count: 3 })
    })

    // Undo all the way back
    act(() => {
      result.current.undo()
    })

    act(() => {
      result.current.undo()
    })

    act(() => {
      result.current.undo()
    })

    expect(result.current.state).toEqual({ count: 0 })

    // Redo all the way forward
    act(() => {
      result.current.redo()
    })

    expect(result.current.state).toEqual({ count: 1 })

    act(() => {
      result.current.redo()
    })

    expect(result.current.state).toEqual({ count: 2 })

    act(() => {
      result.current.redo()
    })

    expect(result.current.state).toEqual({ count: 3 })
  })

  it('respects maxHistorySize option', () => {
    const { result } = renderHook(() =>
      useHistory({ count: 0 }, { maxHistorySize: 3 })
    )

    // Add 5 states - only last 3 should be kept
    act(() => {
      result.current.setState({ count: 1 })
    })

    act(() => {
      result.current.setState({ count: 2 })
    })

    act(() => {
      result.current.setState({ count: 3 })
    })

    act(() => {
      result.current.setState({ count: 4 })
    })

    act(() => {
      result.current.setState({ count: 5 })
    })

    expect(result.current.state).toEqual({ count: 5 })

    // Should only be able to undo 2 times (maxHistorySize - 1)
    act(() => {
      result.current.undo()
    })

    expect(result.current.state).toEqual({ count: 4 })

    act(() => {
      result.current.undo()
    })

    expect(result.current.state).toEqual({ count: 3 })

    // No more undo available
    expect(result.current.canUndo).toBe(false)
  })

  it('skipHistory option prevents adding to history', () => {
    const { result } = renderHook(() => useHistory({ count: 0 }))

    act(() => {
      result.current.setState({ count: 1 })
    })

    act(() => {
      result.current.setState({ count: 2 }, { skipHistory: true })
    })

    expect(result.current.state).toEqual({ count: 2 })

    // Undo should go back to count: 0, skipping count: 2
    act(() => {
      result.current.undo()
    })

    expect(result.current.state).toEqual({ count: 0 })
  })

  it('clearHistory resets history to current state', () => {
    const { result } = renderHook(() => useHistory({ count: 0 }))

    act(() => {
      result.current.setState({ count: 1 })
    })

    act(() => {
      result.current.setState({ count: 2 })
    })

    expect(result.current.canUndo).toBe(true)

    act(() => {
      result.current.clearHistory()
    })

    expect(result.current.state).toEqual({ count: 2 })
    expect(result.current.canUndo).toBe(false)
    expect(result.current.canRedo).toBe(false)
  })

  it('works with array state', () => {
    const { result } = renderHook(() => useHistory<string[]>([]))

    act(() => {
      result.current.setState(['a'])
    })

    act(() => {
      result.current.setState(['a', 'b'])
    })

    expect(result.current.state).toEqual(['a', 'b'])

    act(() => {
      result.current.undo()
    })

    expect(result.current.state).toEqual(['a'])

    act(() => {
      result.current.undo()
    })

    expect(result.current.state).toEqual([])
  })

  it('works with complex object state', () => {
    interface Element {
      id: string
      type: string
      x: number
      y: number
    }

    const { result } = renderHook(() => useHistory<Element[]>([]))

    const element1: Element = { id: '1', type: 'rect', x: 0, y: 0 }
    const element2: Element = { id: '2', type: 'circle', x: 100, y: 100 }

    act(() => {
      result.current.setState([element1])
    })

    act(() => {
      result.current.setState([element1, element2])
    })

    expect(result.current.state).toHaveLength(2)

    act(() => {
      result.current.undo()
    })

    expect(result.current.state).toHaveLength(1)
    expect(result.current.state[0]).toEqual(element1)
  })
})
