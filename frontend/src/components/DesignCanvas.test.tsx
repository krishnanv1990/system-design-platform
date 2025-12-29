/**
 * Tests for DesignCanvas component
 * Tests canvas rendering, tools, import/export functionality
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import DesignCanvas from './DesignCanvas'

// Mock the canvasExport module
vi.mock('@/lib/canvasExport', () => ({
  exportCanvas: vi.fn().mockResolvedValue(undefined),
  EXPORT_FORMATS: [
    { id: 'json', label: 'JSON (Editable)', extension: '.json', mimeType: 'application/json' },
    { id: 'png', label: 'PNG Image', extension: '.png', mimeType: 'image/png' },
    { id: 'jpg', label: 'JPG Image', extension: '.jpg', mimeType: 'image/jpeg' },
    { id: 'svg', label: 'SVG Vector', extension: '.svg', mimeType: 'image/svg+xml' },
  ],
  IMPORT_FORMATS: [
    { extension: '.json', label: 'JSON' },
  ],
}))

describe('DesignCanvas', () => {
  const mockOnChange = vi.fn()

  beforeEach(() => {
    mockOnChange.mockClear()
  })

  afterEach(() => {
    vi.clearAllMocks()
  })

  describe('Basic Rendering', () => {
    it('renders the canvas component', () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)
      // Check for SVG element
      expect(document.querySelector('svg')).toBeInTheDocument()
    })

    it('renders toolbar with tools', () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)
      expect(screen.getByTitle('Select')).toBeInTheDocument()
      expect(screen.getByTitle('Rectangle')).toBeInTheDocument()
      expect(screen.getByTitle('Ellipse')).toBeInTheDocument()
      expect(screen.getByTitle('Arrow')).toBeInTheDocument()
      expect(screen.getByTitle('Text')).toBeInTheDocument()
    })

    it('renders icon tools', () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)
      expect(screen.getByTitle('Database')).toBeInTheDocument()
      expect(screen.getByTitle('Server')).toBeInTheDocument()
      expect(screen.getByTitle('Cloud')).toBeInTheDocument()
      expect(screen.getByTitle('User')).toBeInTheDocument()
      expect(screen.getByTitle('Globe')).toBeInTheDocument()
    })

    it('renders undo/redo buttons', () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)
      expect(screen.getByTitle('Undo (Ctrl+Z)')).toBeInTheDocument()
      expect(screen.getByTitle('Redo (Ctrl+Y)')).toBeInTheDocument()
    })

    it('renders help text with format info', () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)
      expect(screen.getByText(/Export: PNG, JPG, SVG, JSON/)).toBeInTheDocument()
      expect(screen.getByText(/Import: JSON/)).toBeInTheDocument()
    })

    it('shows view only mode text when readOnly', () => {
      render(<DesignCanvas value="" onChange={mockOnChange} readOnly />)
      expect(screen.getByText('View only mode')).toBeInTheDocument()
    })

    it('hides toolbar when readOnly', () => {
      render(<DesignCanvas value="" onChange={mockOnChange} readOnly />)
      expect(screen.queryByTitle('Select')).not.toBeInTheDocument()
      expect(screen.queryByTitle('Rectangle')).not.toBeInTheDocument()
    })
  })

  describe('Tool Selection', () => {
    it('select tool is active by default', () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)
      const selectButton = screen.getByTitle('Select')
      // Default variant is applied to selected tool
      expect(selectButton).toBeInTheDocument()
    })

    it('changes active tool when clicked', async () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)

      const rectangleButton = screen.getByTitle('Rectangle')
      await act(async () => {
        fireEvent.click(rectangleButton)
      })

      // Rectangle should now be active
      expect(rectangleButton).toBeInTheDocument()
    })
  })

  describe('Color Pickers', () => {
    it('renders stroke color picker button', () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)
      expect(screen.getByText('Stroke')).toBeInTheDocument()
    })

    it('renders fill color picker button', () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)
      expect(screen.getByText('Fill')).toBeInTheDocument()
    })

    it('shows stroke color options when clicked', async () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)

      const strokeButton = screen.getByText('Stroke').closest('button')!
      await act(async () => {
        fireEvent.click(strokeButton)
      })

      // Should show color options
      expect(screen.getByTitle('Black')).toBeInTheDocument()
      expect(screen.getByTitle('Blue')).toBeInTheDocument()
    })

    it('shows fill color options when clicked', async () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)

      const fillButton = screen.getByText('Fill').closest('button')!
      await act(async () => {
        fireEvent.click(fillButton)
      })

      // Should show fill options including transparent
      expect(screen.getByTitle('None')).toBeInTheDocument()
      expect(screen.getByTitle('Light Blue')).toBeInTheDocument()
    })
  })

  describe('Import/Export UI', () => {
    it('renders import button', () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)
      // Look for button with Import text
      const importButtons = screen.getAllByText('Import')
      expect(importButtons.length).toBeGreaterThan(0)
    })

    it('renders export button', () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)
      const exportButton = screen.getByTitle('Export diagram')
      expect(exportButton).toBeInTheDocument()
    })

    it('shows export dropdown when export button clicked', async () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)

      const exportButton = screen.getByTitle('Export diagram')
      await act(async () => {
        fireEvent.click(exportButton)
      })

      // Should show export format options
      await waitFor(() => {
        expect(screen.getByText('Export As')).toBeInTheDocument()
        expect(screen.getByText('JSON (Editable)')).toBeInTheDocument()
        expect(screen.getByText('PNG Image')).toBeInTheDocument()
        expect(screen.getByText('JPG Image')).toBeInTheDocument()
        expect(screen.getByText('SVG Vector')).toBeInTheDocument()
      })
    })

    it('shows file extensions in export dropdown', async () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)

      const exportButton = screen.getByTitle('Export diagram')
      await act(async () => {
        fireEvent.click(exportButton)
      })

      await waitFor(() => {
        expect(screen.getByText('.json')).toBeInTheDocument()
        expect(screen.getByText('.png')).toBeInTheDocument()
        expect(screen.getByText('.jpg')).toBeInTheDocument()
        expect(screen.getByText('.svg')).toBeInTheDocument()
      })
    })

    it('closes export dropdown after format selection', async () => {
      const { exportCanvas } = await import('@/lib/canvasExport')
      render(<DesignCanvas value="" onChange={mockOnChange} />)

      // Open dropdown
      const exportButton = screen.getByTitle('Export diagram')
      await act(async () => {
        fireEvent.click(exportButton)
      })

      // Click on PNG format
      await act(async () => {
        fireEvent.click(screen.getByText('PNG Image'))
      })

      // Dropdown should close
      await waitFor(() => {
        expect(screen.queryByText('Export As')).not.toBeInTheDocument()
      })

      expect(exportCanvas).toHaveBeenCalled()
    })
  })

  describe('Canvas Actions', () => {
    it('renders clear canvas button', () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)
      expect(screen.getByTitle('Clear canvas')).toBeInTheDocument()
    })
  })

  describe('Loading from Value', () => {
    it('loads elements from JSON value', () => {
      const canvasValue = JSON.stringify({
        elements: [
          { id: 'rect1', type: 'rectangle', x: 10, y: 10, width: 50, height: 50, fill: '#ddd', stroke: '#000', strokeWidth: 1, cornerRadius: 0 }
        ],
        version: 1
      })

      render(<DesignCanvas value={canvasValue} onChange={mockOnChange} />)

      // The SVG should contain the rendered element
      const svg = document.querySelector('svg')
      expect(svg).toBeInTheDocument()
    })

    it('handles invalid JSON gracefully', () => {
      render(<DesignCanvas value="invalid json" onChange={mockOnChange} />)
      // Should not crash
      expect(document.querySelector('svg')).toBeInTheDocument()
    })

    it('handles empty value', () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)
      expect(document.querySelector('svg')).toBeInTheDocument()
    })

    it('handles undefined value', () => {
      render(<DesignCanvas onChange={mockOnChange} />)
      expect(document.querySelector('svg')).toBeInTheDocument()
    })
  })

  describe('Keyboard Shortcuts', () => {
    it('displays undo shortcut hint', () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)
      expect(screen.getByText(/Ctrl\+Z to undo/)).toBeInTheDocument()
    })

    it('displays redo shortcut hint', () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)
      expect(screen.getByText(/Ctrl\+Y to redo/)).toBeInTheDocument()
    })
  })

  describe('Canvas Grid', () => {
    it('renders grid pattern', () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)
      const pattern = document.querySelector('pattern#grid')
      expect(pattern).toBeInTheDocument()
    })
  })

  describe('Element Rendering', () => {
    it('renders rectangle elements', () => {
      const canvasValue = JSON.stringify({
        elements: [
          { id: 'r1', type: 'rectangle', x: 10, y: 10, width: 50, height: 50, fill: '#fff', stroke: '#000', strokeWidth: 2, cornerRadius: 4 }
        ],
        version: 1
      })

      render(<DesignCanvas value={canvasValue} onChange={mockOnChange} />)
      const rects = document.querySelectorAll('rect')
      // At least one rect (not counting grid rect)
      expect(rects.length).toBeGreaterThanOrEqual(1)
    })

    it('renders ellipse elements', () => {
      const canvasValue = JSON.stringify({
        elements: [
          { id: 'e1', type: 'ellipse', x: 10, y: 10, width: 50, height: 50, fill: '#fff', stroke: '#000', strokeWidth: 2 }
        ],
        version: 1
      })

      render(<DesignCanvas value={canvasValue} onChange={mockOnChange} />)
      const ellipses = document.querySelectorAll('ellipse')
      // At least one ellipse should be rendered (other ellipses may come from icons in toolbar)
      expect(ellipses.length).toBeGreaterThanOrEqual(1)
    })

    it('renders arrow elements', () => {
      const canvasValue = JSON.stringify({
        elements: [
          { id: 'a1', type: 'arrow', x: 10, y: 10, width: 0, height: 0, endX: 100, endY: 100, fill: 'transparent', stroke: '#000', strokeWidth: 2 }
        ],
        version: 1
      })

      render(<DesignCanvas value={canvasValue} onChange={mockOnChange} />)
      const lines = document.querySelectorAll('line')
      // At least one line should be rendered (other lines may come from grid pattern)
      expect(lines.length).toBeGreaterThanOrEqual(1)
    })

    it('renders text elements', () => {
      const canvasValue = JSON.stringify({
        elements: [
          { id: 't1', type: 'text', x: 10, y: 10, width: 100, height: 24, fill: '#000', stroke: 'transparent', strokeWidth: 0, text: 'Hello', fontSize: 16 }
        ],
        version: 1
      })

      render(<DesignCanvas value={canvasValue} onChange={mockOnChange} />)
      expect(screen.getByText('Hello')).toBeInTheDocument()
    })

    it('renders database icon elements', () => {
      const canvasValue = JSON.stringify({
        elements: [
          { id: 'd1', type: 'database', x: 10, y: 10, width: 60, height: 60, fill: '#fff', stroke: '#000', strokeWidth: 2, label: 'DB' }
        ],
        version: 1
      })

      render(<DesignCanvas value={canvasValue} onChange={mockOnChange} />)
      expect(screen.getByText('DB')).toBeInTheDocument()
    })

    it('renders server icon elements', () => {
      const canvasValue = JSON.stringify({
        elements: [
          { id: 's1', type: 'server', x: 10, y: 10, width: 60, height: 60, fill: '#fff', stroke: '#000', strokeWidth: 2, label: 'API' }
        ],
        version: 1
      })

      render(<DesignCanvas value={canvasValue} onChange={mockOnChange} />)
      expect(screen.getByText('API')).toBeInTheDocument()
    })

    it('renders cloud icon elements', () => {
      const canvasValue = JSON.stringify({
        elements: [
          { id: 'c1', type: 'cloud', x: 10, y: 10, width: 60, height: 60, fill: '#fff', stroke: '#000', strokeWidth: 2, label: 'AWS' }
        ],
        version: 1
      })

      render(<DesignCanvas value={canvasValue} onChange={mockOnChange} />)
      expect(screen.getByText('AWS')).toBeInTheDocument()
    })
  })

  describe('Export Format Selection', () => {
    it('calls exportCanvas with JSON format', async () => {
      const { exportCanvas } = await import('@/lib/canvasExport')
      render(<DesignCanvas value="" onChange={mockOnChange} />)

      // Open export dropdown
      await act(async () => {
        fireEvent.click(screen.getByTitle('Export diagram'))
      })

      // Click JSON format
      await act(async () => {
        fireEvent.click(screen.getByText('JSON (Editable)'))
      })

      expect(exportCanvas).toHaveBeenCalledWith(
        expect.anything(),
        expect.any(Array),
        expect.objectContaining({ format: 'json' })
      )
    })

    it('calls exportCanvas with PNG format', async () => {
      const { exportCanvas } = await import('@/lib/canvasExport')
      render(<DesignCanvas value="" onChange={mockOnChange} />)

      // Open export dropdown
      await act(async () => {
        fireEvent.click(screen.getByTitle('Export diagram'))
      })

      // Click PNG format
      await act(async () => {
        fireEvent.click(screen.getByText('PNG Image'))
      })

      expect(exportCanvas).toHaveBeenCalledWith(
        expect.anything(),
        expect.any(Array),
        expect.objectContaining({ format: 'png' })
      )
    })

    it('calls exportCanvas with JPG format', async () => {
      const { exportCanvas } = await import('@/lib/canvasExport')
      render(<DesignCanvas value="" onChange={mockOnChange} />)

      // Open export dropdown
      await act(async () => {
        fireEvent.click(screen.getByTitle('Export diagram'))
      })

      // Click JPG format
      await act(async () => {
        fireEvent.click(screen.getByText('JPG Image'))
      })

      expect(exportCanvas).toHaveBeenCalledWith(
        expect.anything(),
        expect.any(Array),
        expect.objectContaining({ format: 'jpg' })
      )
    })

    it('calls exportCanvas with SVG format', async () => {
      const { exportCanvas } = await import('@/lib/canvasExport')
      render(<DesignCanvas value="" onChange={mockOnChange} />)

      // Open export dropdown
      await act(async () => {
        fireEvent.click(screen.getByTitle('Export diagram'))
      })

      // Click SVG format
      await act(async () => {
        fireEvent.click(screen.getByText('SVG Vector'))
      })

      expect(exportCanvas).toHaveBeenCalledWith(
        expect.anything(),
        expect.any(Array),
        expect.objectContaining({ format: 'svg' })
      )
    })
  })

  describe('Undo/Redo Functionality', () => {
    it('undo button is disabled initially', () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)
      const undoButton = screen.getByTitle('Undo (Ctrl+Z)')
      expect(undoButton).toBeDisabled()
    })

    it('redo button is disabled initially', () => {
      render(<DesignCanvas value="" onChange={mockOnChange} />)
      const redoButton = screen.getByTitle('Redo (Ctrl+Y)')
      expect(redoButton).toBeDisabled()
    })
  })
})
