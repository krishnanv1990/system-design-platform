/**
 * Design Canvas Component
 * An Excalidraw-like drawing canvas for system design diagrams
 *
 * Features:
 * - Element creation (shapes, arrows, text, icons)
 * - Multi-select with shift+click and marquee selection
 * - Resize handles for all elements
 * - Arrow endpoint editing
 * - Element connections
 * - Zoom and pan
 * - Copy/paste/cut
 * - Undo/redo
 * - Grid snap
 * - Export to PNG/JPG/SVG/JSON
 * - Import from JSON/images
 */

import { useState, useRef, useCallback, useEffect, useMemo } from "react"
import {
  Square,
  Circle,
  Type,
  ArrowRight,
  MousePointer,
  Trash2,
  Download,
  Upload,
  RotateCcw,
  Database,
  Server,
  Cloud,
  Users,
  Globe,
  Undo2,
  Redo2,
  ChevronDown,
  FileJson,
  Image,
  FileImage,
  HardDrive,
  Scale,
  MessageSquare,
  Archive,
  Network,
  Monitor,
  Layers,
  Grid3X3,
  Copy,
  Clipboard,
  Scissors,
  HelpCircle,
} from "lucide-react"
import { useHistory } from "@/hooks/useHistory"
import { useResize } from "@/hooks/useResize"
import { useZoomPan } from "@/hooks/useZoomPan"
import { useCanvasSelection } from "@/hooks/useCanvasSelection"
import { useMarqueeSelection } from "@/hooks/useMarqueeSelection"
import { useCanvasClipboard } from "@/hooks/useCanvasClipboard"
import { useClickOutside } from "@/hooks/useClickOutside"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  exportCanvas,
  EXPORT_FORMATS,
  IMPORT_FORMATS,
  getImportAcceptString,
  readFileAsDataUrl,
  readFileAsText,
  getImageDimensions,
  parseSvgFile,
  type ExportFormat,
} from "@/lib/canvasExport"
import { parseAndValidateCanvas } from "@/lib/canvasSchema"
import { snapToGrid, snapPointToGrid } from "@/utils/snap"
import { updateConnectedArrows, findNearestConnectionPoint, getConnectionPoint } from "@/utils/connectionPoints"
import { sortByZIndex, assignZIndex, bringToFront, sendToBack } from "@/utils/zOrder"
import { moveElements, calculateBounds } from "@/utils/alignment"
import { getLineAngle, getScaledArrowHeadSize } from "@/utils/shapePaths"
import { isPointInElement } from "@/utils/hitDetection"
import { CANVAS_CONFIG, STROKE_COLORS, FILL_COLORS, ICON_LABELS } from "@/config/canvas"
import {
  SelectionHandles,
  ArrowEndpoints,
  CanvasGrid,
  ColorPicker,
  ConnectionPoints,
  ZoomControls,
  KeyboardShortcutsModal,
  MarqueeSelection,
} from "@/components/canvas"
import type {
  Tool,
  Point,
  CanvasElement,
  HandlePosition,
  ArrowElement,
  TextElement,
  IconElement,
  ImageElement,
  RectangleElement,
  EllipseElement,
  ConnectionPointPosition,
} from "@/types/canvas"

interface DesignCanvasProps {
  value?: string
  onChange?: (value: string) => void
  readOnly?: boolean
}

