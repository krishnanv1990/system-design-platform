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

    it('removes constraint when clicking on constraint badge', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={onChange} />)

      // Find and click the PK badge to remove it
      const pkBadge = screen.getByText('PK')

      await act(async () => {
        fireEvent.click(pkBadge)
      })

      await waitFor(() => {
        const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1]
        const parsedSchema = JSON.parse(lastCall[0])
        expect(parsedSchema.stores[0].fields[0].constraints).not.toContain('primary_key')
      })
    })

    it('adds constraint when selecting from dropdown', async () => {
      const schemaWithoutIndexed = {
        stores: [{
          name: 'users',
          type: 'sql',
          fields: [
            { name: 'id', type: 'uuid', constraints: ['primary_key'] },
          ],
        }],
      }
      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify(schemaWithoutIndexed)} onChange={onChange} />)

      // Find the add constraint dropdown
      const selects = screen.getAllByRole('combobox')
      const addConstraintSelect = selects[selects.length - 1] // Last select is usually the add dropdown

      await act(async () => {
        fireEvent.change(addConstraintSelect, { target: { value: 'indexed' } })
      })

      await waitFor(() => {
        expect(onChange).toHaveBeenCalled()
        const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1]
        const parsedSchema = JSON.parse(lastCall[0])
        expect(parsedSchema.stores[0].fields[0].constraints).toContain('indexed')
      })
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

    it('updates only the targeted store when editing field in multi-store schema', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify(multiStoreSchema)} onChange={onChange} />)

      // Find and update the first store's field name
      const idInput = screen.getByDisplayValue('id')

      await act(async () => {
        fireEvent.change(idInput, { target: { value: 'user_id' } })
      })

      await waitFor(() => {
        const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1]
        const parsedSchema = JSON.parse(lastCall[0])
        // First store should have updated field
        expect(parsedSchema.stores[0].fields[0].name).toBe('user_id')
        // Second store should remain unchanged
        expect(parsedSchema.stores[1].name).toBe('sessions')
        expect(parsedSchema.stores[1].fields[0].name).toBe('key')
      })
    })

    it('removes column only from the targeted store', async () => {
      const threeFieldSchema = {
        stores: [
          {
            name: 'users',
            type: 'sql',
            fields: [
              { name: 'id', type: 'uuid' },
              { name: 'email', type: 'varchar' },
            ],
          },
          {
            name: 'products',
            type: 'sql',
            fields: [
              { name: 'id', type: 'uuid' },
              { name: 'name', type: 'varchar' },
            ],
          },
        ],
      }

      const onChange = vi.fn()
      const { container } = render(<SchemaEditor value={JSON.stringify(threeFieldSchema)} onChange={onChange} />)

      // Find the delete button for the first column of the first store
      const columnDeleteButtons = container.querySelectorAll('button.opacity-0')

      expect(columnDeleteButtons.length).toBeGreaterThan(0)

      await act(async () => {
        fireEvent.click(columnDeleteButtons[0])
      })

      await waitFor(() => {
        const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1]
        const parsedSchema = JSON.parse(lastCall[0])
        // First store should have one less field
        expect(parsedSchema.stores[0].fields.length).toBe(1)
        // Second store should still have 2 fields
        expect(parsedSchema.stores[1].fields.length).toBe(2)
      })
    })

    it('adds field only to the targeted store', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify(multiStoreSchema)} onChange={onChange} />)

      // Find the Add Field buttons - should be one for each expanded store
      const addFieldButtons = screen.getAllByRole('button', { name: /add field/i })

      // Click the first store's Add Field button
      await act(async () => {
        fireEvent.click(addFieldButtons[0])
      })

      await waitFor(() => {
        const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1]
        const parsedSchema = JSON.parse(lastCall[0])
        // First store should have 2 fields now
        expect(parsedSchema.stores[0].fields.length).toBe(2)
        // Second store should still have 1 field
        expect(parsedSchema.stores[1].fields.length).toBe(1)
      })
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

    it('handles Ctrl+Enter keydown in JSON editor', async () => {
      const mockPreventDefault = vi.fn()
      const mockStopPropagation = vi.fn()

      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={vi.fn()} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      const textarea = screen.getByTestId('json-editor-textarea')

      // Simulate Ctrl+Enter - should prevent default
      await act(async () => {
        const event = new KeyboardEvent('keydown', {
          key: 'Enter',
          ctrlKey: true,
          bubbles: true,
        })
        Object.defineProperty(event, 'preventDefault', { value: mockPreventDefault })
        Object.defineProperty(event, 'stopPropagation', { value: mockStopPropagation })
        textarea.dispatchEvent(event)
      })

      // Textarea should still be visible
      expect(textarea).toBeInTheDocument()
    })

    it('handles Meta+Enter keydown in JSON editor', async () => {
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={vi.fn()} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      const textarea = screen.getByTestId('json-editor-textarea')

      // Simulate Meta+Enter (Cmd+Enter on Mac)
      await act(async () => {
        fireEvent.keyDown(textarea, { key: 'Enter', metaKey: true })
      })

      expect(textarea).toBeInTheDocument()
    })

    it('does not prevent regular Enter keydown', async () => {
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={vi.fn()} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      const textarea = screen.getByTestId('json-editor-textarea')

      // Regular Enter should not be prevented
      await act(async () => {
        fireEvent.keyDown(textarea, { key: 'Enter' })
      })

      expect(textarea).toBeInTheDocument()
    })

    it('shows tip text below JSON editor', async () => {
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={vi.fn()} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      expect(screen.getByText(/Changes here will update the visual editor below/i)).toBeInTheDocument()
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

    it('parses bare array format without stores wrapper', () => {
      const bareArraySchema = [
        {
          name: 'products',
          type: 'sql',
          description: 'Product catalog',
          fields: [
            { name: 'id', type: 'uuid', constraints: ['primary_key'] },
            { name: 'name', type: 'varchar', constraints: ['not_null'] },
          ],
        },
      ]
      render(<SchemaEditor value={JSON.stringify(bareArraySchema)} onChange={vi.fn()} />)

      expect(screen.getByDisplayValue('products')).toBeInTheDocument()
      expect(screen.getByText('2 fields')).toBeInTheDocument()
    })

    it('normalizes string constraints to array', () => {
      const stringConstraintSchema = {
        stores: [{
          name: 'test',
          type: 'sql',
          fields: [
            { name: 'id', type: 'uuid', constraints: 'primary_key' },
          ],
        }],
      }
      render(<SchemaEditor value={JSON.stringify(stringConstraintSchema)} onChange={vi.fn()} />)

      expect(screen.getByDisplayValue('test')).toBeInTheDocument()
      expect(screen.getByText('PK')).toBeInTheDocument()
    })

    it('handles non-array fields property gracefully', () => {
      const badFieldsSchema = {
        stores: [{
          name: 'test',
          type: 'sql',
          fields: 'not an array',
        }],
      }
      render(<SchemaEditor value={JSON.stringify(badFieldsSchema)} onChange={vi.fn()} />)

      expect(screen.getByDisplayValue('test')).toBeInTheDocument()
      expect(screen.getByText('0 fields')).toBeInTheDocument()
    })

    it('handles non-array indexes property gracefully', () => {
      const badIndexesSchema = {
        stores: [{
          name: 'test',
          type: 'sql',
          fields: [{ name: 'id', type: 'uuid' }],
          indexes: 'not an array',
        }],
      }
      render(<SchemaEditor value={JSON.stringify(badIndexesSchema)} onChange={vi.fn()} />)

      expect(screen.getByDisplayValue('test')).toBeInTheDocument()
      expect(screen.getByText('1 field')).toBeInTheDocument()
    })

    it('handles null/undefined constraints gracefully', () => {
      const nullConstraintsSchema = {
        stores: [{
          name: 'test',
          type: 'sql',
          fields: [
            { name: 'id', type: 'uuid', constraints: null },
            { name: 'name', type: 'varchar' },
          ],
        }],
      }
      render(<SchemaEditor value={JSON.stringify(nullConstraintsSchema)} onChange={vi.fn()} />)

      expect(screen.getByDisplayValue('test')).toBeInTheDocument()
      expect(screen.getByText('2 fields')).toBeInTheDocument()
    })

    it('handles empty object JSON gracefully', () => {
      render(<SchemaEditor value="{}" onChange={vi.fn()} />)

      expect(screen.getByText(/No data stores defined yet/i)).toBeInTheDocument()
    })

    it('handles JSON with unrecognized structure gracefully', () => {
      const unknownSchema = { someRandomKey: 'value', anotherKey: 123 }
      render(<SchemaEditor value={JSON.stringify(unknownSchema)} onChange={vi.fn()} />)

      expect(screen.getByText(/No data stores defined yet/i)).toBeInTheDocument()
    })

    it('handles JSON number value gracefully', () => {
      render(<SchemaEditor value="42" onChange={vi.fn()} />)

      expect(screen.getByText(/No data stores defined yet/i)).toBeInTheDocument()
    })

    it('handles JSON string value gracefully', () => {
      render(<SchemaEditor value='"just a string"' onChange={vi.fn()} />)

      expect(screen.getByText(/No data stores defined yet/i)).toBeInTheDocument()
    })
  })

  describe('Controlled Component Behavior', () => {
    it('handles parent value updates after JSON edit correctly', async () => {
      let parentValue = JSON.stringify(sampleSchema)
      const onChange = vi.fn((newValue: string) => {
        parentValue = newValue
      })

      const { rerender } = render(
        <SchemaEditor value={parentValue} onChange={onChange} />
      )

      // Open JSON editor
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      // Create new schema with 3 fields
      const newSchema = {
        stores: [{
          name: 'accounts',
          type: 'sql',
          description: 'User accounts updated',
          fields: [
            { name: 'id', type: 'uuid', constraints: ['primary_key'] },
            { name: 'email', type: 'varchar', constraints: ['unique'] },
            { name: 'created_at', type: 'timestamp', constraints: [] },
          ],
        }],
      }

      const textarea = screen.getByTestId('json-editor-textarea')

      await act(async () => {
        fireEvent.change(textarea, { target: { value: JSON.stringify(newSchema) } })
      })

      // Simulate parent re-rendering with updated value
      await act(async () => {
        rerender(<SchemaEditor value={parentValue} onChange={onChange} />)
      })

      // Visual builder should still show correct data
      await waitFor(() => {
        expect(screen.getByText('3 fields')).toBeInTheDocument()
        expect(screen.getByDisplayValue('accounts')).toBeInTheDocument()
      })
    })

    it('preserves stores when external value matches internal state', async () => {
      const onChange = vi.fn()
      const { rerender } = render(
        <SchemaEditor value={JSON.stringify(sampleSchema)} onChange={onChange} />
      )

      expect(screen.getByDisplayValue('users')).toBeInTheDocument()

      // Re-render with same value should not cause issues
      await act(async () => {
        rerender(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={onChange} />)
      })

      expect(screen.getByDisplayValue('users')).toBeInTheDocument()
    })
  })

  describe('Non-SQL Database Type Field Rendering', () => {
    const kvSchema = {
      stores: [{
        name: 'cache',
        type: 'kv',
        description: 'Redis cache',
        fields: [
          { name: 'key', type: 'string' },
          { name: 'value', type: 'json' },
        ],
      }],
    }

    const documentSchema = {
      stores: [{
        name: 'products',
        type: 'document',
        description: 'MongoDB collection',
        fields: [
          { name: '_id', type: 'objectId' },
          { name: 'data', type: 'object' },
        ],
      }],
    }

    it('renders Key-Value store with correct field types', () => {
      render(<SchemaEditor value={JSON.stringify(kvSchema)} onChange={vi.fn()} />)

      expect(screen.getByDisplayValue('cache')).toBeInTheDocument()
      expect(screen.getByText('Key-Value Store')).toBeInTheDocument()
      expect(screen.getByText('2 fields')).toBeInTheDocument()
    })

    it('renders Document store with correct field types', () => {
      render(<SchemaEditor value={JSON.stringify(documentSchema)} onChange={vi.fn()} />)

      expect(screen.getByDisplayValue('products')).toBeInTheDocument()
      expect(screen.getByText('Document Store')).toBeInTheDocument()
    })

    it('allows adding constraints to non-SQL stores', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify(kvSchema)} onChange={onChange} />)

      // Find the constraint dropdown for non-SQL stores
      const constraintSelects = screen.getAllByRole('combobox')
      const addConstraintSelect = constraintSelects.find(
        select => select.textContent?.includes('+ Add') || (select as HTMLSelectElement).value === ''
      )

      if (addConstraintSelect) {
        await act(async () => {
          fireEvent.change(addConstraintSelect, { target: { value: 'required' } })
        })

        await waitFor(() => {
          expect(onChange).toHaveBeenCalled()
        })
      }
    })

    it('allows changing field types in non-SQL stores', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify(kvSchema)} onChange={onChange} />)

      // Find the type select
      const typeSelects = screen.getAllByRole('combobox')

      await act(async () => {
        fireEvent.change(typeSelects[0], { target: { value: 'hash' } })
      })

      await waitFor(() => {
        expect(onChange).toHaveBeenCalled()
      })
    })
  })

  describe('Graph, TimeSeries, and Search Database Types', () => {
    it('renders Graph database store correctly', () => {
      const graphSchema = {
        stores: [{
          name: 'relationships',
          type: 'graph',
          fields: [{ name: 'source', type: 'string' }],
        }],
      }
      render(<SchemaEditor value={JSON.stringify(graphSchema)} onChange={vi.fn()} />)

      expect(screen.getByText('Graph Database')).toBeInTheDocument()
    })

    it('renders Time Series store correctly', () => {
      const tsSchema = {
        stores: [{
          name: 'metrics',
          type: 'timeseries',
          fields: [{ name: 'timestamp', type: 'timestamp' }],
        }],
      }
      render(<SchemaEditor value={JSON.stringify(tsSchema)} onChange={vi.fn()} />)

      expect(screen.getByText('Time Series')).toBeInTheDocument()
    })

    it('renders Search Engine store correctly', () => {
      const searchSchema = {
        stores: [{
          name: 'documents',
          type: 'search',
          fields: [{ name: 'content', type: 'text' }],
        }],
      }
      render(<SchemaEditor value={JSON.stringify(searchSchema)} onChange={vi.fn()} />)

      expect(screen.getByText('Search Engine')).toBeInTheDocument()
    })
  })

  describe('JSON to Visual Sync Edge Cases', () => {
    it('syncs multiple stores from JSON to visual builder', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify(emptySchema)} onChange={onChange} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      const multiStoreSchema = {
        stores: [
          { name: 'users', type: 'sql', fields: [{ name: 'id', type: 'uuid' }] },
          { name: 'sessions', type: 'kv', fields: [{ name: 'key', type: 'string' }] },
          { name: 'logs', type: 'document', fields: [{ name: 'message', type: 'string' }] },
        ],
      }

      const textarea = screen.getByTestId('json-editor-textarea')

      await act(async () => {
        fireEvent.change(textarea, { target: { value: JSON.stringify(multiStoreSchema) } })
      })

      await waitFor(() => {
        expect(screen.getByDisplayValue('users')).toBeInTheDocument()
        expect(screen.getByDisplayValue('sessions')).toBeInTheDocument()
        expect(screen.getByDisplayValue('logs')).toBeInTheDocument()
      })
    })

    it('clears visual builder when JSON stores are removed', async () => {
      const multiStoreSchema = {
        stores: [
          { name: 'users', type: 'sql', fields: [] },
          { name: 'cache', type: 'kv', fields: [] },
        ],
      }

      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify(multiStoreSchema)} onChange={onChange} />)

      expect(screen.getByDisplayValue('users')).toBeInTheDocument()
      expect(screen.getByDisplayValue('cache')).toBeInTheDocument()

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      const textarea = screen.getByTestId('json-editor-textarea')

      await act(async () => {
        fireEvent.change(textarea, { target: { value: JSON.stringify({ stores: [] }) } })
      })

      await waitFor(() => {
        expect(screen.getByText(/No data stores defined yet/i)).toBeInTheDocument()
      })
    })

    it('updates field count immediately when fields are added in JSON', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify(sampleSchema)} onChange={onChange} />)

      // Initially 2 fields
      expect(screen.getByText('2 fields')).toBeInTheDocument()

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      const schemaWith5Fields = {
        stores: [{
          ...sampleSchema.stores[0],
          fields: [
            { name: 'id', type: 'uuid' },
            { name: 'email', type: 'varchar' },
            { name: 'name', type: 'varchar' },
            { name: 'created_at', type: 'timestamp' },
            { name: 'updated_at', type: 'timestamp' },
          ],
        }],
      }

      const textarea = screen.getByTestId('json-editor-textarea')

      await act(async () => {
        fireEvent.change(textarea, { target: { value: JSON.stringify(schemaWith5Fields) } })
      })

      await waitFor(() => {
        expect(screen.getByText('5 fields')).toBeInTheDocument()
      })
    })
  })

  describe('Comprehensive JSON to Visual Sync Tests', () => {
    it('verifies visual builder inputs are populated from JSON changes', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify({ stores: [] })} onChange={onChange} />)

      // Initially no stores
      expect(screen.getByText(/No data stores defined yet/i)).toBeInTheDocument()

      // Open JSON editor
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      // Add a store via JSON
      const newSchema = {
        stores: [{
          name: 'products',
          type: 'sql',
          description: 'Product catalog',
          fields: [
            { name: 'sku', type: 'varchar', constraints: ['primary_key'], description: 'Stock keeping unit' }
          ],
          indexes: []
        }]
      }

      const textarea = screen.getByTestId('json-editor-textarea')
      await act(async () => {
        fireEvent.change(textarea, { target: { value: JSON.stringify(newSchema) } })
      })

      // Verify visual builder shows the store
      await waitFor(() => {
        // Store name input should have the value
        const storeNameInput = screen.getByDisplayValue('products')
        expect(storeNameInput).toBeInTheDocument()

        // Description should be visible
        const descInput = screen.getByDisplayValue('Product catalog')
        expect(descInput).toBeInTheDocument()

        // Field should be visible
        expect(screen.getByDisplayValue('sku')).toBeInTheDocument()
      })
    })

    it('updates visual builder when JSON field names change', async () => {
      const initialSchema = {
        stores: [{
          name: 'users',
          type: 'sql',
          fields: [{ name: 'old_field', type: 'varchar' }]
        }]
      }

      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify(initialSchema)} onChange={onChange} />)

      // Verify initial field name
      expect(screen.getByDisplayValue('old_field')).toBeInTheDocument()

      // Open JSON editor
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      // Change field name via JSON
      const updatedSchema = {
        stores: [{
          name: 'users',
          type: 'sql',
          fields: [{ name: 'new_field', type: 'varchar' }]
        }]
      }

      const textarea = screen.getByTestId('json-editor-textarea')
      await act(async () => {
        fireEvent.change(textarea, { target: { value: JSON.stringify(updatedSchema) } })
      })

      // Verify field name changed in visual builder
      await waitFor(() => {
        expect(screen.queryByDisplayValue('old_field')).not.toBeInTheDocument()
        expect(screen.getByDisplayValue('new_field')).toBeInTheDocument()
      })
    })

    it('syncs constraints from JSON to visual builder', async () => {
      const initialSchema = {
        stores: [{
          name: 'items',
          type: 'sql',
          fields: [{ name: 'id', type: 'uuid', constraints: [] }]
        }]
      }

      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify(initialSchema)} onChange={onChange} />)

      // Open JSON editor
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      // Add constraints via JSON
      const updatedSchema = {
        stores: [{
          name: 'items',
          type: 'sql',
          fields: [{ name: 'id', type: 'uuid', constraints: ['primary_key', 'not_null'] }]
        }]
      }

      const textarea = screen.getByTestId('json-editor-textarea')
      await act(async () => {
        fireEvent.change(textarea, { target: { value: JSON.stringify(updatedSchema) } })
      })

      // Verify constraints appear in visual builder
      await waitFor(() => {
        expect(screen.getByText('PK')).toBeInTheDocument()
        expect(screen.getByText('NN')).toBeInTheDocument()
      })
    })

    it('maintains sync after multiple JSON edits', async () => {
      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify({ stores: [] })} onChange={onChange} />)

      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      const textarea = screen.getByTestId('json-editor-textarea')

      // First edit
      const schema1 = { stores: [{ name: 'store1', type: 'sql', fields: [] }] }
      await act(async () => {
        fireEvent.change(textarea, { target: { value: JSON.stringify(schema1) } })
      })
      await waitFor(() => {
        expect(screen.getByDisplayValue('store1')).toBeInTheDocument()
      })

      // Second edit
      const schema2 = { stores: [{ name: 'store2', type: 'sql', fields: [] }] }
      await act(async () => {
        fireEvent.change(textarea, { target: { value: JSON.stringify(schema2) } })
      })
      await waitFor(() => {
        expect(screen.queryByDisplayValue('store1')).not.toBeInTheDocument()
        expect(screen.getByDisplayValue('store2')).toBeInTheDocument()
      })

      // Third edit - add more stores
      const schema3 = {
        stores: [
          { name: 'store2', type: 'sql', fields: [] },
          { name: 'store3', type: 'kv', fields: [] }
        ]
      }
      await act(async () => {
        fireEvent.change(textarea, { target: { value: JSON.stringify(schema3) } })
      })
      await waitFor(() => {
        expect(screen.getByDisplayValue('store2')).toBeInTheDocument()
        expect(screen.getByDisplayValue('store3')).toBeInTheDocument()
      })
    })

    it('handles switching between JSON and visual edits seamlessly', async () => {
      const initialSchema = {
        stores: [{ name: 'test', type: 'sql', fields: [] }]
      }

      const onChange = vi.fn()
      render(<SchemaEditor value={JSON.stringify(initialSchema)} onChange={onChange} />)

      // Edit via visual builder
      const nameInput = screen.getByDisplayValue('test')
      await act(async () => {
        fireEvent.change(nameInput, { target: { value: 'visual_edit' } })
      })
      expect(screen.getByDisplayValue('visual_edit')).toBeInTheDocument()

      // Open JSON editor and verify it reflects visual change
      await act(async () => {
        fireEvent.click(screen.getByRole('button', { name: /edit as json/i }))
      })

      const textarea = screen.getByTestId('json-editor-textarea')
      expect(textarea.value).toContain('visual_edit')

      // Edit via JSON
      const newSchema = { stores: [{ name: 'json_edit', type: 'sql', fields: [] }] }
      await act(async () => {
        fireEvent.change(textarea, { target: { value: JSON.stringify(newSchema) } })
      })

      // Verify visual builder updated
      await waitFor(() => {
        expect(screen.getByDisplayValue('json_edit')).toBeInTheDocument()
      })

      // Edit via visual builder again
      const updatedInput = screen.getByDisplayValue('json_edit')
      await act(async () => {
        fireEvent.change(updatedInput, { target: { value: 'final_edit' } })
      })

      // Verify JSON also updated
      expect(textarea.value).toContain('final_edit')
    })
  })
})
