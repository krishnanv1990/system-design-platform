/**
 * Tests for canvasExport utility
 * Tests export functionality for various image formats (PNG, JPG, SVG, JSON)
 */

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import {
  EXPORT_FORMATS,
  IMPORT_FORMATS,
  downloadFile,
  exportAsJson,
  exportAsSvg,
  exportCanvas,
  getFormatInfo,
  type ExportFormat,
} from './canvasExport'

// Helper to read blob as text (since blob.text() isn't available in jsdom)
async function blobToText(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = reject
    reader.readAsText(blob)
  })
}

describe('canvasExport', () => {
  describe('EXPORT_FORMATS', () => {
    it('contains JSON format', () => {
      const jsonFormat = EXPORT_FORMATS.find(f => f.id === 'json')
      expect(jsonFormat).toBeDefined()
      expect(jsonFormat?.label).toBe('JSON (Editable)')
      expect(jsonFormat?.extension).toBe('.json')
      expect(jsonFormat?.mimeType).toBe('application/json')
    })

    it('contains PNG format', () => {
      const pngFormat = EXPORT_FORMATS.find(f => f.id === 'png')
      expect(pngFormat).toBeDefined()
      expect(pngFormat?.label).toBe('PNG Image')
      expect(pngFormat?.extension).toBe('.png')
      expect(pngFormat?.mimeType).toBe('image/png')
    })

    it('contains JPG format', () => {
      const jpgFormat = EXPORT_FORMATS.find(f => f.id === 'jpg')
      expect(jpgFormat).toBeDefined()
      expect(jpgFormat?.label).toBe('JPG Image')
      expect(jpgFormat?.extension).toBe('.jpg')
      expect(jpgFormat?.mimeType).toBe('image/jpeg')
    })

    it('contains SVG format', () => {
      const svgFormat = EXPORT_FORMATS.find(f => f.id === 'svg')
      expect(svgFormat).toBeDefined()
      expect(svgFormat?.label).toBe('SVG Vector')
      expect(svgFormat?.extension).toBe('.svg')
      expect(svgFormat?.mimeType).toBe('image/svg+xml')
    })

    it('has exactly 4 formats', () => {
      expect(EXPORT_FORMATS.length).toBe(4)
    })
  })

  describe('IMPORT_FORMATS', () => {
    it('contains JSON format for import', () => {
      const jsonFormat = IMPORT_FORMATS.find(f => f.extension === '.json')
      expect(jsonFormat).toBeDefined()
      expect(jsonFormat?.label).toBe('JSON')
    })

    it('has exactly 1 import format', () => {
      expect(IMPORT_FORMATS.length).toBe(1)
    })
  })

  describe('getFormatInfo', () => {
    it('returns format info for valid format', () => {
      const info = getFormatInfo('png')
      expect(info).toBeDefined()
      expect(info?.id).toBe('png')
      expect(info?.label).toBe('PNG Image')
    })

    it('returns undefined for invalid format', () => {
      const info = getFormatInfo('invalid' as ExportFormat)
      expect(info).toBeUndefined()
    })

    it('returns correct info for each format', () => {
      const formats: ExportFormat[] = ['json', 'png', 'jpg', 'svg']
      formats.forEach(format => {
        const info = getFormatInfo(format)
        expect(info).toBeDefined()
        expect(info?.id).toBe(format)
      })
    })
  })

  describe('downloadFile', () => {
    let mockClick: ReturnType<typeof vi.fn>
    let mockCreateObjectURL: ReturnType<typeof vi.fn>
    let mockRevokeObjectURL: ReturnType<typeof vi.fn>
    let originalURL: typeof URL

    beforeEach(() => {
      mockClick = vi.fn()
      mockCreateObjectURL = vi.fn().mockReturnValue('blob:mock-url')
      mockRevokeObjectURL = vi.fn()
      originalURL = globalThis.URL

      // Override URL methods
      globalThis.URL = {
        ...originalURL,
        createObjectURL: mockCreateObjectURL,
        revokeObjectURL: mockRevokeObjectURL,
      } as typeof URL
    })

    afterEach(() => {
      globalThis.URL = originalURL
    })

    it('creates a download link with correct URL', () => {
      const blob = new Blob(['test'], { type: 'text/plain' })

      // Mock createElement to return a mock anchor
      const originalCreateElement = document.createElement.bind(document)
      vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
        if (tag === 'a') {
          const anchor = originalCreateElement('a')
          anchor.click = mockClick
          return anchor
        }
        return originalCreateElement(tag)
      })

      downloadFile(blob, 'test.txt')

      expect(mockCreateObjectURL).toHaveBeenCalledWith(blob)
      vi.restoreAllMocks()
    })

    it('triggers a click on the download link', () => {
      const blob = new Blob(['test'], { type: 'text/plain' })

      const originalCreateElement = document.createElement.bind(document)
      vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
        if (tag === 'a') {
          const anchor = originalCreateElement('a')
          anchor.click = mockClick
          return anchor
        }
        return originalCreateElement(tag)
      })

      downloadFile(blob, 'test.txt')

      expect(mockClick).toHaveBeenCalled()
      vi.restoreAllMocks()
    })

    it('revokes the object URL after download', () => {
      const blob = new Blob(['test'], { type: 'text/plain' })

      const originalCreateElement = document.createElement.bind(document)
      vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
        if (tag === 'a') {
          const anchor = originalCreateElement('a')
          anchor.click = mockClick
          return anchor
        }
        return originalCreateElement(tag)
      })

      downloadFile(blob, 'test.txt')

      expect(mockRevokeObjectURL).toHaveBeenCalledWith('blob:mock-url')
      vi.restoreAllMocks()
    })
  })

  describe('exportAsJson', () => {
    it('returns a Blob with JSON content', () => {
      const elements = [{ id: '1', type: 'rectangle' }]
      const blob = exportAsJson(elements)

      expect(blob).toBeInstanceOf(Blob)
      expect(blob.type).toBe('application/json')
    })

    it('includes version in exported JSON', async () => {
      const elements = [{ id: '1' }]
      const blob = exportAsJson(elements, 2)
      const text = await blobToText(blob)
      const data = JSON.parse(text)

      expect(data.version).toBe(2)
    })

    it('defaults version to 1', async () => {
      const elements: unknown[] = []
      const blob = exportAsJson(elements)
      const text = await blobToText(blob)
      const data = JSON.parse(text)

      expect(data.version).toBe(1)
    })

    it('includes elements array in exported JSON', async () => {
      const elements = [
        { id: '1', type: 'rectangle' },
        { id: '2', type: 'ellipse' },
      ]
      const blob = exportAsJson(elements)
      const text = await blobToText(blob)
      const data = JSON.parse(text)

      expect(data.elements).toEqual(elements)
    })

    it('produces valid JSON', async () => {
      const elements = [{ id: '1', x: 100, y: 200 }]
      const blob = exportAsJson(elements)
      const text = await blobToText(blob)

      expect(() => JSON.parse(text)).not.toThrow()
    })

    it('formats JSON with indentation', async () => {
      const elements = [{ id: '1' }]
      const blob = exportAsJson(elements)
      const text = await blobToText(blob)

      expect(text).toContain('\n')
      expect(text).toContain('  ')
    })

    it('handles empty elements array', async () => {
      const blob = exportAsJson([])
      const text = await blobToText(blob)
      const data = JSON.parse(text)

      expect(data.elements).toEqual([])
      expect(data.version).toBe(1)
    })

    it('handles complex element objects', async () => {
      const elements = [{
        id: 'complex1',
        type: 'rectangle',
        x: 100,
        y: 200,
        width: 50,
        height: 75,
        fill: '#ffffff',
        stroke: '#000000',
        strokeWidth: 2,
        cornerRadius: 4,
        nested: { a: 1, b: [1, 2, 3] }
      }]
      const blob = exportAsJson(elements)
      const text = await blobToText(blob)
      const data = JSON.parse(text)

      expect(data.elements[0].nested).toEqual({ a: 1, b: [1, 2, 3] })
    })
  })

  describe('exportAsSvg', () => {
    let mockSvgElement: SVGSVGElement

    beforeEach(() => {
      mockSvgElement = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
      mockSvgElement.setAttribute('width', '800')
      mockSvgElement.setAttribute('height', '600')

      // Add mock methods
      Object.defineProperty(mockSvgElement, 'getBBox', {
        value: () => ({ x: 0, y: 0, width: 100, height: 100 }),
        configurable: true,
      })
      Object.defineProperty(mockSvgElement, 'clientWidth', { value: 800, configurable: true })
      Object.defineProperty(mockSvgElement, 'clientHeight', { value: 600, configurable: true })
    })

    it('returns a Blob with SVG content', () => {
      const blob = exportAsSvg(mockSvgElement)

      expect(blob).toBeInstanceOf(Blob)
      expect(blob.type).toBe('image/svg+xml;charset=utf-8')
    })

    it('adds xmlns attribute to SVG', async () => {
      const blob = exportAsSvg(mockSvgElement)
      const text = await blobToText(blob)

      expect(text).toContain('xmlns="http://www.w3.org/2000/svg"')
    })

    it('adds background rectangle with specified color', async () => {
      const blob = exportAsSvg(mockSvgElement, '#ff0000')
      const text = await blobToText(blob)

      expect(text).toContain('fill="#ff0000"')
    })

    it('uses white background by default', async () => {
      const blob = exportAsSvg(mockSvgElement)
      const text = await blobToText(blob)

      expect(text).toContain('fill="#ffffff"')
    })

    it('removes grid pattern from exported SVG', async () => {
      // Add a grid rect to the SVG
      const gridRect = document.createElementNS('http://www.w3.org/2000/svg', 'rect')
      gridRect.setAttribute('fill', 'url(#grid)')
      mockSvgElement.appendChild(gridRect)

      const blob = exportAsSvg(mockSvgElement)
      const text = await blobToText(blob)

      expect(text).not.toContain('fill="url(#grid)"')
    })

    it('sets explicit dimensions on exported SVG', async () => {
      const blob = exportAsSvg(mockSvgElement)
      const text = await blobToText(blob)

      expect(text).toContain('width=')
      expect(text).toContain('height=')
    })
  })

  describe('exportCanvas', () => {
    let mockSvgElement: SVGSVGElement
    let mockClick: ReturnType<typeof vi.fn>
    let mockCreateObjectURL: ReturnType<typeof vi.fn>
    let mockRevokeObjectURL: ReturnType<typeof vi.fn>
    let originalURL: typeof URL

    beforeEach(() => {
      mockSvgElement = document.createElementNS('http://www.w3.org/2000/svg', 'svg')
      Object.defineProperty(mockSvgElement, 'clientWidth', { value: 800, configurable: true })
      Object.defineProperty(mockSvgElement, 'clientHeight', { value: 600, configurable: true })
      Object.defineProperty(mockSvgElement, 'getBBox', {
        value: () => ({ x: 0, y: 0, width: 100, height: 100 }),
        configurable: true,
      })

      mockClick = vi.fn()
      mockCreateObjectURL = vi.fn().mockReturnValue('blob:mock-url')
      mockRevokeObjectURL = vi.fn()
      originalURL = globalThis.URL

      globalThis.URL = {
        ...originalURL,
        createObjectURL: mockCreateObjectURL,
        revokeObjectURL: mockRevokeObjectURL,
      } as typeof URL

      const originalCreateElement = document.createElement.bind(document)
      vi.spyOn(document, 'createElement').mockImplementation((tag: string) => {
        if (tag === 'a') {
          const anchor = originalCreateElement('a')
          anchor.click = mockClick
          return anchor
        }
        return originalCreateElement(tag)
      })
    })

    afterEach(() => {
      globalThis.URL = originalURL
      vi.restoreAllMocks()
    })

    it('exports JSON format successfully', async () => {
      const elements = [{ id: '1', type: 'rectangle' }]

      await exportCanvas(mockSvgElement, elements, {
        format: 'json',
        filename: 'test',
      })

      expect(mockCreateObjectURL).toHaveBeenCalled()
      expect(mockClick).toHaveBeenCalled()
    })

    it('exports SVG format successfully', async () => {
      const elements: unknown[] = []

      await exportCanvas(mockSvgElement, elements, {
        format: 'svg',
        filename: 'test',
      })

      expect(mockCreateObjectURL).toHaveBeenCalled()
    })

    it('uses default filename when not provided', async () => {
      const elements: unknown[] = []

      await exportCanvas(mockSvgElement, elements, {
        format: 'json',
      })

      expect(mockClick).toHaveBeenCalled()
    })

    it('throws error for unsupported format', async () => {
      const elements: unknown[] = []

      await expect(
        exportCanvas(mockSvgElement, elements, {
          format: 'tiff' as ExportFormat,
        })
      ).rejects.toThrow('Unsupported format: tiff')
    })

    it('accepts all export options', async () => {
      const elements: unknown[] = []

      await exportCanvas(mockSvgElement, elements, {
        format: 'json',
        filename: 'my-diagram',
        quality: 0.9,
        scale: 3,
        backgroundColor: '#f0f0f0',
      })

      expect(mockClick).toHaveBeenCalled()
    })
  })

  describe('Format Extensions', () => {
    it('JSON has .json extension', () => {
      const format = EXPORT_FORMATS.find(f => f.id === 'json')
      expect(format?.extension).toBe('.json')
    })

    it('PNG has .png extension', () => {
      const format = EXPORT_FORMATS.find(f => f.id === 'png')
      expect(format?.extension).toBe('.png')
    })

    it('JPG has .jpg extension', () => {
      const format = EXPORT_FORMATS.find(f => f.id === 'jpg')
      expect(format?.extension).toBe('.jpg')
    })

    it('SVG has .svg extension', () => {
      const format = EXPORT_FORMATS.find(f => f.id === 'svg')
      expect(format?.extension).toBe('.svg')
    })
  })

  describe('MIME Types', () => {
    it('JSON has correct MIME type', () => {
      const format = EXPORT_FORMATS.find(f => f.id === 'json')
      expect(format?.mimeType).toBe('application/json')
    })

    it('PNG has correct MIME type', () => {
      const format = EXPORT_FORMATS.find(f => f.id === 'png')
      expect(format?.mimeType).toBe('image/png')
    })

    it('JPG has correct MIME type', () => {
      const format = EXPORT_FORMATS.find(f => f.id === 'jpg')
      expect(format?.mimeType).toBe('image/jpeg')
    })

    it('SVG has correct MIME type', () => {
      const format = EXPORT_FORMATS.find(f => f.id === 'svg')
      expect(format?.mimeType).toBe('image/svg+xml')
    })
  })

  describe('Format Labels', () => {
    it('JSON label indicates it is editable', () => {
      const format = EXPORT_FORMATS.find(f => f.id === 'json')
      expect(format?.label).toContain('Editable')
    })

    it('PNG label indicates it is an image', () => {
      const format = EXPORT_FORMATS.find(f => f.id === 'png')
      expect(format?.label).toContain('Image')
    })

    it('JPG label indicates it is an image', () => {
      const format = EXPORT_FORMATS.find(f => f.id === 'jpg')
      expect(format?.label).toContain('Image')
    })

    it('SVG label indicates it is vector', () => {
      const format = EXPORT_FORMATS.find(f => f.id === 'svg')
      expect(format?.label).toContain('Vector')
    })
  })
})