export default function DesignCanvas({
  value,
  onChange,
  readOnly = false,
}: DesignCanvasProps) {
  // History for undo/redo
  const {
    state: elements,
    setState: setElements,
    undo,
    redo,
    canUndo,
    canRedo,
  } = useHistory<CanvasElement[]>([])

  // Selection state
  const {
    selectedIds,
    editingId,
    select,
    selectMultiple,
    clearSelection,
    toggleSelection,
    isSelected,
    setEditingId,
    getSelectedElements,
    hasSelection,
    selectionCount,
  } = useCanvasSelection()

  // Resize handling
  const {
    resizeState,
    startResize,
    updateResize,
    endResize,
    getHandleAtPosition,
    getHandleCursor,
    isResizing,
  } = useResize()

  // Zoom and pan
  const {
    viewport,
    isPanning,
    zoomIn,
    zoomOut,
    resetView,
    fitToContent,
    handleWheel,
    startPan,
    updatePan,
    endPan,
    screenToCanvas,
    zoomPercentage,
  } = useZoomPan()

  // Marquee selection
  const {
    marquee,
    isSelecting: isMarqueeSelecting,
    startMarquee,
    updateMarquee,
    endMarquee,
    getElementsInMarquee,
  } = useMarqueeSelection()

  // Clipboard
  const { hasClipboard, copy, cut, paste, canPaste } = useCanvasClipboard()

  // UI state
  const [selectedTool, setSelectedTool] = useState<Tool>("select")
  const [strokeColor, setStrokeColor] = useState(CANVAS_CONFIG.DEFAULT_STROKE_COLOR)
  const [fillColor, setFillColor] = useState(CANVAS_CONFIG.DEFAULT_FILL_COLOR)
  const [isDrawing, setIsDrawing] = useState(false)
  const [drawStart, setDrawStart] = useState<Point | null>(null)
  const [tempElement, setTempElement] = useState<CanvasElement | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState<Point | null>(null)
  const [showStrokeColorPicker, setShowStrokeColorPicker] = useState(false)
  const [showFillColorPicker, setShowFillColorPicker] = useState(false)
  const [textInput, setTextInput] = useState("")
  const [showExportMenu, setShowExportMenu] = useState(false)
  const [showComponentMenu, setShowComponentMenu] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  const [snapEnabled, setSnapEnabled] = useState(CANVAS_CONFIG.SNAP_ENABLED_DEFAULT)
  const [showKeyboardShortcuts, setShowKeyboardShortcuts] = useState(false)
  const [showConnectionPoints, setShowConnectionPoints] = useState(false)
  const [activeConnectionPoint, setActiveConnectionPoint] = useState<string | null>(null)
  const [hoveredHandle, setHoveredHandle] = useState<HandlePosition | null>(null)
  const [draggingArrowEndpoint, setDraggingArrowEndpoint] = useState<'start' | 'end' | null>(null)
  const [spacePressed, setSpacePressed] = useState(false)

  // Refs
  const svgRef = useRef<SVGSVGElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const exportMenuRef = useRef<HTMLDivElement>(null)
  const componentMenuRef = useRef<HTMLDivElement>(null)

  // Click outside handlers for menus
  useClickOutside(exportMenuRef, () => setShowExportMenu(false), showExportMenu)
  useClickOutside(componentMenuRef, () => setShowComponentMenu(false), showComponentMenu)

  // Generate unique ID
  const generateId = () => Math.random().toString(36).substring(2, 11)

  // Sorted elements for rendering
  const sortedElements = useMemo(() => sortByZIndex(elements), [elements])

  // Load from value
  useEffect(() => {
    if (value) {
      try {
        const parsed = JSON.parse(value)
        if (Array.isArray(parsed.elements)) {
          const validated = parsed.elements.map((el: CanvasElement, index: number) => ({
            ...el,
            zIndex: el.zIndex ?? index,
            lineStyle: el.type === 'arrow' ? (el as ArrowElement).lineStyle || 'solid' : undefined,
          }))
          setElements(validated, { skipHistory: true })
        }
      } catch {
        // Invalid JSON, ignore
      }
    }
  }, [value, setElements])

  // Save to value
  useEffect(() => {
    if (onChange) {
      const data = JSON.stringify({ elements, version: 1 })
      onChange(data)
    }
  }, [elements, onChange])

  // Get mouse position in canvas coordinates
  const getMousePosition = useCallback((e: React.MouseEvent): Point => {
    if (!svgRef.current) return { x: 0, y: 0 }
    const rect = svgRef.current.getBoundingClientRect()
    const screenX = e.clientX - rect.left
    const screenY = e.clientY - rect.top
    return screenToCanvas(screenX, screenY)
  }, [screenToCanvas])

  // Apply snap if enabled
  const applySnap = useCallback((point: Point): Point => {
    if (!snapEnabled) return point
    return snapPointToGrid(point, CANVAS_CONFIG.GRID_SIZE, true)
  }, [snapEnabled])

  // Handle mouse down
  const handleMouseDown = (e: React.MouseEvent) => {
    if (readOnly) return

    const pos = getMousePosition(e)

    // Handle space+drag for panning
    if (spacePressed) {
      startPan(e.clientX, e.clientY)
      return
    }

    // Handle middle mouse button for panning
    if (e.button === 1) {
      e.preventDefault()
      startPan(e.clientX, e.clientY)
      return
    }

    if (selectedTool === "select") {
      // Check if clicking on a resize handle
      if (selectedIds.size === 1) {
        const selectedElement = elements.find(el => selectedIds.has(el.id))
        if (selectedElement) {
          const handle = getHandleAtPosition(selectedElement, pos.x, pos.y)
          if (handle) {
            startResize(selectedElement, handle, pos.x, pos.y)
            return
          }
        }
      }

      // Check if clicking on an element
      const clickedElement = [...sortedElements].reverse().find((el) =>
        isPointInElement(pos, el, CANVAS_CONFIG.ARROW_HIT_TOLERANCE)
      )

      if (clickedElement) {
        if (e.shiftKey) {
          toggleSelection(clickedElement.id)
        } else if (!isSelected(clickedElement.id)) {
          select(clickedElement.id)
        }
        setIsDragging(true)
        setDragStart(pos)
      } else {
        // Start marquee selection
        if (!e.shiftKey) {
          clearSelection()
        }
        startMarquee(pos.x, pos.y)
      }
    } else if (selectedTool === "text") {
      const snappedPos = applySnap(pos)
      const newElement: TextElement = {
        id: generateId(),
        type: "text",
        x: snappedPos.x,
        y: snappedPos.y,
        width: 100,
        height: 24,
        fill: strokeColor,
        stroke: "transparent",
        strokeWidth: 0,
        text: "Text",
        fontSize: CANVAS_CONFIG.DEFAULT_FONT_SIZE,
        fontFamily: CANVAS_CONFIG.DEFAULT_FONT_FAMILY,
        zIndex: 0,
      }
      const withZIndex = assignZIndex(elements, newElement)
      setElements([...elements, withZIndex])
      setEditingId(withZIndex.id)
      setTextInput("Text")
      select(withZIndex.id)
    } else if (Object.keys(ICON_LABELS).includes(selectedTool)) {
      const snappedPos = applySnap(pos)
      const newElement: IconElement = {
        id: generateId(),
        type: selectedTool as IconElement["type"],
        x: snappedPos.x - CANVAS_CONFIG.DEFAULT_ICON_SIZE / 2,
        y: snappedPos.y - CANVAS_CONFIG.DEFAULT_ICON_SIZE / 2,
        width: CANVAS_CONFIG.DEFAULT_ICON_SIZE,
        height: CANVAS_CONFIG.DEFAULT_ICON_SIZE,
        fill: fillColor,
        stroke: strokeColor,
        strokeWidth: 2,
        label: ICON_LABELS[selectedTool],
        zIndex: 0,
      }
      const withZIndex = assignZIndex(elements, newElement)
      setElements([...elements, withZIndex])
      select(withZIndex.id)
      setSelectedTool("select")
    } else {
      setIsDrawing(true)
      setDrawStart(applySnap(pos))
      setShowConnectionPoints(selectedTool === "arrow")
    }
  }

  // Handle mouse move
  const handleMouseMove = (e: React.MouseEvent) => {
    if (readOnly) return

    const pos = getMousePosition(e)

    // Handle panning
    if (isPanning) {
      updatePan(e.clientX, e.clientY)
      return
    }

    // Handle resize
    if (isResizing && resizeState.elementId) {
      const element = elements.find(el => el.id === resizeState.elementId)
      if (element) {
        const updates = updateResize(pos.x, pos.y, element, e.shiftKey)
        if (updates) {
          setElements(
            elements.map(el =>
              el.id === resizeState.elementId ? { ...el, ...updates } : el
            ),
            { skipHistory: true }
          )
        }
      }
      return
    }

    // Handle arrow endpoint dragging
    if (draggingArrowEndpoint && selectedIds.size === 1) {
      const arrowId = Array.from(selectedIds)[0]
      const arrow = elements.find(el => el.id === arrowId) as ArrowElement
      if (arrow) {
        const snappedPos = applySnap(pos)
        const nearest = findNearestConnectionPoint(snappedPos, elements, arrowId)

        if (nearest) {
          setActiveConnectionPoint(nearest.connectionPoint.id)
        } else {
          setActiveConnectionPoint(null)
        }

        const updates = draggingArrowEndpoint === 'start'
          ? { x: snappedPos.x, y: snappedPos.y }
          : { endX: snappedPos.x, endY: snappedPos.y }

        setElements(
          elements.map(el =>
            el.id === arrowId ? { ...el, ...updates } : el
          ),
          { skipHistory: true }
        )
      }
      return
    }

    // Handle marquee selection
    if (isMarqueeSelecting) {
      updateMarquee(pos.x, pos.y)
      return
    }

    // Handle element dragging
    if (isDragging && hasSelection && dragStart) {
      const dx = pos.x - dragStart.x
      const dy = pos.y - dragStart.y

      // Move all selected elements
      const updatedElements = moveElements(elements, selectedIds, dx, dy)

      // Update connected arrows
      const withConnections = selectedIds.size > 0
        ? Array.from(selectedIds).reduce((els, id) => updateConnectedArrows(els, id), updatedElements)
        : updatedElements

      setElements(withConnections, { skipHistory: true })
      setDragStart(pos)
      return
    }

    // Handle drawing preview
    if (isDrawing && drawStart) {
      const snappedPos = applySnap(pos)
      const width = snappedPos.x - drawStart.x
      const height = snappedPos.y - drawStart.y

      if (selectedTool === "rectangle") {
        setTempElement({
          id: "temp",
          type: "rectangle",
          x: width > 0 ? drawStart.x : snappedPos.x,
          y: height > 0 ? drawStart.y : snappedPos.y,
          width: Math.abs(width),
          height: Math.abs(height),
          fill: fillColor,
          stroke: strokeColor,
          strokeWidth: 2,
          cornerRadius: 4,
          zIndex: 0,
        })
      } else if (selectedTool === "ellipse") {
        setTempElement({
          id: "temp",
          type: "ellipse",
          x: width > 0 ? drawStart.x : snappedPos.x,
          y: height > 0 ? drawStart.y : snappedPos.y,
          width: Math.abs(width),
          height: Math.abs(height),
          fill: fillColor,
          stroke: strokeColor,
          strokeWidth: 2,
          zIndex: 0,
        })
      } else if (selectedTool === "arrow") {
        // Check for connection point
        const nearest = findNearestConnectionPoint(snappedPos, elements)
        if (nearest) {
          setActiveConnectionPoint(nearest.connectionPoint.id)
        } else {
          setActiveConnectionPoint(null)
        }

        setTempElement({
          id: "temp",
          type: "arrow",
          x: drawStart.x,
          y: drawStart.y,
          width: 0,
          height: 0,
          endX: snappedPos.x,
          endY: snappedPos.y,
          fill: "transparent",
          stroke: strokeColor,
          strokeWidth: 2,
          lineStyle: 'solid',
          zIndex: 0,
        })
      }
    }

    // Update hovered handle
    if (selectedTool === "select" && selectedIds.size === 1) {
      const selectedElement = elements.find(el => selectedIds.has(el.id))
      if (selectedElement && selectedElement.type !== 'arrow') {
        const handle = getHandleAtPosition(selectedElement, pos.x, pos.y)
        setHoveredHandle(handle)
      } else {
        setHoveredHandle(null)
      }
    }
  }

  // Handle mouse up
  const handleMouseUp = (e: React.MouseEvent) => {
    if (readOnly) return

    const pos = getMousePosition(e)

    // End panning
    if (isPanning) {
      endPan()
      return
    }

    // End resize
    if (isResizing) {
      endResize()
      setElements([...elements]) // Commit to history
      return
    }

    // End arrow endpoint dragging with connection
    if (draggingArrowEndpoint && selectedIds.size === 1) {
      const arrowId = Array.from(selectedIds)[0]
      const arrow = elements.find(el => el.id === arrowId) as ArrowElement
      if (arrow) {
        const snappedPos = applySnap(pos)
        const nearest = findNearestConnectionPoint(snappedPos, elements, arrowId)

        if (nearest) {
          const connectionUpdate = draggingArrowEndpoint === 'start'
            ? {
                x: nearest.connectionPoint.x,
                y: nearest.connectionPoint.y,
                startConnection: {
                  elementId: nearest.element.id,
                  point: nearest.connectionPoint.position,
                },
              }
            : {
                endX: nearest.connectionPoint.x,
                endY: nearest.connectionPoint.y,
                endConnection: {
                  elementId: nearest.element.id,
                  point: nearest.connectionPoint.position,
                },
              }

          setElements(
            elements.map(el =>
              el.id === arrowId ? { ...el, ...connectionUpdate } : el
            )
          )
        } else {
          setElements([...elements]) // Commit to history
        }
      }
      setDraggingArrowEndpoint(null)
      setActiveConnectionPoint(null)
      setShowConnectionPoints(false)
      return
    }

    // End marquee selection
    if (isMarqueeSelecting) {
      const selected = getElementsInMarquee(elements)
      if (selected.length > 0) {
        if (e.shiftKey) {
          selectMultiple([...Array.from(selectedIds), ...selected])
        } else {
          selectMultiple(selected)
        }
      }
      endMarquee()
      return
    }

    // End drawing
    if (isDrawing && tempElement && tempElement.id === "temp") {
      const snappedPos = applySnap(pos)

      // Handle arrow connections
      let newElement: CanvasElement = { ...tempElement, id: generateId() }

      if (newElement.type === 'arrow') {
        const arrow = newElement as ArrowElement

        // Check start connection
        const startNearest = findNearestConnectionPoint({ x: arrow.x, y: arrow.y }, elements)
        if (startNearest) {
          arrow.x = startNearest.connectionPoint.x
          arrow.y = startNearest.connectionPoint.y
          arrow.startConnection = {
            elementId: startNearest.element.id,
            point: startNearest.connectionPoint.position,
          }
        }

        // Check end connection
        const endNearest = findNearestConnectionPoint({ x: arrow.endX, y: arrow.endY }, elements)
        if (endNearest) {
          arrow.endX = endNearest.connectionPoint.x
          arrow.endY = endNearest.connectionPoint.y
          arrow.endConnection = {
            elementId: endNearest.element.id,
            point: endNearest.connectionPoint.position,
          }
        }
      }

      newElement = assignZIndex(elements, newElement)
      setElements([...elements, newElement])
      select(newElement.id)
    }

    // Commit drag to history
    if (isDragging && hasSelection) {
      setElements([...elements])
    }

    // Reset state
    setIsDrawing(false)
    setDrawStart(null)
    setTempElement(null)
    setIsDragging(false)
    setDragStart(null)
    setShowConnectionPoints(false)
    setActiveConnectionPoint(null)
  }

  // Handle wheel for zoom
  const handleWheelEvent = useCallback((e: WheelEvent) => {
    if (readOnly || !containerRef.current) return
    const rect = containerRef.current.getBoundingClientRect()
    handleWheel(e, rect)
  }, [readOnly, handleWheel])

  useEffect(() => {
    const container = containerRef.current
    if (!container) return

    container.addEventListener('wheel', handleWheelEvent, { passive: false })
    return () => container.removeEventListener('wheel', handleWheelEvent)
  }, [handleWheelEvent])

  // Handle keyboard events
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (readOnly) return

      // Don't handle shortcuts when editing text
      if (editingId) return

      const ctrlOrMeta = e.ctrlKey || e.metaKey

      // Space for panning
      if (e.code === 'Space' && !spacePressed) {
        setSpacePressed(true)
        e.preventDefault()
        return
      }

      // Show keyboard shortcuts
      if (e.key === '?') {
        setShowKeyboardShortcuts(true)
        e.preventDefault()
        return
      }

      // Undo
      if (ctrlOrMeta && e.key === "z" && !e.shiftKey) {
        e.preventDefault()
        undo()
        return
      }

      // Redo
      if (ctrlOrMeta && (e.key === "y" || (e.key === "z" && e.shiftKey))) {
        e.preventDefault()
        redo()
        return
      }

      // Copy
      if (ctrlOrMeta && e.key === "c") {
        e.preventDefault()
        copy(getSelectedElements(elements))
        return
      }

      // Paste
      if (ctrlOrMeta && e.key === "v") {
        e.preventDefault()
        const pasted = paste()
        if (pasted.length > 0) {
          const withZIndex = pasted.map((el, i) => assignZIndex([...elements, ...pasted.slice(0, i)], el))
          setElements([...elements, ...withZIndex])
          selectMultiple(pasted.map(el => el.id))
        }
        return
      }

      // Cut
      if (ctrlOrMeta && e.key === "x") {
        e.preventDefault()
        const idsToDelete = cut(getSelectedElements(elements))
        setElements(elements.filter(el => !idsToDelete.includes(el.id)))
        clearSelection()
        return
      }

      // Select all
      if (ctrlOrMeta && e.key === "a") {
        e.preventDefault()
        selectMultiple(elements.map(el => el.id))
        return
      }

      // Duplicate
      if (ctrlOrMeta && e.key === "d") {
        e.preventDefault()
        copy(getSelectedElements(elements))
        const pasted = paste({ x: 20, y: 20 })
        if (pasted.length > 0) {
          const withZIndex = pasted.map((el, i) => assignZIndex([...elements, ...pasted.slice(0, i)], el))
          setElements([...elements, ...withZIndex])
          selectMultiple(pasted.map(el => el.id))
        }
        return
      }

      // Delete
      if (e.key === "Delete" || e.key === "Backspace") {
        if (hasSelection) {
          setElements(elements.filter((el) => !selectedIds.has(el.id)))
          clearSelection()
        }
        return
      }

      // Escape
      if (e.key === "Escape") {
        clearSelection()
        setSelectedTool("select")
        return
      }

      // Arrow keys for moving
      if (hasSelection && ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight"].includes(e.key)) {
        e.preventDefault()
        const step = e.shiftKey ? 10 : 1
        let dx = 0, dy = 0

        switch (e.key) {
          case "ArrowUp": dy = -step; break
          case "ArrowDown": dy = step; break
          case "ArrowLeft": dx = -step; break
          case "ArrowRight": dx = step; break
        }

        const movedElements = moveElements(elements, selectedIds, dx, dy)
        const withConnections = Array.from(selectedIds).reduce(
          (els, id) => updateConnectedArrows(els, id),
          movedElements
        )
        setElements(withConnections)
        return
      }

      // Bring to front
      if (ctrlOrMeta && e.key === "]") {
        e.preventDefault()
        if (hasSelection) {
          setElements(bringToFront(elements, selectedIds))
        }
        return
      }

      // Send to back
      if (ctrlOrMeta && e.key === "[") {
        e.preventDefault()
        if (hasSelection) {
          setElements(sendToBack(elements, selectedIds))
        }
        return
      }
    },
    [
      elements,
      selectedIds,
      hasSelection,
      editingId,
      readOnly,
      spacePressed,
      undo,
      redo,
      copy,
      paste,
      cut,
      getSelectedElements,
      clearSelection,
      selectMultiple,
      setElements,
    ]
  )

  const handleKeyUp = useCallback((e: KeyboardEvent) => {
    if (e.code === 'Space') {
      setSpacePressed(false)
    }
  }, [])

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown)
    window.addEventListener("keyup", handleKeyUp)
    return () => {
      window.removeEventListener("keydown", handleKeyDown)
      window.removeEventListener("keyup", handleKeyUp)
    }
  }, [handleKeyDown, handleKeyUp])

  // Handle double click for text editing
  const handleDoubleClick = useCallback((elementId: string) => {
    if (readOnly) return
    const element = elements.find((el) => el.id === elementId)
    if (!element) return

    if (element.type === "text" || Object.keys(ICON_LABELS).includes(element.type)) {
      setEditingId(elementId)
      setTextInput((element as TextElement | IconElement).text || (element as IconElement).label || "")
    }
  }, [readOnly, elements, setEditingId])

  // Handle text submit
  const handleTextSubmit = useCallback(() => {
    if (editingId) {
      setElements(
        elements.map((el) => {
          if (el.id === editingId) {
            if (el.type === "text") {
              return { ...el, text: textInput }
            } else {
              return { ...el, label: textInput }
            }
          }
          return el
        })
      )
      setEditingId(null)
      setTextInput("")
    }
  }, [editingId, textInput, elements, setElements, setEditingId])

  // Clear canvas
  const clearCanvas = useCallback(() => {
    if (!readOnly) {
      setElements([])
      clearSelection()
    }
  }, [readOnly, setElements, clearSelection])

  // Export
  const handleExport = async (format: ExportFormat) => {
    if (!svgRef.current) return

    setIsExporting(true)
    setShowExportMenu(false)

    try {
      await exportCanvas(svgRef.current, elements, {
        format,
        filename: 'system-design',
        scale: 2,
        quality: 0.92,
        backgroundColor: '#ffffff',
      })
    } catch (error) {
      console.error('Export failed:', error)
    } finally {
      setIsExporting(false)
    }
  }

  // Import
  const importCanvas = async () => {
    setImportError(null)
    const input = document.createElement("input")
    input.type = "file"
    input.accept = getImportAcceptString()
    input.onchange = async (e) => {
      const file = (e.target as HTMLInputElement).files?.[0]
      if (!file) return

      const fileExtension = file.name.toLowerCase().split('.').pop()
      const fileType = file.type.toLowerCase()

      const maxSize = 10 * 1024 * 1024
      if (file.size > maxSize) {
        setImportError(`File too large. Maximum size is 10MB, got ${(file.size / 1024 / 1024).toFixed(1)}MB`)
        return
      }

      try {
        if (fileExtension === 'json' || fileType === 'application/json') {
          const text = await readFileAsText(file)
          const result = parseAndValidateCanvas(text)

          if (!result.success) {
            setImportError(`Invalid JSON: ${result.errors.join(', ')}`)
            return
          }

          if (result.warnings.length > 0) {
            console.warn('Import warnings:', result.warnings)
          }

          setElements(result.data!.elements)
          return
        }

        if (fileExtension === 'svg' || fileType === 'image/svg+xml') {
          const { dataUrl, width, height } = await parseSvgFile(file)
          const maxWidth = 400
          const maxHeight = 300
          const scale = Math.min(maxWidth / width, maxHeight / height, 1)

          const imageElement: ImageElement = {
            id: generateId(),
            type: "image",
            x: 50,
            y: 50,
            width: width * scale,
            height: height * scale,
            fill: "transparent",
            stroke: "transparent",
            strokeWidth: 0,
            dataUrl,
            originalWidth: width,
            originalHeight: height,
            zIndex: 0,
          }
          const withZIndex = assignZIndex(elements, imageElement)
          setElements([...elements, withZIndex])
          select(withZIndex.id)
          return
        }

        if (fileType.startsWith('image/')) {
          const dataUrl = await readFileAsDataUrl(file)
          const { width, height } = await getImageDimensions(dataUrl)
          const maxWidth = 400
          const maxHeight = 300
          const scale = Math.min(maxWidth / width, maxHeight / height, 1)

          const imageElement: ImageElement = {
            id: generateId(),
            type: "image",
            x: 50,
            y: 50,
            width: width * scale,
            height: height * scale,
            fill: "transparent",
            stroke: "transparent",
            strokeWidth: 0,
            dataUrl,
            originalWidth: width,
            originalHeight: height,
            zIndex: 0,
          }
          const withZIndex = assignZIndex(elements, imageElement)
          setElements([...elements, withZIndex])
          select(withZIndex.id)
          return
        }

        setImportError(`Unsupported file type: ${fileType || fileExtension}`)
      } catch (err) {
        const errorMessage = err instanceof Error ? err.message : 'Unknown error'
        setImportError(`Failed to import: ${errorMessage}`)
        console.error("Failed to import:", err)
      }
    }
    input.click()
  }

  // Render element
  const renderElement = (element: CanvasElement, isTemp = false) => {
    const elementSelected = !isTemp && isSelected(element.id)

    const commonProps = {
      key: element.id,
      onClick: (e: React.MouseEvent) => {
        e.stopPropagation()
        if (!readOnly && selectedTool === "select" && !isResizing && !isDragging) {
          if (e.shiftKey) {
            toggleSelection(element.id)
          } else {
            select(element.id)
          }
        }
      },
      onDoubleClick: () => handleDoubleClick(element.id),
      style: {
        cursor: readOnly ? "default" :
          (elementSelected && hoveredHandle) ? getHandleCursor(hoveredHandle) :
          spacePressed ? "grab" : "move"
      },
    }

    const renderSelectionUI = () => {
      if (!elementSelected || isTemp) return null

      if (element.type === 'arrow') {
        return (
          <ArrowEndpoints
            arrow={element as ArrowElement}
            onStartDrag={(e) => {
              e.stopPropagation()
              setDraggingArrowEndpoint('start')
              setShowConnectionPoints(true)
            }}
            onEndDrag={(e) => {
              e.stopPropagation()
              setDraggingArrowEndpoint('end')
              setShowConnectionPoints(true)
            }}
            hoveredEndpoint={null}
          />
        )
      }

      return (
        <SelectionHandles
          element={element}
          onMouseDown={(handle, e) => {
            e.stopPropagation()
            startResize(element, handle, getMousePosition(e).x, getMousePosition(e).y)
          }}
          hoveredHandle={hoveredHandle}
        />
      )
    }

    switch (element.type) {
      case "rectangle": {
        const rect = element as RectangleElement
        return (
          <g {...commonProps}>
            <rect
              x={rect.x}
              y={rect.y}
              width={rect.width}
              height={rect.height}
              rx={rect.cornerRadius}
              fill={rect.fill}
              stroke={elementSelected ? CANVAS_CONFIG.SELECTION_STROKE : rect.stroke}
              strokeWidth={elementSelected ? 3 : rect.strokeWidth}
              strokeDasharray={isTemp ? "5,5" : undefined}
            />
            {renderSelectionUI()}
          </g>
        )
      }

      case "ellipse": {
        const ellipse = element as EllipseElement
        return (
          <g {...commonProps}>
            <ellipse
              cx={ellipse.x + ellipse.width / 2}
              cy={ellipse.y + ellipse.height / 2}
              rx={ellipse.width / 2}
              ry={ellipse.height / 2}
              fill={ellipse.fill}
              stroke={elementSelected ? CANVAS_CONFIG.SELECTION_STROKE : ellipse.stroke}
              strokeWidth={elementSelected ? 3 : ellipse.strokeWidth}
              strokeDasharray={isTemp ? "5,5" : undefined}
            />
            {renderSelectionUI()}
          </g>
        )
      }

      case "arrow": {
        const arrow = element as ArrowElement
        const angle = getLineAngle(arrow.x, arrow.y, arrow.endX, arrow.endY)
        const headSize = getScaledArrowHeadSize(arrow.x, arrow.y, arrow.endX, arrow.endY)
        const arrowAngle = CANVAS_CONFIG.ARROW_HEAD_ANGLE

        const x1 = arrow.endX - headSize * Math.cos(angle - arrowAngle)
        const y1 = arrow.endY - headSize * Math.sin(angle - arrowAngle)
        const x2 = arrow.endX - headSize * Math.cos(angle + arrowAngle)
        const y2 = arrow.endY - headSize * Math.sin(angle + arrowAngle)

        const dashArray = arrow.lineStyle === 'dashed'
          ? '8,4'
          : arrow.lineStyle === 'dotted'
          ? '2,4'
          : undefined

        return (
          <g {...commonProps}>
            <line
              x1={arrow.x}
              y1={arrow.y}
              x2={arrow.endX}
              y2={arrow.endY}
              stroke={elementSelected ? CANVAS_CONFIG.SELECTION_STROKE : arrow.stroke}
              strokeWidth={elementSelected ? 3 : arrow.strokeWidth}
              strokeDasharray={isTemp ? "5,5" : dashArray}
            />
            <polygon
              points={`${arrow.endX},${arrow.endY} ${x1},${y1} ${x2},${y2}`}
              fill={elementSelected ? CANVAS_CONFIG.SELECTION_STROKE : arrow.stroke}
            />
            {renderSelectionUI()}
          </g>
        )
      }

      case "text": {
        const textEl = element as TextElement
        return (
          <g {...commonProps}>
            {elementSelected && (
              <rect
                x={textEl.x - 4}
                y={textEl.y - textEl.fontSize - 4}
                width={textEl.width + 8}
                height={textEl.fontSize + 8}
                fill="transparent"
                stroke={CANVAS_CONFIG.SELECTION_STROKE}
                strokeWidth={2}
                strokeDasharray="4,4"
              />
            )}
            <text
              x={textEl.x}
              y={textEl.y}
              fill={textEl.fill}
              fontSize={textEl.fontSize}
              fontFamily={textEl.fontFamily || CANVAS_CONFIG.DEFAULT_FONT_FAMILY}
            >
              {textEl.text}
            </text>
            {renderSelectionUI()}
          </g>
        )
      }

      case "image": {
        const imgEl = element as ImageElement
        return (
          <g {...commonProps}>
            <image
              href={imgEl.dataUrl}
              x={imgEl.x}
              y={imgEl.y}
              width={imgEl.width}
              height={imgEl.height}
              preserveAspectRatio="xMidYMid meet"
            />
            {renderSelectionUI()}
          </g>
        )
      }

      // Icon elements
      default: {
        if (Object.keys(ICON_LABELS).includes(element.type)) {
          const iconEl = element as IconElement
          const centerX = element.x + element.width / 2
          const centerY = element.y + element.height / 2

          return (
            <g {...commonProps}>
              <rect
                x={element.x}
                y={element.y}
                width={element.width}
                height={element.height}
                rx={8}
                fill={element.fill}
                stroke={elementSelected ? CANVAS_CONFIG.SELECTION_STROKE : element.stroke}
                strokeWidth={elementSelected ? 3 : element.strokeWidth}
              />
              {/* Icon rendering based on type */}
              {element.type === "database" && (
                <>
                  <ellipse cx={centerX} cy={element.y + 15} rx={15} ry={6} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                  <path d={`M ${centerX - 15} ${element.y + 15} v 20 a 15 6 0 0 0 30 0 v -20`} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                </>
              )}
              {element.type === "server" && (
                <>
                  <rect x={centerX - 12} y={element.y + 10} width={24} height={8} rx={2} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                  <rect x={centerX - 12} y={element.y + 22} width={24} height={8} rx={2} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                  <circle cx={centerX - 6} cy={element.y + 14} r={1.5} fill={element.stroke} />
                  <circle cx={centerX - 6} cy={element.y + 26} r={1.5} fill={element.stroke} />
                </>
              )}
              {element.type === "cloud" && (
                <path
                  d={`M ${centerX - 15} ${element.y + 28} a 10 10 0 0 1 0 -14 a 12 12 0 0 1 20 -4 a 10 10 0 0 1 10 14 z`}
                  fill="none"
                  stroke={element.stroke}
                  strokeWidth={1.5}
                />
              )}
              {element.type === "user" && (
                <>
                  <circle cx={centerX} cy={element.y + 15} r={8} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                  <path d={`M ${centerX - 12} ${element.y + 38} a 12 10 0 0 1 24 0`} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                </>
              )}
              {element.type === "globe" && (
                <>
                  <circle cx={centerX} cy={centerY - 5} r={15} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                  <ellipse cx={centerX} cy={centerY - 5} rx={6} ry={15} fill="none" stroke={element.stroke} strokeWidth={1} />
                  <line x1={centerX - 15} y1={centerY - 5} x2={centerX + 15} y2={centerY - 5} stroke={element.stroke} strokeWidth={1} />
                </>
              )}
              {element.type === "cache" && (
                <>
                  <ellipse cx={centerX} cy={element.y + 12} rx={14} ry={5} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                  <path d={`M ${centerX - 14} ${element.y + 12} v 18 a 14 5 0 0 0 28 0 v -18`} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                  <path d={`M ${centerX + 2} ${element.y + 18} l -6 8 h 5 l -4 8`} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                </>
              )}
              {element.type === "load_balancer" && (
                <>
                  <circle cx={centerX} cy={element.y + 20} r={12} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                  <line x1={centerX - 8} y1={element.y + 20} x2={centerX + 8} y2={element.y + 20} stroke={element.stroke} strokeWidth={1.5} />
                  <line x1={centerX} y1={element.y + 12} x2={centerX} y2={element.y + 28} stroke={element.stroke} strokeWidth={1.5} />
                  <path d={`M ${centerX - 5} ${element.y + 14} l 5 -4 l 5 4`} fill="none" stroke={element.stroke} strokeWidth={1} />
                  <path d={`M ${centerX - 5} ${element.y + 26} l 5 4 l 5 -4`} fill="none" stroke={element.stroke} strokeWidth={1} />
                </>
              )}
              {element.type === "queue" && (
                <>
                  <rect x={centerX - 16} y={element.y + 12} width={32} height={6} rx={1} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                  <rect x={centerX - 16} y={element.y + 21} width={32} height={6} rx={1} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                  <rect x={centerX - 16} y={element.y + 30} width={32} height={6} rx={1} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                </>
              )}
              {element.type === "blob_storage" && (
                <>
                  <rect x={centerX - 14} y={element.y + 14} width={28} height={22} rx={2} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                  <path d={`M ${centerX - 14} ${element.y + 18} h 10 l 4 -4 h 14`} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                </>
              )}
              {element.type === "dns" && (
                <>
                  <circle cx={centerX} cy={element.y + 14} r={6} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                  <circle cx={centerX - 12} cy={element.y + 32} r={5} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                  <circle cx={centerX + 12} cy={element.y + 32} r={5} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                  <line x1={centerX - 4} y1={element.y + 18} x2={centerX - 10} y2={element.y + 28} stroke={element.stroke} strokeWidth={1} />
                  <line x1={centerX + 4} y1={element.y + 18} x2={centerX + 10} y2={element.y + 28} stroke={element.stroke} strokeWidth={1} />
                </>
              )}
              {element.type === "client" && (
                <>
                  <rect x={centerX - 14} y={element.y + 10} width={28} height={18} rx={2} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                  <line x1={centerX - 10} y1={element.y + 28} x2={centerX + 10} y2={element.y + 28} stroke={element.stroke} strokeWidth={1.5} />
                  <rect x={centerX - 18} y={element.y + 32} width={36} height={4} rx={1} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                </>
              )}
              {element.type === "api_gateway" && (
                <>
                  <rect x={centerX - 12} y={element.y + 10} width={24} height={28} rx={3} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                  <line x1={centerX - 8} y1={element.y + 18} x2={centerX + 8} y2={element.y + 18} stroke={element.stroke} strokeWidth={1} />
                  <line x1={centerX - 8} y1={element.y + 24} x2={centerX + 8} y2={element.y + 24} stroke={element.stroke} strokeWidth={1} />
                  <line x1={centerX - 8} y1={element.y + 30} x2={centerX + 8} y2={element.y + 30} stroke={element.stroke} strokeWidth={1} />
                </>
              )}
              {/* Label */}
              <text
                x={centerX}
                y={element.y + element.height - 5}
                fill={element.stroke}
                fontSize={10}
                textAnchor="middle"
                fontFamily={CANVAS_CONFIG.DEFAULT_FONT_FAMILY}
              >
                {iconEl.label}
              </text>
              {renderSelectionUI()}
            </g>
          )
        }
        return null
      }
    }
  }

  // Tool definitions
  const drawingTools: { id: Tool; icon: React.ElementType; label: string }[] = [
    { id: "select", icon: MousePointer, label: "Select (V)" },
    { id: "rectangle", icon: Square, label: "Rectangle (R)" },
    { id: "ellipse", icon: Circle, label: "Ellipse (O)" },
    { id: "arrow", icon: ArrowRight, label: "Arrow (A)" },
    { id: "text", icon: Type, label: "Text (T)" },
  ]

  const componentTools: { id: Tool; icon: React.ElementType; label: string }[] = [
    { id: "client", icon: Monitor, label: "Client" },
    { id: "dns", icon: Network, label: "DNS" },
    { id: "load_balancer", icon: Scale, label: "Load Balancer" },
    { id: "api_gateway", icon: Layers, label: "API Gateway" },
    { id: "server", icon: Server, label: "Server" },
    { id: "database", icon: Database, label: "Database" },
    { id: "cache", icon: HardDrive, label: "Cache" },
    { id: "queue", icon: MessageSquare, label: "Message Queue" },
    { id: "blob_storage", icon: Archive, label: "Blob Storage" },
    { id: "cloud", icon: Cloud, label: "Cloud" },
    { id: "user", icon: Users, label: "User" },
    { id: "globe", icon: Globe, label: "Internet" },
  ]

  const getFormatIcon = (format: ExportFormat) => {
    switch (format) {
      case 'json': return FileJson
      case 'svg': return FileImage
      case 'png':
      case 'jpg': return Image
      default: return Download
    }
  }

  return (
    <div className="border rounded-lg overflow-hidden bg-white dark:bg-slate-900">
      {/* Toolbar */}
      {!readOnly && (
        <div className="flex items-center justify-between border-b bg-muted/50 px-2 py-1.5 flex-wrap gap-1">
          {/* Drawing Tools */}
          <div className="flex items-center gap-1">
            {drawingTools.map((tool) => {
              const Icon = tool.icon
              return (
                <Button
                  key={tool.id}
                  variant={selectedTool === tool.id ? "default" : "ghost"}
                  size="sm"
                  className="h-8 w-8 p-0"
                  onClick={() => setSelectedTool(tool.id)}
                  title={tool.label}
                >
                  <Icon className="h-4 w-4" />
                </Button>
              )
            })}

            <div className="w-px h-6 bg-border mx-1" />

            {/* System Design Components */}
            <div className="relative" ref={componentMenuRef}>
              <Button
                variant={componentTools.some(t => t.id === selectedTool) ? "default" : "ghost"}
                size="sm"
                className="h-8 gap-1 px-2"
                onClick={() => setShowComponentMenu(!showComponentMenu)}
                title="System Components"
              >
                <Layers className="h-4 w-4" />
                <span className="text-xs hidden sm:inline">Components</span>
                <ChevronDown className="h-3 w-3" />
              </Button>
              {showComponentMenu && (
                <div className="absolute top-full left-0 mt-1 bg-popover border rounded-lg shadow-lg z-20 min-w-[180px] py-1">
                  <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground border-b mb-1">
                    System Components
                  </div>
                  <div className="max-h-[300px] overflow-y-auto">
                    {componentTools.map((tool) => {
                      const Icon = tool.icon
                      return (
                        <button
                          key={tool.id}
                          className={cn(
                            "w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted transition-colors text-left",
                            selectedTool === tool.id && "bg-muted"
                          )}
                          onClick={() => {
                            setSelectedTool(tool.id)
                            setShowComponentMenu(false)
                          }}
                        >
                          <Icon className="h-4 w-4 text-muted-foreground" />
                          <span>{tool.label}</span>
                        </button>
                      )
                    })}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Color pickers */}
          <div className="flex items-center gap-2">
            <div className="relative">
              <Button
                variant="ghost"
                size="sm"
                className="h-8 gap-1.5"
                onClick={() => setShowStrokeColorPicker(!showStrokeColorPicker)}
              >
                <div className="w-4 h-4 rounded border" style={{ backgroundColor: strokeColor }} />
                <span className="text-xs">Stroke</span>
              </Button>
              <ColorPicker
                isOpen={showStrokeColorPicker}
                onClose={() => setShowStrokeColorPicker(false)}
                onSelect={setStrokeColor}
                colors={STROKE_COLORS}
                selectedColor={strokeColor}
              />
            </div>

            <div className="relative">
              <Button
                variant="ghost"
                size="sm"
                className="h-8 gap-1.5"
                onClick={() => setShowFillColorPicker(!showFillColorPicker)}
              >
                <div
                  className="w-4 h-4 rounded border"
                  style={{
                    backgroundColor: fillColor === "transparent" ? "white" : fillColor,
                    backgroundImage: fillColor === "transparent"
                      ? "linear-gradient(45deg, #ccc 25%, transparent 25%, transparent 75%, #ccc 75%), linear-gradient(45deg, #ccc 25%, transparent 25%, transparent 75%, #ccc 75%)"
                      : undefined,
                    backgroundSize: "4px 4px",
                    backgroundPosition: "0 0, 2px 2px",
                  }}
                />
                <span className="text-xs">Fill</span>
              </Button>
              <ColorPicker
                isOpen={showFillColorPicker}
                onClose={() => setShowFillColorPicker(false)}
                onSelect={setFillColor}
                colors={FILL_COLORS}
                selectedColor={fillColor}
                showTransparent
              />
            </div>

            <div className="w-px h-4 bg-border mx-1" />

            {/* Grid snap toggle */}
            <Button
              variant={snapEnabled ? "default" : "ghost"}
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => setSnapEnabled(!snapEnabled)}
              title={snapEnabled ? "Snap to grid enabled" : "Snap to grid disabled"}
            >
              <Grid3X3 className="h-4 w-4" />
            </Button>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={undo}
              disabled={!canUndo}
              title="Undo (Ctrl+Z)"
            >
              <Undo2 className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={redo}
              disabled={!canRedo}
              title="Redo (Ctrl+Y)"
            >
              <Redo2 className="h-4 w-4" />
            </Button>

            <div className="w-px h-4 bg-border mx-1" />

            {/* Clipboard actions */}
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => copy(getSelectedElements(elements))}
              disabled={!hasSelection}
              title="Copy (Ctrl+C)"
            >
              <Copy className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => {
                const idsToDelete = cut(getSelectedElements(elements))
                setElements(elements.filter(el => !idsToDelete.includes(el.id)))
                clearSelection()
              }}
              disabled={!hasSelection}
              title="Cut (Ctrl+X)"
            >
              <Scissors className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => {
                const pasted = paste()
                if (pasted.length > 0) {
                  const withZIndex = pasted.map((el, i) => assignZIndex([...elements, ...pasted.slice(0, i)], el))
                  setElements([...elements, ...withZIndex])
                  selectMultiple(pasted.map(el => el.id))
                }
              }}
              disabled={!canPaste}
              title="Paste (Ctrl+V)"
            >
              <Clipboard className="h-4 w-4" />
            </Button>

            <div className="w-px h-4 bg-border mx-1" />

            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={clearCanvas}
              title="Clear canvas"
            >
              <RotateCcw className="h-4 w-4" />
            </Button>

            <Button
              variant="ghost"
              size="sm"
              className="h-8 gap-1 px-2"
              onClick={importCanvas}
              title="Import diagram"
            >
              <Upload className="h-4 w-4" />
              <span className="text-xs hidden sm:inline">Import</span>
            </Button>

            <div className="relative" ref={exportMenuRef}>
              <Button
                variant="ghost"
                size="sm"
                className="h-8 gap-1 px-2"
                onClick={() => setShowExportMenu(!showExportMenu)}
                disabled={isExporting}
                title="Export diagram"
              >
                <Download className="h-4 w-4" />
                <span className="text-xs hidden sm:inline">Export</span>
                <ChevronDown className="h-3 w-3" />
              </Button>
              {showExportMenu && (
                <div className="absolute top-full right-0 mt-1 bg-popover border rounded-lg shadow-lg z-20 min-w-[180px] py-1">
                  <div className="px-3 py-1.5 text-xs font-medium text-muted-foreground border-b mb-1">
                    Export As
                  </div>
                  {EXPORT_FORMATS.map((format) => {
                    const Icon = getFormatIcon(format.id)
                    return (
                      <button
                        key={format.id}
                        className="w-full flex items-center gap-2 px-3 py-2 text-sm hover:bg-muted transition-colors text-left"
                        onClick={() => handleExport(format.id)}
                      >
                        <Icon className="h-4 w-4 text-muted-foreground" />
                        <span>{format.label}</span>
                        <span className="ml-auto text-xs text-muted-foreground">{format.extension}</span>
                      </button>
                    )
                  })}
                </div>
              )}
            </div>

            {hasSelection && (
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                onClick={() => {
                  setElements(elements.filter((el) => !selectedIds.has(el.id)))
                  clearSelection()
                }}
                title="Delete selected"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            )}

            <div className="w-px h-4 bg-border mx-1" />

            <Button
              variant="ghost"
              size="sm"
              className="h-8 w-8 p-0"
              onClick={() => setShowKeyboardShortcuts(true)}
              title="Keyboard shortcuts (?)"
            >
              <HelpCircle className="h-4 w-4" />
            </Button>
          </div>
        </div>
      )}

      {/* Canvas container with zoom controls */}
      <div className="relative" ref={containerRef}>
        {/* Zoom controls overlay */}
        {!readOnly && (
          <div className="absolute top-2 right-2 z-10">
            <ZoomControls
              zoomPercentage={zoomPercentage}
              onZoomIn={zoomIn}
              onZoomOut={zoomOut}
              onReset={resetView}
              onFitContent={() => fitToContent(elements)}
            />
          </div>
        )}

        {/* Canvas */}
        <svg
          ref={svgRef}
          className={cn(
            "w-full bg-white dark:bg-slate-950",
            spacePressed && "cursor-grab",
            isPanning && "cursor-grabbing"
          )}
          style={{ height: "500px" }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          role="img"
          aria-label={`System design diagram with ${elements.length} elements${hasSelection ? `, ${selectionCount} selected` : ""}`}
          tabIndex={0}
        >
          <g transform={`translate(${viewport.translateX}, ${viewport.translateY}) scale(${viewport.scale})`}>
            {/* Grid */}
            <CanvasGrid />

            {/* Connection points on hover during arrow drawing */}
            {showConnectionPoints && sortedElements.map(el => (
              <ConnectionPoints
                key={`cp-${el.id}`}
                element={el}
                activePoint={activeConnectionPoint || undefined}
                visible={el.type !== 'arrow'}
              />
            ))}

            {/* Render elements */}
            {sortedElements.map((element) => renderElement(element))}

            {/* Temp element while drawing */}
            {tempElement && renderElement(tempElement, true)}

            {/* Marquee selection rectangle */}
            <MarqueeSelection marquee={marquee} />
          </g>
        </svg>

        {/* Text input overlay */}
        {editingId && (
          <div
            className="absolute bg-white dark:bg-slate-900 border rounded shadow-lg p-2"
            style={{
              left: (elements.find((el) => el.id === editingId)?.x ?? 0) * viewport.scale + viewport.translateX,
              top: ((elements.find((el) => el.id === editingId)?.y ?? 0) - 40) * viewport.scale + viewport.translateY,
            }}
          >
            <input
              type="text"
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  handleTextSubmit()
                }
                if (e.key === "Escape") {
                  setEditingId(null)
                  setTextInput("")
                }
              }}
              onBlur={handleTextSubmit}
              className="px-2 py-1 border rounded text-sm w-32"
              autoFocus
            />
          </div>
        )}
      </div>

      {/* Error message */}
      {importError && (
        <div className="px-3 py-2 bg-red-50 dark:bg-red-950 border-t border-red-200 dark:border-red-800 text-xs text-red-600 dark:text-red-400 flex items-center justify-between">
          <span>{importError}</span>
          <button onClick={() => setImportError(null)} className="text-red-500 hover:text-red-700">
            ✕
          </button>
        </div>
      )}

      {/* Status bar */}
      <div className="px-3 py-2 bg-muted/30 border-t text-xs text-muted-foreground flex flex-wrap justify-between gap-2">
        {readOnly ? (
          <span>View only mode</span>
        ) : (
          <>
            <span>
              {selectionCount > 0 ? `${selectionCount} selected` : 'Click to select'} •
              Shift+click for multi-select •
              Double-click to edit •
              Press ? for shortcuts
            </span>
            <span className="text-muted-foreground/70">
              {snapEnabled ? 'Snap: ON' : 'Snap: OFF'} • Zoom: {zoomPercentage}%
            </span>
          </>
        )}
      </div>

      {/* Keyboard shortcuts modal */}
      <KeyboardShortcutsModal
        isOpen={showKeyboardShortcuts}
        onClose={() => setShowKeyboardShortcuts(false)}
      />
    </div>
  )
}
