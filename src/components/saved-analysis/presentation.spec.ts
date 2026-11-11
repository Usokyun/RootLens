import { describe, expect, it } from 'vitest'
import { projectSavedAnalysis } from '@/services/saved-analysis-reader'
import { chooseSavedPath, detailTab, factOnPath, isRootPropagation, observationChannel, observationUsage, pathForFact, savedProofGroups, stageForTab, truthLabel, valueLabel } from './presentation'

const atom = { fact_id: 'fact:p', predicate_id: 'p', value: true, source_obs_ids: ['obs-a'], predicate_check: { feature_id: 'appearance.semantic_candidates', op: 'candidate_contains', operand: { kind: 'category', category: 'cracked_or_missing_glass' } } }
const unknown = { fact_id: 'fact:q', predicate_id: 'q', value: null, source_obs_ids: ['obs-b'], reason: 'open_candidate_set_does_not_refute' }
const candidate = { candidate_id: 'c', candidate_name: '候选 C', active_hypothesis_world_entities: ['c', 'm'], activated_effect_rule_ids: ['e'],
  support_obs_ids: ['obs-a'], expectation_checks: [{ rule_id: 'r', pattern_id: 'pattern', observed_value: true, predicate_ids: ['p', 'q'] }] }
const topPath = {
  path_id: 'path-c', nodes: ['p', 'expr', 'pattern', 'r', 'm', 'e', 'c'], candidate_id: 'c', support_obs_ids: ['obs-a'], required_joint_fact_ids: ['fact:p'],
  source_edge_views: [{ edge_id: 'edge-p', reverse: false }, { edge_id: 'edge-expr', reverse: false }, { edge_id: 'edge-r-to', reverse: true },
    { edge_id: 'edge-r-from', reverse: true }, { edge_id: 'edge-e-to', reverse: true }, { edge_id: 'edge-e-from', reverse: true }],
}
const frameBody = { case_id: 'frame-a', task: { scope_id: 'scope' }, scopes: [{ kind: 'time_window', scope_id: 'scope', sample_start: 161, sample_end: 260 }],
  subjects: [{ subject_id: 'subject', external_id: 'xmv_10' }], observations: [
    { obs_id: 'obs-a', subject_id: 'subject', scope_id: 'scope', feature_id: 'appearance.semantic_candidates' },
    { obs_id: 'obs-b', subject_id: 'subject', scope_id: 'scope', feature_id: 'geometry.morphology' },
  ], assets: [], procedures: [], references: [], }
const resultBody = { case_id: 'frame-a', display_labels: { c: '候选 C', m: '保存机制', pattern: '联合现象' },
  ranked_root_causes: [{ ...candidate, rank: 1, score: -0.25 }], candidate_evaluations: [candidate],
  top_k_paths: [topPath], grounded_facts: [atom, unknown], observed_patterns: [{ pattern_id: 'pattern', scope_join: 'same_subject_same_scope' }], }
const snapshot = { knowledge: {
  pattern_definitions: [{ pattern_id: 'pattern', label: '保存的现象', body: { all: ['p', { any: ['q', 'r2'] }] } }],
  expectation_rules: [{ rule_id: 'r', from_id: 'm' }], effect_rules: [{ rule_id: 'e', to_id: 'm' }],
} }
function fixture(result = resultBody) {
  return projectSavedAnalysis({ run_id: 'run', input_mode: 'evidence', working_graph_snapshot: snapshot,
    cases: [{ case_id: 'sample-a', evidence_frames: [frameBody], results: [result] }, {
      case_id: 'sample-normal', evidence_frames: [{ ...frameBody, case_id: 'frame-normal', observations: [{ obs_id: 'obs-normal' }] }],
      results: [{ case_id: 'frame-normal', outcome: 'no_match', reason: 'normal_reference_gate_is_false', ranked_root_causes: [], top_k_paths: [] }],
    }], }, 'http://127.0.0.1:8012')
}

