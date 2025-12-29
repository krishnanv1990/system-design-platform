/**
 * Tests for DesignTextSummary component
 *
 * Tests the display of design text summary including:
 * - Component counts and badges
 * - Connection counts
 * - Named components list
 * - Text annotations
 * - Design notes
 * - Empty states
 */

import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import DesignTextSummary from './DesignTextSummary'

// Helper to create canvas data JSON
const createCanvasData = (elements: any[]) => JSON.stringify({ elements })

describe('DesignTextSummary', () => {
  describe('Empty States', () => {
    it('returns null when canvasData is null and no textData', () => {
      const { container } = render(
        <DesignTextSummary canvasData={null} textData={null} />
      )
      expect(container.firstChild).toBeNull()
    })

    it('returns null when canvasData is empty JSON', () => {
      const { container } = render(
        <DesignTextSummary canvasData={createCanvasData([])} textData={null} />
      )
      expect(container.firstChild).toBeNull()
    })

    it('renders with only textData', () => {
      render(
        <DesignTextSummary canvasData={null} textData="Some design notes" />
      )
      expect(screen.getByText('Design Summary')).toBeInTheDocument()
      expect(screen.getByText('Design Notes')).toBeInTheDocument()
      expect(screen.getByText('Some design notes')).toBeInTheDocument()
    })

    it('shows empty state message when no components in canvas', () => {
      render(
        <DesignTextSummary canvasData={createCanvasData([])} textData="" />
      )
      // Component returns null when no content
      expect(screen.queryByText('Design Summary')).not.toBeInTheDocument()
    })
  })

  describe('Component Counts', () => {
    it('renders database component count', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'database', label: 'Users DB' },
        { id: '2', type: 'database', label: 'Orders DB' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      expect(screen.getByText('Database')).toBeInTheDocument()
      expect(screen.getByText('×2')).toBeInTheDocument()
    })

    it('renders server component without count when single', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'server', label: 'API Server' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      expect(screen.getByText('Server')).toBeInTheDocument()
      expect(screen.queryByText('×1')).not.toBeInTheDocument()
    })

    it('renders multiple component types', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'database', label: 'DB' },
        { id: '2', type: 'server', label: 'API' },
        { id: '3', type: 'cache', label: 'Redis' },
        { id: '4', type: 'load_balancer', label: 'LB' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      expect(screen.getByText('Database')).toBeInTheDocument()
      expect(screen.getByText('Server')).toBeInTheDocument()
      expect(screen.getByText('Cache')).toBeInTheDocument()
      expect(screen.getByText('Load Balancer')).toBeInTheDocument()
    })

    it('shows total elements count', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'database' },
        { id: '2', type: 'server' },
        { id: '3', type: 'arrow' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      expect(screen.getByText(/Components \(3 elements\)/)).toBeInTheDocument()
    })
  })

  describe('Connection Counts', () => {
    it('renders arrow connections count', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'database' },
        { id: '2', type: 'server' },
        { id: 'a1', type: 'arrow', endX: 100, endY: 100 },
        { id: 'a2', type: 'arrow', endX: 200, endY: 200 },
        { id: 'a3', type: 'arrow', endX: 300, endY: 300 },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      expect(screen.getByText('3 connections')).toBeInTheDocument()
    })

    it('renders singular connection when only one arrow', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'database' },
        { id: 'a1', type: 'arrow' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      expect(screen.getByText('1 connection')).toBeInTheDocument()
    })

    it('does not render connections when no arrows', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'database' },
        { id: '2', type: 'server' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      expect(screen.queryByText(/connection/)).not.toBeInTheDocument()
    })
  })

  describe('Named Components', () => {
    it('renders named components section when labels exist', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'database', label: 'Users DB' },
        { id: '2', type: 'database', label: 'Orders DB' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      expect(screen.getByText('Named Components')).toBeInTheDocument()
      expect(screen.getByText('Users DB, Orders DB')).toBeInTheDocument()
    })

    it('groups labels by component type', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'database', label: 'Users DB' },
        { id: '2', type: 'server', label: 'API Server' },
        { id: '3', type: 'database', label: 'Orders DB' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      expect(screen.getByText('Users DB, Orders DB')).toBeInTheDocument()
      expect(screen.getByText('API Server')).toBeInTheDocument()
    })

    it('does not render named components section when no labels', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'database' },
        { id: '2', type: 'server' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      expect(screen.queryByText('Named Components')).not.toBeInTheDocument()
    })
  })

  describe('Text Annotations', () => {
    it('renders text annotations from text elements', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'text', text: 'First annotation' },
        { id: '2', type: 'text', text: 'Second annotation' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      expect(screen.getByText('Annotations')).toBeInTheDocument()
      expect(screen.getByText(/First annotation/)).toBeInTheDocument()
      expect(screen.getByText(/Second annotation/)).toBeInTheDocument()
    })

    it('limits text annotations to 5 and shows count', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'text', text: 'Annotation 1' },
        { id: '2', type: 'text', text: 'Annotation 2' },
        { id: '3', type: 'text', text: 'Annotation 3' },
        { id: '4', type: 'text', text: 'Annotation 4' },
        { id: '5', type: 'text', text: 'Annotation 5' },
        { id: '6', type: 'text', text: 'Annotation 6' },
        { id: '7', type: 'text', text: 'Annotation 7' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      expect(screen.getByText('...and 2 more')).toBeInTheDocument()
    })

    it('does not render annotations section when no text elements', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'database' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      expect(screen.queryByText('Annotations')).not.toBeInTheDocument()
    })
  })

  describe('Design Notes', () => {
    it('renders design notes when textData is provided', () => {
      render(
        <DesignTextSummary
          canvasData={createCanvasData([{ id: '1', type: 'database' }])}
          textData="These are my design notes for the system."
        />
      )

      expect(screen.getByText('Design Notes')).toBeInTheDocument()
      expect(screen.getByText('These are my design notes for the system.')).toBeInTheDocument()
    })

    it('does not render design notes when textData is empty', () => {
      render(
        <DesignTextSummary
          canvasData={createCanvasData([{ id: '1', type: 'database' }])}
          textData=""
        />
      )

      expect(screen.queryByText('Design Notes')).not.toBeInTheDocument()
    })

    it('does not render design notes when textData is whitespace only', () => {
      render(
        <DesignTextSummary
          canvasData={createCanvasData([{ id: '1', type: 'database' }])}
          textData="   "
        />
      )

      expect(screen.queryByText('Design Notes')).not.toBeInTheDocument()
    })
  })

  describe('Component Types', () => {
    it('renders cloud service components', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'cloud', label: 'AWS' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      expect(screen.getByText('Cloud Service')).toBeInTheDocument()
    })

    it('renders user/client components', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'user', label: 'Mobile User' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      expect(screen.getByText('User/Client')).toBeInTheDocument()
    })

    it('renders queue components', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'queue', label: 'Kafka' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      expect(screen.getByText('Message Queue')).toBeInTheDocument()
    })

    it('renders API gateway components', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'api_gateway', label: 'Kong' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      expect(screen.getByText('API Gateway')).toBeInTheDocument()
    })

    it('renders DNS components', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'dns', label: 'DNS Server' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      expect(screen.getByText('DNS')).toBeInTheDocument()
    })

    it('renders blob storage components', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'blob_storage', label: 'S3 Bucket' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      expect(screen.getByText('Blob Storage')).toBeInTheDocument()
    })

    it('renders globe/CDN components', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'globe', label: 'CDN' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      expect(screen.getByText('Internet/CDN')).toBeInTheDocument()
    })

    it('renders client app components', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'client', label: 'Web App' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      expect(screen.getByText('Client App')).toBeInTheDocument()
    })
  })

  describe('Styling', () => {
    it('applies custom className', () => {
      const { container } = render(
        <DesignTextSummary
          canvasData={createCanvasData([{ id: '1', type: 'database' }])}
          className="custom-class"
        />
      )

      expect(container.firstChild).toHaveClass('custom-class')
    })
  })

  describe('Edge Cases', () => {
    it('handles invalid JSON gracefully', () => {
      const { container } = render(
        <DesignTextSummary canvasData="invalid json" />
      )
      // Should not crash, just render nothing
      expect(container.firstChild).toBeNull()
    })

    it('handles missing elements array', () => {
      const { container } = render(
        <DesignTextSummary canvasData="{}" />
      )
      expect(container.firstChild).toBeNull()
    })

    it('handles unknown element types', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'database' },
        { id: '2', type: 'unknown_type' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      // Should render known type but ignore unknown
      expect(screen.getByText('Database')).toBeInTheDocument()
    })

    it('handles elements without labels', () => {
      const canvasData = createCanvasData([
        { id: '1', type: 'database' },
        { id: '2', type: 'database', label: '' },
      ])
      render(<DesignTextSummary canvasData={canvasData} />)

      // Should show count but not named components section
      expect(screen.getByText('Database')).toBeInTheDocument()
      expect(screen.queryByText('Named Components')).not.toBeInTheDocument()
    })
  })
})
