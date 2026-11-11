const zoneLabels = { all_valid: '全片有效区', center: '中心区', middle: '中间区', edge: '边缘区' } as const
type ZoneName = keyof typeof zoneLabels

export interface SavedWaferZone {
  name: ZoneName
  label: string
  parentId: string
  interval: readonly [number, number]
}

export function savedWaferZone(scope: unknown): SavedWaferZone | null {
  if (!scope || typeof scope !== 'object') return null
  const row = scope as Record<string, unknown>
  const range = row.normalized_radius_interval
  if (row.kind !== 'spatial_zone' || typeof row.zone !== 'string' || !Object.hasOwn(zoneLabels, row.zone)
    || typeof row.parent_scope_id !== 'string' || !Array.isArray(range) || range.length !== 2) return null
  const [lower, upper] = range
  if (typeof lower !== 'number' || typeof upper !== 'number' || !(0 <= lower && lower < upper && upper <= 1)) return null
  const name = row.zone as ZoneName
  return { name, label: zoneLabels[name], parentId: row.parent_scope_id, interval: [lower, upper] }
}

/** Highlight the saved scope's cells; never replace the saved density or feed reasoning. */
export function waferZoneOverlay(grid: readonly (readonly number[])[], zone: SavedWaferZone) {
  const valid = (value: number) => value === 1 || value === 2
  let left = Infinity, right = -Infinity, top = Infinity, bottom = -Infinity
  for (const [y, row] of grid.entries()) for (const [x, value] of row.entries()) if (valid(value)) {
    left = Math.min(left, x); right = Math.max(right, x)
    top = Math.min(top, y); bottom = Math.max(bottom, y)
  }
  const cx = (left + right) / 2, cy = (top + bottom) / 2
  const rx = Math.max((right - left) / 2, 1), ry = Math.max((bottom - top) / 2, 1)
  const [lower, upper] = zone.interval
  let validCount = 0, failedCount = 0
  const cells = grid.map((row, y) => row.map((value, x) => {
    if (!valid(value)) return false
    const radius = Math.min(1, Math.sqrt(((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2))
    const inside = zone.name === 'all_valid' || (zone.name === 'middle'
      ? radius > lower && radius < upper
      : radius >= lower && radius <= upper)
    if (inside) { validCount += 1; if (value === 2) failedCount += 1 }
    return inside
  }))
  return { cells, validCount, failedCount }
}
