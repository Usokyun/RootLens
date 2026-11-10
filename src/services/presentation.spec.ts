import { describe, expect, it } from 'vitest'
import { channelLabel, featureNames, formatValue, friendly, materialLocator, outcomeLabel, parseWindows } from '@/services/presentation'
import { tepChannelLabels } from '@/data/tep-channel-labels'

describe('reader-facing evidence values', () => {
  it('keeps explicit negative distinct from a missing value', () => {
    expect(formatValue({ kind: 'boolean', boolean: false })).toBe('否')
    expect(formatValue(null)).toBe('未提供')
    expect(formatValue({ kind: 'number', number: 0, unit: '1' })).toBe('0')
  })
  it('makes open VLM vocabularies readable without treating absence as negative', () => {
    expect(formatValue({ kind: 'candidate_set', items: ['chipped_edge', 'cracked_or_missing_glass'], exhaustive: false })).toBe('玻璃边缘崩缺、裂纹或玻璃缺失（开放候选集）')
  })
  it('keeps technical identifiers out of titles and preserves readable unknown labels', () => {
    expect(friendly('graph_abcdef1234567890','当前知识')).toBe('当前知识')
    expect(friendly('some newly supplied label')).toBe('some newly supplied label')
    expect(outcomeLabel('ambiguous')).toBe('多个候选并列')
  })
  it('uses all 52 catalogued TEP names while retaining meaningful channel codes', () => {
    expect(Object.keys(tepChannelLabels)).toHaveLength(52)
    expect(channelLabel('variable:xmeas_9')).toBe('反应器温度 · XMEAS(9)')
    expect(channelLabel('XMV_10')).toContain('XMV(10)')
    expect(featureNames['residual.contribution']).toBe('PCA 残差贡献')
  })
})
describe('source locations and process windows', () => {
  it('renders parser JSON locations as readable line/page locators', () => {
    expect(materialLocator('{"start_line":1,"end_line":164,"type":"text"}')).toBe('第 1–164 行')
    expect(materialLocator({ page_number: 13 })).toBe('第 13 页')
    expect(materialLocator('p. 13, Finish')).toBe('p. 13, Finish')
  })
  it('preserves one-based closed intervals and accepts Chinese separators', () => {
    expect(parseWindows('1–100，161-260; 361:460')).toEqual([[1,100],[161,260],[361,460]])
  })
  it.each(['', '0-100', '100-1', '1-100 extra', 'foo'])('rejects an invalid window instead of silently changing it: %s', (value) => {
    expect(() => parseWindows(value)).toThrow()
  })
})

describe('actual media tabs', () => {
  it('distinguishes an ROI crop from an original image even when both use kind=image', async () => {
    const {mediaOptions}=await import('@/services/presentation')
    const options=mediaOptions([{artifact_id:'original',kind:'image',source_key:'source_path',url:'/a'}, {artifact_id:'crop',kind:'image',source_key:'roi_path',url:'/b'}, {artifact_id:'unavailable',kind:'mask',available:false,url:'/c'}])
    expect(options.map((o) => [o.mediaKey,o.display])).toEqual([['original','原图'],['crop','区域裁切']])
  })
})
