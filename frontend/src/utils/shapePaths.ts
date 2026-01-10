/**
 * Shape Path Utilities
 * SVG path generators for various shapes
 */

/**
 * Generate a diamond/rhombus path
 */
export function getDiamondPath(
  x: number,
  y: number,
  width: number,
  height: number
): string {
  const cx = x + width / 2
  const cy = y + height / 2

  return `M ${cx} ${y} L ${x + width} ${cy} L ${cx} ${y + height} L ${x} ${cy} Z`
}

/**
 * Generate a cylinder path (for databases)
 * Returns top ellipse, body, and bottom ellipse as separate parts
 */
export function getCylinderPath(
  x: number,
  y: number,
  width: number,
  height: number
): { body: string; top: string; bottom: string } {
  const ellipseHeight = height * 0.15
  const rx = width / 2
  const ry = ellipseHeight / 2

  const top = `M ${x} ${y + ry}
    A ${rx} ${ry} 0 0 1 ${x + width} ${y + ry}
    A ${rx} ${ry} 0 0 1 ${x} ${y + ry}`

  const body = `M ${x} ${y + ry}
    V ${y + height - ry}
    A ${rx} ${ry} 0 0 0 ${x + width} ${y + height - ry}
    V ${y + ry}`

  const bottom = `M ${x} ${y + height - ry}
    A ${rx} ${ry} 0 0 0 ${x + width} ${y + height - ry}`

  return { body, top, bottom }
}

/**
 * Generate a hexagon path
 */
export function getHexagonPath(
  x: number,
  y: number,
  width: number,
  height: number
): string {
  const inset = width * 0.25

  return `M ${x + inset} ${y}
    L ${x + width - inset} ${y}
    L ${x + width} ${y + height / 2}
    L ${x + width - inset} ${y + height}
    L ${x + inset} ${y + height}
    L ${x} ${y + height / 2}
    Z`
}

/**
 * Generate a parallelogram path
 */
export function getParallelogramPath(
  x: number,
  y: number,
  width: number,
  height: number,
  skew: number = 0.2
): string {
  const offset = width * skew

  return `M ${x + offset} ${y}
    L ${x + width} ${y}
    L ${x + width - offset} ${y + height}
    L ${x} ${y + height}
    Z`
}

/**
 * Generate a rounded rectangle path
 */
export function getRoundedRectPath(
  x: number,
  y: number,
  width: number,
  height: number,
  radius: number
): string {
  const r = Math.min(radius, width / 2, height / 2)

  return `M ${x + r} ${y}
    H ${x + width - r}
    Q ${x + width} ${y} ${x + width} ${y + r}
    V ${y + height - r}
    Q ${x + width} ${y + height} ${x + width - r} ${y + height}
    H ${x + r}
    Q ${x} ${y + height} ${x} ${y + height - r}
    V ${y + r}
    Q ${x} ${y} ${x + r} ${y}
    Z`
}

/**
 * Generate an arrow head path
 */
export function getArrowHeadPath(
  endX: number,
  endY: number,
  angle: number,
  size: number = 12,
  arrowAngle: number = Math.PI / 6
): string {
  const x1 = endX - size * Math.cos(angle - arrowAngle)
  const y1 = endY - size * Math.sin(angle - arrowAngle)
  const x2 = endX - size * Math.cos(angle + arrowAngle)
  const y2 = endY - size * Math.sin(angle + arrowAngle)

  return `M ${endX} ${endY} L ${x1} ${y1} L ${x2} ${y2} Z`
}

/**
 * Get the angle of a line between two points
 */
export function getLineAngle(
  x1: number,
  y1: number,
  x2: number,
  y2: number
): number {
  return Math.atan2(y2 - y1, x2 - x1)
}

/**
 * Calculate scaled arrow head size based on line length
 */
export function getScaledArrowHeadSize(
  startX: number,
  startY: number,
  endX: number,
  endY: number,
  baseSize: number = 12,
  minScale: number = 0.5,
  maxScale: number = 1.5
): number {
  const length = Math.hypot(endX - startX, endY - startY)
  const scale = Math.min(maxScale, Math.max(minScale, length / 100))
  return baseSize * scale
}
