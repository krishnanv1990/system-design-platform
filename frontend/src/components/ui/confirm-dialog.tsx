/**
 * Confirmation dialog to replace browser confirm()
 */

import { useState, createContext, useContext, useCallback, ReactNode } from 'react'
import { AlertTriangle, Info } from 'lucide-react'
import { Button } from './button'
import { cn } from '@/lib/utils'

type DialogType = 'danger' | 'warning' | 'info'

interface ConfirmOptions {
  title: string
  message: string
  type?: DialogType
  confirmLabel?: string
  cancelLabel?: string
}

interface ConfirmContextValue {
  confirm: (options: ConfirmOptions) => Promise<boolean>
}

const ConfirmContext = createContext<ConfirmContextValue | null>(null)

export function useConfirm() {
  const context = useContext(ConfirmContext)
  if (!context) {
    throw new Error('useConfirm must be used within a ConfirmProvider')
  }
  return context.confirm
}

interface ConfirmProviderProps {
  children: ReactNode
}

export function ConfirmProvider({ children }: ConfirmProviderProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [options, setOptions] = useState<ConfirmOptions | null>(null)
  const [resolveRef, setResolveRef] = useState<((value: boolean) => void) | null>(null)

  const confirm = useCallback((opts: ConfirmOptions): Promise<boolean> => {
    setOptions(opts)
    setIsOpen(true)
    return new Promise((resolve) => {
      setResolveRef(() => resolve)
    })
  }, [])

  const handleConfirm = useCallback(() => {
    setIsOpen(false)
    resolveRef?.(true)
    setResolveRef(null)
  }, [resolveRef])

  const handleCancel = useCallback(() => {
    setIsOpen(false)
    resolveRef?.(false)
    setResolveRef(null)
  }, [resolveRef])

  return (
    <ConfirmContext.Provider value={{ confirm }}>
      {children}
      {isOpen && options && (
        <ConfirmDialog
          {...options}
          onConfirm={handleConfirm}
          onCancel={handleCancel}
        />
      )}
    </ConfirmContext.Provider>
  )
}

interface ConfirmDialogProps extends ConfirmOptions {
  onConfirm: () => void
  onCancel: () => void
}

function ConfirmDialog({
  title,
  message,
  type = 'warning',
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const icons = {
    danger: AlertTriangle,
    warning: AlertTriangle,
    info: Info,
  }

  const iconColors = {
    danger: 'text-red-600 bg-red-100 dark:bg-red-900/30',
    warning: 'text-amber-600 bg-amber-100 dark:bg-amber-900/30',
    info: 'text-blue-600 bg-blue-100 dark:bg-blue-900/30',
  }

  const buttonVariants = {
    danger: 'bg-red-600 hover:bg-red-700 text-white',
    warning: 'bg-amber-600 hover:bg-amber-700 text-white',
    info: 'bg-blue-600 hover:bg-blue-700 text-white',
  }

  const Icon = icons[type]

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center"
      role="dialog"
      aria-modal="true"
      aria-labelledby="confirm-title"
      aria-describedby="confirm-message"
    >
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50 backdrop-blur-sm"
        onClick={onCancel}
        aria-hidden="true"
      />

      {/* Dialog */}
      <div className="relative bg-background rounded-lg shadow-xl max-w-md w-full mx-4 p-6 animate-in zoom-in-95 fade-in duration-200">
        <div className="flex gap-4">
          <div className={cn('p-3 rounded-full shrink-0', iconColors[type])}>
            <Icon className="h-6 w-6" aria-hidden="true" />
          </div>
          <div className="flex-1">
            <h2 id="confirm-title" className="text-lg font-semibold">
              {title}
            </h2>
            <p id="confirm-message" className="mt-2 text-sm text-muted-foreground">
              {message}
            </p>
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <Button variant="outline" onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button
            className={buttonVariants[type]}
            onClick={onConfirm}
          >
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  )
}
