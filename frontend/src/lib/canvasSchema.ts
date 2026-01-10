/**
 * Canvas Schema Validation
 * Validates imported canvas data to prevent crashes
 */

import type { CanvasElement, CanvasExportData, ElementType } from '@/types/canvas'

// Valid element types
const VALID_ELEMENT_TYPES: ElementType[] = [
  'rectangle',
  'ellipse',
  'arrow',
  'text',
  'image',
  'database',
  'server',
  'cloud',
  'user',
  'globe',
  'cache',
  'load_balancer',
  'queue',
  'blob_storage',
  'dns',
  'client',
  'api_gateway',
  'diamond',
  'cylinder',
  'hexagon',
]

// Valid line styles
const VALID_LINE_STYLES = ['solid', 'dashed', 'dotted']

// Color regex (hex color)
const HEX_COLOR_REGEX = /^#[0-9a-fA-F]{6}$/

// Validation result
export interface ValidationResult {
  success: boolean
  data?: CanvasExportData
  errors: string[]
  warnings: string[]
}

/**
 * Check if a value is a valid number
 */
function isValidNumber(value: unknown): value is number {
  return typeof value === 'number' && !isNaN(value) && isFinite(value)
}

/**
 * Check if a value is a valid string
 */
function isValidString(value: unknown): value is string {
  return typeof value === 'string'
}

/**
 * Check if a value is a valid color (hex or 'transparent')
 */
function isValidColor(value: unknown): boolean {
  if (!isValidString(value)) return false
  return value === 'transparent' || HEX_COLOR_REGEX.test(value)
}

/**
 * Check if a value is a valid UUID-like string
 */
function isValidId(value: unknown): boolean {
  if (!isValidString(value)) return false
  return value.length > 0 && value.length <= 50
}

/**
 * Validate base element properties
 */
function validateBaseElement(
  element: Record<string, unknown>,
  errors: string[],
  index: number
): boolean {
  let valid = true

  // Required fields
  if (!isValidId(element.id)) {
    errors.push(`Element ${index}: Invalid or missing 'id'`)
    valid = false
  }

  if (!isValidString(element.type) || !VALID_ELEMENT_TYPES.includes(element.type as ElementType)) {
    errors.push(`Element ${index}: Invalid or missing 'type'. Got: ${element.type}`)
    valid = false
  }

  if (!isValidNumber(element.x)) {
    errors.push(`Element ${index}: Invalid or missing 'x' coordinate`)
    valid = false
  }

  if (!isValidNumber(element.y)) {
    errors.push(`Element ${index}: Invalid or missing 'y' coordinate`)
    valid = false
  }

  if (!isValidNumber(element.width) || (element.width as number) < 0) {
    errors.push(`Element ${index}: Invalid or missing 'width'`)
    valid = false
  }

  if (!isValidNumber(element.height) || (element.height as number) < 0) {
    errors.push(`Element ${index}: Invalid or missing 'height'`)
    valid = false
  }

  // Optional but should be valid if present
  if (element.fill !== undefined && !isValidColor(element.fill)) {
    errors.push(`Element ${index}: Invalid 'fill' color`)
    valid = false
  }

  if (element.stroke !== undefined && !isValidColor(element.stroke)) {
    errors.push(`Element ${index}: Invalid 'stroke' color`)
    valid = false
  }

  if (element.strokeWidth !== undefined && !isValidNumber(element.strokeWidth)) {
    errors.push(`Element ${index}: Invalid 'strokeWidth'`)
    valid = false
  }

  if (element.zIndex !== undefined && !isValidNumber(element.zIndex)) {
    errors.push(`Element ${index}: Invalid 'zIndex'`)
    valid = false
  }

  return valid
}

/**
 * Validate arrow element
 */
function validateArrowElement(
  element: Record<string, unknown>,
  errors: string[],
  index: number
): boolean {
  let valid = true

  if (!isValidNumber(element.endX)) {
    errors.push(`Element ${index} (arrow): Invalid or missing 'endX'`)
    valid = false
  }

  if (!isValidNumber(element.endY)) {
    errors.push(`Element ${index} (arrow): Invalid or missing 'endY'`)
    valid = false
  }

  if (element.lineStyle !== undefined) {
    if (!isValidString(element.lineStyle) || !VALID_LINE_STYLES.includes(element.lineStyle)) {
      errors.push(`Element ${index} (arrow): Invalid 'lineStyle'`)
      valid = false
    }
  }

  return valid
}

/**
 * Validate text element
 */
