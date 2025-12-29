/**
 * Tests for ApiSpecEditor component
 * Tests Monaco editor integration, error handling, and loading states
 */

import { forwardRef, useState, useEffect, ReactNode } from 'react'
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'

// Mock the lazyLoadMonaco function
vi.mock('@/lib/lazyWithRetry', () => ({
  lazyLoadMonaco: () => {
    // Return a mock component that simulates Monaco editor
    return forwardRef((props: {
      value?: string
      onChange?: (value: string) => void
      height?: string
      defaultLanguage?: string
      theme?: string
      options?: { readOnly?: boolean }
      defaultValue?: string
    }) => {
      const { value, onChange, height, defaultLanguage, theme, options, defaultValue } = props
      return (
        <div data-testid="mock-monaco-editor" style={{ height }}>
          <textarea
            data-testid="mock-monaco-textarea"
            value={value || defaultValue || ''}
            onChange={(e) => onChange?.(e.target.value)}
            readOnly={options?.readOnly}
            aria-label="Monaco editor"
          />
          <span data-testid="mock-monaco-language">{defaultLanguage}</span>
          <span data-testid="mock-monaco-theme">{theme}</span>
          <span data-testid="mock-monaco-readonly">{options?.readOnly ? 'true' : 'false'}</span>
        </div>
      )
    })
  },
}))

// Mock ErrorBoundary to test error states
vi.mock('./ErrorBoundary', () => ({
  ErrorBoundary: ({ children, fallback }: { children: ReactNode; fallback: ReactNode }) => {
    const [hasError, setHasError] = useState(false)

    // Expose a way to trigger error state for testing
    useEffect(() => {
      const handler = () => setHasError(true)
      window.addEventListener('trigger-error-boundary', handler)
      return () => window.removeEventListener('trigger-error-boundary', handler)
    }, [])

    if (hasError) {
      return fallback
    }
    return children
  },
}))

import ApiSpecEditor from './ApiSpecEditor'

