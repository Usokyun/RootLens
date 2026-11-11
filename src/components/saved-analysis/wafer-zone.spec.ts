import { describe, expect, it } from 'vitest'
import { savedWaferZone, waferZoneOverlay } from './wafer-zone'

const scope = (zone: string, range: [number, number]) => ({
  kind: 'spatial_zone', zone, parent_scope_id: 'scope:grid', normalized_radius_interval: range,
})
// Offset, rectangular valid bbox. Expected counts measured by measure_wafer_map on this grid.
const grid = Array.from({ length: 13 }, (_, y) => Array.from({ length: 15 }, (_, x) =>
  x >= 3 && x <= 13 && y >= 2 && y <= 10 ? (x + 2 * y) % 3 === 0 ? 1 : 2 : 0,
))

describe('saved Wafer zone display', () => {
  it('uses the producer half-span and counts only valid cells in the exact saved zones', () => {
    const all = waferZoneOverlay(grid, savedWaferZone(scope('all_valid', [0, 1]))!)
    const center = waferZoneOverlay(grid, savedWaferZone(scope('center', [0, 0.4]))!)
    const middle = waferZoneOverlay(grid, savedWaferZone(scope('middle', [0.4, 0.8]))!)
    const edge = waferZoneOverlay(grid, savedWaferZone(scope('edge', [0.8, 1]))!)
    expect([all, center, middle, edge].map(o => [o.validCount, o.failedCount])).toEqual([
      [99, 66], [11, 7], [30, 20], [58, 39],
    ])
    expect(center.cells[6]?.[10]).toBe(true) // r = 0.4 belongs only to center
    expect(middle.cells[6]?.[10]).toBe(false)
    expect(middle.cells[6]?.[12]).toBe(false) // r = 0.8 belongs only to edge
    expect(edge.cells[6]?.[12]).toBe(true)
    expect(edge.cells[2]?.[3]).toBe(true) // clip r > 1 for the valid corners
    expect(edge.cells[1]?.[3]).toBe(false)
  })

  it('uses persisted limits and does not make up a zone for an invalid scope', () => {
    const narrow = savedWaferZone(scope('center', [0, 0.2]))!
    expect(waferZoneOverlay(grid, narrow).validCount).toBe(3)
    expect(savedWaferZone({ ...scope('edge', [0.8, 1]), parent_scope_id: null })).toBeNull()
    expect(savedWaferZone(scope('unknown', [0, 1]))).toBeNull()
    expect(savedWaferZone(scope('center', [0.8, 0.4]))).toBeNull()
  })
})
