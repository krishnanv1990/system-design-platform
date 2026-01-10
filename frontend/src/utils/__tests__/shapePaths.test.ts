/**
 * Shape Paths Utility Tests
 */

import { describe, it, expect } from 'vitest'
import {
  getDiamondPath,
  getCylinderPath,
  getHexagonPath,
  getParallelogramPath,
  getRoundedRectPath,
  getArrowHeadPath,
  getLineAngle,
  getScaledArrowHeadSize,
} from '../shapePaths'

describe('getDiamondPath', () => {
  it('should generate valid diamond path', () => {
    const path = getDiamondPath(0, 0, 100, 80)
    expect(path).toContain('M 50 0') // Top point
    expect(path).toContain('L 100 40') // Right point
    expect(path).toContain('L 50 80') // Bottom point
    expect(path).toContain('L 0 40') // Left point
    expect(path).toContain('Z') // Close path
  })

  it('should handle offset position', () => {
    const path = getDiamondPath(100, 50, 80, 60)
    expect(path).toContain('M 140 50') // Top at x + width/2, y
    expect(path).toContain('L 100 80') // Left at x, y + height/2
  })
})

describe('getCylinderPath', () => {
  it('should return body, top, and bottom paths', () => {
    const { body, top, bottom } = getCylinderPath(0, 0, 100, 100)
    expect(body).toBeDefined()
    expect(top).toBeDefined()
    expect(bottom).toBeDefined()
  })

  it('should contain arc commands', () => {
    const { top, bottom } = getCylinderPath(0, 0, 100, 100)
    expect(top).toContain('A') // Arc command
    expect(bottom).toContain('A')
  })
})

describe('getHexagonPath', () => {
  it('should generate valid hexagon path with 6 points', () => {
    const path = getHexagonPath(0, 0, 100, 80)
    // Should have 6 line segments
    const lineCount = (path.match(/L /g) || []).length
    expect(lineCount).toBe(5) // M followed by 5 L commands
    expect(path).toContain('Z') // Closed path
  })

  it('should have correct inset', () => {
    const path = getHexagonPath(0, 0, 100, 80)
    // Inset is width * 0.25 = 25
    expect(path).toContain('M 25 0') // Top-left point
  })
})

describe('getParallelogramPath', () => {
  it('should generate valid parallelogram path', () => {
    const path = getParallelogramPath(0, 0, 100, 80)
    expect(path).toContain('M') // Move
    expect(path).toContain('L') // Line
    expect(path).toContain('Z') // Close
  })

  it('should respect custom skew', () => {
    const path1 = getParallelogramPath(0, 0, 100, 80, 0.2)
    const path2 = getParallelogramPath(0, 0, 100, 80, 0.4)
    // Different skew should produce different paths
    expect(path1).not.toBe(path2)
  })
})

describe('getRoundedRectPath', () => {
  it('should generate path with quadratic curves for corners', () => {
    const path = getRoundedRectPath(0, 0, 100, 80, 10)
    expect(path).toContain('Q') // Quadratic curves for rounded corners
  })

  it('should limit radius to half of smaller dimension', () => {
    const path = getRoundedRectPath(0, 0, 50, 30, 100)
    // Radius should be limited to min(100, 25, 15) = 15
    expect(path).toContain('M 15 0') // Start at x + radius
  })

  it('should handle zero radius', () => {
    const path = getRoundedRectPath(0, 0, 100, 80, 0)
    expect(path).toBeDefined()
    expect(path).toContain('M 0 0')
  })
})

describe('getArrowHeadPath', () => {
  it('should generate valid triangle path', () => {
    const path = getArrowHeadPath(100, 100, 0, 12)
    expect(path).toContain('M 100 100') // Tip point
    expect(path).toContain('L') // Line to other points
    expect(path).toContain('Z') // Closed triangle
  })

  it('should respect angle parameter', () => {
    const path0 = getArrowHeadPath(100, 100, 0, 12)
    const path90 = getArrowHeadPath(100, 100, Math.PI / 2, 12)
    expect(path0).not.toBe(path90)
  })

  it('should respect size parameter', () => {
    const pathSmall = getArrowHeadPath(100, 100, 0, 8)
    const pathLarge = getArrowHeadPath(100, 100, 0, 16)
    expect(pathSmall).not.toBe(pathLarge)
  })
})

describe('getLineAngle', () => {
  it('should return 0 for horizontal line to the right', () => {
    const angle = getLineAngle(0, 0, 100, 0)
    expect(angle).toBe(0)
  })

  it('should return PI/2 for vertical line downward', () => {
    const angle = getLineAngle(0, 0, 0, 100)
    expect(angle).toBeCloseTo(Math.PI / 2)
  })

  it('should return PI for horizontal line to the left', () => {
    const angle = getLineAngle(100, 0, 0, 0)
    expect(angle).toBeCloseTo(Math.PI)
  })

  it('should return -PI/2 for vertical line upward', () => {
    const angle = getLineAngle(0, 100, 0, 0)
    expect(angle).toBeCloseTo(-Math.PI / 2)
  })

  it('should return correct angle for diagonal', () => {
    const angle = getLineAngle(0, 0, 100, 100)
    expect(angle).toBeCloseTo(Math.PI / 4)
  })
})

describe('getScaledArrowHeadSize', () => {
  it('should return base size for medium-length arrow', () => {
    const size = getScaledArrowHeadSize(0, 0, 100, 0, 12)
    expect(size).toBe(12)
  })

  it('should scale down for short arrows', () => {
    const size = getScaledArrowHeadSize(0, 0, 30, 0, 12)
    expect(size).toBeLessThan(12)
    expect(size).toBeGreaterThan(0)
  })

  it('should scale up for long arrows within max', () => {
    const size = getScaledArrowHeadSize(0, 0, 200, 0, 12, 0.5, 1.5)
    expect(size).toBeGreaterThan(12)
    expect(size).toBeLessThanOrEqual(18)
  })

  it('should respect minScale', () => {
    const size = getScaledArrowHeadSize(0, 0, 10, 0, 12, 0.5, 1.5)
    expect(size).toBeGreaterThanOrEqual(6) // 12 * 0.5
  })

  it('should respect maxScale', () => {
    const size = getScaledArrowHeadSize(0, 0, 500, 0, 12, 0.5, 1.5)
    expect(size).toBeLessThanOrEqual(18) // 12 * 1.5
  })
})
