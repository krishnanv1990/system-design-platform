/**
 * useResize Hook
 * Handles element resizing with corner and edge handles
 */

import { useState, useCallback, useRef } from 'react'
import type { CanvasElement, HandlePosition, Point } from '@/types/canvas'
import { CANVAS_CONFIG } from '@/config/canvas'

export interface ResizeState {
  isResizing: boolean
  handle: HandlePosition | null
  elementId: string | null
  startX: number
  startY: number
  startWidth: number
  startHeight: number
  startElementX: number
  startElementY: number
}

export interface UseResizeReturn {
  resizeState: ResizeState
  startResize: (
    element: CanvasElement,
    handle: HandlePosition,
    mouseX: number,
    mouseY: number
  ) => void
  updateResize: (
    mouseX: number,
    mouseY: number,
    element: CanvasElement,
    maintainAspectRatio?: boolean
  ) => Partial<CanvasElement> | null
  endResize: () => void
  getHandleAtPosition: (
    element: CanvasElement,
    mouseX: number,
    mouseY: number
  ) => HandlePosition | null
  getHandleCursor: (handle: HandlePosition) => string
  isResizing: boolean
}

const initialState: ResizeState = {
  isResizing: false,
  handle: null,
  elementId: null,
  startX: 0,
  startY: 0,
  startWidth: 0,
  startHeight: 0,
  startElementX: 0,
  startElementY: 0,
}

export function useResize(): UseResizeReturn {
  const [resizeState, setResizeState] = useState<ResizeState>(initialState)
  const aspectRatioRef = useRef<number>(1)

  const startResize = useCallback(
    (
      element: CanvasElement,
      handle: HandlePosition,
      mouseX: number,
      mouseY: number
    ) => {
      aspectRatioRef.current = element.width / element.height
      setResizeState({
        isResizing: true,
        handle,
        elementId: element.id,
        startX: mouseX,
        startY: mouseY,
        startWidth: element.width,
        startHeight: element.height,
        startElementX: element.x,
        startElementY: element.y,
      })
    },
    []
  )

  const updateResize = useCallback(
    (
      mouseX: number,
      mouseY: number,
      element: CanvasElement,
      maintainAspectRatio: boolean = false
    ): Partial<CanvasElement> | null => {
      if (!resizeState.isResizing || !resizeState.handle) {
        return null
      }

      const dx = mouseX - resizeState.startX
      const dy = mouseY - resizeState.startY

      let newX = resizeState.startElementX
      let newY = resizeState.startElementY
      let newWidth = resizeState.startWidth
      let newHeight = resizeState.startHeight

      const handle = resizeState.handle

      // Calculate new dimensions based on handle
      switch (handle) {
        case 'se': // Bottom-right
          newWidth = resizeState.startWidth + dx
          newHeight = resizeState.startHeight + dy
          break

        case 'sw': // Bottom-left
          newX = resizeState.startElementX + dx
          newWidth = resizeState.startWidth - dx
          newHeight = resizeState.startHeight + dy
          break

        case 'ne': // Top-right
          newY = resizeState.startElementY + dy
          newWidth = resizeState.startWidth + dx
          newHeight = resizeState.startHeight - dy
          break

        case 'nw': // Top-left
          newX = resizeState.startElementX + dx
          newY = resizeState.startElementY + dy
          newWidth = resizeState.startWidth - dx
          newHeight = resizeState.startHeight - dy
          break

        case 'n': // Top
          newY = resizeState.startElementY + dy
          newHeight = resizeState.startHeight - dy
          break

        case 's': // Bottom
          newHeight = resizeState.startHeight + dy
          break

        case 'e': // Right
          newWidth = resizeState.startWidth + dx
          break

        case 'w': // Left
          newX = resizeState.startElementX + dx
          newWidth = resizeState.startWidth - dx
          break
      }

      // Maintain aspect ratio if requested
      if (maintainAspectRatio && ['nw', 'ne', 'sw', 'se'].includes(handle)) {
        const aspect = aspectRatioRef.current
        if (Math.abs(dx) > Math.abs(dy)) {
          newHeight = newWidth / aspect
          if (handle === 'nw' || handle === 'ne') {
            newY = resizeState.startElementY + resizeState.startHeight - newHeight
          }
        } else {
          newWidth = newHeight * aspect
          if (handle === 'nw' || handle === 'sw') {
            newX = resizeState.startElementX + resizeState.startWidth - newWidth
          }
        }
      }

      // Enforce minimum size
      const minSize = CANVAS_CONFIG.MIN_ELEMENT_SIZE

      if (newWidth < minSize) {
        if (handle === 'w' || handle === 'nw' || handle === 'sw') {
          newX = resizeState.startElementX + resizeState.startWidth - minSize
        }
        newWidth = minSize
      }

      if (newHeight < minSize) {
        if (handle === 'n' || handle === 'nw' || handle === 'ne') {
          newY = resizeState.startElementY + resizeState.startHeight - minSize
        }
        newHeight = minSize
      }

      return {
        x: newX,
        y: newY,
        width: newWidth,
        height: newHeight,
      }
    },
    [resizeState]
  )

  const endResize = useCallback(() => {
    setResizeState(initialState)
  }, [])

  const getHandleAtPosition = useCallback(
    (element: CanvasElement, mouseX: number, mouseY: number): HandlePosition | null => {
      if (element.type === 'arrow') return null

      const handleSize = CANVAS_CONFIG.HANDLE_SIZE
      const halfHandle = handleSize / 2

      const { x, y, width, height } = element

      // Define handle positions
      const handles: { position: HandlePosition; x: number; y: number }[] = [
        { position: 'nw', x: x - halfHandle, y: y - halfHandle },
        { position: 'n', x: x + width / 2 - halfHandle, y: y - halfHandle },
        { position: 'ne', x: x + width - halfHandle, y: y - halfHandle },
        { position: 'e', x: x + width - halfHandle, y: y + height / 2 - halfHandle },
        { position: 'se', x: x + width - halfHandle, y: y + height - halfHandle },
        { position: 's', x: x + width / 2 - halfHandle, y: y + height - halfHandle },
        { position: 'sw', x: x - halfHandle, y: y + height - halfHandle },
        { position: 'w', x: x - halfHandle, y: y + height / 2 - halfHandle },
      ]

      for (const handle of handles) {
        if (
          mouseX >= handle.x &&
          mouseX <= handle.x + handleSize &&
          mouseY >= handle.y &&
          mouseY <= handle.y + handleSize
        ) {
          return handle.position
        }
      }

      return null
    },
    []
  )

  const getHandleCursor = useCallback((handle: HandlePosition): string => {
    return CANVAS_CONFIG.CURSORS[handle]
  }, [])

  return {
    resizeState,
    startResize,
    updateResize,
    endResize,
    getHandleAtPosition,
    getHandleCursor,
    isResizing: resizeState.isResizing,
  }
}
