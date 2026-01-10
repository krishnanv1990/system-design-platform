/**
 * Canvas Configuration
 * Constants and configuration for the DesignCanvas component
 */

export const CANVAS_CONFIG = {
  // Grid
  GRID_SIZE: 20,
  GRID_COLOR: '#e5e5e5',

  // Selection
  HANDLE_SIZE: 8,
  HANDLE_COLOR: '#3b82f6',
  SELECTION_STROKE: '#3b82f6',
  SELECTION_STROKE_WIDTH: 2,

  // Snap
  SNAP_THRESHOLD: 8,
  SNAP_ENABLED_DEFAULT: true,

  // Zoom
  MIN_ZOOM: 0.1,
  MAX_ZOOM: 4,
  ZOOM_STEP: 0.1,

  // Arrow
  ARROW_HEAD_SIZE: 12,
  ARROW_HEAD_ANGLE: Math.PI / 6,
  CONNECTION_SNAP_DISTANCE: 15,

  // Text
  DEFAULT_FONT_SIZE: 16,
  DEFAULT_FONT_FAMILY: 'system-ui, sans-serif',
  MIN_FONT_SIZE: 8,
  MAX_FONT_SIZE: 72,

  // History
  MAX_HISTORY_LENGTH: 50,
  HISTORY_DEBOUNCE_MS: 300,

  // Colors
  DEFAULT_STROKE_COLOR: '#1a1a1a',
  DEFAULT_FILL_COLOR: 'transparent',

  // Sizes
  MIN_ELEMENT_SIZE: 20,
  DEFAULT_ELEMENT_WIDTH: 100,
  DEFAULT_ELEMENT_HEIGHT: 60,
  DEFAULT_ICON_SIZE: 60,

  // Canvas
  DEFAULT_CANVAS_WIDTH: 800,
  DEFAULT_CANVAS_HEIGHT: 500,
  CANVAS_PADDING: 100,

  // Cursor
  CURSORS: {
    nw: 'nw-resize',
    n: 'n-resize',
    ne: 'ne-resize',
    e: 'e-resize',
    se: 'se-resize',
    s: 's-resize',
    sw: 'sw-resize',
    w: 'w-resize',
  } as const,

  // Line styles
  LINE_STYLES: {
    solid: [],
    dashed: [8, 4],
    dotted: [2, 4],
  } as const,

  // Z-Index
  DEFAULT_Z_INDEX: 0,
} as const

// Color palettes
export const STROKE_COLORS = [
  { name: 'Black', value: '#1a1a1a' },
  { name: 'Blue', value: '#3b82f6' },
  { name: 'Green', value: '#22c55e' },
  { name: 'Red', value: '#ef4444' },
  { name: 'Yellow', value: '#eab308' },
  { name: 'Purple', value: '#a855f7' },
  { name: 'Orange', value: '#f97316' },
  { name: 'Cyan', value: '#06b6d4' },
] as const

export const FILL_COLORS = [
  { name: 'None', value: 'transparent' },
  { name: 'Light Blue', value: '#dbeafe' },
  { name: 'Light Green', value: '#dcfce7' },
  { name: 'Light Yellow', value: '#fef9c3' },
  { name: 'Light Purple', value: '#f3e8ff' },
  { name: 'Light Orange', value: '#ffedd5' },
  { name: 'Light Gray', value: '#f3f4f6' },
  { name: 'White', value: '#ffffff' },
] as const

// Icon label mappings
export const ICON_LABELS: Record<string, string> = {
  database: 'Database',
  server: 'Server',
  cloud: 'Cloud',
  user: 'User',
  globe: 'Internet',
  cache: 'Cache',
  load_balancer: 'Load Balancer',
  queue: 'Queue',
  blob_storage: 'Blob Storage',
  dns: 'DNS',
  client: 'Client',
  api_gateway: 'API Gateway',
} as const

// Keyboard shortcuts
export const KEYBOARD_SHORTCUTS = {
  DELETE: ['Delete', 'Backspace'],
  UNDO: { key: 'z', modifiers: ['ctrl', 'meta'] },
  REDO: { key: 'y', modifiers: ['ctrl', 'meta'] },
  REDO_ALT: { key: 'z', modifiers: ['ctrl+shift', 'meta+shift'] },
  COPY: { key: 'c', modifiers: ['ctrl', 'meta'] },
  PASTE: { key: 'v', modifiers: ['ctrl', 'meta'] },
  CUT: { key: 'x', modifiers: ['ctrl', 'meta'] },
  SELECT_ALL: { key: 'a', modifiers: ['ctrl', 'meta'] },
  ESCAPE: 'Escape',
  GROUP: { key: 'g', modifiers: ['ctrl', 'meta'] },
  UNGROUP: { key: 'g', modifiers: ['ctrl+shift', 'meta+shift'] },
  BRING_FRONT: { key: ']', modifiers: ['ctrl', 'meta'] },
  SEND_BACK: { key: '[', modifiers: ['ctrl', 'meta'] },
  DUPLICATE: { key: 'd', modifiers: ['ctrl', 'meta'] },
  HELP: '?',
} as const
