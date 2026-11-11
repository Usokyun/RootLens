import type { WorkingGraphSummary } from '@/api/contracts'
import type { Dataset, DemoGraphReference, DemoInferenceInput, DemoLibrary, DemoSample, InferenceInput, InputMode, InputVariant, Reasoner, ReasonerId } from '@/api/two-loop'

export const datasetNames: Record<Dataset, string> = { mvtec: '视觉检测（MVTec）', tep: '过程监测（TEP）', wafer: '晶圆图案（Wafer）' }
export interface AnalysisDraftSeed {
  dataset?: Dataset
  graphId?: string
  graphOrigin?: 'implicit' | 'explicit'
  reasonerId?: ReasonerId
  topK?: number
}
export interface AnalysisCatalog {
  graphs: WorkingGraphSummary[]
  reasoners: Reasoner[]
  demos: DemoLibrary | null
}
export interface AnalysisDraft {
  dataset: Dataset
  graphId: string
  graphOrigin: 'implicit' | 'explicit'
  reasonerId: ReasonerId | ''
  variant: InputVariant
  sampleId: string
  file: File | null
  referenceFile: File | null
  title: string
  topK: number
  windows: string
  samplingSeconds: number
  objectName: string
  modelPreset: string
  roiSemantics: boolean
}

export function createAnalysisDraft(seed: AnalysisDraftSeed = {}): AnalysisDraft {
  return {
    dataset: seed.dataset ?? 'mvtec', graphId: seed.graphId ?? '', graphOrigin: seed.graphOrigin ?? 'implicit',
    reasonerId: seed.reasonerId ?? 'unified_abduction', variant: 'raw', sampleId: '', file: null,
    referenceFile: null, title: '', topK: seed.topK ?? 5, windows: '1–100', samplingSeconds: 180,
    objectName: 'bottle', modelPreset: '', roiSemantics: false,
  }
}
export function isAnalysisDataset(value: unknown): value is Dataset {
  return value === 'mvtec' || value === 'tep' || value === 'wafer'
}
export function sampleIdentity(sample: DemoSample) { return sample.sample_id ?? sample.id }
export function enabledAnalysisGraphs(graphs: WorkingGraphSummary[], dataset: Dataset) {
  return graphs.filter((graph) => graph.dataset === dataset && graph.enabled === true && graph.status === 'ready'
    && graph.knowledge?.schema_version === 'rootlens-knowledge-package.v2')
}
export function demoGraphReference(sample: DemoSample | null, library: DemoLibrary | null): DemoGraphReference | null {
  if (!sample) return null
  return sample.graph_ref ?? library?.demos.find((demo) => demo.id === sample.demo_id
    || demo.samples.some((candidate) => sampleIdentity(candidate) === sampleIdentity(sample)))?.graph_ref ?? null
}
export function readyDemoGraph(reference: DemoGraphReference | null, graphs: WorkingGraphSummary[], dataset: Dataset) {
  if (reference?.state !== 'ready' || reference.available !== true || !reference.graph_id) return null
  return enabledAnalysisGraphs(graphs, dataset).find((graph) => graph.graph_id === reference.graph_id) ?? null
}
export function demoGraphUnavailableNote(reference: DemoGraphReference | null) {
  if (!reference) return '未取得样例配套图信息，请重读目录。'
  return reference.note || ({
    disabled: '样例配套图尚未启用。', missing: '尚未导入样例配套图。',
    ambiguous: '存在多张内容相同的配套图，请明确选择。', unavailable: '无法读取样例配套图。',
    ready: '配套图不在当前已启用列表，请重读目录。',
  })[reference.state]
}
export function currentDemoSample(draft: AnalysisDraft, catalog: AnalysisCatalog) {
  return catalog.demos?.samples.find((sample) => sampleIdentity(sample) === draft.sampleId) ?? null
}

export function analysisReasoners(catalog: AnalysisCatalog, dataset: Dataset, graphId: string) {
  const graph = enabledAnalysisGraphs(catalog.graphs, dataset).find(item => item.graph_id === graphId)
  return catalog.reasoners.filter(reasoner => reasoner.datasets.includes(dataset)
    && (reasoner.requires_graded_policy !== true || !!graph?.knowledge?.graded_policy))
}

