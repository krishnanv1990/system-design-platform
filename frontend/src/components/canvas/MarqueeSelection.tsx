/**
 * Marquee Selection Component
 * Renders the selection rectangle during box selection
 */

import React from 'react'
import type { MarqueeState } from '@/types/canvas'
import { CANVAS_CONFIG } from '@/config/canvas'

interface MarqueeSelectionProps {
  marquee: MarqueeState
}

export const MarqueeSelection: React.FC<MarqueeSelectionProps> = ({ marquee }) => {
  if (!marquee.isSelecting) {
    return null
  }

  const x = Math.min(marquee.startX, marquee.endX)
  const y = Math.min(marquee.startY, marquee.endY)
  const width = Math.abs(marquee.endX - marquee.startX)
  const height = Math.abs(marquee.endY - marquee.startY)

  // Don't render if too small
  if (width < 5 && height < 5) {
    return null
  }

  return (
    <rect
      x={x}
      y={y}
      width={width}
      height={height}
      fill={`${CANVAS_CONFIG.HANDLE_COLOR}10`}
      stroke={CANVAS_CONFIG.HANDLE_COLOR}
      strokeWidth={1}
      strokeDasharray="4,4"
      pointerEvents="none"
    />
  )
}

export default MarqueeSelection
