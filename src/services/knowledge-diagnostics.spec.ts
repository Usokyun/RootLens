import { describe, expect, it } from 'vitest'
import { diagnosticReport, diagnosticTruthCounts, diagnosticGroupSummary, diagnosticGroupParticipation, diagnosticGroupNote } from '@/services/knowledge-diagnostics'
describe('saved knowledge diagnostics',()=>{
  it('does not manufacture diagnostics for older results',()=>{
    expect(diagnosticReport({candidate_evaluations:[]})).toBeNull()
    expect(diagnosticReport({authoring_diagnostics:{schema_version:'future'}})).toBeNull()
  })
  it('counts actual true, false and unknown facts once rather than treating grounded observations as support',()=>{
    const a={fact_id:'a',value:true},b={fact_id:'b',value:false},c={fact_id:'c',value:null}
    expect(diagnosticTruthCounts({candidate_checks:[{predicate_checks:[a,b,c]},{predicate_checks:[a,b]}]})).toEqual({total:3,satisfied:1,unsatisfied:1,unknown:1})
  })
  it('does not mistake unavailable or incomplete grouping for discriminated candidates',()=>{
    expect(diagnosticGroupSummary({grouping_status:'unavailable',equivalence_groups:[]})).toContain('暂不能判断')
    expect(diagnosticGroupSummary({grouping_status:'incomplete',equivalence_groups:[]})).toContain('未完成')
    expect(diagnosticGroupSummary({grouping_status:'available',equivalence_groups:[]})).toContain('不代表')
  })
  it('names structural equivalence separately from expectation-condition equivalence',()=>{
    expect(diagnosticGroupSummary({grouping_status:'available',grouping_basis:'actual_structural_projection',equivalence_groups:[{}]})).toContain('实际传播结构无法区分 1 组')
    expect(diagnosticGroupSummary({grouping_status:'available',grouping_basis:'reachable_expectation_conditions',equivalence_groups:[{}]})).toContain('当前期待条件无法区分 1 组')
  })
})

describe('knowledge groups are not ranking ties',()=>{
  const group={candidate_ids:['a','b']}
  it('labels all-ineligible normal or insufficient groups as authoring checks, not current ties',()=>{
    const report={grouping_status:'available',candidate_checks:[{candidate_id:'a',eligible_for_ranking:false},{candidate_id:'b',eligible_for_ranking:false}]}
    expect(diagnosticGroupParticipation(report,group)).toEqual({eligible:0,ineligible:2,unknown:0,total:2});expect(diagnosticGroupNote(report,group)).toContain('本组本次未获支持')
  })
  it('preserves unknown and incomplete status instead of declaring zero support',()=>{
    expect(diagnosticGroupNote({grouping_status:'available',candidate_checks:[]},group)).toContain('尚未完整评估')
    expect(diagnosticGroupNote({grouping_status:'incomplete',candidate_checks:[{candidate_id:'a',eligible_for_ranking:false},{candidate_id:'b',eligible_for_ranking:false}]},group)).toContain('不能完整判断')
  })
  it('states observation ambiguity only for a group with a ranked eligible member',()=>{
    expect(diagnosticGroupNote({grouping_status:'available',candidate_checks:[{candidate_id:'a',eligible_for_ranking:true}]},group)).toContain('当前观测不足以区分')
  })
})
