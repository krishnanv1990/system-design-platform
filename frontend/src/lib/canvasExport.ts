/**
 * Canvas Export Utilities
 * Handles exporting SVG canvas to various image formats (PNG, JPG, SVG)
 */

export type ExportFormat = 'json' | 'png' | 'jpg' | 'svg'

export interface ExportOptions {
  format: ExportFormat
  filename?: string
  quality?: number // For JPG (0-1)
  scale?: number // For PNG/JPG resolution scaling
  backgroundColor?: string
}

export const EXPORT_FORMATS: { id: ExportFormat; label: string; extension: string; mimeType: string }[] = [
  { id: 'json', label: 'JSON (Editable)', extension: '.json', mimeType: 'application/json' },
  { id: 'png', label: 'PNG Image', extension: '.png', mimeType: 'image/png' },
  { id: 'jpg', label: 'JPG Image', extension: '.jpg', mimeType: 'image/jpeg' },
  { id: 'svg', label: 'SVG Vector', extension: '.svg', mimeType: 'image/svg+xml' },
]

export const IMPORT_FORMATS = [
  { extension: '.json', label: 'JSON' },
]

/**
 * Trigger a file download
 */
export function downloadFile(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/**
 * Export canvas elements as JSON
 */
export function exportAsJson(elements: unknown[], version: number = 1): Blob {
  const data = JSON.stringify({ elements, version }, null, 2)
  return new Blob([data], { type: 'application/json' })
}

/**
 * Export SVG element as SVG file
 */
export function exportAsSvg(svgElement: SVGSVGElement, backgroundColor: string = '#ffffff'): Blob {
  // Clone the SVG to avoid modifying the original
  const clonedSvg = svgElement.cloneNode(true) as SVGSVGElement

  // Get the actual dimensions
  const bbox = svgElement.getBBox()
  const padding = 20

  // Set explicit dimensions with padding
  const width = Math.max(bbox.x + bbox.width + padding, svgElement.clientWidth || 800)
  const height = Math.max(bbox.y + bbox.height + padding, svgElement.clientHeight || 500)

  clonedSvg.setAttribute('width', String(width))
  clonedSvg.setAttribute('height', String(height))
  clonedSvg.setAttribute('xmlns', 'http://www.w3.org/2000/svg')

  // Add background
  const bgRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
  bgRect.setAttribute('width', '100%')
  bgRect.setAttribute('height', '100%')
  bgRect.setAttribute('fill', backgroundColor)
  clonedSvg.insertBefore(bgRect, clonedSvg.firstChild)

  // Remove the grid pattern for cleaner export
  const gridRect = clonedSvg.querySelector('rect[fill="url(#grid)"]')
  if (gridRect) {
    gridRect.remove()
  }

  const svgString = new XMLSerializer().serializeToString(clonedSvg)
  return new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' })
}

/**
 * Convert SVG to canvas for raster export
 */
export function svgToCanvas(
  svgElement: SVGSVGElement,
  options: { scale?: number; backgroundColor?: string } = {}
): Promise<HTMLCanvasElement> {
  return new Promise((resolve, reject) => {
    const { scale = 2, backgroundColor = '#ffffff' } = options

    // Clone and prepare SVG
    const clonedSvg = svgElement.cloneNode(true) as SVGSVGElement

    // Get dimensions
    const width = svgElement.clientWidth || 800
    const height = svgElement.clientHeight || 500

    clonedSvg.setAttribute('width', String(width))
    clonedSvg.setAttribute('height', String(height))
    clonedSvg.setAttribute('xmlns', 'http://www.w3.org/2000/svg')

    // Remove grid pattern for cleaner export
    const gridRect = clonedSvg.querySelector('rect[fill="url(#grid)"]')
    if (gridRect) {
      gridRect.setAttribute('fill', backgroundColor)
    }

    // Serialize SVG
    const svgString = new XMLSerializer().serializeToString(clonedSvg)
    const svgBlob = new Blob([svgString], { type: 'image/svg+xml;charset=utf-8' })
    const svgUrl = URL.createObjectURL(svgBlob)

    // Create canvas
    const canvas = document.createElement('canvas')
    canvas.width = width * scale
    canvas.height = height * scale

    const ctx = canvas.getContext('2d')
    if (!ctx) {
      URL.revokeObjectURL(svgUrl)
      reject(new Error('Failed to get canvas context'))
      return
    }

    // Set background
    ctx.fillStyle = backgroundColor
    ctx.fillRect(0, 0, canvas.width, canvas.height)
    ctx.scale(scale, scale)

    // Load and draw SVG
    const img = new Image()
    img.onload = () => {
      ctx.drawImage(img, 0, 0)
      URL.revokeObjectURL(svgUrl)
      resolve(canvas)
    }
    img.onerror = () => {
      URL.revokeObjectURL(svgUrl)
      reject(new Error('Failed to load SVG as image'))
    }
    img.src = svgUrl
  })
}

/**
 * Export SVG as PNG image
 */
export async function exportAsPng(
  svgElement: SVGSVGElement,
  options: { scale?: number; backgroundColor?: string } = {}
): Promise<Blob> {
  const canvas = await svgToCanvas(svgElement, options)

  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) {
          resolve(blob)
        } else {
          reject(new Error('Failed to create PNG blob'))
        }
      },
      'image/png'
    )
  })
}

/**
 * Export SVG as JPG image
 */
export async function exportAsJpg(
  svgElement: SVGSVGElement,
  options: { scale?: number; backgroundColor?: string; quality?: number } = {}
): Promise<Blob> {
  const { quality = 0.92, ...canvasOptions } = options
  // JPG doesn't support transparency, ensure we have a background
  const canvas = await svgToCanvas(svgElement, { ...canvasOptions, backgroundColor: canvasOptions.backgroundColor || '#ffffff' })

  return new Promise((resolve, reject) => {
    canvas.toBlob(
      (blob) => {
        if (blob) {
          resolve(blob)
        } else {
          reject(new Error('Failed to create JPG blob'))
        }
      },
      'image/jpeg',
      quality
    )
  })
}

/**
 * Main export function that handles all formats
 */
export async function exportCanvas(
  svgElement: SVGSVGElement,
  elements: unknown[],
  options: ExportOptions
): Promise<void> {
  const {
    format,
    filename = 'system-design',
    quality = 0.92,
    scale = 2,
    backgroundColor = '#ffffff',
  } = options

  const formatInfo = EXPORT_FORMATS.find(f => f.id === format)
  if (!formatInfo) {
    throw new Error(`Unsupported format: ${format}`)
  }

  const fullFilename = `${filename}${formatInfo.extension}`

  let blob: Blob

  switch (format) {
    case 'json':
      blob = exportAsJson(elements)
      break
    case 'svg':
      blob = exportAsSvg(svgElement, backgroundColor)
      break
    case 'png':
      blob = await exportAsPng(svgElement, { scale, backgroundColor })
      break
    case 'jpg':
      blob = await exportAsJpg(svgElement, { scale, backgroundColor, quality })
      break
    default:
      throw new Error(`Unsupported format: ${format}`)
  }

  downloadFile(blob, fullFilename)
}

/**
 * Get format info by ID
 */
export function getFormatInfo(format: ExportFormat) {
  return EXPORT_FORMATS.find(f => f.id === format)
}
