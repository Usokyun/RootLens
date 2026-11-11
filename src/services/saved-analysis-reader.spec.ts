import { afterEach, describe, expect, it, vi } from 'vitest'
import { projectSavedAnalysis, readSavedAnalysis } from './saved-analysis-reader'

const base = 'http://127.0.0.1:8012'
const root = '/api/analyses/run-a'
const frame = (id: string, scope: Record<string, unknown>) => ({
  case_id: id, schema_version: 'rootlens-evidence.v2',
  task: { scope_id: 'scope', target_role: 'mechanism' },
  scopes: [{ scope_id: 'scope', ...scope }], subjects: [], assets: [], references: [], procedures: [],
  observations: [{ obs_id: `obs:${id}`, feature_id: 'residual.contribution', subject_id: 'channel',
    scope_id: 'scope', value: { kind: 'number', number: .12, unit: '1' }, status: 'observed' }],
})

const result = (id: string) => ({
  case_id: id, graph_id: 'saved-graph', outcome: 'ambiguous',
  ranked_root_causes: [{ candidate_id: 'c', rank: 1, score: .5854474293642782, support_obs_ids: [`obs:${id}`] }],
  candidate_evaluations: [{ candidate_id: 'c', scoring_details: { structural_score: .5854474293642782 } }],
  proof_graph: { nodes: [{ node_id: 'c' }], edges: [] },
  top_k_paths: [{
    path_id: `path:${id}`, nodes: ['condition', 'c'], node_names: ['测量', '解释'],
    support_obs_ids: [`obs:${id}`, 'not-from-this-frame'],
    source_edge_views: [{ edge_id: `edge:${id}`, reverse: true }],
  }],
})

function run(cases: unknown[], inputMode = 'evidence') {
  return {
    run_id: 'run-a', title: '保存分析', graph_id: 'saved-graph', input_mode: inputMode, cases,
    evidence_download_url: `${root}/evidence`, working_graph_snapshot: { knowledge: { title: '历史名称' } },
  }
}

const scope = (sample_start: number) => ({ kind: 'time_window', sample_start, sample_end: sample_start + 99 })
const location = (id: string, start: number) => ({ obs_id: `obs:${id}`, scope: { scope_id: 'scope', ...scope(start) }, subject_external_id: 'xmv_10' })
const image = (id: string, url: string, metadata: Record<string, unknown> = {}, source_key = 'source_path') => ({
  artifact_id: id, kind: 'image', url, available: true, metadata, source_key,
})

afterEach(() => vi.unstubAllGlobals())

