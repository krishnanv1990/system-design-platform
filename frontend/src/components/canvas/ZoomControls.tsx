/**
 * Zoom Controls Component
 * Renders zoom in/out buttons and zoom percentage display
 */

import React from 'react'
import { ZoomIn, ZoomOut, Maximize2, RotateCcw } from 'lucide-react'
import { Button } from '@/components/ui/button'

interface ZoomControlsProps {
  zoomPercentage: number
  onZoomIn: () => void
  onZoomOut: () => void
  onReset: () => void
  onFitContent: () => void
  disabled?: boolean
}

export const ZoomControls: React.FC<ZoomControlsProps> = ({
  zoomPercentage,
  onZoomIn,
  onZoomOut,
  onReset,
  onFitContent,
  disabled = false,
}) => {
  return (
    <div className="flex items-center gap-1 border rounded-lg bg-background/80 backdrop-blur-sm p-1">
      <Button
        variant="ghost"
        size="sm"
        className="h-7 w-7 p-0"
        onClick={onZoomOut}
        disabled={disabled || zoomPercentage <= 10}
        title="Zoom out"
        aria-label="Zoom out"
      >
        <ZoomOut className="h-4 w-4" />
      </Button>

      <span
        className="text-xs font-medium min-w-[3rem] text-center cursor-pointer hover:text-primary"
        onClick={onReset}
        title="Click to reset zoom"
        role="button"
        aria-label={`Current zoom: ${zoomPercentage}%. Click to reset`}
      >
        {zoomPercentage}%
      </span>

      <Button
        variant="ghost"
        size="sm"
        className="h-7 w-7 p-0"
        onClick={onZoomIn}
        disabled={disabled || zoomPercentage >= 400}
        title="Zoom in"
        aria-label="Zoom in"
      >
        <ZoomIn className="h-4 w-4" />
      </Button>

      <div className="w-px h-4 bg-border mx-0.5" />

      <Button
        variant="ghost"
        size="sm"
        className="h-7 w-7 p-0"
        onClick={onFitContent}
        disabled={disabled}
        title="Fit to content"
        aria-label="Fit to content"
      >
        <Maximize2 className="h-4 w-4" />
      </Button>

      <Button
        variant="ghost"
        size="sm"
        className="h-7 w-7 p-0"
        onClick={onReset}
        disabled={disabled}
        title="Reset view"
        aria-label="Reset view"
      >
        <RotateCcw className="h-3.5 w-3.5" />
      </Button>
    </div>
  )
}

export default ZoomControls
