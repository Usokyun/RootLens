import { afterEach, describe, expect, it, vi } from 'vitest'
import { updateAppPreferences } from '@/services/app-preferences'
import { canSubmitReviewTargetType, getRootLensService } from '@/services/rootlens-service'

afterEach(() => { localStorage.clear(); vi.unstubAllGlobals() })

describe('review target feedback gating', () => {
  it('allows supported feedback target types', () => {
    for (const target of ['path', 'edge', 'entity_link', 'correction', 'root_cause_candidate']) {
      expect(canSubmitReviewTargetType(target)).toBe(true)
    }
  })
})

describe('offline graph source boundary', () => {
  it('does not call live graph management or read a native result in Demo', async () => {
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    updateAppPreferences({ dataSourceMode: 'mock' })
    const service = getRootLensService()
    await expect(service.enableWorkingGraph('graph', true)).rejects.toThrow('需要 Backend')
    await expect(service.getRun('analysis', 'analysis-v2')).rejects.toThrow('已保存分析属于 Backend')
    expect(fetch).not.toHaveBeenCalled()
  })
  it('keeps an imported Replay offline even with Backend selected', async () => {
    const fetch = vi.fn()
    vi.stubGlobal('fetch', fetch)
    updateAppPreferences({ dataSourceMode: 'backend' })
    localStorage.setItem('rootlens.local.meta', JSON.stringify({ source: 'import', updatedAt: '2026-11-11' }))
    const service = getRootLensService()
    await expect(service.listRuns()).resolves.toEqual([])
    await expect(service.kgStudio('active-graph')).rejects.toThrow('请先退出成品回放')
    expect(fetch).not.toHaveBeenCalled()
  })
})
