/**
 * Tests for SchemaEditor component
 * Tests JSON to visual builder synchronization
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react'
import SchemaEditor from './SchemaEditor'

// Sample schema data for testing
const sampleSchema = {
  stores: [
    {
      name: 'users',
      type: 'sql',
      description: 'User accounts',
      fields: [
        { name: 'id', type: 'uuid', constraints: ['primary_key'], description: 'Primary key' },
        { name: 'email', type: 'varchar', constraints: ['unique', 'not_null'], description: 'User email' },
      ],
      indexes: [],
    },
  ],
}

const emptySchema = { stores: [] }

describe('SchemaEditor', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('Basic Rendering', () => {
    it('renders empty state when no value provided', () => {
      render(<SchemaEditor value="" onChange={vi.fn()} />)
      expect(screen.getByText(/No data stores defined yet/i)).toBeInTheDocument()
    })

    it('renders visual builder with stores from value prop', () => {
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={vi.fn()} />)
      expect(screen.getByDisplayValue('users')).toBeInTheDocument()
      expect(screen.getByText('2 fields')).toBeInTheDocument()
    })

    it('renders the Edit as JSON button', () => {
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={vi.fn()} />)
      expect(screen.getByRole('button', { name: /edit as json/i })).toBeInTheDocument()
    })

    it('shows Add Data Store button when not read only', () => {
      render(<SchemaEditor value="" onChange={vi.fn()} />)
      expect(screen.getByRole('button', { name: /add data store/i })).toBeInTheDocument()
    })

    it('hides Add Data Store button when read only', () => {
      render(<SchemaEditor value="" onChange={vi.fn()} readOnly />)
      expect(screen.queryByRole('button', { name: /add data store/i })).not.toBeInTheDocument()
    })
  })

  describe('JSON Editor Toggle', () => {
    it('shows JSON editor when Edit as JSON is clicked', async () => {
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={vi.fn()} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      expect(screen.getByText('JSON Editor')).toBeInTheDocument()
      expect(screen.getByRole('button', { name: /hide json/i })).toBeInTheDocument()
    })

    it('hides JSON editor when Hide JSON is clicked', async () => {
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={vi.fn()} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })
      expect(screen.getByText('JSON Editor')).toBeInTheDocument()

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /hide json/i }))
      })
      expect(screen.queryByText('JSON Editor')).not.toBeInTheDocument()
    })

    it('displays formatted JSON in editor', async () => {
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={vi.fn()} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      // Get the textarea using data-testid
      const textarea = screen.getByTestId('json-editor-textarea')
      expect(textarea).toHaveValue(JSON.stringify(sampleSchema, null, 2))
    })
  })

  describe('JSON to Visual Builder Sync - Core Fix', () => {
    it('updates visual builder when valid JSON is entered', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={onChange} />)

      // Open JSON editor
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      // Create new schema with 3 fields
      const newSchema = {
        stores: [
          {
            name: 'users',
            type: 'sql',
            description: 'User accounts',
            fields: [
              { name: 'id', type: 'uuid', constraints: ['primary_key'], description: '' },
              { name: 'email', type: 'varchar', constraints: ['unique'], description: '' },
              { name: 'created_at', type: 'timestamp', constraints: [], description: '' },
            ],
            indexes: [],
          },
        ],
      }

      // Find the textarea using data-testid
      const textarea = screen.getByTestId('json-editor-textarea')

      await act(async () => {
        fireEvent.change(textarea, { target: { value: JSON.stringify(newSchema) } })
      })

      // Visual builder should show 3 fields
      await waitFor(() => {
        expect(screen.getByText('3 fields')).toBeInTheDocument()
      })

      // onChange should be called
      expect(onChange).toHaveBeenCalled()
    })

    it('syncs store name changes from JSON to visual builder', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={onChange} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      const newSchema = {
        stores: [{ ...sampleSchema.stores[0], name: 'accounts' }],
      }

      const textarea = screen.getByTestId('json-editor-textarea')

      await act(async () => {
        fireEvent.change(textarea, { target: { value: JSON.stringify(newSchema) } })
      })

      await waitFor(() => {
        expect(screen.getByDisplayValue('accounts')).toBeInTheDocument()
      })
    })

    it('handles empty stores array from JSON', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={onChange} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      const textarea = screen.getByTestId('json-editor-textarea')

      await act(async () => {
        fireEvent.change(textarea, { target: { value: JSON.stringify(emptySchema) } })
      })

      await waitFor(() => {
        expect(screen.getByText(/No data stores defined yet/i)).toBeInTheDocument()
      })
    })

    it('shows JSON error for invalid JSON', async () => {
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={vi.fn()} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      const textarea = screen.getByTestId('json-editor-textarea')

      await act(async () => {
        fireEvent.change(textarea, { target: { value: '{ invalid json' } })
      })

      await waitFor(() => {
        expect(screen.getByText(/Error:/i)).toBeInTheDocument()
      })
    })

    it('does not call onChange when JSON is invalid', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={onChange} />)

      onChange.mockClear()

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      const textarea = screen.getByTestId('json-editor-textarea')

      await act(async () => {
        fireEvent.change(textarea, { target: { value: 'invalid json' } })
      })

      // Wait a tick and check error is shown
      await waitFor(() => {
        expect(screen.getByText(/Error:/i)).toBeInTheDocument()
      })

      // onChange should not have been called after we cleared it
      const callsAfterClear = onChange.mock.calls.filter(
        call => call[0] === 'invalid json'
      )
      expect(callsAfterClear.length).toBe(0)
    })
  })

  describe('Visual Builder to JSON Sync', () => {
    it('updates JSON when store name is changed in visual builder', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={onChange} />)

      const nameInput = screen.getByDisplayValue('users')

      await act(async () => {
        fireEvent.change(nameInput, { target: { value: 'accounts' } })
      })

      await waitFor(() => {
        const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1]
        const parsedSchema = JSON.parse(lastCall[0])
        expect(parsedSchema.stores[0].name).toBe('accounts')
      })
    })

    it('updates JSON when field is added via visual builder', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={onChange} />)

      const addFieldButton = screen.getByRole('button', { name: /add field/i })

      await act(async () => {
        fireEvent.click(addFieldButton)
      })

      await waitFor(() => {
        const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1]
        const parsedSchema = JSON.parse(lastCall[0])
        expect(parsedSchema.stores[0].fields.length).toBe(3)
      })
    })
  })

  describe('Database Type Support', () => {
    it('shows database type selector when Add Data Store is clicked', async () => {
      render(<SchemaEditor value="" onChange={vi.fn()} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /add data store/i }))
      })

      expect(screen.getByText('SQL Database')).toBeInTheDocument()
      expect(screen.getByText('Key-Value Store')).toBeInTheDocument()
      expect(screen.getByText('Document Store')).toBeInTheDocument()
    })

    it('adds SQL store when SQL Database is selected', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value="" onChange={onChange} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /add data store/i }))
      })

      await act(async () => {
        fireEvent.click(screen.getByText('SQL Database'))
      })

      await waitFor(() => {
        expect(onChange).toHaveBeenCalled()
        const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1]
        const parsedSchema = JSON.parse(lastCall[0])
        expect(parsedSchema.stores[0].type).toBe('sql')
      })
    })
  })

  describe('Constraint Handling', () => {
    it('shows constraint badges for SQL fields', () => {
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={vi.fn()} />)

      expect(screen.getByText('PK')).toBeInTheDocument()
      expect(screen.getByText('UQ')).toBeInTheDocument()
      expect(screen.getByText('NN')).toBeInTheDocument()
    })
  })

  describe('Read Only Mode', () => {
    it('disables inputs when readOnly is true', () => {
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={vi.fn()} readOnly />)

      const inputs = screen.getAllByRole('textbox')
      inputs.forEach(input => {
        expect(input).toHaveAttribute('readonly')
      })
    })

    it('hides Add Field button when readOnly is true', () => {
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={vi.fn()} readOnly />)

      expect(screen.queryByRole('button', { name: /add field/i })).not.toBeInTheDocument()
    })
  })

  describe('External Value Updates', () => {
    it('updates stores when value prop changes externally', async () => {
      const { rerender } = render(
        <SchemaEditor value={JSON.stringify(sampleSchema)} onChange={vi.fn()} />
      )

      expect(screen.getByDisplayValue('users')).toBeInTheDocument()

      const newSchema = {
        stores: [{ ...sampleSchema.stores[0], name: 'customers' }],
      }

      await act(async () => {
        rerender(<SchemaEditor value={JSON.stringify(newSchema)} onChange={vi.fn()} />)
      })

      await waitFor(() => {
        expect(screen.getByDisplayValue('customers')).toBeInTheDocument()
      })
    })
  })

  describe('Summary Footer', () => {
    it('shows field counts', () => {
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={vi.fn()} />)

      expect(screen.getByText(/total fields/i)).toBeInTheDocument()
    })
  })
})
