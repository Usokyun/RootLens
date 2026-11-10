/** Display coordinates for the exact radial regions used by measure_wafer_map. */
export interface WaferDisplayExtent { cx: number; cy: number; rx: number; ry: number }

export function waferDisplayExtent(grid: number[][]): WaferDisplayExtent | null {
  const cells = grid.flatMap((row, y) => row.flatMap((value, x) => value > 0 ? [{ x, y }] : []))
  if (!cells.length) return null
  const xs = cells.map((cell) => cell.x), ys = cells.map((cell) => cell.y)
  const left = Math.min(...xs), right = Math.max(...xs), top = Math.min(...ys), bottom = Math.max(...ys)
  // SVG cells start at integer coordinates; their centers are index + 0.5.
  // Radii use the backend's index half-span, not half the number of cells.
  return { cx: (left + right + 1) / 2, cy: (top + bottom + 1) / 2, rx: Math.max((right - left) / 2, 1), ry: Math.max((bottom - top) / 2, 1) }
}

export function waferRegionContains(x: number, y: number, zone: string, extent: WaferDisplayExtent | null): boolean {
  if (zone === 'all_valid') return true
  if (!extent) return false
  const radius = Math.sqrt(((x + .5 - extent.cx) / extent.rx) ** 2 + ((y + .5 - extent.cy) / extent.ry) ** 2)
  return zone === 'center' ? radius <= .4 : zone === 'middle' ? radius > .4 && radius < .8 : radius >= .8
}
