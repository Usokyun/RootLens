import { describe, expect, it } from 'vitest'
import type { WorkingGraphSummary } from '@/api/contracts'
import type { Dataset, DemoGraphReference, DemoSample } from '@/api/two-loop'
import {
  analysisSubmission, canInstallDemoGraph, createAnalysisDraft, demoAnalysisSeed, modeForDraft, parseAnalysisWindows,
  reconcileAnalysisSelection, type AnalysisCatalog,
} from './analysis-draft'

function graph(id: string, dataset: Dataset = 'mvtec', enabled = true, graded = true): WorkingGraphSummary {
  return { graph_id: id, title: id, dataset, enabled, status: 'ready', build_id: 'b', node_count: 1, edge_count: 1,
    knowledge: { schema_version: 'rootlens-knowledge-package.v2', ...(graded ? { graded_policy: { groups: [{}] } } : {}) } }
}
function reference(graph_id: string, state: DemoGraphReference['state'] = 'ready'): DemoGraphReference {
  return { graph_id, title: '配套工作图', state, enabled: state === 'ready', ready: state === 'ready', available: state === 'ready',
    note: '', asset_id: null, download_url: null, candidates: [] }
}
function sample(graphRef?: DemoGraphReference): DemoSample {
  return { sample_id: 'tep-d04-graded', demo_id: 'tep-graded', title: '真实过程窗口', dataset: 'tep',
    evidence: { available: true }, raw_input: { available: true }, normal_reference: { available: true }, graph_ref: graphRef }
}
function catalog(samples = [sample(reference('tep-paired'))]): AnalysisCatalog {
  return { graphs: [graph('mvtec'), graph('tep-unpaired', 'tep'), graph('tep-paired', 'tep'), graph('wafer', 'wafer')],
    reasoners: [{ reasoner_id: 'tep_rootkgd', title: 'RootKGD', datasets: ['tep'], description: '' },
      { reasoner_id: 'graded_abduction', title: '分级', datasets: ['mvtec', 'tep', 'wafer'], description: '', requires_graded_policy: true }],
    demos: { demos: [], samples } }
}

describe('demo identity and explicit graph installation', () => {
  it('opens the exact current sample as Evidence and prefers graded analysis even when RootKGD is listed first', () => {
    const target = sample(reference('tep-paired'))
    const draft = createAnalysisDraft(demoAnalysisSeed(target))
    Object.assign(draft, reconcileAnalysisSelection(draft, catalog([target])))
    expect(analysisSubmission(draft, catalog([target]))).toEqual({
      kind: 'demo', input: { graph_id: 'tep-paired', reasoner_id: 'graded_abduction', top_k: 8, sample_id: target.sample_id, input_variant: 'evidence' },
    })
  })
  it('keeps a sample and its variant during a missing-to-ready catalog refresh, without silently using the latest graph', () => {
    const target = sample(reference('tep-paired', 'missing'))
    const draft = createAnalysisDraft(demoAnalysisSeed(target))
    Object.assign(draft, reconcileAnalysisSelection(draft, catalog([target])))
    expect(draft).toMatchObject({ graphId: '', reasonerId: '', sampleId: target.sample_id, variant: 'evidence' })
    expect(canInstallDemoGraph(target)).toBe(true)
    expect(() => analysisSubmission(draft, catalog([target]))).toThrow('当前场景已启用')

    const afterInstall = catalog()
    Object.assign(draft, reconcileAnalysisSelection(draft, afterInstall))
    expect(draft).toMatchObject({ graphId: 'tep-paired', reasonerId: 'graded_abduction', sampleId: target.sample_id, variant: 'evidence' })
  })
  it('does not replace an explicitly chosen graph, variant or file when the paired graph becomes ready', () => {
    const file = new File(['{"frames":[]}'], 'native-evidence.json')
    const draft = { ...createAnalysisDraft({ graphId: 'tep-unpaired', graphOrigin: 'explicit', dataset: 'tep', variant: 'evidence' }), file }
    Object.assign(draft, reconcileAnalysisSelection(draft, catalog()))
    expect(draft.file).toBe(file)
    draft.sampleId = 'tep-d04-graded'
    Object.assign(draft, reconcileAnalysisSelection(draft, catalog([sample(reference('tep-paired', 'disabled'))])))
    Object.assign(draft, reconcileAnalysisSelection(draft, catalog()))
    expect(draft).toMatchObject({ graphId: 'tep-unpaired', variant: 'evidence', sampleId: 'tep-d04-graded' })
    expect(analysisSubmission(draft, catalog()).input.graph_id).toBe('tep-unpaired')
  })
  it('offers installation only for missing or disabled packages and never guesses an ambiguous graph', () => {
    for (const state of ['missing', 'disabled', 'ambiguous', 'unavailable', 'ready'] as const) {
      expect(canInstallDemoGraph(sample(reference('tep-paired', state)))).toBe(state === 'missing' || state === 'disabled')
    }
    expect(canInstallDemoGraph(sample())).toBe(false)
    const draft = createAnalysisDraft(demoAnalysisSeed(sample()))
    expect(reconcileAnalysisSelection(draft, catalog([sample(reference('tep-paired', 'ambiguous'))])).graphId).toBe('')
    const stale = catalog()
    stale.graphs[2] = graph('tep-paired', 'tep', false)
    expect(reconcileAnalysisSelection(draft, stale).graphId).toBe('')
  })
  it('holds a cross-scene explicit selection until the user picks an eligible graph', () => {
    const draft = createAnalysisDraft({ dataset: 'tep', graphId: 'mvtec', graphOrigin: 'explicit', reasonerId: 'tep_rootkgd' })
    expect(reconcileAnalysisSelection(draft, catalog())).toEqual({ graphId: 'mvtec', reasonerId: '' })
    expect(() => analysisSubmission(draft, catalog())).toThrow('当前场景已启用')
  })
})

