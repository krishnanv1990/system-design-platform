/**
 * Canvas Types
 * Type definitions for the DesignCanvas component
 */

// Element Types
export type ElementType =
  | 'rectangle'
  | 'ellipse'
  | 'arrow'
  | 'text'
  | 'image'
  | 'database'
  | 'server'
  | 'cloud'
  | 'user'
  | 'globe'
  | 'cache'
  | 'load_balancer'
  | 'queue'
  | 'blob_storage'
  | 'dns'
  | 'client'
  | 'api_gateway'
  | 'diamond'
  | 'cylinder'
  | 'hexagon'

export type Tool =
  | 'select'
  | 'rectangle'
  | 'ellipse'
  | 'arrow'
  | 'text'
  | 'database'
  | 'server'
  | 'cloud'
  | 'user'
  | 'globe'
  | 'cache'
  | 'load_balancer'
  | 'queue'
  | 'blob_storage'
  | 'dns'
  | 'client'
  | 'api_gateway'
  | 'diamond'
  | 'cylinder'
  | 'hexagon'

export type HandlePosition = 'nw' | 'n' | 'ne' | 'e' | 'se' | 's' | 'sw' | 'w'

export type ConnectionPointPosition = 'top' | 'right' | 'bottom' | 'left'

export type LineStyle = 'solid' | 'dashed' | 'dotted'

// Point interface
export interface Point {
  x: number
  y: number
}

// Bounds interface
export interface Bounds {
  x: number
  y: number
  width: number
  height: number
}

// Connection reference for arrows connected to elements
export interface ConnectionRef {
  elementId: string
  point: ConnectionPointPosition
}

// Connection point on an element
export interface ConnectionPoint {
  id: string
  position: ConnectionPointPosition
  x: number
  y: number
}

// Base element interface
export interface BaseElement {
  id: string
  type: ElementType
  x: number
  y: number
  width: number
  height: number
  fill: string
  stroke: string
  strokeWidth: number
  zIndex: number
  locked?: boolean
  opacity?: number
}

// Rectangle element
export interface RectangleElement extends BaseElement {
  type: 'rectangle'
  cornerRadius: number
}

// Ellipse element
export interface EllipseElement extends BaseElement {
  type: 'ellipse'
}

// Diamond element
export interface DiamondElement extends BaseElement {
  type: 'diamond'
}

// Cylinder element (for databases)
export interface CylinderElement extends BaseElement {
  type: 'cylinder'
}

// Hexagon element
export interface HexagonElement extends BaseElement {
  type: 'hexagon'
}

// Arrow element with optional connections
export interface ArrowElement extends BaseElement {
  type: 'arrow'
  endX: number
  endY: number
  startConnection?: ConnectionRef
  endConnection?: ConnectionRef
  lineStyle: LineStyle
}

// Text element
export interface TextElement extends BaseElement {
  type: 'text'
  text: string
  fontSize: number
  fontFamily: string
  textAlign?: 'left' | 'center' | 'right'
}

// Image element
export interface ImageElement extends BaseElement {
  type: 'image'
  dataUrl: string
  originalWidth: number
  originalHeight: number
}

// Icon element types
export type IconType =
  | 'database'
  | 'server'
  | 'cloud'
  | 'user'
  | 'globe'
  | 'cache'
  | 'load_balancer'
  | 'queue'
  | 'blob_storage'
  | 'dns'
  | 'client'
  | 'api_gateway'

export interface IconElement extends BaseElement {
  type: IconType
  label?: string
}

// Union type for all canvas elements
export type CanvasElement =
  | RectangleElement
  | EllipseElement
  | DiamondElement
  | CylinderElement
  | HexagonElement
  | ArrowElement
  | TextElement
  | ImageElement
  | IconElement

// Selection state
export interface SelectionState {
  selectedIds: Set<string>
  editingId: string | null
}

// Resize state
export interface ResizeState {
  isResizing: boolean
  handle: HandlePosition | null
  startX: number
  startY: number
  startWidth: number
  startHeight: number
  startElementX: number
  startElementY: number
}

// Zoom/Pan state
export interface ViewportState {
  scale: number
  translateX: number
  translateY: number
}

// Marquee selection state
export interface MarqueeState {
  isSelecting: boolean
  startX: number
  startY: number
  endX: number
  endY: number
}

// Clipboard data
export interface ClipboardData {
  elements: CanvasElement[]
  bounds: Bounds
}

// Canvas export schema for validation
export interface CanvasExportData {
  version: number
  elements: CanvasElement[]
  metadata?: {
    createdAt?: string
    exportedAt?: string
    name?: string
  }
}

// Icon definitions for the palette
export interface IconDefinition {
  id: IconType
  label: string
  icon: React.ComponentType<{ className?: string }>
}

// Export options
export interface ExportOptions {
  format: 'json' | 'png' | 'jpg' | 'svg'
  filename?: string
  quality?: number
  scale?: number
  backgroundColor?: string
  transparent?: boolean
}
