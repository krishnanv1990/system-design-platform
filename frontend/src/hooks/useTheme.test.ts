import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useTheme } from './useTheme'

describe('useTheme', () => {
  const mockMatchMedia = (matches: boolean) => {
    return vi.fn().mockImplementation((query: string) => ({
      matches,
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }))
  }

  beforeEach(() => {
    // Reset localStorage
    vi.spyOn(window.localStorage, 'getItem').mockReturnValue(null)
    vi.spyOn(window.localStorage, 'setItem').mockImplementation(() => {})
    // Default to light mode
    window.matchMedia = mockMatchMedia(false)
  })

  afterEach(() => {
    vi.restoreAllMocks()
    document.documentElement.classList.remove('light', 'dark')
  })

  it('returns theme, resolvedTheme, setTheme, and isDark', () => {
    const { result } = renderHook(() => useTheme())

    expect(result.current).toHaveProperty('theme')
    expect(result.current).toHaveProperty('resolvedTheme')
    expect(result.current).toHaveProperty('setTheme')
    expect(result.current).toHaveProperty('isDark')
  })

  it('defaults to system theme when no stored theme', () => {
    const { result } = renderHook(() => useTheme())

    expect(result.current.theme).toBe('system')
  })

  it('uses stored theme from localStorage', () => {
    vi.spyOn(window.localStorage, 'getItem').mockReturnValue('dark')

    const { result } = renderHook(() => useTheme())

    expect(result.current.theme).toBe('dark')
    expect(result.current.resolvedTheme).toBe('dark')
    expect(result.current.isDark).toBe(true)
  })

  it('resolves system theme to light when system prefers light', () => {
    window.matchMedia = mockMatchMedia(false)

    const { result } = renderHook(() => useTheme())

    expect(result.current.resolvedTheme).toBe('light')
    expect(result.current.isDark).toBe(false)
  })

  it('resolves system theme to dark when system prefers dark', () => {
    window.matchMedia = mockMatchMedia(true)

    const { result } = renderHook(() => useTheme())

    expect(result.current.resolvedTheme).toBe('dark')
    expect(result.current.isDark).toBe(true)
  })

  it('allows setting theme to light', () => {
    const { result } = renderHook(() => useTheme())

    act(() => {
      result.current.setTheme('light')
    })

    expect(result.current.theme).toBe('light')
    expect(result.current.resolvedTheme).toBe('light')
    expect(localStorage.setItem).toHaveBeenCalledWith('theme', 'light')
  })

  it('allows setting theme to dark', () => {
    const { result } = renderHook(() => useTheme())

    act(() => {
      result.current.setTheme('dark')
    })

    expect(result.current.theme).toBe('dark')
    expect(result.current.resolvedTheme).toBe('dark')
    expect(localStorage.setItem).toHaveBeenCalledWith('theme', 'dark')
  })

  it('applies theme class to document element', () => {
    vi.spyOn(window.localStorage, 'getItem').mockReturnValue('dark')

    renderHook(() => useTheme())

    expect(document.documentElement.classList.contains('dark')).toBe(true)
  })
})