describe('native sample and Frame submissions', () => {
  it('keeps raw TEP reference and exact windows, and checks the one-based contract', () => {
    const file = new File(['actual series'], 'd04.dat'), referenceFile = new File(['normal'], 'd00.dat')
    const draft = { ...createAnalysisDraft({ dataset: 'tep', graphId: 'tep-paired', reasonerId: 'tep_rootkgd' }), file, windows: '1–100，161-260' }
    expect(() => analysisSubmission(draft, catalog())).toThrow('配套的正常参考')
    expect(analysisSubmission({ ...draft, referenceFile }, catalog())).toMatchObject({ kind: 'upload', input: { file, reference_file: referenceFile,
      input_mode: 'process', reasoner_id: 'tep_rootkgd', windows: [[1, 100], [161, 260]], sampling_seconds: 180 } })
    expect(() => parseAnalysisWindows('0–100')).toThrow('一基闭区间')
    expect(() => parseAnalysisWindows('101–100')).toThrow('一基闭区间')
  })
  it('defaults to grading, leaves ordinary MVTec ROI semantics off and requires an explicit toggle to enable it', () => {
    const draft = { ...createAnalysisDraft({ graphId: 'mvtec' }), file: new File(['image bytes'], 'sample.png') }
    expect(analysisSubmission(draft, catalog())).toMatchObject({ input: { input_mode: 'image', object_name: 'bottle',
      reasoner_id: 'graded_abduction', semantic_mode: 'disabled' } })
    expect(analysisSubmission({ ...draft, roiSemantics: true }, catalog())).toMatchObject({ input: { semantic_mode: 'vlm' } })
  })
  it('does not put raw reference, window or ROI options on an ordinary Evidence re-upload', () => {
    const file = new File(['{"frames":[{}]}'], 'evidence-frames.json')
    const draft = { ...createAnalysisDraft({ dataset: 'tep', graphId: 'tep-paired', topK: 8, reasonerId: 'tep_rootkgd' }), file, variant: 'evidence' as const }
    expect(analysisSubmission(draft, catalog()).input).toEqual({ file, graph_id: 'tep-paired', reasoner_id: 'tep_rootkgd',
      top_k: 8, input_mode: 'evidence', dataset: 'tep', title: undefined })
  })
  it('keeps native Wafer mode, excludes RootKGD, and does not submit to an ungraded graph', () => {
    const draft = { ...createAnalysisDraft({ dataset: 'wafer', graphId: 'wafer', reasonerId: 'tep_rootkgd' }), file: new File(['{"waferMap":[[0,1,2]]}'], 'wafer.jsonl') }
    expect(modeForDraft(draft)).toBe('wafer')
    expect(() => analysisSubmission(draft, catalog())).toThrow('兼容的推理器')
    Object.assign(draft, reconcileAnalysisSelection(draft, catalog()))
    expect(analysisSubmission(draft, catalog())).toMatchObject({ input: { input_mode: 'wafer', reasoner_id: 'graded_abduction' } })
    const ungraded = catalog()
    ungraded.graphs[3] = graph('wafer', 'wafer', true, false)
    expect(() => analysisSubmission(draft, ungraded)).toThrow('兼容的推理器')
  })
})
