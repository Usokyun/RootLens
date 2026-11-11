// @vitest-environment jsdom
import { Button, Tag } from '@arco-design/web-vue'
import { createApp, h, nextTick, ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import { projectSavedAnalysis } from '@/services/saved-analysis-reader'
import { isSavedGradedResult } from '@/services/unified-reasoning-display'
import SavedRunGraded from './SavedRunGraded.vue'
import { gradedCandidateGroups, gradedConditionRows, gradedScore, gradedUnranked } from './graded-presentation'

const actual = { kind: 'number', number: 0.94, unit: '1' }
const pending = {
  candidate_id: 'slender', candidate_name: '待核验形态', rank: 1, status: 'pending',
  scoring_details: { support: 0.75, conflict: 0.25, score: 0.5, coverage: 1 },
  graded_conditions: [
    { predicate_id: 'eccentricity', rule_id: 'expected-shape', label: '主轴离心率', feature_id: 'geometry.eccentricity',
      obs_ids: ['obs:ecc', 'outside-frame'], actual_values: [actual], slot_id: 'eccentricity',
      status: 'conflicting', support: 0, conflict: 0.5, weight: 0.5, score_contribution: -0.25 },
    { predicate_id: 'outline', rule_id: 'expected-shape', label: '参考轮廓', feature_id: 'geometry.outline',
      obs_ids: [], actual_values: [], slot_id: 'outline', status: 'unknown', support: null, conflict: null, weight: 0.3, score_contribution: 0 },
  ],
}
const supported = { ...pending, candidate_id: 'block', candidate_name: '有支持形态', status: 'supported',
  graded_conditions: [], scoring_details: { support: 0.5, conflict: 0, score: 0.5, coverage: 1 } }
const path = {
  path_id: 'conflict-path', path_kind: 'graded_contribution', contribution_kind: 'conflict', predicate_id: 'eccentricity',
  rule_id: 'expected-shape', candidate_id: 'slender', nodes: ['eccentricity', 'slender'], joint_proof_id: null,
  source_edge_views: [{ edge_id: 'actual-source-edge', reverse: true }],
  source_edges: [{ edge_id: 'actual-source-edge', head: 'slender', tail: 'eccentricity', relation: 'requires' }],
  observation_ids: ['obs:ecc'], support_obs_ids: [], counter_obs_ids: ['obs:ecc'],
}
const candidateEvaluations = [supported, pending, { ...pending, candidate_id: 'insufficient', status: 'insufficient_evidence' }]
const result = { case_id: 'frame', scoring_method: 'graded_joint_abduction_v1', graded_candidates: [supported, pending],
  ranked_root_causes: [supported], candidate_evaluations: candidateEvaluations,
  top_k_paths: [{ ...path, path_id: 'different-rule-path', rule_id: 'other-rule' }, path],
}
function frame(row: Record<string, unknown> = result) {
  return projectSavedAnalysis({ run_id: 'demo', input_mode: 'evidence', cases: [{ case_id: 'case', results: [row], evidence_frames: [
    { case_id: 'frame', task: { scope_id: 'roi' }, subjects: [], scopes: [{ scope_id: 'roi', kind: 'image_region' }],
      assets: [], procedures: [], references: [],
      observations: [{ obs_id: 'obs:ecc', status: 'observed', value: actual, feature_id: 'geometry.eccentricity', scope_id: 'roi' }],
    },
  ] }] }, 'http://localhost:8027').frames[0]!
}

describe('graded saved-result display', () => {
  it('keeps equal saved S in separate groups, never derives it from another engine, and skips normal windows', () => {
    const grouped = gradedCandidateGroups(result)
    expect(grouped).toEqual({ supported: [supported], pending: [pending] })
    expect(gradedScore(grouped.supported[0]!).score).toBe(gradedScore(grouped.pending[0]!).score)
    const root = { ...result, scoring_method: 'tep_rootkgd_propagation_v2' }
    expect(isSavedGradedResult(root)).toBe(false)
    expect(gradedCandidateGroups(root)).toEqual({ supported: [], pending: [] })
    expect(gradedUnranked({ ...result, reason: 'anomaly_gate_is_false' })).toEqual([])
    expect(gradedUnranked(result).map(row => row.candidate_id)).toEqual(['insufficient'])
  })

  it('links a saved negative observation to the exact rule and source edge; no fabricated missing-measurement path', () => {
    const saved = frame()
    const [measured, missing] = gradedConditionRows(saved, pending)
    expect(measured?.observations.map(({ id, focus }) => ({ id, focus }))).toEqual([{
      id: 'obs:ecc', focus: { pathId: 'conflict-path', edgeId: 'actual-source-edge', obsId: 'obs:ecc' },
    }])
    expect(missing?.observations).toEqual([])
    expect(saved.pathsByObsId.get('obs:ecc')?.map(row => row.path_id)).toContain('conflict-path')
    expect(saved.pathsById.get('conflict-path')?.edges[0]).toMatchObject({
      edge_id: 'actual-source-edge', source_node_id: 'slender', target_node_id: 'eccentricity',
    })
  })

  it('lets the user select a pending candidate, click its negative observation and open that same source edge', async () => {
    const chosen = ref<typeof pending | null>(null)
    const saved = frame(), onGraph = vi.fn(), onObservation = vi.fn()
    const host = document.createElement('div')
    document.body.append(host)
    const app = createApp({ render: () => h(SavedRunGraded, {
      frame: saved, candidate: chosen.value, pathId: '', observationId: '',
      onCandidate: (id: string) => { if (id === pending.candidate_id) chosen.value = pending },
      onGraph, onObservation,
    }) })
    app.use(Button).use(Tag).mount(host)
    try {
      host.querySelector<HTMLButtonElement>('[aria-label="待核验"] [data-candidate-id="slender"]')!.click()
      await nextTick()
      expect(host.querySelector('[data-graded-score="S"]')?.textContent).toBe('0.5')
      expect(host.querySelector('[data-graded-score="C"]')?.textContent).toBe('0.25')
      expect(host.querySelector('[data-predicate-id="eccentricity"] .graded-delta')?.textContent).toBe('−0.25')
      const focus = { pathId: 'conflict-path', edgeId: 'actual-source-edge', obsId: 'obs:ecc' }
      host.querySelector<HTMLButtonElement>('button[data-observation-id="obs:ecc"]')!.click()
      expect(onObservation).toHaveBeenCalledWith('obs:ecc', focus)
      host.querySelector<HTMLButtonElement>('button[data-graded-path-id="conflict-path"]')!.click()
      expect(onGraph).toHaveBeenCalledWith(focus)
      expect(host.querySelector('[data-predicate-id="outline"] button')).toBeNull()
    } finally {
      app.unmount()
      host.remove()
    }
  })
})