describe('saved run detail presentation', () => {
  it('treats graph as a view of the fourth stage, not a fifth stage', () => {
    expect(stageForTab(detailTab('graph'))).toBe('reasoning')
    expect(stageForTab(detailTab('evidence'))).toBe('evidence')
    expect(detailTab('invented')).toBe('overview')
  })
  it('uses exactly the saved expression and proof fact, source edge, observation IDs', () => {
    const frame = fixture().framesById.get('frame-a')!
    const [group] = savedProofGroups(snapshot, frame, candidate)
    expect(group?.label).toBe('保存机制')
    expect(group?.edgeFocus).toEqual({ pathId: 'path-c', edgeId: 'edge-e-to' })
    const [condition] = group!.conditions
    expect(condition?.expression).toEqual({ all: ['p', { any: ['q', 'r2'] }] })
    expect(condition?.factsByPredicate.get('q')).toEqual([unknown])
    expect(pathForFact(frame, 'c', atom)).toEqual({ pathId: 'path-c', edgeId: 'edge-p', obsId: 'obs-a', factId: 'fact:p' })
    expect(factOnPath(frame, frame.pathsById.get('path-c')!, 'obs-a', 'edge-p')).toBe(atom)
    expect(pathForFact(frame, 'c', unknown)).toBeNull()
    expect(pathForFact(frame, 'another-candidate', atom)).toBeNull()
  })
  it('does not infer conjunction from the path alone or when expression was not saved', () => {
    const frame = fixture().frames[0]!
    const [group] = savedProofGroups(undefined, frame, candidate)
    expect(group?.conditions[0]?.expression).toBeUndefined()
    expect(group?.conditions[0]?.predicates).toEqual(['p', 'q'])
    expect(savedProofGroups(snapshot, frame, { candidate_id: 'c' })).toEqual([])
  })
  it('retains a saved path without choosing an arbitrary edge for an ambiguous condition link', () => {
    const alternative = { ...topPath, path_id: 'path-alternative', source_edge_views: [
      { edge_id: 'edge-p-alternative', reverse: false }, ...topPath.source_edge_views.slice(1),
    ] }
    const frame = fixture({ ...resultBody, top_k_paths: [topPath, alternative] }).frames[0]!
    expect(pathForFact(frame, 'c', atom)).toEqual({ pathId: 'path-c', edgeId: undefined, obsId: 'obs-a', factId: 'fact:p' })
  })
  it('keeps the exact assessed fact rather than a later fact with the same predicate ID', () => {
    const other = { ...atom, fact_id: 'fact:p@other', source_obs_ids: ['obs-b'], value: false }
    const assessment = { ...candidate, expectation_checks: candidate.expectation_checks.map(check => ({ ...check, covered_fact_ids: ['fact:p'] })) }
    const frame = fixture({ ...resultBody, grounded_facts: [atom, unknown, other] }).frames[0]!
    const [group] = savedProofGroups(snapshot, frame, assessment)
    expect(group?.conditions[0]?.factsByPredicate.get('p')).toEqual([atom])
  })
  it('treats structure scoring IDs separately from fact IDs and does not borrow another window', () => {
    const analysis = fixture({ ...resultBody, ...{ scoring_method: 'tep_rootkgd_propagation_v2', propagation: { scoring_input_obs_ids: ['obs-a'] } } })
    const [frame, normal] = analysis.frames
    expect(isRootPropagation(frame!.result)).toBe(true)
    expect(savedProofGroups(snapshot, frame!, candidate)).toEqual([])
    expect(observationUsage(frame!, candidate).structural).toEqual(new Set(['obs-a']))
    expect(observationUsage(frame!, candidate).condition).toEqual(new Set(['obs-a', 'obs-b']))
    expect(observationChannel(frame!, frame!.observationsById.get('obs-a')!)).toBe('xmv_10')
    expect(chooseSavedPath(normal!.pathsByEdgeId.get('edge-p') ?? [], 'path-c', 'c')).toBeNull()
    expect(normal!.observationsById.has('obs-a')).toBe(false)
  })
  it('keeps unknown separate from false and annotates a non-exhaustive candidate set', () => {
    expect(truthLabel(null)).toBe('未知')
    expect(truthLabel(false)).toBe('不成立')
    expect(valueLabel({ kind: 'candidate_set', items: ['cracked_or_missing_glass'], exhaustive: false })).toBe('开裂或玻璃缺失（开放集合）')
    expect(valueLabel({ kind: 'number', number: 0, unit: '1/sample' })).toBe('0 1/sample')
  })
})