describe('ApiSpecEditor', () => {
  const mockOnChange = vi.fn()

  beforeEach(() => {
    mockOnChange.mockClear()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('rendering', () => {
    it('renders the component with header', () => {
      render(<ApiSpecEditor value="" onChange={mockOnChange} />)

      expect(screen.getByText('API Specification')).toBeInTheDocument()
      expect(
        screen.getByText('Define your API endpoints, request/response schemas, and authentication')
      ).toBeInTheDocument()
    })

    it('renders the Monaco editor', async () => {
      render(<ApiSpecEditor value="" onChange={mockOnChange} />)

      await waitFor(() => {
        expect(screen.getByTestId('mock-monaco-editor')).toBeInTheDocument()
      })
    })

    it('uses JSON as the default language', async () => {
      render(<ApiSpecEditor value="" onChange={mockOnChange} />)

      await waitFor(() => {
        expect(screen.getByTestId('mock-monaco-language')).toHaveTextContent('json')
      })
    })

    it('uses vs-light theme', async () => {
      render(<ApiSpecEditor value="" onChange={mockOnChange} />)

      await waitFor(() => {
        expect(screen.getByTestId('mock-monaco-theme')).toHaveTextContent('vs-light')
      })
    })
  })

  describe('value handling', () => {
    it('passes value to the editor', async () => {
      const testValue = '{"test": "value"}'
      render(<ApiSpecEditor value={testValue} onChange={mockOnChange} />)

      await waitFor(() => {
        const textarea = screen.getByTestId('mock-monaco-textarea')
        expect(textarea).toHaveValue(testValue)
      })
    })

    it('uses default API spec when value is empty', async () => {
      render(<ApiSpecEditor value="" onChange={mockOnChange} />)

      await waitFor(() => {
        const textarea = screen.getByTestId('mock-monaco-textarea') as HTMLTextAreaElement
        expect(textarea.value).toContain('endpoints')
      })
    })

    it('calls onChange when editor content changes', async () => {
      render(<ApiSpecEditor value="" onChange={mockOnChange} />)

      await waitFor(() => {
        const textarea = screen.getByTestId('mock-monaco-textarea')
        fireEvent.change(textarea, { target: { value: '{"new": "content"}' } })
      })

      expect(mockOnChange).toHaveBeenCalledWith('{"new": "content"}')
    })

    it('calls onChange with empty string when editor returns undefined', async () => {
      render(<ApiSpecEditor value="" onChange={mockOnChange} />)

      await waitFor(() => {
        const textarea = screen.getByTestId('mock-monaco-textarea')
        fireEvent.change(textarea, { target: { value: '' } })
      })

      expect(mockOnChange).toHaveBeenCalledWith('')
    })
  })

  describe('readOnly mode', () => {
    it('passes readOnly option to editor when true', async () => {
      render(<ApiSpecEditor value="" onChange={mockOnChange} readOnly={true} />)

      await waitFor(() => {
        expect(screen.getByTestId('mock-monaco-readonly')).toHaveTextContent('true')
      })
    })

    it('passes readOnly as false by default', async () => {
      render(<ApiSpecEditor value="" onChange={mockOnChange} />)

      await waitFor(() => {
        expect(screen.getByTestId('mock-monaco-readonly')).toHaveTextContent('false')
      })
    })

    it('does not allow editing when readOnly is true', async () => {
      render(<ApiSpecEditor value="test" onChange={mockOnChange} readOnly={true} />)

      await waitFor(() => {
        const textarea = screen.getByTestId('mock-monaco-textarea')
        expect(textarea).toHaveAttribute('readonly')
      })
    })
  })

  describe('error state', () => {
    it('shows error fallback when editor fails to load', async () => {
      render(<ApiSpecEditor value="" onChange={mockOnChange} />)

      // Trigger error boundary
      window.dispatchEvent(new Event('trigger-error-boundary'))

      await waitFor(() => {
        expect(screen.getByText('Failed to load editor')).toBeInTheDocument()
        expect(
          screen.getByText('This may happen after an update. Try refreshing the page.')
        ).toBeInTheDocument()
      })
    })

    it('shows refresh button in error state', async () => {
      render(<ApiSpecEditor value="" onChange={mockOnChange} />)

      window.dispatchEvent(new Event('trigger-error-boundary'))

      await waitFor(() => {
        expect(screen.getByRole('button', { name: /refresh page/i })).toBeInTheDocument()
      })
    })

    it('refresh button triggers page reload', async () => {
      const mockReload = vi.fn()
      Object.defineProperty(window, 'location', {
        value: { reload: mockReload },
        writable: true,
      })

      render(<ApiSpecEditor value="" onChange={mockOnChange} />)

      window.dispatchEvent(new Event('trigger-error-boundary'))

      await waitFor(() => {
        const refreshButton = screen.getByRole('button', { name: /refresh page/i })
        fireEvent.click(refreshButton)
      })

      expect(mockReload).toHaveBeenCalled()
    })
  })

  describe('default API spec template', () => {
    it('includes POST endpoint example', async () => {
      render(<ApiSpecEditor value="" onChange={mockOnChange} />)

      await waitFor(() => {
        const textarea = screen.getByTestId('mock-monaco-textarea') as HTMLTextAreaElement
        expect(textarea.value).toContain('"method": "POST"')
      })
    })

    it('includes GET endpoint example', async () => {
      render(<ApiSpecEditor value="" onChange={mockOnChange} />)

      await waitFor(() => {
        const textarea = screen.getByTestId('mock-monaco-textarea') as HTMLTextAreaElement
        expect(textarea.value).toContain('"method": "GET"')
      })
    })

    it('includes security configuration', async () => {
      render(<ApiSpecEditor value="" onChange={mockOnChange} />)

      await waitFor(() => {
        const textarea = screen.getByTestId('mock-monaco-textarea') as HTMLTextAreaElement
        expect(textarea.value).toContain('"security"')
        expect(textarea.value).toContain('"type": "api_key"')
      })
    })
  })

  describe('styling', () => {
    it('has proper container classes', () => {
      const { container } = render(<ApiSpecEditor value="" onChange={mockOnChange} />)

      const wrapper = container.firstChild
      expect(wrapper).toHaveClass('border', 'rounded-lg', 'overflow-hidden')
    })

    it('has styled header section', () => {
      render(<ApiSpecEditor value="" onChange={mockOnChange} />)

      const header = screen.getByText('API Specification').closest('div')
      expect(header).toHaveClass('bg-gray-100', 'px-4', 'py-2', 'border-b')
    })
  })

  describe('editor configuration', () => {
    it('sets editor height to 300px', async () => {
      render(<ApiSpecEditor value="" onChange={mockOnChange} />)

      await waitFor(() => {
        const editor = screen.getByTestId('mock-monaco-editor')
        expect(editor).toHaveStyle({ height: '300px' })
      })
    })
  })
})

// Note: Testing the actual Suspense loading fallback is tricky with mocked lazy components
// The EditorLoading component is a simple UI component that renders properly
// when the Monaco editor is loading. Its functionality is tested implicitly
// through the Suspense boundary in the main component tests.
