/**
 * Design Canvas Component
 * An Excalidraw-like drawing canvas for system design diagrams
 */

import { useState, useRef, useCallback, useEffect } from "react"
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
} from "lucide-react"
import { useHistory } from "@/hooks/useHistory"
import { Button } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  exportCanvas,
  EXPORT_FORMATS,
  IMPORT_FORMATS,
  type ExportFormat,
} from "@/lib/canvasExport"

// Types
type Tool = "select" | "rectangle" | "ellipse" | "arrow" | "text" | "database" | "server" | "cloud" | "user" | "globe" | "cache" | "load_balancer" | "queue" | "blob_storage" | "dns" | "client" | "api_gateway"

interface Point {
  x: number
  y: number
}

interface BaseElement {
  id: string
  type: string
  x: number
  y: number
  width: number
  height: number
  fill: string
  stroke: string
  strokeWidth: number
  text?: string
  selected?: boolean
}

interface RectangleElement extends BaseElement {
  type: "rectangle"
  cornerRadius: number
}

interface EllipseElement extends BaseElement {
  type: "ellipse"
}

interface ArrowElement extends BaseElement {
  type: "arrow"
  endX: number
  endY: number
}

interface TextElement extends BaseElement {
  type: "text"
  fontSize: number
}

interface IconElement extends BaseElement {
  type: "database" | "server" | "cloud" | "user" | "globe" | "cache" | "load_balancer" | "queue" | "blob_storage" | "dns" | "client" | "api_gateway"
  label?: string
}

type CanvasElement = RectangleElement | EllipseElement | ArrowElement | TextElement | IconElement

// Color palette
const colors = [
  { name: "Black", value: "#1a1a1a" },
  { name: "Blue", value: "#3b82f6" },
  { name: "Green", value: "#22c55e" },
  { name: "Red", value: "#ef4444" },
  { name: "Yellow", value: "#eab308" },
  { name: "Purple", value: "#a855f7" },
  { name: "Orange", value: "#f97316" },
  { name: "Cyan", value: "#06b6d4" },
]

