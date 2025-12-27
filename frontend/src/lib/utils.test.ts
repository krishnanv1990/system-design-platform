import { describe, it, expect } from 'vitest'
import { cn } from './utils'

describe('cn utility function', () => {
  it('merges class names', () => {
    const result = cn('foo', 'bar')
    expect(result).toBe('foo bar')
  })

  it('handles undefined and null values', () => {
    const result = cn('foo', undefined, null, 'bar')
    expect(result).toBe('foo bar')
  })

  it('handles conditional classes', () => {
    const isActive = true
    const isDisabled = false
    const result = cn('base', isActive && 'active', isDisabled && 'disabled')
    expect(result).toBe('base active')
  })

  it('handles arrays of classes', () => {
    const result = cn(['foo', 'bar'], 'baz')
    expect(result).toBe('foo bar baz')
  })

  it('merges Tailwind classes correctly', () => {
    // tailwind-merge should resolve conflicts
    const result = cn('px-2 py-1', 'px-4')
    expect(result).toBe('py-1 px-4')
  })

  it('handles empty input', () => {
    const result = cn()
    expect(result).toBe('')
  })

  it('handles object syntax', () => {
    const result = cn({
      foo: true,
      bar: false,
      baz: true,
    })
    expect(result).toBe('foo baz')
  })

  it('handles mixed input types', () => {
    const result = cn(
      'base',
      ['arr1', 'arr2'],
      { conditional: true },
      undefined,
      'final'
    )
    expect(result).toBe('base arr1 arr2 conditional final')
  })
})