describe('native saved analysis reader', () => {
  it('joins by exact Frame identity, keeps raw rows, and indexes only selected source edges and observations', () => {
    const early = frame('first', scope(1)), later = frame('later', scope(161))
    const first = { case_id: 'first', graph_id: 'saved-graph', outcome: 'no_match', reason: 'normal_reference_gate_is_false' }
    const second = result('later')
    const raw = run([{ case_id: 'sample', evidence_frames: [early, later], results: [second, first],
      observation_locations: [location('first', 1), location('later', 161)] }])
    const view = projectSavedAnalysis(raw, base)
    expect(view.run).toBe(raw)
    expect(view.frames.map((item) => item.id)).toEqual(['first', 'later'])
    expect(view.framesById.get('missing')).toBeUndefined()
    expect(view.framesById.get('first')?.result).toBe(first)
    expect(view.framesById.get('first')?.pathsByCandidateId.size).toBe(0)
    const selected = view.framesById.get('later')!
    expect(selected.frame).toBe(later)
    expect(selected.result).toBe(second)
    expect(selected.scope?.sample_start).toBe(161)
    expect(selected.locationsByObsId.get('obs:later')?.subject_external_id).toBe('xmv_10')
    expect(selected.locationsByObsId.has('obs:first')).toBe(false)
    expect(selected.candidatesById.get('c')).toBe(second.candidate_evaluations[0])
    const path = selected.pathsById.get('path:later')
    expect(selected.pathsByCandidateId.get('c')).toEqual([path])
    expect(selected.pathsByEdgeId.get('edge:later')).toEqual([path])
    expect(selected.pathsByObsId.get('obs:later')).toEqual([path])
    expect(selected.pathsByObsId.has('not-from-this-frame')).toBe(false)
    expect(path?.edges[0]).toMatchObject({
      edge_id: 'edge:later', source_node_id: 'c', target_node_id: 'condition', relation: '源边（类型未保存）',
    })
  })

  it('exposes a stored curve as inherited without rerunning Backbone and rejects ambiguous sample-level attachment', () => {
    const a = frame('first', scope(1)), b = frame('later', scope(161))
    const process_trends = [{ channel: 'xmv_10', samples: [18, 21] }]
    const single = projectSavedAnalysis(run([{ evidence_frames: [b], results: [result('later')], process_trends }]), base)
    expect(single.backbone).toEqual({ state: 'skipped', inherited: true })
    expect(single.frames[0]?.processTrends).toEqual(process_trends)
    expect(single.frames[0]?.processTrends[0]?.samples).toBe(process_trends[0]?.samples)
    const shared = projectSavedAnalysis(run([{ evidence_frames: [a, b], results: [result('later')], process_trends }]), base)
    expect(shared.frames[0]?.result).toBeNull()
    expect(shared.frames.map((item) => item.processTrends)).toEqual([[], []])
    expect(shared.backbone.inherited).toBe(false)
  })

  it('only resolves managed attachments of this Run and attaches the selected ROI', () => {
    const a = frame('r1', { kind: 'image_region' }), b = frame('r2', { kind: 'image_region' })
    const visual_evidence = [
      image('original', `${root}/artifacts/original.png`),
      image('roi1', `${root}/artifacts/roi1.png`, { obs_id: 'obs:r1' }, 'roi_path'),
      image('roi2', `${root}/artifacts/roi2.png`, { obs_id: 'obs:r2' }, 'roi_path'),
      image('different-run', '/api/analyses/other/artifacts/image.png'),
      image('unmanaged', 'file:///private/tmp/example.png'),
    ]
    const view = projectSavedAnalysis(run([{ evidence_frames: [a, b], results: [result('r1'), result('r2')], visual_evidence }], 'image'), base)
    expect(view.backbone).toEqual({ state: 'measured', inherited: false })
    expect(view.framesById.get('r2')?.media.map((item) => item.artifact_id)).toEqual(['original', 'roi2'])
    expect(view.framesById.get('r2')?.media[0]?.url).toBe(`${base}${root}/artifacts/original.png`)
    expect(view.framesById.get('r2')?.caseDetail?.visual_evidence?.[1]?.url).toBe(`${root}/artifacts/roi2.png`)
    expect(view.evidenceUrl).toBe(`${base}${root}/evidence`)
  })

  it('uses a saved native wafer grid without filling media or results that were not stored', () => {
    const wafer_map = [[0, 1], [1, 2]]
    const a = frame('wafer-a', { kind: 'spatial_grid' })
    const view = projectSavedAnalysis(run([{ evidence_frames: [a], results: [result('wafer-a')], wafer_map }], 'wafer'), base)
    expect(view.frames[0]?.waferGrid).toBe(wafer_map)
    const missing = projectSavedAnalysis({
      ...run([{ evidence_frames: [a], results: [] }], ''), evidence_download_url: '/api/analyses/other/evidence',
    }, base)
    expect(missing.frames[0]).toMatchObject({ result: null, caseDetail: null, waferGrid: null, media: [] })
    expect(missing.evidenceUrl).toBeNull()
    expect(missing.backbone.state).toBe('not_recorded')
  })

  it('rejects unmatched Frame or graph identities instead of substituting another saved result', () => {
    const a = frame('first', scope(1))
    expect(() => projectSavedAnalysis(run([{ evidence_frames: [a], results: [result('other')] }]), base))
      .toThrow('缺少对应 EvidenceFrame')
    expect(() => projectSavedAnalysis(run([{ evidence_frames: [a], results: [{ ...result('first'), graph_id: 'current-kg' }] }]), base))
      .toThrow('保存图身份不一致')
  })

  it('fetches only the requested native analysis and rejects a different returned Run', async () => {
    const raw = run([])
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => raw })
    vi.stubGlobal('fetch', fetch)
    await expect(readSavedAnalysis(base, 'run-a')).resolves.toMatchObject({ run: raw })
    expect(fetch.mock.calls).toEqual([[`${base}${root}`, undefined]])
    await expect(readSavedAnalysis(base, 'another/run')).rejects.toThrow('没有返回请求的保存分析')
    expect(fetch.mock.calls[1]).toEqual([`${base}/api/analyses/another%2Frun`, undefined])
  })
})
