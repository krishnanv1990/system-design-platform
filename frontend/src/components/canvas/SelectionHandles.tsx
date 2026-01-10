/**
 * Selection Handles Component
 * Renders resize handles for selected elements
 */

import React from 'react'
import type { CanvasElement, HandlePosition } from '@/types/canvas'
import { CANVAS_CONFIG } from '@/config/canvas'

interface SelectionHandlesProps {
  element: CanvasElement
  onMouseDown: (handle: HandlePosition, e: React.MouseEvent) => void
  hoveredHandle: HandlePosition | null
}

interface HandleDef {
  position: HandlePosition
  x: number
  y: number
  cursor: string
}

export const SelectionHandles: React.FC<SelectionHandlesProps> = ({
  element,
  onMouseDown,
  hoveredHandle,
}) => {
  // Don't show handles for arrows (they have endpoint handles instead)
  if (element.type === 'arrow') {
    return null
  }

  const { x, y, width, height } = element
  const size = CANVAS_CONFIG.HANDLE_SIZE
  const half = size / 2

  const handles: HandleDef[] = [
    { position: 'nw', x: x - half, y: y - half, cursor: 'nw-resize' },
    { position: 'n', x: x + width / 2 - half, y: y - half, cursor: 'n-resize' },
    { position: 'ne', x: x + width - half, y: y - half, cursor: 'ne-resize' },
    { position: 'e', x: x + width - half, y: y + height / 2 - half, cursor: 'e-resize' },
    { position: 'se', x: x + width - half, y: y + height - half, cursor: 'se-resize' },
    { position: 's', x: x + width / 2 - half, y: y + height - half, cursor: 's-resize' },
    { position: 'sw', x: x - half, y: y + height - half, cursor: 'sw-resize' },
    { position: 'w', x: x - half, y: y + height / 2 - half, cursor: 'w-resize' },
  ]

  return (
    <g className="selection-handles">
      {/* Selection outline */}
      <rect
        x={x}
        y={y}
        width={width}
        height={height}
        fill="none"
        stroke={CANVAS_CONFIG.SELECTION_STROKE}
        strokeWidth={CANVAS_CONFIG.SELECTION_STROKE_WIDTH}
        strokeDasharray="4,4"
        pointerEvents="none"
      />

      {/* Resize handles */}
      {handles.map((handle) => (
        <rect
          key={handle.position}
          x={handle.x}
          y={handle.y}
          width={size}
          height={size}
          fill={hoveredHandle === handle.position ? '#2563eb' : CANVAS_CONFIG.HANDLE_COLOR}
          stroke="#ffffff"
          strokeWidth={1}
          style={{ cursor: handle.cursor }}
          onMouseDown={(e) => {
            e.stopPropagation()
            onMouseDown(handle.position, e)
          }}
        />
      ))}
    </g>
  )
}

export default SelectionHandles
