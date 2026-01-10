/**
 * Arrow Endpoints Component
 * Renders draggable endpoint handles for arrow elements
 */

import React from 'react'
import type { ArrowElement } from '@/types/canvas'
import { CANVAS_CONFIG } from '@/config/canvas'

interface ArrowEndpointsProps {
  arrow: ArrowElement
  onStartDrag: (e: React.MouseEvent) => void
  onEndDrag: (e: React.MouseEvent) => void
  hoveredEndpoint: 'start' | 'end' | null
}

export const ArrowEndpoints: React.FC<ArrowEndpointsProps> = ({
  arrow,
  onStartDrag,
  onEndDrag,
  hoveredEndpoint,
}) => {
  const handleRadius = 6
  const hoverRadius = 8

  return (
    <g className="arrow-endpoints">
      {/* Selection line highlight */}
      <line
        x1={arrow.x}
        y1={arrow.y}
        x2={arrow.endX}
        y2={arrow.endY}
        stroke={CANVAS_CONFIG.SELECTION_STROKE}
        strokeWidth={arrow.strokeWidth + 2}
        strokeDasharray="4,4"
        pointerEvents="none"
      />

      {/* Start endpoint handle */}
      <circle
        cx={arrow.x}
        cy={arrow.y}
        r={hoveredEndpoint === 'start' ? hoverRadius : handleRadius}
        fill={hoveredEndpoint === 'start' ? '#2563eb' : CANVAS_CONFIG.HANDLE_COLOR}
        stroke="#ffffff"
        strokeWidth={2}
        style={{ cursor: 'move' }}
        onMouseDown={(e) => {
          e.stopPropagation()
          onStartDrag(e)
        }}
      />

      {/* End endpoint handle */}
      <circle
        cx={arrow.endX}
        cy={arrow.endY}
        r={hoveredEndpoint === 'end' ? hoverRadius : handleRadius}
        fill={hoveredEndpoint === 'end' ? '#2563eb' : CANVAS_CONFIG.HANDLE_COLOR}
        stroke="#ffffff"
        strokeWidth={2}
        style={{ cursor: 'move' }}
        onMouseDown={(e) => {
          e.stopPropagation()
          onEndDrag(e)
        }}
      />
    </g>
  )
}

export default ArrowEndpoints
