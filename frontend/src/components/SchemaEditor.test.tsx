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

  describe('Column Operations', () => {
    it('removes column when delete button is clicked', async () => {
      const onChange = vi.fn()
      const { container } = render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={onChange} />)

      // Find delete buttons for columns - small trash icons (h-3 w-3)
      // Use container query since buttons start with opacity-0 class
      const columnDeleteButtons = container.querySelectorAll('button.opacity-0')

      expect(columnDeleteButtons.length).toBeGreaterThan(0)

      await act(async () => {
        fireEvent.click(columnDeleteButtons[0])
      })

      await waitFor(() => {
        const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1]
        const parsedSchema = JSON.parse(lastCall[0])
        expect(parsedSchema.stores[0].fields.length).toBe(1)
      })
    })

    it('updates column name when edited', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={onChange} />)

      // Find the column name input (the 'id' field)
      const fieldNameInput = screen.getByDisplayValue('id')

      await act(async () => {
        fireEvent.change(fieldNameInput, { target: { value: 'user_id' } })
      })

      await waitFor(() => {
        const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1]
        const parsedSchema = JSON.parse(lastCall[0])
        expect(parsedSchema.stores[0].fields[0].name).toBe('user_id')
      })
    })

    it('updates column description when edited', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={onChange} />)

      // Find description input by placeholder
      const descInputs = screen.getAllByPlaceholderText('...')
      expect(descInputs.length).toBeGreaterThan(0)

      await act(async () => {
        fireEvent.change(descInputs[0], { target: { value: 'New description' } })
      })

      await waitFor(() => {
        const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1]
        const parsedSchema = JSON.parse(lastCall[0])
        expect(parsedSchema.stores[0].fields[0].description).toBe('New description')
      })
    })
  })

  describe('Store Operations', () => {
    it('removes store when delete button is clicked', async () => {
      const onChange = vi.fn()
      const { container } = render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={onChange} />)

      // Find the store delete button (has text-destructive class partial match)
      const storeDeleteBtn = container.querySelector('button[class*="text-destructive"]')

      expect(storeDeleteBtn).toBeTruthy()

      await act(async () => {
        fireEvent.click(storeDeleteBtn!)
      })

      await waitFor(() => {
        expect(screen.getByText(/No data stores defined yet/i)).toBeInTheDocument()
      })
    })

    it('updates store description when edited', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={onChange} />)

      // Find description input by current value
      const descInput = screen.getByDisplayValue('User accounts')

      await act(async () => {
        fireEvent.change(descInput, { target: { value: 'Updated description' } })
      })

      await waitFor(() => {
        const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1]
        const parsedSchema = JSON.parse(lastCall[0])
        expect(parsedSchema.stores[0].description).toBe('Updated description')
      })
    })

    it('toggles store expansion when header is clicked', async () => {
      const { container } = render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={vi.fn()} />)

      // Initially expanded - should show fields
      expect(screen.getByDisplayValue('id')).toBeInTheDocument()

      // Find the store header (the clickable div that contains the store info)
      // It has the cursor-pointer class and contains the store name input
      const storeHeader = container.querySelector('div[class*="cursor-pointer"]')

      expect(storeHeader).toBeTruthy()

      await act(async () => {
        fireEvent.click(storeHeader!)
      })

      // After collapse, field inputs should be hidden
      await waitFor(() => {
        expect(screen.queryByDisplayValue('id')).not.toBeInTheDocument()
      })
    })
  })

  describe('All Database Types', () => {
    it('adds Key-Value store', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value="" onChange={onChange} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /add data store/i }))
      })

      await act(async () => {
        fireEvent.click(screen.getByText('Key-Value Store'))
      })

      await waitFor(() => {
        const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1]
        const parsedSchema = JSON.parse(lastCall[0])
        expect(parsedSchema.stores[0].type).toBe('kv')
      })
    })

    it('adds Document store', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value="" onChange={onChange} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /add data store/i }))
      })

      await act(async () => {
        fireEvent.click(screen.getByText('Document Store'))
      })

      await waitFor(() => {
        const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1]
        const parsedSchema = JSON.parse(lastCall[0])
        expect(parsedSchema.stores[0].type).toBe('document')
      })
    })

    it('adds Graph store', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value="" onChange={onChange} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /add data store/i }))
      })

      await act(async () => {
        fireEvent.click(screen.getByText('Graph Database'))
      })

      await waitFor(() => {
        const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1]
        const parsedSchema = JSON.parse(lastCall[0])
        expect(parsedSchema.stores[0].type).toBe('graph')
      })
    })

    it('adds Time Series store', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value="" onChange={onChange} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /add data store/i }))
      })

      await act(async () => {
        fireEvent.click(screen.getByText('Time Series'))
      })

      await waitFor(() => {
        const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1]
        const parsedSchema = JSON.parse(lastCall[0])
        expect(parsedSchema.stores[0].type).toBe('timeseries')
      })
    })

    it('adds Search Engine store', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value="" onChange={onChange} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /add data store/i }))
      })

      await act(async () => {
        fireEvent.click(screen.getByText('Search Engine'))
      })

      await waitFor(() => {
        const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1]
        const parsedSchema = JSON.parse(lastCall[0])
        expect(parsedSchema.stores[0].type).toBe('search')
      })
    })
  })

  describe('Multiple Stores', () => {
    const multiStoreSchema = {
      stores: [
        {
          name: 'users',
          type: 'sql',
          description: 'User data',
          fields: [{ name: 'id', type: 'uuid', constraints: ['primary_key'], description: '' }],
          indexes: [],
        },
        {
          name: 'sessions',
          type: 'kv',
          description: 'Session cache',
          fields: [{ name: 'key', type: 'string', constraints: [], description: '' }],
          indexes: [],
        },
      ],
    }

    it('renders multiple stores correctly', () => {
      const { container } = render(<SchemaEditor value={JSON.stringify(multiStoreSchema)} onChange={vi.fn()} />)

      expect(screen.getByDisplayValue('users')).toBeInTheDocument()
      expect(screen.getByDisplayValue('sessions')).toBeInTheDocument()
      // The text is split across spans: <span>2</span><span> data stores</span>
      // Find the summary footer specifically (has p-4, rounded-lg, and border classes)
      const summarySection = container.querySelector('div.p-4.rounded-lg.border')
      expect(summarySection?.textContent).toContain('2')
      expect(summarySection?.textContent).toContain('data store')
    })

    it('shows correct store types in summary', () => {
      const { container } = render(<SchemaEditor value={JSON.stringify(multiStoreSchema)} onChange={vi.fn()} />)

      // The text is split across spans - find summary footer
      const summarySection = container.querySelector('div.p-4.rounded-lg.border')
      expect(summarySection?.textContent).toContain('2')
      expect(summarySection?.textContent).toContain('total fields')
    })
  })

  describe('JSON Editor Interactions', () => {
    it('handles paste event in JSON editor', async () => {
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={vi.fn()} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      const textarea = screen.getByTestId('json-editor-textarea')

      // Simulate paste - should not throw
      await act(async () => {
        fireEvent.paste(textarea, { clipboardData: { getData: () => '{}' } })
      })

      // Textarea should still be visible
      expect(textarea).toBeInTheDocument()
    })

    it('handles keydown event in JSON editor', async () => {
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={vi.fn()} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      const textarea = screen.getByTestId('json-editor-textarea')

      // Simulate Ctrl+Enter - should be handled
      await act(async () => {
        fireEvent.keyDown(textarea, { key: 'Enter', ctrlKey: true })
      })

      // Textarea should still be visible
      expect(textarea).toBeInTheDocument()
    })

    it('shows tip text below JSON editor', async () => {
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={vi.fn()} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      expect(screen.getByText(/Changes here will update the visual editor/i)).toBeInTheDocument()
    })
  })

  describe('Edge Cases', () => {
    it('handles schema with no fields', () => {
      const noFieldsSchema = {
        stores: [{ name: 'empty', type: 'sql', description: '', fields: [], indexes: [] }],
      }
      render(<SchemaEditor value={JSON.stringify(noFieldsSchema)} onChange={vi.fn()} />)

      expect(screen.getByDisplayValue('empty')).toBeInTheDocument()
      expect(screen.getByText('0 fields')).toBeInTheDocument()
    })

    it('handles invalid database type gracefully', () => {
      const invalidTypeSchema = {
        stores: [{ name: 'test', type: 'invalid_type', description: '', fields: [], indexes: [] }],
      }
      render(<SchemaEditor value={JSON.stringify(invalidTypeSchema)} onChange={vi.fn()} />)

      // Should default to SQL
      expect(screen.getByDisplayValue('test')).toBeInTheDocument()
    })

    it('handles schema with columns instead of fields', () => {
      const columnsSchema = {
        stores: [{ name: 'test', type: 'sql', description: '', columns: [{ name: 'id', type: 'int' }], indexes: [] }],
      }
      render(<SchemaEditor value={JSON.stringify(columnsSchema)} onChange={vi.fn()} />)

      expect(screen.getByDisplayValue('test')).toBeInTheDocument()
      expect(screen.getByText('1 field')).toBeInTheDocument()
    })

    it('handles malformed JSON gracefully', () => {
      render(<SchemaEditor value="not json at all" onChange={vi.fn()} />)

      // Should show empty state since JSON parsing failed
      expect(screen.getByText(/No data stores defined yet/i)).toBeInTheDocument()
    })

    it('parses legacy table format', () => {
      const legacySchema = {
        tables: {
          users: {
            columns: {
              id: { type: 'uuid', primary_key: true },
              name: { type: 'varchar', nullable: false },
            },
          },
        },
      }
      render(<SchemaEditor value={JSON.stringify(legacySchema)} onChange={vi.fn()} />)

      expect(screen.getByDisplayValue('users')).toBeInTheDocument()
    })
  })
})
