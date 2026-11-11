import { canSubmitReviewTargetType } from '@/services/rootlens-service'
import { describe, expect, it } from 'vitest'

describe('review target feedback gating', () => {
  it('allows supported feedback target types', () => {
    expect(canSubmitReviewTargetType('path')).toBe(true)
    expect(canSubmitReviewTargetType('edge')).toBe(true)
    expect(canSubmitReviewTargetType('entity_link')).toBe(true)
    expect(canSubmitReviewTargetType('correction')).toBe(true)
  })

  it('allows root cause candidate feedback once backend mode catches up', () => {
    expect(canSubmitReviewTargetType('root_cause_candidate')).toBe(true)
  })
})

describe('restored Demo processing boundary',()=>{
  it('keeps source extraction and graph construction on the real backend',async()=>{
    const {updateAppPreferences}=await import('@/services/app-preferences');const {getRootLensService}=await import('@/services/rootlens-service');updateAppPreferences({dataSourceMode:'mock'});const service=getRootLensService();await expect(service.extractKGMaterial('source')).rejects.toThrow('只展示成品快照');await expect(service.buildKGConstruction({sources:[],output_name:'readonly-test',overwrite:false})).rejects.toThrow('浏览器不执行');await expect(service.generateKGSourceDraft({source_id:'source',source_text:'公开资料',provider:'heuristic',default_scenario:'mvtec',confidence:.5})).rejects.toThrow('切换 Backend')
  })
})
