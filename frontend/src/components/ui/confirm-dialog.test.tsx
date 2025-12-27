import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { ConfirmProvider, useConfirm } from './confirm-dialog'

// Test component that uses the confirm hook
function TestComponent({ onResult }: { onResult: (result: boolean) => void }) {
  const confirm = useConfirm()

  const handleClick = async () => {
    const result = await confirm({
      title: 'Test Title',
      message: 'Test message',
      type: 'warning',
      confirmLabel: 'Yes',
      cancelLabel: 'No',
    })
    onResult(result)
  }

  return <button onClick={handleClick}>Open Dialog</button>
}

describe('ConfirmDialog', () => {
  it('renders dialog when confirm is called', async () => {
    const onResult = vi.fn()

    render(
      <ConfirmProvider>
        <TestComponent onResult={onResult} />
      </ConfirmProvider>
    )

    // Dialog should not be visible initially
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()

    // Click button to open dialog
    fireEvent.click(screen.getByText('Open Dialog'))

    // Dialog should now be visible
    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })
  })

  it('displays title and message', async () => {
    render(
      <ConfirmProvider>
        <TestComponent onResult={() => {}} />
      </ConfirmProvider>
    )

    fireEvent.click(screen.getByText('Open Dialog'))

    await waitFor(() => {
      expect(screen.getByText('Test Title')).toBeInTheDocument()
      expect(screen.getByText('Test message')).toBeInTheDocument()
    })
  })

  it('displays custom button labels', async () => {
    render(
      <ConfirmProvider>
        <TestComponent onResult={() => {}} />
      </ConfirmProvider>
    )

    fireEvent.click(screen.getByText('Open Dialog'))

    await waitFor(() => {
      expect(screen.getByText('Yes')).toBeInTheDocument()
      expect(screen.getByText('No')).toBeInTheDocument()
    })
  })

  it('resolves with true when confirm button is clicked', async () => {
    const onResult = vi.fn()

    render(
      <ConfirmProvider>
        <TestComponent onResult={onResult} />
      </ConfirmProvider>
    )

    fireEvent.click(screen.getByText('Open Dialog'))

    await waitFor(() => {
      expect(screen.getByText('Yes')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Yes'))

    await waitFor(() => {
      expect(onResult).toHaveBeenCalledWith(true)
    })
  })

  it('resolves with false when cancel button is clicked', async () => {
    const onResult = vi.fn()

    render(
      <ConfirmProvider>
        <TestComponent onResult={onResult} />
      </ConfirmProvider>
    )

    fireEvent.click(screen.getByText('Open Dialog'))

    await waitFor(() => {
      expect(screen.getByText('No')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('No'))

    await waitFor(() => {
      expect(onResult).toHaveBeenCalledWith(false)
    })
  })

  it('resolves with false when backdrop is clicked', async () => {
    const onResult = vi.fn()

    render(
      <ConfirmProvider>
        <TestComponent onResult={onResult} />
      </ConfirmProvider>
    )

    fireEvent.click(screen.getByText('Open Dialog'))

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    // Click the backdrop (the element with the click handler that calls onCancel)
    const backdrop = document.querySelector('[aria-hidden="true"]')
    if (backdrop) {
      fireEvent.click(backdrop)
    }

    await waitFor(() => {
      expect(onResult).toHaveBeenCalledWith(false)
    })
  })

  it('closes dialog after confirm', async () => {
    render(
      <ConfirmProvider>
        <TestComponent onResult={() => {}} />
      </ConfirmProvider>
    )

    fireEvent.click(screen.getByText('Open Dialog'))

    await waitFor(() => {
      expect(screen.getByRole('dialog')).toBeInTheDocument()
    })

    fireEvent.click(screen.getByText('Yes'))

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
    })
  })

  it('has proper accessibility attributes', async () => {
    render(
      <ConfirmProvider>
        <TestComponent onResult={() => {}} />
      </ConfirmProvider>
    )

    fireEvent.click(screen.getByText('Open Dialog'))

    await waitFor(() => {
      const dialog = screen.getByRole('dialog')
      expect(dialog).toHaveAttribute('aria-modal', 'true')
      expect(dialog).toHaveAttribute('aria-labelledby', 'confirm-title')
      expect(dialog).toHaveAttribute('aria-describedby', 'confirm-message')
    })
  })

  it('throws error when useConfirm is used outside provider', () => {
    // Suppress console.error for this test
    const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

    function TestOutsideProvider() {
      try {
        useConfirm()
        return <div>Should not render</div>
      } catch (e) {
        return <div>Error caught</div>
      }
    }

    render(<TestOutsideProvider />)
    expect(screen.getByText('Error caught')).toBeInTheDocument()

    consoleSpy.mockRestore()
  })
})
