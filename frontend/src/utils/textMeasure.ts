/**
 * Text Measurement Utilities
 * Functions for measuring text dimensions for accurate bounding boxes
 */

interface TextDimensions {
  width: number
  height: number
}

// Cache for canvas context
let measureCanvas: HTMLCanvasElement | null = null
let measureContext: CanvasRenderingContext2D | null = null

/**
 * Get or create a canvas context for text measurement
 */
function getMeasureContext(): CanvasRenderingContext2D | null {
  if (!measureContext) {
    measureCanvas = document.createElement('canvas')
    measureContext = measureCanvas.getContext('2d')
  }
  return measureContext
}

/**
 * Measure text dimensions using canvas
 */
export function measureText(
  text: string,
  fontSize: number,
  fontFamily: string = 'system-ui, sans-serif'
): TextDimensions {
  const ctx = getMeasureContext()

  if (!ctx) {
    // Fallback estimation if canvas context unavailable
    const avgCharWidth = fontSize * 0.6
    return {
      width: Math.max(text.length * avgCharWidth, 20),
      height: fontSize * 1.2,
    }
  }

  ctx.font = `${fontSize}px ${fontFamily}`
  const metrics = ctx.measureText(text)

  // Calculate height using font metrics when available, otherwise estimate
  const height = metrics.actualBoundingBoxAscent !== undefined
    ? metrics.actualBoundingBoxAscent + metrics.actualBoundingBoxDescent
    : fontSize * 1.2

  return {
    width: Math.max(metrics.width, 20), // Minimum width
    height: Math.max(height, fontSize), // At least font size
  }
}

/**
 * Measure multi-line text dimensions
 */
export function measureMultilineText(
  text: string,
  fontSize: number,
  fontFamily: string = 'system-ui, sans-serif',
  lineHeight: number = 1.2
): TextDimensions {
  const lines = text.split('\n')
  const ctx = getMeasureContext()

  if (!ctx) {
    const avgCharWidth = fontSize * 0.6
    const maxWidth = Math.max(...lines.map(line => line.length * avgCharWidth), 20)
    return {
      width: maxWidth,
      height: lines.length * fontSize * lineHeight,
    }
  }

  ctx.font = `${fontSize}px ${fontFamily}`

  let maxWidth = 0
  for (const line of lines) {
    const metrics = ctx.measureText(line)
    maxWidth = Math.max(maxWidth, metrics.width)
  }

  return {
    width: Math.max(maxWidth, 20),
    height: lines.length * fontSize * lineHeight,
  }
}

/**
 * Calculate text element dimensions with padding
 */
export function calculateTextElementDimensions(
  text: string,
  fontSize: number,
  fontFamily: string = 'system-ui, sans-serif',
  padding: number = 8
): TextDimensions {
  const textDimensions = text.includes('\n')
    ? measureMultilineText(text, fontSize, fontFamily)
    : measureText(text, fontSize, fontFamily)

  return {
    width: textDimensions.width + padding * 2,
    height: textDimensions.height + padding * 2,
  }
}
