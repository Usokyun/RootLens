import { beforeEach, describe, expect, it, vi } from 'vitest'

beforeEach(() => { vi.resetModules(); localStorage.clear() })
describe('current workbench settings', () => {
  it('starts as a real backend workspace and ignores the removed old demo mode', async () => {
    localStorage.setItem('rootlens-app-preferences', JSON.stringify({dataSourceMode:'mock'}))
    const {workspace}=await import('@/services/workspace')
    expect(workspace.baseUrl).toContain('127.0.0.1')
    expect('dataSourceMode' in workspace).toBe(false)
  })
  it('keeps an automatic graph default distinguishable after reload',async()=>{
    const {workspace,selectGraph}=await import('@/services/workspace')
    expect(workspace.graphSelection).toBe('implicit');selectGraph('default-graph','implicit');expect(JSON.parse(localStorage.getItem('rootlens-workbench-v2')!).graphSelection).toBe('implicit')
    vi.resetModules();expect((await import('@/services/workspace')).workspace.graphSelection).toBe('implicit')
  })
  it('preserves saved user graph choices that predate provenance metadata',async()=>{
    localStorage.setItem('rootlens-workbench-v2',JSON.stringify({graphId:'selected-before-update'}))
    expect((await import('@/services/workspace')).workspace.graphSelection).toBe('explicit')
  })
  it('persists named selections without storing any engine output as a fallback', async () => {
    const {workspace,selectGraph,selectAnalysis,setBackend}=await import('@/services/workspace')
    selectGraph('graph-a');selectAnalysis('run-a');setBackend('https://backend.example/')
    expect(workspace.baseUrl).toBe('https://backend.example')
    expect(JSON.parse(localStorage.getItem('rootlens-workbench-v2')!)).toEqual({graphId:'graph-a',graphSelection:'explicit',analysisId:'run-a',baseUrl:'https://backend.example'})
  })
})
