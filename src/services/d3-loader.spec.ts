import { describe, expect, it } from 'vitest'
import { loadD3 } from './d3-loader'
describe('project-local original graph renderer',()=>{
  it('loads the locked force, zoom and drag APIs without injecting a CDN script',async()=>{
    const first=loadD3();expect(loadD3()).toBe(first);const d3=await first
    expect(typeof d3.forceSimulation).toBe('function');expect(typeof d3.zoom).toBe('function');expect(typeof d3.drag).toBe('function')
    expect(document.querySelector('script[data-rootlens-d3]')).toBeNull()
  })
})
