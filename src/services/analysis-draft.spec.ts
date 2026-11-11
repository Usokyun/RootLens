import { describe, expect, it } from 'vitest'
import type { WorkingGraphSummary } from '@/api/contracts'
import type { Dataset, DemoGraphReference, DemoSample } from '@/api/two-loop'
import { analysisSubmission, createAnalysisDraft, demoGraphReference, modeForDraft, parseAnalysisWindows, reconcileAnalysisSelection, type AnalysisCatalog } from '@/services/analysis-draft'

function graph(id: string, dataset: Dataset = 'mvtec', enabled = true): WorkingGraphSummary {
  return { graph_id: id, title: id, dataset, enabled, status: 'ready', build_id: 'b', node_count: 1, edge_count: 1,
    knowledge: { schema_version: 'rootlens-knowledge-package.v2' } }
}
function reference(state: DemoGraphReference['state'] = 'ready'): DemoGraphReference {
  return { graph_id: 'paired', title: '配套工作图', state, enabled: true, ready: true, available: true, note: '', asset_id: null, download_url: null, candidates: [] }
}
function sample(graphRef: DemoGraphReference | undefined = reference()): DemoSample {
  return { id: 'sample', title: '实际样本', dataset: 'mvtec', evidence: { available: true }, raw_input: { available: true }, graph_ref: graphRef }
}
function catalog(samples = [sample()]): AnalysisCatalog {
  return { graphs: [graph('strict-latest'), graph('paired'), graph('tep', 'tep'), graph('wafer', 'wafer')],
    reasoners: [{ reasoner_id: 'unified_abduction', title: '统一', datasets: ['mvtec', 'tep', 'wafer'], description: '' },
      { reasoner_id: 'tep_rootkgd', title: 'RootKGD', datasets: ['tep'], description: '' }],
    demos: { demos: [], samples } }
}

describe('analysis selection is independent from result history', () => {
  it('uses only the actual paired graph for an implicitly selected sample, not latest enabled', () => {
    const draft = { ...createAnalysisDraft({ graphId: 'strict-latest' }), sampleId: 'sample', variant: 'evidence' as const }
    expect(reconcileAnalysisSelection(draft, catalog()).graphId).toBe('paired')
  })
  it('keeps a graph-page or manual explicit choice through example loading and late catalog refresh', () => {
    const file = new File(['{"frames":[]}'], 'original-frame.json')
    const draft = { ...createAnalysisDraft({ graphId: 'strict-latest', graphOrigin: 'explicit' }), file, variant: 'evidence' as const }
    Object.assign(draft, reconcileAnalysisSelection(draft, catalog()))
    expect(draft.file).toBe(file)
    expect(draft.variant).toBe('evidence')
    draft.sampleId = 'sample'
    expect(reconcileAnalysisSelection(draft, catalog()).graphId).toBe('strict-latest')
  })
  it('does not silently substitute another graph for missing or disabled demo knowledge', () => {
    const draft = { ...createAnalysisDraft({ graphId: 'strict-latest' }), sampleId: 'sample' }
    expect(reconcileAnalysisSelection(draft, catalog([sample(reference('missing'))])).graphId).toBe('')
    const stale = catalog()
    stale.graphs[1] = graph('paired', 'mvtec', false)
    expect(reconcileAnalysisSelection(draft, stale).graphId).toBe('')
  })
  it('does not let a cross-scene sample invalidate the stored explicit choice or actually run the wrong graph', () => {
    const draft = createAnalysisDraft({ dataset: 'tep', graphId: 'paired', graphOrigin: 'explicit', reasonerId: 'tep_rootkgd' })
    expect(reconcileAnalysisSelection(draft, catalog())).toEqual({ graphId: 'paired', reasonerId: 'tep_rootkgd' })
    expect(() => analysisSubmission(draft, catalog())).toThrow('当前场景已启用')
  })
  it('takes a supplied sample reference before its group and reads group only by the manifest identity', () => {
    const a = sample()
    const own = reference('ambiguous')
    a.graph_ref = own
    const library = { samples: [a], demos: [{ id: 'glass', dataset: 'mvtec' as const, title: '玻璃', purpose: '', capability_id: 'v2', materials: [], working_graph: {}, samples: [a], graph_ref: reference() }] }
    expect(demoGraphReference(a, library)).toBe(own)
    a.graph_ref = undefined
    expect(demoGraphReference(a, library)).toEqual(reference())
  })
})

