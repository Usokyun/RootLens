import { describe, expect, it } from 'vitest'
import { waferDisplayExtent, waferRegionContains } from '@/services/wafer-regions'

describe('wafer display regions match backend measurement geometry', () => {
  it('preserves 38×38 radial mask counts without adding half a die to each radius', () => {
    const grid = Array.from({length:38}, () => Array<number>(38).fill(1))
    const extent = waferDisplayExtent(grid)
    expect(extent).toEqual({cx:19,cy:19,rx:18.5,ry:18.5})
    const counts = Object.fromEntries(['center','middle','edge'].map((zone) => [zone, grid.reduce((count,row,y) => count + row.filter((value,x) => value > 0 && waferRegionContains(x,y,zone,extent)).length,0)]))
    expect(counts).toEqual({center:172,middle:516,edge:756})
  })
  it('uses the inclusive center and edge boundaries and the open middle interval', () => {
    const extent = {cx:.5,cy:.5,rx:5,ry:5}
    expect(waferRegionContains(2,0,'center',extent)).toBe(true) // r = 0.4
    expect(waferRegionContains(2,0,'middle',extent)).toBe(false)
    expect(waferRegionContains(3,0,'middle',extent)).toBe(true)
    expect(waferRegionContains(4,0,'middle',extent)).toBe(false) // r = 0.8
    expect(waferRegionContains(4,0,'edge',extent)).toBe(true)
  })
  it('derives the bounds from valid dies and uses a minimum half-span of one', () => {
    expect(waferDisplayExtent([[0,0,0],[0,2,0],[0,0,0]])).toEqual({cx:1.5,cy:1.5,rx:1,ry:1})
    expect(waferDisplayExtent([[0,0]])).toBeNull()
  })
})
