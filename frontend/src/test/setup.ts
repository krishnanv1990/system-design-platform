/**
 * Test Setup
 * Global test configuration and mocks
 */

import '@testing-library/jest-dom'

// Mock window.matchMedia
Object.defineProperty(window, 'matchMedia', {
  writable: true,
  value: vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  })),
})

// Mock ResizeObserver
global.ResizeObserver = vi.fn().mockImplementation(() => ({
  observe: vi.fn(),
  unobserve: vi.fn(),
  disconnect: vi.fn(),
}))

// Mock clipboard API
Object.assign(navigator, {
  clipboard: {
    writeText: vi.fn().mockResolvedValue(undefined),
    readText: vi.fn().mockResolvedValue(''),
  },
})

// Mock canvas context for SVG operations
HTMLCanvasElement.prototype.getContext = vi.fn().mockReturnValue({
  fillRect: vi.fn(),
  clearRect: vi.fn(),
  getImageData: vi.fn().mockReturnValue({
    data: new Uint8ClampedArray(4),
  }),
  putImageData: vi.fn(),
  createImageData: vi.fn().mockReturnValue({
    data: new Uint8ClampedArray(4),
  }),
  setTransform: vi.fn(),
  drawImage: vi.fn(),
  save: vi.fn(),
  restore: vi.fn(),
  scale: vi.fn(),
  rotate: vi.fn(),
  translate: vi.fn(),
  transform: vi.fn(),
  beginPath: vi.fn(),
  closePath: vi.fn(),
  moveTo: vi.fn(),
  lineTo: vi.fn(),
  bezierCurveTo: vi.fn(),
  quadraticCurveTo: vi.fn(),
  arc: vi.fn(),
  arcTo: vi.fn(),
  ellipse: vi.fn(),
  rect: vi.fn(),
  fill: vi.fn(),
  stroke: vi.fn(),
  clip: vi.fn(),
  measureText: vi.fn().mockReturnValue({ width: 0 }),
  fillText: vi.fn(),
  strokeText: vi.fn(),
  fillStyle: '',
  strokeStyle: '',
  lineWidth: 1,
  font: '',
})

// Mock URL object
global.URL.createObjectURL = vi.fn().mockReturnValue('blob:mock-url')
global.URL.revokeObjectURL = vi.fn()

// Mock FileReader with proper callback simulation
class MockFileReader {
  result: string | ArrayBuffer | null = null
  onload: ((e: ProgressEvent<FileReader>) => void) | null = null
  onloadend: ((e: ProgressEvent<FileReader>) => void) | null = null
  onerror: ((e: ProgressEvent<FileReader>) => void) | null = null
  readyState: number = 0
  error: DOMException | null = null

  readAsDataURL(blob: Blob): void {
    const reader = new (Object.getPrototypeOf(this).constructor.OriginalFileReader || FileReader)()
    reader.onload = () => {
      this.result = reader.result
      this.readyState = 2
      const event = { target: this } as ProgressEvent<FileReader>
      this.onload?.(event)
      this.onloadend?.(event)
    }
    reader.onerror = () => {
      this.error = reader.error
      this.onerror?.({ target: this } as ProgressEvent<FileReader>)
    }
    reader.readAsDataURL(blob)
  }

  readAsText(blob: Blob): void {
    const reader = new (Object.getPrototypeOf(this).constructor.OriginalFileReader || FileReader)()
    reader.onload = () => {
      this.result = reader.result
      this.readyState = 2
      const event = { target: this } as ProgressEvent<FileReader>
      this.onload?.(event)
      this.onloadend?.(event)
    }
    reader.onerror = () => {
      this.error = reader.error
      this.onerror?.({ target: this } as ProgressEvent<FileReader>)
    }
    reader.readAsText(blob)
  }

  readAsArrayBuffer(_blob: Blob): void {
    // Stub for interface compliance
  }

  readAsBinaryString(_blob: Blob): void {
    // Stub for interface compliance
  }

  abort(): void {
    // Stub for interface compliance
  }

  addEventListener(): void {
    // Stub for interface compliance
  }

  removeEventListener(): void {
    // Stub for interface compliance
  }

  dispatchEvent(): boolean {
    return true
  }
}

// Store original FileReader before mocking
;(MockFileReader as unknown as { OriginalFileReader: typeof FileReader }).OriginalFileReader = globalThis.FileReader

// Don't actually mock FileReader - let jsdom's native one work
// global.FileReader = MockFileReader as unknown as typeof FileReader