/** Re-reading metadata changes only the implicit choice; inputs and explicit IDs survive. */
export function reconcileAnalysisSelection(draft: AnalysisDraft, catalog: AnalysisCatalog) {
  const enabled = enabledAnalysisGraphs(catalog.graphs, draft.dataset)
  const sample = currentDemoSample(draft, catalog)
  const paired = readyDemoGraph(demoGraphReference(sample, catalog.demos), catalog.graphs, draft.dataset)
  const graphId = draft.graphOrigin === 'explicit' ? draft.graphId : draft.sampleId ? paired?.graph_id ?? ''
    : enabled.find((graph) => graph.graph_id === draft.graphId)?.graph_id ?? enabled[0]?.graph_id ?? ''
  const compatible = analysisReasoners(catalog, draft.dataset, graphId)
  return { graphId, reasonerId: compatible.some((reasoner) => reasoner.reasoner_id === draft.reasonerId)
    ? draft.reasonerId : compatible[0]?.reasoner_id ?? '' }
}
export function modeForDraft(draft: AnalysisDraft): InputMode {
  return draft.variant === 'evidence' ? 'evidence' : ({ mvtec: 'image', tep: 'process', wafer: 'wafer' } as const)[draft.dataset]
}
export function demoInputAvailable(sample: DemoSample, variant: InputVariant) {
  return variant === 'evidence' ? sample.evidence?.available === true
    : sample.raw_input?.available === true && (sample.dataset !== 'tep' || sample.normal_reference?.available === true)
}
export function parseAnalysisWindows(value: string): [number, number][] {
  const parts = value.split(/[,，;；\n]+/).map((part) => part.trim()).filter(Boolean)
  if (!parts.length) throw new Error('请填写至少一个分析窗口，例如 1–100。')
  return parts.map((part) => {
    const match = part.match(/^(\d+)\s*[-–—:]\s*(\d+)$/)
    const start = Number(match?.[1]), end = Number(match?.[2])
    if (!Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start < 1 || end < start) {
      throw new Error(`窗口“${part}”无效。请使用一基闭区间，例如 1–100。`)
    }
    return [start, end]
  })
}

type AnalysisSubmission = { kind: 'upload'; input: InferenceInput } | { kind: 'demo'; input: DemoInferenceInput }
export function analysisSubmission(draft: AnalysisDraft, catalog: AnalysisCatalog): AnalysisSubmission {
  if (!enabledAnalysisGraphs(catalog.graphs, draft.dataset).some((graph) => graph.graph_id === draft.graphId)) {
    throw new Error('请选择当前场景已启用的 v2 工作图。')
  }
  const reasoner = analysisReasoners(catalog, draft.dataset, draft.graphId).find((item) => item.reasoner_id === draft.reasonerId)
  if (!reasoner) throw new Error('请选择与当前场景和工作图兼容的推理器。')
  if (!Number.isInteger(draft.topK) || draft.topK < 1 || draft.topK > 100) throw new Error('结果条数须为 1–100 的整数。')
  const options = { graph_id: draft.graphId, reasoner_id: reasoner.reasoner_id, top_k: draft.topK }
  if (draft.sampleId) {
    const sample = currentDemoSample(draft, catalog)
    if (!sample || sample.dataset !== draft.dataset || !demoInputAvailable(sample, draft.variant)) {
      throw new Error('该公开样例的所选输入不可用，请重读目录或改用本地文件。')
    }
    return { kind: 'demo', input: { ...options, sample_id: draft.sampleId, input_variant: draft.variant } }
  }
  if (!draft.file?.size) throw new Error('请选择非空的待分析文件。')
  const inputMode = modeForDraft(draft)
  const input: InferenceInput = { ...options, input_mode: inputMode, file: draft.file, dataset: draft.dataset, title: draft.title.trim() || undefined }
  if (inputMode === 'process') {
    if (!draft.referenceFile?.size) throw new Error('TEP 原始序列需要配套的正常参考文件。')
    if (!Number.isFinite(draft.samplingSeconds) || draft.samplingSeconds <= 0) throw new Error('采样间隔须大于 0 秒。')
    input.reference_file = draft.referenceFile
    input.windows = parseAnalysisWindows(draft.windows)
    input.sampling_seconds = draft.samplingSeconds
  } else if (inputMode === 'image') {
    if (!draft.objectName.trim()) throw new Error('请输入后端已配置模型的产品对象。')
    input.object_name = draft.objectName.trim()
    input.model_preset = draft.modelPreset || undefined
    input.semantic_mode = draft.roiSemantics ? 'vlm' : 'disabled'
  }
  return { kind: 'upload', input }
}
