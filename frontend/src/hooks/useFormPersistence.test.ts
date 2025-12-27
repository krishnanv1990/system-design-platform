import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useFormPersistence, useUnsavedChangesWarning } from './useFormPersistence'

// Mock localStorage with accessible store
let mockStore: Record<string, string> = {}

const localStorageMock = {
  getItem: vi.fn((key: string) => mockStore[key] ?? null),
  setItem: vi.fn((key: string, value: string) => {
    mockStore[key] = value
  }),
  removeItem: vi.fn((key: string) => {
    delete mockStore[key]
  }),
  clear: vi.fn(() => {
    mockStore = {}
  }),
}

Object.defineProperty(window, 'localStorage', { value: localStorageMock })

describe('useFormPersistence', () => {
  beforeEach(() => {
    // Clear the mock store
    mockStore = {}
    // Clear mock call history
    vi.clearAllMocks()
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('returns initial value when no stored data', () => {
    const { result } = renderHook(() =>
      useFormPersistence({
        key: 'test-key',
        initialValue: { name: 'initial' },
      })
    )

    expect(result.current.value).toEqual({ name: 'initial' })
  })

  it('loads stored value from localStorage', () => {
    // Set up stored data before rendering
    mockStore['test-key'] = JSON.stringify({ value: { name: 'stored' }, savedAt: new Date().toISOString() })

    const { result } = renderHook(() =>
      useFormPersistence({
        key: 'test-key',
        initialValue: { name: 'initial' },
      })
    )

    expect(result.current.value).toEqual({ name: 'stored' })
  })

  it('updates value when setValue is called', () => {
    const { result } = renderHook(() =>
      useFormPersistence({
        key: 'test-key',
        initialValue: { name: 'initial' },
      })
    )

    act(() => {
      result.current.setValue({ name: 'updated' })
    })

    expect(result.current.value).toEqual({ name: 'updated' })
  })

  it('marks as dirty when value changes', () => {
    const { result } = renderHook(() =>
      useFormPersistence({
        key: 'test-key',
        initialValue: { name: 'initial' },
      })
    )

    expect(result.current.isDirty).toBe(false)

    act(() => {
      result.current.setValue({ name: 'updated' })
    })

    expect(result.current.isDirty).toBe(true)
  })

  it('saves to localStorage after debounce', async () => {
    const { result } = renderHook(() =>
      useFormPersistence({
        key: 'test-key',
        initialValue: { name: 'initial' },
        debounceMs: 500,
      })
    )

    act(() => {
      result.current.setValue({ name: 'updated' })
    })

    // Fast-forward past debounce time
    act(() => {
      vi.advanceTimersByTime(600)
    })

    // Now it should have called setItem
    expect(localStorageMock.setItem).toHaveBeenCalled()
    const stored = JSON.parse(mockStore['test-key'])
    expect(stored.value).toEqual({ name: 'updated' })
  })

  it('clears storage when clearStorage is called', () => {
    mockStore['test-key'] = JSON.stringify({ value: { name: 'stored' } })

    const { result } = renderHook(() =>
      useFormPersistence({
        key: 'test-key',
        initialValue: { name: 'initial' },
      })
    )

    act(() => {
      result.current.clearStorage()
    })

    expect(localStorageMock.removeItem).toHaveBeenCalledWith('test-key')
    expect(result.current.isDirty).toBe(false)
  })

  it('updates lastSaved after saving', () => {
    const { result } = renderHook(() =>
      useFormPersistence({
        key: 'test-key',
        initialValue: { name: 'initial' },
        debounceMs: 500,
      })
    )

    expect(result.current.lastSaved).toBeNull()

    act(() => {
      result.current.setValue({ name: 'updated' })
    })

    act(() => {
      vi.advanceTimersByTime(600)
    })

    expect(result.current.lastSaved).toBeInstanceOf(Date)
  })

  it('supports function updater for setValue', () => {
    const { result } = renderHook(() =>
      useFormPersistence({
        key: 'test-key',
        initialValue: { count: 0 },
      })
    )

    act(() => {
      result.current.setValue((prev) => ({ count: prev.count + 1 }))
    })

    expect(result.current.value).toEqual({ count: 1 })
  })

  it('handles invalid stored JSON gracefully', () => {
    // Set invalid JSON in store
    mockStore['test-key'] = 'invalid json'

    const { result } = renderHook(() =>
      useFormPersistence({
        key: 'test-key',
        initialValue: { name: 'initial' },
      })
    )

    // Should fall back to initial value
    expect(result.current.value).toEqual({ name: 'initial' })
  })
})

describe('useUnsavedChangesWarning', () => {
  it('adds beforeunload listener when dirty', () => {
    const addEventListenerSpy = vi.spyOn(window, 'addEventListener')

    renderHook(() => useUnsavedChangesWarning(true))

    expect(addEventListenerSpy).toHaveBeenCalledWith(
      'beforeunload',
      expect.any(Function)
    )

    addEventListenerSpy.mockRestore()
  })

  it('removes beforeunload listener on unmount', () => {
    const removeEventListenerSpy = vi.spyOn(window, 'removeEventListener')

    const { unmount } = renderHook(() => useUnsavedChangesWarning(true))

    unmount()

    expect(removeEventListenerSpy).toHaveBeenCalledWith(
      'beforeunload',
      expect.any(Function)
    )

    removeEventListenerSpy.mockRestore()
  })

  it('does not prevent default when not dirty', () => {
    renderHook(() => useUnsavedChangesWarning(false))

    const event = new Event('beforeunload')
    const preventDefaultSpy = vi.spyOn(event, 'preventDefault')

    window.dispatchEvent(event)

    expect(preventDefaultSpy).not.toHaveBeenCalled()
  })
})
