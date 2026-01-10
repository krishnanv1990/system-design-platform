/**
 * useZoomPan Hook
 * Handles zoom and pan functionality for the canvas
 */

import { useState, useCallback, useRef, useEffect } from 'react'
import type { Point, ViewportState, CanvasElement, Bounds } from '@/types/canvas'
import { CANVAS_CONFIG } from '@/config/canvas'
import { calculateBounds } from '@/utils/alignment'

export interface UseZoomPanReturn {
  viewport: ViewportState
  isPanning: boolean
  zoomIn: () => void
  zoomOut: () => void
  resetView: () => void
  fitToContent: (elements: CanvasElement[]) => void
  setZoom: (zoom: number) => void
  handleWheel: (e: WheelEvent, containerRect: DOMRect) => void
  startPan: (x: number, y: number) => void
  updatePan: (x: number, y: number) => void
  endPan: () => void
  screenToCanvas: (screenX: number, screenY: number) => Point
  canvasToScreen: (canvasX: number, canvasY: number) => Point
  zoomToFit: (bounds: Bounds, containerWidth: number, containerHeight: number) => void
  zoomPercentage: number
}

const initialViewport: ViewportState = {
  scale: 1,
  translateX: 0,
  translateY: 0,
}

export function useZoomPan(
  minScale: number = CANVAS_CONFIG.MIN_ZOOM,
  maxScale: number = CANVAS_CONFIG.MAX_ZOOM
): UseZoomPanReturn {
  const [viewport, setViewport] = useState<ViewportState>(initialViewport)
  const [isPanning, setIsPanning] = useState(false)
  const panStartRef = useRef<Point>({ x: 0, y: 0 })
  const viewportStartRef = useRef<ViewportState>(initialViewport)

  const clampScale = useCallback(
    (scale: number): number => {
      return Math.max(minScale, Math.min(maxScale, scale))
    },
    [minScale, maxScale]
  )

  const zoomIn = useCallback(() => {
    setViewport((prev) => ({
      ...prev,
      scale: clampScale(prev.scale * 1.2),
    }))
  }, [clampScale])

  const zoomOut = useCallback(() => {
    setViewport((prev) => ({
      ...prev,
      scale: clampScale(prev.scale / 1.2),
    }))
  }, [clampScale])

  const resetView = useCallback(() => {
    setViewport(initialViewport)
  }, [])

  const setZoom = useCallback(
    (zoom: number) => {
      setViewport((prev) => ({
        ...prev,
        scale: clampScale(zoom),
      }))
    },
    [clampScale]
  )

  const fitToContent = useCallback(
    (elements: CanvasElement[]) => {
      if (elements.length === 0) {
        resetView()
        return
      }

      const bounds = calculateBounds(elements)
      const padding = CANVAS_CONFIG.CANVAS_PADDING

      // Calculate scale to fit content
      const containerWidth = CANVAS_CONFIG.DEFAULT_CANVAS_WIDTH
      const containerHeight = CANVAS_CONFIG.DEFAULT_CANVAS_HEIGHT

      const scaleX = (containerWidth - padding * 2) / bounds.width
      const scaleY = (containerHeight - padding * 2) / bounds.height
      const scale = clampScale(Math.min(scaleX, scaleY, 1))

      // Center content
      const centerX = bounds.x + bounds.width / 2
      const centerY = bounds.y + bounds.height / 2
      const translateX = containerWidth / 2 - centerX * scale
      const translateY = containerHeight / 2 - centerY * scale

      setViewport({
        scale,
        translateX,
        translateY,
      })
    },
    [clampScale, resetView]
  )

  const zoomToFit = useCallback(
    (bounds: Bounds, containerWidth: number, containerHeight: number) => {
      const padding = CANVAS_CONFIG.CANVAS_PADDING

      const scaleX = (containerWidth - padding * 2) / bounds.width
      const scaleY = (containerHeight - padding * 2) / bounds.height
      const scale = clampScale(Math.min(scaleX, scaleY, 1))

      const centerX = bounds.x + bounds.width / 2
      const centerY = bounds.y + bounds.height / 2
      const translateX = containerWidth / 2 - centerX * scale
      const translateY = containerHeight / 2 - centerY * scale

      setViewport({
        scale,
        translateX,
        translateY,
      })
    },
    [clampScale]
  )

  const handleWheel = useCallback(
    (e: WheelEvent, containerRect: DOMRect) => {
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault()

        const zoomFactor = e.deltaY > 0 ? 0.9 : 1.1
        const newScale = clampScale(viewport.scale * zoomFactor)

        // Zoom toward cursor position
        const mouseX = e.clientX - containerRect.left
        const mouseY = e.clientY - containerRect.top

        // Calculate new translation to zoom toward cursor
        const scaleRatio = newScale / viewport.scale
        const newTranslateX = mouseX - (mouseX - viewport.translateX) * scaleRatio
        const newTranslateY = mouseY - (mouseY - viewport.translateY) * scaleRatio

        setViewport({
          scale: newScale,
          translateX: newTranslateX,
          translateY: newTranslateY,
        })
      }
    },
    [viewport, clampScale]
  )

  const startPan = useCallback(
    (x: number, y: number) => {
      setIsPanning(true)
      panStartRef.current = { x, y }
      viewportStartRef.current = { ...viewport }
    },
    [viewport]
  )

  const updatePan = useCallback((x: number, y: number) => {
    if (!isPanning) return

    const dx = x - panStartRef.current.x
    const dy = y - panStartRef.current.y

    setViewport({
      ...viewportStartRef.current,
      translateX: viewportStartRef.current.translateX + dx,
      translateY: viewportStartRef.current.translateY + dy,
    })
  }, [isPanning])

  const endPan = useCallback(() => {
    setIsPanning(false)
  }, [])

  const screenToCanvas = useCallback(
    (screenX: number, screenY: number): Point => {
      return {
        x: (screenX - viewport.translateX) / viewport.scale,
        y: (screenY - viewport.translateY) / viewport.scale,
      }
    },
    [viewport]
  )

  const canvasToScreen = useCallback(
    (canvasX: number, canvasY: number): Point => {
      return {
        x: canvasX * viewport.scale + viewport.translateX,
        y: canvasY * viewport.scale + viewport.translateY,
      }
    },
    [viewport]
  )

  const zoomPercentage = Math.round(viewport.scale * 100)

  return {
    viewport,
    isPanning,
    zoomIn,
    zoomOut,
    resetView,
    fitToContent,
    setZoom,
    handleWheel,
    startPan,
    updatePan,
    endPan,
    screenToCanvas,
    canvasToScreen,
    zoomToFit,
    zoomPercentage,
  }
}
