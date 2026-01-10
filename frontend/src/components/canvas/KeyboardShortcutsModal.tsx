/**
 * Keyboard Shortcuts Modal Component
 * Displays available keyboard shortcuts
 */

import React, { useRef, useEffect } from 'react'
import { X, Keyboard } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { useClickOutside } from '@/hooks/useClickOutside'

interface ShortcutItem {
  keys: string[]
  description: string
}

const shortcuts: ShortcutItem[] = [
  { keys: ['Delete', 'Backspace'], description: 'Delete selected element(s)' },
  { keys: ['Ctrl', 'Z'], description: 'Undo' },
  { keys: ['Ctrl', 'Y'], description: 'Redo' },
  { keys: ['Ctrl', 'Shift', 'Z'], description: 'Redo (alternative)' },
  { keys: ['Ctrl', 'C'], description: 'Copy selected element(s)' },
  { keys: ['Ctrl', 'V'], description: 'Paste' },
  { keys: ['Ctrl', 'X'], description: 'Cut selected element(s)' },
  { keys: ['Ctrl', 'A'], description: 'Select all elements' },
  { keys: ['Ctrl', 'D'], description: 'Duplicate selected element(s)' },
  { keys: ['Escape'], description: 'Deselect / Cancel' },
  { keys: ['Shift', 'Click'], description: 'Add to selection' },
  { keys: ['Ctrl', 'Scroll'], description: 'Zoom in/out' },
  { keys: ['Space', 'Drag'], description: 'Pan canvas' },
  { keys: ['Arrow keys'], description: 'Move selected by 1px' },
  { keys: ['Shift', 'Arrow'], description: 'Move selected by 10px' },
  { keys: ['?'], description: 'Show keyboard shortcuts' },
]

interface KeyboardShortcutsModalProps {
  isOpen: boolean
  onClose: () => void
}

export const KeyboardShortcutsModal: React.FC<KeyboardShortcutsModalProps> = ({
  isOpen,
  onClose,
}) => {
  const modalRef = useRef<HTMLDivElement>(null)
  useClickOutside(modalRef, onClose, isOpen)

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [isOpen, onClose])

  if (!isOpen) {
    return null
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50">
      <div
        ref={modalRef}
        className="bg-background rounded-lg shadow-xl max-w-md w-full max-h-[80vh] overflow-hidden"
        role="dialog"
        aria-modal="true"
        aria-labelledby="shortcuts-title"
      >
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b">
          <div className="flex items-center gap-2">
            <Keyboard className="h-5 w-5 text-muted-foreground" />
            <h2 id="shortcuts-title" className="text-lg font-semibold">
              Keyboard Shortcuts
            </h2>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="h-8 w-8 p-0"
            onClick={onClose}
            aria-label="Close"
          >
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Content */}
        <div className="p-4 overflow-y-auto max-h-[60vh]">
          <div className="space-y-2">
            {shortcuts.map((shortcut, index) => (
              <div
                key={index}
                className="flex items-center justify-between py-2 border-b border-border/50 last:border-0"
              >
                <span className="text-sm text-muted-foreground">
                  {shortcut.description}
                </span>
                <div className="flex items-center gap-1">
                  {shortcut.keys.map((key, keyIndex) => (
                    <React.Fragment key={keyIndex}>
                      {keyIndex > 0 && (
                        <span className="text-xs text-muted-foreground">+</span>
                      )}
                      <kbd className="px-2 py-1 text-xs font-mono bg-muted rounded border border-border">
                        {key}
                      </kbd>
                    </React.Fragment>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Footer */}
        <div className="p-4 border-t bg-muted/30">
          <p className="text-xs text-muted-foreground text-center">
            Press <kbd className="px-1 py-0.5 text-xs font-mono bg-muted rounded border">?</kbd> anytime to show this dialog
          </p>
        </div>
      </div>
    </div>
  )
}

export default KeyboardShortcutsModal