const fillColors = [
  { name: "None", value: "transparent" },
  { name: "Light Blue", value: "#dbeafe" },
  { name: "Light Green", value: "#dcfce7" },
  { name: "Light Yellow", value: "#fef9c3" },
  { name: "Light Purple", value: "#f3e8ff" },
  { name: "Light Orange", value: "#ffedd5" },
  { name: "Light Gray", value: "#f3f4f6" },
  { name: "White", value: "#ffffff" },
]

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
  // Use history hook for undo/redo support
  const {
    state: elements,
    setState: setElements,
    undo,
    redo,
    canUndo,
    canRedo,
  } = useHistory<CanvasElement[]>([])
  const [selectedTool, setSelectedTool] = useState<Tool>("select")
  const [selectedElement, setSelectedElement] = useState<string | null>(null)
  const [strokeColor, setStrokeColor] = useState("#1a1a1a")
  const [fillColor, setFillColor] = useState("transparent")
  const [isDrawing, setIsDrawing] = useState(false)
  const [drawStart, setDrawStart] = useState<Point | null>(null)
  const [tempElement, setTempElement] = useState<CanvasElement | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [dragStart, setDragStart] = useState<Point | null>(null)
  const [showColorPicker, setShowColorPicker] = useState<"stroke" | "fill" | null>(null)
  const [editingText, setEditingText] = useState<string | null>(null)
  const [textInput, setTextInput] = useState("")
  const [showExportMenu, setShowExportMenu] = useState(false)
  const [isExporting, setIsExporting] = useState(false)
  const svgRef = useRef<SVGSVGElement>(null)
  const exportMenuRef = useRef<HTMLDivElement>(null)

  // Load from value - only on initial mount or when value changes externally
  useEffect(() => {
    if (value) {
      try {
        const parsed = JSON.parse(value)
        if (Array.isArray(parsed.elements)) {
          // Skip history when loading initial/external value
          setElements(parsed.elements, { skipHistory: true })
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

  // Close export menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (exportMenuRef.current && !exportMenuRef.current.contains(event.target as Node)) {
        setShowExportMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const generateId = () => Math.random().toString(36).substring(2, 11)

  const getMousePosition = (e: React.MouseEvent): Point => {
    if (!svgRef.current) return { x: 0, y: 0 }
    const rect = svgRef.current.getBoundingClientRect()
    return {
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
    }
  }

  const handleMouseDown = (e: React.MouseEvent) => {
    if (readOnly) return
    const pos = getMousePosition(e)

    if (selectedTool === "select") {
      // Check if clicking on an element
      const clickedElement = [...elements].reverse().find((el) => {
        if (el.type === "arrow") {
          // Simple hit test for arrows
          const arrow = el as ArrowElement
          const midX = (el.x + arrow.endX) / 2
          const midY = (el.y + arrow.endY) / 2
          return Math.abs(pos.x - midX) < 20 && Math.abs(pos.y - midY) < 20
        }
        return (
          pos.x >= el.x &&
          pos.x <= el.x + el.width &&
          pos.y >= el.y &&
          pos.y <= el.y + el.height
        )
      })

      if (clickedElement) {
        setSelectedElement(clickedElement.id)
        setIsDragging(true)
        setDragStart(pos)
      } else {
        setSelectedElement(null)
      }
    } else if (selectedTool === "text") {
      // Create text element at click position
      const newElement: TextElement = {
        id: generateId(),
        type: "text",
        x: pos.x,
        y: pos.y,
        width: 100,
        height: 24,
        fill: strokeColor,
        stroke: "transparent",
        strokeWidth: 0,
        text: "Text",
        fontSize: 16,
      }
      setElements([...elements, newElement])
      setEditingText(newElement.id)
      setTextInput("Text")
    } else if (["database", "server", "cloud", "user", "globe", "cache", "load_balancer", "queue", "blob_storage", "dns", "client", "api_gateway"].includes(selectedTool)) {
      // Create icon element
      const labelMap: Record<string, string> = {
        database: "Database",
        server: "Server",
        cloud: "Cloud",
        user: "User",
        globe: "Internet",
        cache: "Cache",
        load_balancer: "Load Balancer",
        queue: "Queue",
        blob_storage: "Blob Storage",
        dns: "DNS",
        client: "Client",
        api_gateway: "API Gateway",
      }
      const newElement: IconElement = {
        id: generateId(),
        type: selectedTool as IconElement["type"],
        x: pos.x - 30,
        y: pos.y - 30,
        width: 60,
        height: 60,
        fill: fillColor,
        stroke: strokeColor,
        strokeWidth: 2,
        label: labelMap[selectedTool] || selectedTool,
      }
      setElements([...elements, newElement])
      setSelectedElement(newElement.id)
      setSelectedTool("select")
    } else {
      setIsDrawing(true)
      setDrawStart(pos)
    }
  }

  const handleMouseMove = (e: React.MouseEvent) => {
    if (readOnly) return
    const pos = getMousePosition(e)

    if (isDragging && selectedElement && dragStart) {
      const dx = pos.x - dragStart.x
      const dy = pos.y - dragStart.y

      setElements(
        elements.map((el) => {
          if (el.id === selectedElement) {
            if (el.type === "arrow") {
              const arrow = el as ArrowElement
              return {
                ...arrow,
                x: arrow.x + dx,
                y: arrow.y + dy,
                endX: arrow.endX + dx,
                endY: arrow.endY + dy,
              }
            }
            return { ...el, x: el.x + dx, y: el.y + dy }
          }
          return el
        })
      )
      setDragStart(pos)
    }

    if (isDrawing && drawStart) {
      const width = pos.x - drawStart.x
      const height = pos.y - drawStart.y

      if (selectedTool === "rectangle") {
        setTempElement({
          id: "temp",
          type: "rectangle",
          x: width > 0 ? drawStart.x : pos.x,
          y: height > 0 ? drawStart.y : pos.y,
          width: Math.abs(width),
          height: Math.abs(height),
          fill: fillColor,
          stroke: strokeColor,
          strokeWidth: 2,
          cornerRadius: 4,
        })
      } else if (selectedTool === "ellipse") {
        setTempElement({
          id: "temp",
          type: "ellipse",
          x: width > 0 ? drawStart.x : pos.x,
          y: height > 0 ? drawStart.y : pos.y,
          width: Math.abs(width),
          height: Math.abs(height),
          fill: fillColor,
          stroke: strokeColor,
          strokeWidth: 2,
        })
      } else if (selectedTool === "arrow") {
        setTempElement({
          id: "temp",
          type: "arrow",
          x: drawStart.x,
          y: drawStart.y,
          width: 0,
          height: 0,
          endX: pos.x,
          endY: pos.y,
          fill: "transparent",
          stroke: strokeColor,
          strokeWidth: 2,
        })
      }
    }
  }

  const handleMouseUp = () => {
    if (readOnly) return

    if (isDrawing && tempElement && tempElement.id === "temp") {
      const newElement = { ...tempElement, id: generateId() }
      setElements([...elements, newElement])
      setSelectedElement(newElement.id)
    }

    setIsDrawing(false)
    setDrawStart(null)
    setTempElement(null)
    setIsDragging(false)
    setDragStart(null)
  }

  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (readOnly) return

      // Undo: Ctrl+Z (or Cmd+Z on Mac)
      if ((e.ctrlKey || e.metaKey) && e.key === "z" && !e.shiftKey) {
        e.preventDefault()
        undo()
        return
      }

      // Redo: Ctrl+Y or Ctrl+Shift+Z (or Cmd+Y / Cmd+Shift+Z on Mac)
      if ((e.ctrlKey || e.metaKey) && (e.key === "y" || (e.key === "z" && e.shiftKey))) {
        e.preventDefault()
        redo()
        return
      }

      if (e.key === "Delete" || e.key === "Backspace") {
        if (selectedElement && !editingText) {
          setElements(elements.filter((el) => el.id !== selectedElement))
          setSelectedElement(null)
        }
      }
      if (e.key === "Escape") {
        setSelectedElement(null)
        setEditingText(null)
        setSelectedTool("select")
      }
    },
    [elements, selectedElement, editingText, readOnly, undo, redo, setElements]
  )

  useEffect(() => {
    window.addEventListener("keydown", handleKeyDown)
    return () => window.removeEventListener("keydown", handleKeyDown)
  }, [handleKeyDown])

  const handleDoubleClick = (elementId: string) => {
    if (readOnly) return
    const element = elements.find((el) => el.id === elementId)
    if (element && (element.type === "text" || ["database", "server", "cloud", "user", "globe", "cache", "load_balancer", "queue", "blob_storage", "dns", "client", "api_gateway"].includes(element.type))) {
      setEditingText(elementId)
      setTextInput((element as TextElement | IconElement).text || (element as IconElement).label || "")
    }
  }

  const handleTextSubmit = () => {
    if (editingText) {
      setElements(
        elements.map((el) => {
          if (el.id === editingText) {
            if (el.type === "text") {
              return { ...el, text: textInput }
            } else {
              return { ...el, label: textInput }
            }
          }
          return el
        })
      )
      setEditingText(null)
      setTextInput("")
    }
  }

  const clearCanvas = () => {
    if (!readOnly) {
      setElements([])
      setSelectedElement(null)
    }
  }

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

  const getFormatIcon = (format: ExportFormat) => {
    switch (format) {
      case 'json':
        return FileJson
      case 'svg':
        return FileImage
      case 'png':
      case 'jpg':
        return Image
      default:
        return Download
    }
  }

  const importCanvas = () => {
    const input = document.createElement("input")
    input.type = "file"
    input.accept = ".json"
    input.onchange = (e) => {
      const file = (e.target as HTMLInputElement).files?.[0]
      if (file) {
        const reader = new FileReader()
        reader.onload = (e) => {
          try {
            const data = JSON.parse(e.target?.result as string)
            if (Array.isArray(data.elements)) {
              setElements(data.elements)
            }
          } catch (err) {
            console.error("Failed to import:", err)
          }
        }
        reader.readAsText(file)
      }
    }
    input.click()
  }

  const renderElement = (element: CanvasElement, isTemp = false) => {
    const isSelected = element.id === selectedElement && !isTemp

    const commonProps = {
      key: element.id,
      onClick: (e: React.MouseEvent) => {
        e.stopPropagation()
        if (!readOnly && selectedTool === "select") {
          setSelectedElement(element.id)
        }
      },
      onDoubleClick: () => handleDoubleClick(element.id),
      style: { cursor: readOnly ? "default" : "move" },
    }

    switch (element.type) {
      case "rectangle":
        return (
          <g {...commonProps}>
            <rect
              x={element.x}
              y={element.y}
              width={element.width}
              height={element.height}
              rx={(element as RectangleElement).cornerRadius}
              fill={element.fill}
              stroke={isSelected ? "#3b82f6" : element.stroke}
              strokeWidth={isSelected ? 3 : element.strokeWidth}
              strokeDasharray={isTemp ? "5,5" : undefined}
            />
            {isSelected && (
              <>
                <rect x={element.x - 4} y={element.y - 4} width={8} height={8} fill="#3b82f6" />
                <rect x={element.x + element.width - 4} y={element.y - 4} width={8} height={8} fill="#3b82f6" />
                <rect x={element.x - 4} y={element.y + element.height - 4} width={8} height={8} fill="#3b82f6" />
                <rect x={element.x + element.width - 4} y={element.y + element.height - 4} width={8} height={8} fill="#3b82f6" />
              </>
            )}
          </g>
        )

      case "ellipse":
        return (
          <g {...commonProps}>
            <ellipse
              cx={element.x + element.width / 2}
              cy={element.y + element.height / 2}
              rx={element.width / 2}
              ry={element.height / 2}
              fill={element.fill}
              stroke={isSelected ? "#3b82f6" : element.stroke}
              strokeWidth={isSelected ? 3 : element.strokeWidth}
              strokeDasharray={isTemp ? "5,5" : undefined}
            />
          </g>
        )

      case "arrow": {
        const arrow = element as ArrowElement
        const angle = Math.atan2(arrow.endY - arrow.y, arrow.endX - arrow.x)
        const arrowLength = 12
        const arrowAngle = Math.PI / 6

        const arrowPoint1X = arrow.endX - arrowLength * Math.cos(angle - arrowAngle)
        const arrowPoint1Y = arrow.endY - arrowLength * Math.sin(angle - arrowAngle)
        const arrowPoint2X = arrow.endX - arrowLength * Math.cos(angle + arrowAngle)
        const arrowPoint2Y = arrow.endY - arrowLength * Math.sin(angle + arrowAngle)

        return (
          <g {...commonProps}>
            <line
              x1={arrow.x}
              y1={arrow.y}
              x2={arrow.endX}
              y2={arrow.endY}
              stroke={isSelected ? "#3b82f6" : element.stroke}
              strokeWidth={isSelected ? 3 : element.strokeWidth}
              strokeDasharray={isTemp ? "5,5" : undefined}
            />
            <polygon
              points={`${arrow.endX},${arrow.endY} ${arrowPoint1X},${arrowPoint1Y} ${arrowPoint2X},${arrowPoint2Y}`}
              fill={isSelected ? "#3b82f6" : element.stroke}
            />
          </g>
        )
      }

      case "text": {
        const textEl = element as TextElement
        return (
          <g {...commonProps}>
            {isSelected && (
              <rect
                x={element.x - 4}
                y={element.y - textEl.fontSize - 4}
                width={element.width + 8}
                height={textEl.fontSize + 8}
                fill="transparent"
                stroke="#3b82f6"
                strokeWidth={2}
                strokeDasharray="4,4"
              />
            )}
            <text
              x={element.x}
              y={element.y}
              fill={element.fill}
              fontSize={textEl.fontSize}
              fontFamily="system-ui, sans-serif"
            >
              {textEl.text}
            </text>
          </g>
        )
      }

      case "database":
      case "server":
      case "cloud":
      case "user":
      case "globe":
      case "cache":
      case "load_balancer":
      case "queue":
      case "blob_storage":
      case "dns":
      case "client":
      case "api_gateway": {
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
              stroke={isSelected ? "#3b82f6" : element.stroke}
              strokeWidth={isSelected ? 3 : element.strokeWidth}
            />
            {/* Icon representation using simple shapes */}
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
                d={`M ${centerX - 15} ${element.y + 28}
                   a 10 10 0 0 1 0 -14
                   a 12 12 0 0 1 20 -4
                   a 10 10 0 0 1 10 14 z`}
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
            {/* Cache - cylinder with lightning bolt */}
            {element.type === "cache" && (
              <>
                <ellipse cx={centerX} cy={element.y + 12} rx={14} ry={5} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                <path d={`M ${centerX - 14} ${element.y + 12} v 18 a 14 5 0 0 0 28 0 v -18`} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                <path d={`M ${centerX + 2} ${element.y + 18} l -6 8 h 5 l -4 8`} fill="none" stroke={element.stroke} strokeWidth={1.5} />
              </>
            )}
            {/* Load Balancer - scale with arrows */}
            {element.type === "load_balancer" && (
              <>
                <circle cx={centerX} cy={element.y + 20} r={12} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                <line x1={centerX - 8} y1={element.y + 20} x2={centerX + 8} y2={element.y + 20} stroke={element.stroke} strokeWidth={1.5} />
                <line x1={centerX} y1={element.y + 12} x2={centerX} y2={element.y + 28} stroke={element.stroke} strokeWidth={1.5} />
                <path d={`M ${centerX - 5} ${element.y + 14} l 5 -4 l 5 4`} fill="none" stroke={element.stroke} strokeWidth={1} />
                <path d={`M ${centerX - 5} ${element.y + 26} l 5 4 l 5 -4`} fill="none" stroke={element.stroke} strokeWidth={1} />
              </>
            )}
            {/* Queue - horizontal bars with arrow */}
            {element.type === "queue" && (
              <>
                <rect x={centerX - 16} y={element.y + 12} width={32} height={6} rx={1} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                <rect x={centerX - 16} y={element.y + 21} width={32} height={6} rx={1} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                <rect x={centerX - 16} y={element.y + 30} width={32} height={6} rx={1} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                <path d={`M ${centerX + 20} ${element.y + 24} l 6 0 l -2 -3 m 2 3 l -2 3`} fill="none" stroke={element.stroke} strokeWidth={1} />
              </>
            )}
            {/* Blob Storage - folder with cloud */}
            {element.type === "blob_storage" && (
              <>
                <rect x={centerX - 14} y={element.y + 14} width={28} height={22} rx={2} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                <path d={`M ${centerX - 14} ${element.y + 18} h 10 l 4 -4 h 14`} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                <circle cx={centerX - 4} cy={element.y + 26} r={4} fill="none" stroke={element.stroke} strokeWidth={1} />
                <circle cx={centerX + 4} cy={element.y + 28} r={3} fill="none" stroke={element.stroke} strokeWidth={1} />
              </>
            )}
            {/* DNS - network nodes */}
            {element.type === "dns" && (
              <>
                <circle cx={centerX} cy={element.y + 14} r={6} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                <circle cx={centerX - 12} cy={element.y + 32} r={5} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                <circle cx={centerX + 12} cy={element.y + 32} r={5} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                <line x1={centerX - 4} y1={element.y + 18} x2={centerX - 10} y2={element.y + 28} stroke={element.stroke} strokeWidth={1} />
                <line x1={centerX + 4} y1={element.y + 18} x2={centerX + 10} y2={element.y + 28} stroke={element.stroke} strokeWidth={1} />
                <text x={centerX} y={element.y + 17} fill={element.stroke} fontSize={6} textAnchor="middle" fontFamily="system-ui">@</text>
              </>
            )}
            {/* Client - monitor/laptop */}
            {element.type === "client" && (
              <>
                <rect x={centerX - 14} y={element.y + 10} width={28} height={18} rx={2} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                <line x1={centerX - 10} y1={element.y + 28} x2={centerX + 10} y2={element.y + 28} stroke={element.stroke} strokeWidth={1.5} />
                <rect x={centerX - 18} y={element.y + 32} width={36} height={4} rx={1} fill="none" stroke={element.stroke} strokeWidth={1.5} />
              </>
            )}
            {/* API Gateway - layered rectangles with arrows */}
            {element.type === "api_gateway" && (
              <>
                <rect x={centerX - 12} y={element.y + 10} width={24} height={28} rx={3} fill="none" stroke={element.stroke} strokeWidth={1.5} />
                <line x1={centerX - 8} y1={element.y + 18} x2={centerX + 8} y2={element.y + 18} stroke={element.stroke} strokeWidth={1} />
                <line x1={centerX - 8} y1={element.y + 24} x2={centerX + 8} y2={element.y + 24} stroke={element.stroke} strokeWidth={1} />
                <line x1={centerX - 8} y1={element.y + 30} x2={centerX + 8} y2={element.y + 30} stroke={element.stroke} strokeWidth={1} />
                <path d={`M ${centerX - 18} ${element.y + 24} l -4 0`} stroke={element.stroke} strokeWidth={1} />
                <path d={`M ${centerX + 18} ${element.y + 18} l 4 0`} stroke={element.stroke} strokeWidth={1} />
                <path d={`M ${centerX + 18} ${element.y + 24} l 4 0`} stroke={element.stroke} strokeWidth={1} />
                <path d={`M ${centerX + 18} ${element.y + 30} l 4 0`} stroke={element.stroke} strokeWidth={1} />
              </>
            )}
            {/* Label */}
            <text
              x={centerX}
              y={element.y + element.height - 5}
              fill={element.stroke}
              fontSize={10}
              textAnchor="middle"
              fontFamily="system-ui, sans-serif"
            >
              {iconEl.label}
            </text>
          </g>
        )
      }

      default:
        return null
    }
  }

  // Basic drawing tools
  const drawingTools: { id: Tool; icon: React.ElementType; label: string }[] = [
    { id: "select", icon: MousePointer, label: "Select" },
    { id: "rectangle", icon: Square, label: "Rectangle" },
    { id: "ellipse", icon: Circle, label: "Ellipse" },
    { id: "arrow", icon: ArrowRight, label: "Arrow" },
    { id: "text", icon: Type, label: "Text" },
  ]

  // System design component icons
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
            {/* Separator */}
            <div className="w-px h-6 bg-border mx-1" />
            {/* System Design Components */}
            {componentTools.map((tool) => {
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
          </div>

          {/* Color pickers */}
          <div className="flex items-center gap-2">
            <div className="relative">
              <Button
                variant="ghost"
                size="sm"
                className="h-8 gap-1.5"
                onClick={() => setShowColorPicker(showColorPicker === "stroke" ? null : "stroke")}
              >
                <div
                  className="w-4 h-4 rounded border"
                  style={{ backgroundColor: strokeColor }}
                />
                <span className="text-xs">Stroke</span>
              </Button>
              {showColorPicker === "stroke" && (
                <div className="absolute top-full left-0 mt-1 p-2 bg-popover border rounded-lg shadow-lg z-10 grid grid-cols-4 gap-1">
                  {colors.map((color) => (
                    <button
                      key={color.value}
                      className={cn(
                        "w-6 h-6 rounded border-2",
                        strokeColor === color.value ? "border-primary" : "border-transparent"
                      )}
                      style={{ backgroundColor: color.value }}
                      onClick={() => {
                        setStrokeColor(color.value)
                        setShowColorPicker(null)
                      }}
                      title={color.name}
                    />
                  ))}
                </div>
              )}
            </div>

            <div className="relative">
              <Button
                variant="ghost"
                size="sm"
                className="h-8 gap-1.5"
                onClick={() => setShowColorPicker(showColorPicker === "fill" ? null : "fill")}
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
              {showColorPicker === "fill" && (
                <div className="absolute top-full left-0 mt-1 p-2 bg-popover border rounded-lg shadow-lg z-10 grid grid-cols-4 gap-1">
                  {fillColors.map((color) => (
                    <button
                      key={color.value}
                      className={cn(
                        "w-6 h-6 rounded border-2",
                        fillColor === color.value ? "border-primary" : "border-transparent"
                      )}
                      style={{
                        backgroundColor: color.value === "transparent" ? "white" : color.value,
                        backgroundImage: color.value === "transparent"
                          ? "linear-gradient(45deg, #ccc 25%, transparent 25%, transparent 75%, #ccc 75%), linear-gradient(45deg, #ccc 25%, transparent 25%, transparent 75%, #ccc 75%)"
                          : undefined,
                        backgroundSize: "4px 4px",
                        backgroundPosition: "0 0, 2px 2px",
                      }}
                      onClick={() => {
                        setFillColor(color.value)
                        setShowColorPicker(null)
                      }}
                      title={color.name}
                    />
                  ))}
                </div>
              )}
            </div>
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
              aria-label="Undo"
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
              aria-label="Redo"
            >
              <Redo2 className="h-4 w-4" />
            </Button>
            <div className="w-px h-4 bg-border mx-1" />
            <Button variant="ghost" size="sm" className="h-8 w-8 p-0" onClick={clearCanvas} title="Clear canvas">
              <RotateCcw className="h-4 w-4" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              className="h-8 gap-1 px-2"
              onClick={importCanvas}
              title={`Import diagram (${IMPORT_FORMATS.map(f => f.extension).join(', ')})`}
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
            {selectedElement && (
              <Button
                variant="ghost"
                size="sm"
                className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                onClick={() => {
                  setElements(elements.filter((el) => el.id !== selectedElement))
                  setSelectedElement(null)
                }}
                title="Delete"
              >
                <Trash2 className="h-4 w-4" />
              </Button>
            )}
          </div>
        </div>
      )}

      {/* Canvas */}
      <div className="relative">
        <svg
          ref={svgRef}
          className="w-full bg-white dark:bg-slate-950"
          style={{ height: "500px" }}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
        >
          {/* Grid pattern */}
          <defs>
            <pattern id="grid" width="20" height="20" patternUnits="userSpaceOnUse">
              <path
                d="M 20 0 L 0 0 0 20"
                fill="none"
                stroke="currentColor"
                strokeWidth="0.5"
                className="text-muted-foreground/20"
              />
            </pattern>
          </defs>
          <rect width="100%" height="100%" fill="url(#grid)" />

          {/* Render elements */}
          {elements.map((element) => renderElement(element))}

          {/* Render temp element while drawing */}
          {tempElement && renderElement(tempElement, true)}
        </svg>

        {/* Text input overlay */}
        {editingText && (
          <div
            className="absolute bg-white dark:bg-slate-900 border rounded shadow-lg p-2"
            style={{
              left: elements.find((el) => el.id === editingText)?.x || 0,
              top: (elements.find((el) => el.id === editingText)?.y || 0) - 40,
            }}
          >
            <input
              type="text"
              value={textInput}
              onChange={(e) => setTextInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleTextSubmit()
                if (e.key === "Escape") {
                  setEditingText(null)
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

      {/* Help text */}
      <div className="px-3 py-2 bg-muted/30 border-t text-xs text-muted-foreground flex flex-wrap justify-between gap-2">
        {readOnly ? (
          <span>View only mode</span>
        ) : (
          <>
            <span>
              Click to select • Drag to move • Double-click to edit text • Delete/Backspace to remove •
              Ctrl+Z to undo • Ctrl+Y to redo
            </span>
            <span className="text-muted-foreground/70">
              Export: PNG, JPG, SVG, JSON • Import: JSON
            </span>
          </>
        )}
      </div>
    </div>
  )
}
