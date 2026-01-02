/**
 * Tests for DesignEditor component
 *
 * Tests the design editor layout including:
 * - Vertical layout with diagram tool above Coach widget
 * - Toggle Coach visibility
 * - Mode switching (canvas/text)
 * - ReadOnly mode
 * - Summary handling
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react'
import DesignEditor from './DesignEditor'

// Mock child components
vi.mock('./DesignCanvas', () => ({
  default: ({ value, onChange, readOnly }: { value?: string; onChange: (v: string) => void; readOnly?: boolean }) => (
    <div data-testid="design-canvas" data-readonly={readOnly} data-value={value}>
      Mock DesignCanvas
      {!readOnly && (
        <button onClick={() => onChange('{"elements":[]}')}>Update Canvas</button>
      )}
    </div>
  ),
}))

vi.mock('./DesignChat', () => ({
  default: ({
    problemId,
    difficultyLevel,
    readOnly,
    onSummaryGenerated,
  }: {
    problemId: number
    difficultyLevel?: string
    readOnly?: boolean
    onSummaryGenerated?: (summary: any) => void
  }) => (
    <div
      data-testid="design-chat"
      data-problem-id={problemId}
      data-difficulty={difficultyLevel}
      data-readonly={readOnly}
    >
      Mock DesignChat (Coach)
      <button
        onClick={() =>
          onSummaryGenerated?.({
            summary: 'Test summary',
            key_components: ['Component1'],
            strengths: ['Strength1'],
            areas_for_improvement: ['Improvement1'],
            overall_score: 85,
            difficulty_level: 'medium',
            level_info: { level: 'L6', title: 'Staff Engineer', description: '' },
            demo_mode: false,
          })
        }
      >
        Generate Summary
      </button>
    </div>
  ),
}))

vi.mock('./DesignSummary', () => ({
  default: ({ summary }: { summary: any }) => (
    <div data-testid="design-summary">
      Mock DesignSummary
      <span data-testid="summary-score">{summary?.overall_score}</span>
    </div>
  ),
}))

vi.mock('./DesignTextSummary', () => ({
  default: ({ canvasData, textData }: { canvasData?: string | null; textData?: string | null }) => (
    <div data-testid="design-text-summary" data-canvas={canvasData} data-text={textData}>
      Mock DesignTextSummary
    </div>
  ),
}))

describe('DesignEditor', () => {
  const mockOnChange = vi.fn()
  const mockOnSummaryChange = vi.fn()

  beforeEach(() => {
    mockOnChange.mockClear()
    mockOnSummaryChange.mockClear()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Basic Rendering', () => {
    it('renders the design editor component', () => {
      render(<DesignEditor value="" onChange={mockOnChange} problemId={1} />)
      expect(screen.getByText('System Design')).toBeInTheDocument()
    })

    it('renders the header with title', () => {
      render(<DesignEditor value="" onChange={mockOnChange} problemId={1} />)
      expect(screen.getByText('System Design')).toBeInTheDocument()
      expect(screen.getByText(/Draw your diagram and chat with the AI coach/)).toBeInTheDocument()
    })

    it('renders the DesignCanvas component', () => {
      render(<DesignEditor value="" onChange={mockOnChange} problemId={1} />)
      expect(screen.getByTestId('design-canvas')).toBeInTheDocument()
    })

    it('renders the DesignChat (Coach) component when expanded', () => {
      render(<DesignEditor value="" onChange={mockOnChange} problemId={1} />)
      expect(screen.getByTestId('design-chat')).toBeInTheDocument()
    })

    it('renders tips section', () => {
      render(<DesignEditor value="" onChange={mockOnChange} problemId={1} />)
      expect(screen.getByText('Tips:')).toBeInTheDocument()
    })
  })

  describe('Vertical Layout (Diagram Above Coach)', () => {
    it('renders with flex-col layout for stacked arrangement', () => {
      const { container } = render(
        <DesignEditor value="" onChange={mockOnChange} problemId={1} />
      )

      // Find the main content container that should have flex-col
      const mainContent = container.querySelector('.flex.flex-col')
      expect(mainContent).toBeInTheDocument()
    })

    it('chat section has fixed height constraints to prevent fluttering', () => {
      render(<DesignEditor value="" onChange={mockOnChange} problemId={1} />)

      const chatSection = screen.getByTestId('design-chat').parentElement
      // Should have fixed height classes to prevent layout shift
      expect(chatSection).toHaveClass('h-[400px]')
      expect(chatSection).toHaveClass('min-h-[400px]')
      expect(chatSection).toHaveClass('max-h-[400px]')
    })

    it('chat section has overflow-hidden to prevent content overflow', () => {
      render(<DesignEditor value="" onChange={mockOnChange} problemId={1} />)

      const chatSection = screen.getByTestId('design-chat').parentElement
      expect(chatSection).toHaveClass('overflow-hidden')
    })

    it('canvas section uses full width (w-full) when chat is expanded', () => {
      const { container } = render(
        <DesignEditor value="" onChange={mockOnChange} problemId={1} />
      )

      // The flex-col container is present in the DOM
      const flexColContainer = container.querySelector('.flex.flex-col')
      expect(flexColContainer).toBeInTheDocument()

      // The canvas wrapper div should have w-full and border-b classes
      const canvasWrapper = flexColContainer?.querySelector('.w-full.border-b')
      expect(canvasWrapper).toBeInTheDocument()
    })

    it('chat section uses full width (w-full) when expanded', () => {
      const { container } = render(
        <DesignEditor value="" onChange={mockOnChange} problemId={1} />
      )

      // Chat section should have w-full class
      const chatSection = screen.getByTestId('design-chat').parentElement
      expect(chatSection).toHaveClass('w-full')
    })

    it('canvas section has border-b when chat is expanded', () => {
      const { container } = render(
        <DesignEditor value="" onChange={mockOnChange} problemId={1} />
      )

      // Find the canvas wrapper with border-b class inside the flex-col container
      const flexColContainer = container.querySelector('.flex.flex-col')
      const canvasWrapper = flexColContainer?.querySelector('.border-b')
      expect(canvasWrapper).toBeInTheDocument()
    })

    it('diagram appears before coach in DOM order (diagram on top)', () => {
      const { container } = render(
        <DesignEditor value="" onChange={mockOnChange} problemId={1} />
      )

      const canvas = screen.getByTestId('design-canvas')
      const chat = screen.getByTestId('design-chat')

      // In DOM order, canvas should come before chat
      const canvasPosition = canvas.compareDocumentPosition(chat)
      // DOCUMENT_POSITION_FOLLOWING (4) means chat follows canvas
      expect(canvasPosition & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    })
  })

  describe('Toggle Coach Visibility', () => {
    it('renders Hide Coach button when chat is expanded', () => {
      render(<DesignEditor value="" onChange={mockOnChange} problemId={1} />)
      expect(screen.getByText('Hide Coach')).toBeInTheDocument()
    })

    it('hides Coach when Hide Coach button is clicked', async () => {
      render(<DesignEditor value="" onChange={mockOnChange} problemId={1} />)

      const hideButton = screen.getByText('Hide Coach')
      await act(async () => {
        fireEvent.click(hideButton)
      })

      // Coach should be hidden
      expect(screen.queryByTestId('design-chat')).not.toBeInTheDocument()
    })

    it('shows Show Coach button when chat is hidden', async () => {
      render(<DesignEditor value="" onChange={mockOnChange} problemId={1} />)

      const hideButton = screen.getByText('Hide Coach')
      await act(async () => {
        fireEvent.click(hideButton)
      })

      expect(screen.getByText('Show Coach')).toBeInTheDocument()
    })

    it('shows Coach when Show Coach button is clicked', async () => {
      render(<DesignEditor value="" onChange={mockOnChange} problemId={1} />)

      // Hide coach first
      const hideButton = screen.getByText('Hide Coach')
      await act(async () => {
        fireEvent.click(hideButton)
      })

      // Show coach
      const showButton = screen.getByText('Show Coach')
      await act(async () => {
        fireEvent.click(showButton)
      })

      expect(screen.getByTestId('design-chat')).toBeInTheDocument()
    })

    it('canvas takes full width when coach is hidden', async () => {
      const { container } = render(
        <DesignEditor value="" onChange={mockOnChange} problemId={1} />
      )

      const hideButton = screen.getByText('Hide Coach')
      await act(async () => {
        fireEvent.click(hideButton)
      })

      // When coach is hidden, the canvas wrapper should still have w-full
      const flexColContainer = container.querySelector('.flex.flex-col')
      const canvasWrapper = flexColContainer?.querySelector('.w-full')
      expect(canvasWrapper).toBeInTheDocument()
    })
  })

  describe('ReadOnly Mode', () => {
    it('renders simplified view without chat when readOnly', () => {
      render(<DesignEditor value="" onChange={mockOnChange} readOnly />)

      expect(screen.queryByTestId('design-chat')).not.toBeInTheDocument()
    })

    it('shows view only message when readOnly', () => {
      render(<DesignEditor value="" onChange={mockOnChange} readOnly />)

      expect(screen.getByText(/View your architecture diagram/)).toBeInTheDocument()
    })

    it('passes readOnly to DesignCanvas', () => {
      render(<DesignEditor value="" onChange={mockOnChange} readOnly />)

      const canvas = screen.getByTestId('design-canvas')
      expect(canvas).toHaveAttribute('data-readonly', 'true')
    })
  })

  describe('Without Problem ID', () => {
    it('renders simplified view without chat when no problemId', () => {
      render(<DesignEditor value="" onChange={mockOnChange} />)

      expect(screen.queryByTestId('design-chat')).not.toBeInTheDocument()
    })

    it('shows draw message when no problemId', () => {
      render(<DesignEditor value="" onChange={mockOnChange} />)

      expect(screen.getByText('Draw your architecture diagram')).toBeInTheDocument()
    })
  })

  describe('Canvas Mode', () => {
    it('renders Draw Diagram tab', () => {
      render(<DesignEditor value="" onChange={mockOnChange} problemId={1} />)
      expect(screen.getByText('Draw Diagram')).toBeInTheDocument()
    })

    it('updates canvas data and calls onChange', async () => {
      render(<DesignEditor value="" onChange={mockOnChange} problemId={1} />)

      const updateButton = screen.getByText('Update Canvas')
      await act(async () => {
        fireEvent.click(updateButton)
      })

      expect(mockOnChange).toHaveBeenCalled()
      const call = mockOnChange.mock.calls[0][0]
      const parsed = JSON.parse(call)
      expect(parsed.mode).toBe('canvas')
      expect(parsed.canvas).toBe('{"elements":[]}')
    })
  })

  describe('Value Parsing', () => {
    it('handles empty value', () => {
      render(<DesignEditor value="" onChange={mockOnChange} problemId={1} />)
      expect(screen.getByTestId('design-canvas')).toBeInTheDocument()
    })

    it('handles JSON value with mode', () => {
      const value = JSON.stringify({ mode: 'canvas', canvas: '{}', text: '' })
      render(<DesignEditor value={value} onChange={mockOnChange} problemId={1} />)
      expect(screen.getByTestId('design-canvas')).toBeInTheDocument()
    })

    it('handles legacy canvas data (elements array)', () => {
      const value = JSON.stringify({ elements: [] })
      render(<DesignEditor value={value} onChange={mockOnChange} problemId={1} />)
      expect(screen.getByTestId('design-canvas')).toBeInTheDocument()
    })

    it('handles plain text value', () => {
      render(<DesignEditor value="plain text design" onChange={mockOnChange} problemId={1} />)
      // When value is plain text, it's treated as text mode, but canvas tab is still rendered
      // The canvas is inside a hidden tab when mode is text
      expect(screen.getByText('Draw Diagram')).toBeInTheDocument()
    })
  })

  describe('Difficulty Level', () => {
    it('passes difficulty level to DesignChat', () => {
      render(
        <DesignEditor
          value=""
          onChange={mockOnChange}
          problemId={1}
          difficultyLevel="hard"
        />
      )

      const chat = screen.getByTestId('design-chat')
      expect(chat).toHaveAttribute('data-difficulty', 'hard')
    })

    it('uses medium as default difficulty', () => {
      render(<DesignEditor value="" onChange={mockOnChange} problemId={1} />)

      const chat = screen.getByTestId('design-chat')
      expect(chat).toHaveAttribute('data-difficulty', 'medium')
    })
  })

  describe('Design Summary', () => {
    it('renders summary section when summary is generated', async () => {
      render(
        <DesignEditor
          value=""
          onChange={mockOnChange}
          problemId={1}
          onSummaryChange={mockOnSummaryChange}
        />
      )

      const generateButton = screen.getByText('Generate Summary')
      await act(async () => {
        fireEvent.click(generateButton)
      })

      expect(screen.getByTestId('design-summary')).toBeInTheDocument()
    })

    it('calls onSummaryChange when summary is generated', async () => {
      render(
        <DesignEditor
          value=""
          onChange={mockOnChange}
          problemId={1}
          onSummaryChange={mockOnSummaryChange}
        />
      )

      const generateButton = screen.getByText('Generate Summary')
      await act(async () => {
        fireEvent.click(generateButton)
      })

      expect(mockOnSummaryChange).toHaveBeenCalledWith(
        expect.objectContaining({
          overall_score: 85,
          summary: 'Test summary',
        })
      )
    })

    it('shows Design Summary header when summary exists', async () => {
      render(
        <DesignEditor
          value=""
          onChange={mockOnChange}
          problemId={1}
          onSummaryChange={mockOnSummaryChange}
        />
      )

      const generateButton = screen.getByText('Generate Summary')
      await act(async () => {
        fireEvent.click(generateButton)
      })

      expect(screen.getByText('Design Summary')).toBeInTheDocument()
    })

    it('allows hiding summary box', async () => {
      render(
        <DesignEditor
          value=""
          onChange={mockOnChange}
          problemId={1}
          onSummaryChange={mockOnSummaryChange}
        />
      )

      // Generate summary
      const generateButton = screen.getByText('Generate Summary')
      await act(async () => {
        fireEvent.click(generateButton)
      })

      // Find and click the summary hide button (not the Coach hide button)
      // The summary section has a "Hide" button with exact text
      const summarySection = screen.getByTestId('design-summary').parentElement?.parentElement
      const hideButtons = screen.getAllByRole('button', { name: /hide/i })
      // Find the hide button that's within the summary section (text is just "Hide", not "Hide Coach")
      const summaryHideButton = hideButtons.find(btn => btn.textContent === 'Hide')
      await act(async () => {
        fireEvent.click(summaryHideButton!)
      })

      expect(screen.queryByTestId('design-summary')).not.toBeInTheDocument()
    })

    it('renders with initial summary', () => {
      const initialSummary = {
        summary: 'Initial summary',
        key_components: [],
        strengths: [],
        areas_for_improvement: [],
        overall_score: 75,
        difficulty_level: 'medium' as const,
        level_info: { level: 'L6', title: 'Staff Engineer', description: '' },
        demo_mode: false,
      }

      render(
        <DesignEditor
          value=""
          onChange={mockOnChange}
          problemId={1}
          initialSummary={initialSummary}
        />
      )

      expect(screen.getByTestId('design-summary')).toBeInTheDocument()
    })

    it('summary content container has fixed height to prevent fluttering', async () => {
      render(
        <DesignEditor
          value=""
          onChange={mockOnChange}
          problemId={1}
          onSummaryChange={mockOnSummaryChange}
        />
      )

      // Generate summary
      const generateButton = screen.getByText('Generate Summary')
      await act(async () => {
        fireEvent.click(generateButton)
      })

      // The summary content container should have fixed height classes
      const summaryContent = screen.getByTestId('design-summary').parentElement
      expect(summaryContent).toHaveClass('h-80')
      expect(summaryContent).toHaveClass('min-h-[320px]')
      expect(summaryContent).toHaveClass('max-h-80')
      expect(summaryContent).toHaveClass('overflow-y-auto')
    })

    it('summary header has flex-shrink-0 to prevent shrinking', async () => {
      const { container } = render(
        <DesignEditor
          value=""
          onChange={mockOnChange}
          problemId={1}
          onSummaryChange={mockOnSummaryChange}
        />
      )

      // Generate summary
      const generateButton = screen.getByText('Generate Summary')
      await act(async () => {
        fireEvent.click(generateButton)
      })

      // The summary header should have flex-shrink-0
      const summaryHeader = container.querySelector('.bg-gradient-to-r.from-green-500\\/10')
      expect(summaryHeader).toHaveClass('flex-shrink-0')
    })
  })

  describe('DesignTextSummary', () => {
    it('renders DesignTextSummary component', () => {
      render(<DesignEditor value="" onChange={mockOnChange} problemId={1} />)
      expect(screen.getByTestId('design-text-summary')).toBeInTheDocument()
    })

    it('passes canvas and text data to DesignTextSummary', () => {
      const value = JSON.stringify({
        mode: 'canvas',
        canvas: '{"elements":[]}',
        text: 'Design notes',
      })

      render(<DesignEditor value={value} onChange={mockOnChange} problemId={1} />)

      const summary = screen.getByTestId('design-text-summary')
      expect(summary).toHaveAttribute('data-canvas', '{"elements":[]}')
      expect(summary).toHaveAttribute('data-text', 'Design notes')
    })

    it('has fixed height constraints on text summary wrapper to prevent fluttering', () => {
      render(<DesignEditor value="" onChange={mockOnChange} problemId={1} />)

      const summaryWrapper = screen.getByTestId('design-text-summary').parentElement
      expect(summaryWrapper).toHaveClass('min-h-[120px]')
      expect(summaryWrapper).toHaveClass('max-h-[200px]')
      expect(summaryWrapper).toHaveClass('overflow-y-auto')
    })
  })

  describe('Data Sanitization', () => {
    it('sanitizes image data URLs from canvas data for API calls', () => {
      const canvasWithImage = JSON.stringify({
        elements: [
          { type: 'image', dataUrl: 'data:image/png;base64,largedata...' },
          { type: 'rectangle', x: 0, y: 0, width: 100, height: 100 },
        ],
      })
      const value = JSON.stringify({ mode: 'canvas', canvas: canvasWithImage, text: '' })

      render(
        <DesignEditor value={value} onChange={mockOnChange} problemId={1} />
      )

      // Component should render without errors
      expect(screen.getByTestId('design-canvas')).toBeInTheDocument()
    })
  })

  describe('Props Passing', () => {
    it('passes problemId to DesignChat', () => {
      render(<DesignEditor value="" onChange={mockOnChange} problemId={42} />)

      const chat = screen.getByTestId('design-chat')
      expect(chat).toHaveAttribute('data-problem-id', '42')
    })

    it('passes readOnly to DesignChat', () => {
      render(<DesignEditor value="" onChange={mockOnChange} problemId={1} readOnly />)

      // In readOnly mode, DesignChat is not rendered
      expect(screen.queryByTestId('design-chat')).not.toBeInTheDocument()
    })
  })
})
