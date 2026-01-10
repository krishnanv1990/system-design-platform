/**
 * Canvas Grid Component
 * Renders the grid pattern for the canvas background
 */

import React from 'react'
import { CANVAS_CONFIG } from '@/config/canvas'

interface CanvasGridProps {
  gridSize?: number
  visible?: boolean
}

export const CanvasGrid: React.FC<CanvasGridProps> = ({
  gridSize = CANVAS_CONFIG.GRID_SIZE,
  visible = true,
}) => {
  if (!visible) {
    return null
  }

  return (
    <>
      <defs>
        <pattern
          id="canvas-grid"
          width={gridSize}
          height={gridSize}
          patternUnits="userSpaceOnUse"
        >
          <path
            d={`M ${gridSize} 0 L 0 0 0 ${gridSize}`}
            fill="none"
            stroke="currentColor"
            strokeWidth="0.5"
            className="text-muted-foreground/20"
          />
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill="url(#canvas-grid)" />
    </>
  )
}

export default CanvasGrid