function validateTextElement(
  element: Record<string, unknown>,
  errors: string[],
  index: number
): boolean {
  let valid = true

  if (element.text !== undefined && !isValidString(element.text)) {
    errors.push(`Element ${index} (text): Invalid 'text'`)
    valid = false
  }

  if (element.fontSize !== undefined) {
    if (!isValidNumber(element.fontSize) || (element.fontSize as number) <= 0) {
      errors.push(`Element ${index} (text): Invalid 'fontSize'`)
      valid = false
    }
  }

  return valid
}

/**
 * Validate image element
 */
function validateImageElement(
  element: Record<string, unknown>,
  errors: string[],
  index: number
): boolean {
  let valid = true

  if (!isValidString(element.dataUrl)) {
    errors.push(`Element ${index} (image): Invalid or missing 'dataUrl'`)
    valid = false
  } else if (!(element.dataUrl as string).startsWith('data:')) {
    errors.push(`Element ${index} (image): 'dataUrl' must be a data URI`)
    valid = false
  }

  return valid
}

/**
 * Validate a single element
 */
function validateElement(
  element: unknown,
  errors: string[],
  warnings: string[],
  index: number
): CanvasElement | null {
  if (typeof element !== 'object' || element === null) {
    errors.push(`Element ${index}: Must be an object`)
    return null
  }

  const el = element as Record<string, unknown>

  // Validate base properties
  if (!validateBaseElement(el, errors, index)) {
    return null
  }

  // Type-specific validation
  switch (el.type) {
    case 'arrow':
      if (!validateArrowElement(el, errors, index)) {
        return null
      }
      break
    case 'text':
      if (!validateTextElement(el, errors, index)) {
        return null
      }
      break
    case 'image':
      if (!validateImageElement(el, errors, index)) {
        return null
      }
      break
  }

  // Set default values for missing optional fields
  const validated: CanvasElement = {
    ...(el as unknown as CanvasElement),
    fill: isValidColor(el.fill) ? (el.fill as string) : 'transparent',
    stroke: isValidColor(el.stroke) ? (el.stroke as string) : '#1a1a1a',
    strokeWidth: isValidNumber(el.strokeWidth) ? (el.strokeWidth as number) : 2,
    zIndex: isValidNumber(el.zIndex) ? (el.zIndex as number) : index,
  }

  // Add default lineStyle for arrows
  if (validated.type === 'arrow' && !validated.lineStyle) {
    (validated as unknown as Record<string, unknown>).lineStyle = 'solid'
  }

  return validated
}

/**
 * Validate canvas export data
 */
export function validateCanvasData(data: unknown): ValidationResult {
  const errors: string[] = []
  const warnings: string[] = []

  // Check if data is an object
  if (typeof data !== 'object' || data === null) {
    return {
      success: false,
      errors: ['Import data must be an object'],
      warnings: [],
    }
  }

  const obj = data as Record<string, unknown>

  // Check for elements array
  if (!Array.isArray(obj.elements)) {
    return {
      success: false,
      errors: ["Import data must have an 'elements' array"],
      warnings: [],
    }
  }

  // Validate version
  if (obj.version !== undefined && !isValidNumber(obj.version)) {
    warnings.push('Invalid version number, defaulting to 1')
  }

  // Validate each element
  const validatedElements: CanvasElement[] = []
  const seenIds = new Set<string>()

  for (let i = 0; i < obj.elements.length; i++) {
    const element = obj.elements[i]
    const validated = validateElement(element, errors, warnings, i)

    if (validated) {
      // Check for duplicate IDs
      if (seenIds.has(validated.id)) {
        warnings.push(`Element ${i}: Duplicate ID '${validated.id}', generating new ID`)
        validated.id = generateId()
      }
      seenIds.add(validated.id)
      validatedElements.push(validated)
    }
  }

  // If there are errors, return failure
  if (errors.length > 0) {
    return {
      success: false,
      errors,
      warnings,
    }
  }

  // Return success with validated data
  return {
    success: true,
    data: {
      version: isValidNumber(obj.version) ? (obj.version as number) : 1,
      elements: validatedElements,
      metadata: obj.metadata as CanvasExportData['metadata'],
    },
    errors: [],
    warnings,
  }
}

/**
 * Generate a unique ID
 */
function generateId(): string {
  return Math.random().toString(36).substring(2, 11)
}

/**
 * Parse and validate JSON string
 */
export function parseAndValidateCanvas(jsonString: string): ValidationResult {
  try {
    const data = JSON.parse(jsonString)
    return validateCanvasData(data)
  } catch (e) {
    return {
      success: false,
      errors: [`Invalid JSON: ${e instanceof Error ? e.message : 'Parse error'}`],
      warnings: [],
    }
  }
}

/**
 * Migrate older schema versions to current version
 */
export function migrateSchema(data: CanvasExportData): CanvasExportData {
  // Currently no migrations needed, but this is where we'd handle them
  return {
    ...data,
    version: 1,
  }
}
