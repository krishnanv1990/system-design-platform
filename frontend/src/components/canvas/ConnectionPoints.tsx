/**
 * Connection Points Component
 * Renders connection point indicators on elements for arrow snapping
 */

import React from 'react'
import type { CanvasElement, ConnectionPoint as ConnectionPointType } from '@/types/canvas'
import { getConnectionPoints } from '@/utils/connectionPoints'
import { CANVAS_CONFIG } from '@/config/canvas'

interface ConnectionPointsProps {
  element: CanvasElement
  activePoint?: string
  visible?: boolean
}

export const ConnectionPoints: React.FC<ConnectionPointsProps> = ({
  element,
  activePoint,
  visible = true,
}) => {
  if (!visible || element.type === 'arrow') {
    return null
  }

  const points = getConnectionPoints(element)
  const pointRadius = 5
  const activeRadius = 7

  return (
    <g className="connection-points" pointerEvents="none">
      {points.map((point) => {
        const isActive = activePoint === point.id
        return (
          <g key={point.id}>
            {/* Outer ring for visibility */}
            <circle
              cx={point.x}
              cy={point.y}
              r={isActive ? activeRadius + 2 : pointRadius + 2}
              fill="transparent"
              stroke={isActive ? '#22c55e' : CANVAS_CONFIG.HANDLE_COLOR}
              strokeWidth={2}
              opacity={isActive ? 1 : 0.5}
            />
            {/* Inner filled circle */}
            <circle
              cx={point.x}
              cy={point.y}
              r={isActive ? activeRadius : pointRadius}
              fill={isActive ? '#22c55e' : '#ffffff'}
              stroke={isActive ? '#16a34a' : CANVAS_CONFIG.HANDLE_COLOR}
              strokeWidth={1.5}
            />
          </g>
        )
      })}
    </g>
  )
}

export default ConnectionPoints
