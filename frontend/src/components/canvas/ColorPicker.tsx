/**
 * Color Picker Component
 * A dropdown color picker with outside click handling
 */

import React, { useRef } from 'react'
import { useClickOutside } from '@/hooks/useClickOutside'
import { cn } from '@/lib/utils'

interface ColorOption {
  name: string
  value: string
}

interface ColorPickerProps {
  isOpen: boolean
  onClose: () => void
  onSelect: (color: string) => void
  colors: readonly ColorOption[]
  selectedColor: string
  showTransparent?: boolean
}

export const ColorPicker: React.FC<ColorPickerProps> = ({
  isOpen,
  onClose,
  onSelect,
  colors,
  selectedColor,
  showTransparent = false,
}) => {
  const ref = useRef<HTMLDivElement>(null)
  useClickOutside(ref, onClose, isOpen)

  if (!isOpen) {
    return null
  }

  const handleSelect = (color: string) => {
    onSelect(color)
    onClose()
  }

  const renderColorButton = (color: ColorOption) => {
    const isTransparent = color.value === 'transparent'
    const isSelected = selectedColor === color.value

    return (
      <button
        key={color.value}
        className={cn(
          'w-6 h-6 rounded border-2 transition-all',
          isSelected ? 'border-primary ring-2 ring-primary/30' : 'border-transparent hover:border-gray-300'
        )}
        style={{
          backgroundColor: isTransparent ? 'white' : color.value,
          backgroundImage: isTransparent
            ? 'linear-gradient(45deg, #ccc 25%, transparent 25%, transparent 75%, #ccc 75%), linear-gradient(45deg, #ccc 25%, transparent 25%, transparent 75%, #ccc 75%)'
            : undefined,
          backgroundSize: isTransparent ? '4px 4px' : undefined,
          backgroundPosition: isTransparent ? '0 0, 2px 2px' : undefined,
        }}
        onClick={() => handleSelect(color.value)}
        title={color.name}
        aria-label={`Select ${color.name}`}
      />
    )
  }

  return (
    <div
      ref={ref}
      className="absolute top-full left-0 mt-1 p-2 bg-popover border rounded-lg shadow-lg z-10 grid grid-cols-4 gap-1"
      role="listbox"
      aria-label="Color options"
    >
      {colors.map(renderColorButton)}
    </div>
  )
}

export default ColorPicker