describe('original samples and native Frame submission', () => {
  it('keeps raw TEP reference and exact windows, and checks the one-based contract', () => {
    const file = new File(['actual series'], 'd04.dat'), referenceFile = new File(['normal'], 'd00.dat')
    const draft = { ...createAnalysisDraft({ dataset: 'tep', graphId: 'tep', reasonerId: 'tep_rootkgd' }), file, windows: '1–100，161-260' }
    expect(() => analysisSubmission(draft, catalog())).toThrow('配套的正常参考')
    expect(analysisSubmission({ ...draft, referenceFile }, catalog())).toMatchObject({ kind: 'upload', input: { file, reference_file: referenceFile,
      input_mode: 'process', reasoner_id: 'tep_rootkgd', windows: [[1, 100], [161, 260]], sampling_seconds: 180 } })
    expect(() => parseAnalysisWindows('0–100')).toThrow('一基闭区间')
    expect(() => parseAnalysisWindows('101–100')).toThrow('一基闭区间')
  })
  it('keeps ordinary MVTec ROI semantics off by default and only enables it by an explicit toggle', () => {
    const draft = { ...createAnalysisDraft({ graphId: 'paired' }), file: new File(['image bytes'], 'sample.png') }
    expect(analysisSubmission(draft, catalog())).toMatchObject({ input: { input_mode: 'image', object_name: 'bottle', semantic_mode: 'disabled' } })
    expect(analysisSubmission({ ...draft, roiSemantics: true }, catalog())).toMatchObject({ input: { semantic_mode: 'vlm' } })
  })
  it('does not put any raw reference, window or ROI model options on an ordinary Evidence re-upload', () => {
    const file = new File(['{"frames":[{}]}'], 'evidence-frames.json')
    const draft = { ...createAnalysisDraft({ dataset: 'tep', graphId: 'tep', topK: 8, reasonerId: 'tep_rootkgd' }), file, variant: 'evidence' as const }
    const submission = analysisSubmission(draft, catalog())
    expect(submission.input).toEqual({ file, graph_id: 'tep', reasoner_id: 'tep_rootkgd', top_k: 8, input_mode: 'evidence', dataset: 'tep', title: undefined })
  })
  it('keeps native Wafer mode and excludes the incompatible TEP-only engine', () => {
    const draft = { ...createAnalysisDraft({ dataset: 'wafer', graphId: 'wafer', reasonerId: 'tep_rootkgd' }), file: new File(['{"waferMap":[[0,1,2]]}\n'], 'wafer.jsonl') }
    expect(modeForDraft(draft)).toBe('wafer')
    expect(() => analysisSubmission(draft, catalog())).toThrow('兼容的推理器')
    Object.assign(draft, reconcileAnalysisSelection(draft, catalog()))
    expect(analysisSubmission(draft, catalog())).toMatchObject({ input: { input_mode: 'wafer', reasoner_id: 'unified_abduction' } })
  })
  it('requires an explicit eligible work graph for graded runs, without changing the old default', () => {
    const loaded = catalog()
    loaded.reasoners.push({ reasoner_id: 'graded_abduction', title: '分级', datasets: ['wafer'], description: '', requires_graded_policy: true })
    loaded.graphs.push({ ...graph('graded', 'wafer'), knowledge: { schema_version: 'rootlens-knowledge-package.v2', graded_policy: { groups: [{}] } } })
    const draft = { ...createAnalysisDraft({ dataset: 'wafer', graphId: 'wafer', reasonerId: 'graded_abduction' }), file: new File(['actual'], 'wafer.jsonl') }
    expect(() => analysisSubmission(draft, loaded)).toThrow('兼容的推理器')
    draft.graphId = 'graded'
    expect(analysisSubmission(draft, loaded)).toMatchObject({ input: { graph_id: 'graded', reasoner_id: 'graded_abduction' } })
    expect(reconcileAnalysisSelection({ ...draft, reasonerId: 'unified_abduction' }, loaded).reasonerId).toBe('unified_abduction')
  })
})
