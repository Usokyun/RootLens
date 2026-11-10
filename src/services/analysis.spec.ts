import { describe, expect, it } from 'vitest'
import type { AnalysisCase } from '@/api/workbench'
import { caseLabel, evaluationCandidates, pathsFor, queriesFor, scopeLabel, observationTitle } from '@/services/analysis'
const firstFrame = { case_id: 'query-a', task: { scope_id: 'window' }, scopes: [{ scope_id: 'window', kind: 'time_window', sample_start: 161, sample_end: 260 }], subjects: [{ subject_id: 'variable:xmeas_9', kind: 'variable', external_id: 'xmeas_9' }] }
const caseItem: AnalysisCase = { case_id: 'a', display_name: 'process_window_161_260', evidence_frames: [firstFrame], results: [{ case_id: 'query-a', outcome: 'ambiguous' }], generated_evidence:{}, visual_evidence:[], observation_locations:[] }
describe('stored analysis presentation', () => {
  it('binds a result to its own complete frame and preserves the actual window', () => {
    const query = queriesFor(caseItem)[0]!
    expect(query.frame).toBe(firstFrame); expect(query.label).toBe('样本 161–260')
    expect(caseLabel(caseItem,0)).toBe('样本 161–260')
    expect(scopeLabel(firstFrame,'window')).toBe('样本 161–260')
  })
  it('presents feature meaning and variable identity together', () => {
    expect(observationTitle({ subject_id:'variable:xmeas_9', feature_id:'statistics.mean_z' },firstFrame)).toBe('反应器温度 · XMEAS(9) · 均值偏移（标准化）')
  })
  it('keeps all candidate evaluations including unsupported candidates and an unranked supported candidate', () => {
    const result = { candidate_evaluations: [{candidate_id:'other',eligible_for_ranking:false}, {candidate_id:'tie',eligible_for_ranking:true}, {candidate_id:'top',eligible_for_ranking:true}], ranked_root_causes:[{candidate_id:'top',rank:1}] }
    const candidates = evaluationCandidates(result)
    expect(candidates.map((c) => c.candidate_id)).toEqual(['top','tie','other'])
    expect(candidates[1]?.rank).toBeUndefined()
  })
  it('retains backend ties and exact scores rather than making probabilities or a unique winner', () => {
    const result = { ranked_root_causes:[{candidate_id:'a',rank:1,score:-.25},{candidate_id:'b',rank:1,score:-.25}] }
    expect(evaluationCandidates(result).map((c) => [c.rank,c.score])).toEqual([[1,-.25],[1,-.25]])
  })
  it('selects paths by the actual candidate membership, not by the displayed case title', () => {
    const path = { path_id:'p', nodes:['condition','mechanism','candidate-a'], required_joint_fact_ids:['fact-a','fact-b'] }
    expect(pathsFor({top_k_paths:[path]},{candidate_id:'candidate-a'})).toEqual([path])
    expect(pathsFor({top_k_paths:[path]},{candidate_id:'candidate-b'})).toEqual([])
  })
})

describe('normal process windows', () => {
  it('identifies the backend normal-reference gate rather than treating it as a binding/configuration error', async () => {
    const {normalGateClosed}=await import('@/services/analysis')
    expect(normalGateClosed({outcome:'no_match',reason:'normal_reference_gate_is_false'})).toBe(true)
    expect(normalGateClosed({outcome:'no_match'})).toBe(false)
  })
  it('shows the actual sampling interval preserved in a native Frame before a legacy value', async () => {
    const {windowSamplingSeconds}=await import('@/services/analysis')
    expect(windowSamplingSeconds({scopes:[{kind:'time_window',sampling_seconds:180}]},{sampling_interval_seconds:60})).toBe(180)
    expect(windowSamplingSeconds({scopes:[]},{sampling_interval_seconds:60})).toBe(60)
  })
})
