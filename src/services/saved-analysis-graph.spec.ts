import { describe, expect, it } from 'vitest'
import type { PathGraphPath, RunCaseDetail, VisualEvidenceItem } from '@/api/contracts'
import { buildObservationBrowseItems } from './evidence-observation'
import { buildSavedPathProvenance, savedObservationLocation, savedPathForEdge, savedPathObservation, savedPathsForCandidate } from './saved-analysis-graph'

const base = 'http://rootlens.test'

function path(id: string, candidate: string, obsId: string): PathGraphPath {
  return {
    path_id: id, target_key: id, target_entity_id: candidate, supporting_evidence: [obsId],
    nodes: [{ node_id: 'cue', label: '线索', role: 'source' }, { node_id: candidate, label: '同名', role: 'target' }],
    edges: [{ edge_id: 'shared-edge', target_key: 'shared-edge', relation: '实际关系', source_node_id: candidate, target_node_id: 'cue' }],
  }
}

function image(key: string, obsId?: string): VisualEvidenceItem {
  return {
    artifact_id: key, source_key: obsId ? 'roi_path' : key, title: key, case_id: 'frame', dataset: 'mvtec',
    kind: 'image', source_path: null, preview_path: null, url: `/api/analyses/run/artifacts/${key}.png`,
    available: true, note: '', metadata: obsId ? { obs_id: obsId } : {},
  }
}

describe('saved analysis graph inspection', () => {
  it('uses exact candidate, source-edge and observation IDs; does not borrow a different proof', () => {
    const paths = [path('one', 'cause-a', 'obs-a'), path('two', 'cause-b', 'obs-b')]
    const frame = { case_id: 'frame', path_graph: { paths, path_count: 2, edge_count: 1, node_count: 3 } }
    expect(savedPathsForCandidate(frame, 'cause-b')).toEqual([paths[1]])
    expect(savedPathsForCandidate(frame, '同名')).toEqual([])
    expect(savedPathForEdge(frame, 'shared-edge', 'cause-b')?.path_id).toBe('two')
    expect(savedPathForEdge(frame, 'shared-edge', 'cause-b', 'one')?.path_id).toBe('one')
    expect(savedPathForEdge(frame, 'not-saved')).toBeNull()
    expect(savedPathObservation(paths[1], 'obs-a')).toBe('obs-b')
  })

  it('keeps exact ROI pixel coordinates and only relevant saved media', () => {
    const scope = { kind: 'image_region', scope_id: 'scope-a', coordinate_space: 'original_image_pixels', bbox_xyxy: [9.5, 20, 80, 90], image_shape_hw: [100, 110] }
    const caseDetail: RunCaseDetail = {
      case_id: 'frame', dataset: 'mvtec',
      generated_evidence: { observations: [{ obs_id: 'roi-a:cue', facet: 'visual_region', feature_id: 'appearance.semantic_candidates', observation_location: { obs_id: 'roi-a:cue', scope } }] },
      visual_evidence: [image('source_path'), image('heatmap_path'), image('roi-a', 'roi-a'), image('roi-b', 'roi-b')],
    }
    const observation = buildObservationBrowseItems(caseDetail)[0]!
    const location = savedObservationLocation(caseDetail, observation, base)
    expect(location).toMatchObject({ kind: 'image_region', bbox: [9.5, 20, 80, 90], imageShape: [100, 110] })
    expect(location?.kind === 'image_region' && location.media.map(item => item.artifact_id)).toEqual(['roi-a', 'source_path', 'heatmap_path'])
  })

  it('locates the exact channel in the selected window, with original samples and sampling time', () => {
    const caseDetail: RunCaseDetail = {
      case_id: 'frame', dataset: 'tep',
      generated_evidence: { observations: [{ obs_id: 'valve', facet: 'variable', feature_id: 'residual.contribution', observation_location: {
        obs_id: 'valve', subject_external_id: 'xmv_10', scope: { kind: 'time_window', sample_start: 161, sample_end: 163, sampling_seconds: 180 },
      } }] },
      process_trends: [{ channel: 'xmeas_9', samples: [50, 60, 70] }, { channel: 'xmv_10', samples: [20.05, 21, 21.24] }],
    }
    const observation = buildObservationBrowseItems(caseDetail)[0]!
    expect(savedObservationLocation(caseDetail, observation, base)).toMatchObject({
      kind: 'time_window', channel: 'xmv_10', start: 161, end: 163, samplingSeconds: 180, samples: [20.05, 21, 21.24],
    })
    expect(savedObservationLocation({ ...caseDetail, process_trends: [] }, observation, base)).toMatchObject({ samples: null })
  })

  it('shows the saved PDF assertion and actual source edge rather than looking up the current graph', () => {
    const item = path('one', 'cause-a', 'obs-a')
    const frame: RunCaseDetail = {
      case_id: 'frame', path_graph: { paths: [item], path_count: 1, edge_count: 1, node_count: 2 },
      top_k_paths: [{ path_id: 'one', source_assertions: [{ assertion_id: 'saved-source', source_id: 'public-pdf', origin: 'source_explicit', locator: '{"page":13}', text: '原快照断言' }] }],
    }
    expect(buildSavedPathProvenance(frame, 'one', '保存分析', base)?.records).toMatchObject([
      { recordId: 'assertion:saved-source', sourcePathOrId: 'public-pdf · PDF 第 13 页', snippetOrPreview: '原快照断言' },
      { recordId: 'saved-edge:shared-edge', sourcePathOrId: 'shared-edge', snippetOrPreview: 'cause-a → cue' },
    ])
  })
})
