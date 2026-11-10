import { reactive } from 'vue'
import { resolveApiBaseUrl } from '@/api/url'
import type { KGMaterialRecord, KGMaterialChunkRecord, WorkingGraphPackage } from '@/api/contracts'

export type RecordValue = Record<string, unknown>
export type Dataset = 'mvtec' | 'tep' | 'wafer'
export type ReasonerId = 'unified_abduction' | 'tep_rootkgd'
export type InputMode = 'evidence' | 'records' | 'image' | 'process' | 'wafer'
export interface AuthoringFeature {
  feature_id:string; value_kind:'number'|'boolean'|'category'|'candidate_set'|'interval'|'array_ref'
  unit:string|null; definition:string; requires_reference:boolean; allowed_values?:string[]|null
}
export interface AuthoringCapability {
  capability_id:string; features:AuthoringFeature[]; scopes:string[]; zones:string[]; notes:string
  [key:string]:unknown
}
export interface GraphSummary {
  graph_id: string; title: string; dataset: Dataset; status: string; enabled: boolean
  node_count: number; edge_count: number; build_id: string; knowledge?: RecordValue
}
export interface TaskEvent {
  sequence: number; at: string; stage: string; label: string
  completed?: number; total?: number; unit?: string
}
export interface WorkTask {
  task_id: string; kind: 'material_parse' | 'material_build' | 'inference' | string
  status: 'queued' | 'running' | 'completed' | 'failed' | 'interrupted'
  title: string; created_at: string; updated_at: string; stage: string; stage_label: string
  progress: { completed?: number; total?: number; unit?: string; indeterminate?: boolean } | null
  events: TaskEvent[]; result: RecordValue | null
  error: { stage?: string; message: string; type?: string } | null; retry_of?: string | null
}
export interface Reasoner {
  reasoner_id: ReasonerId; title: string; datasets: Dataset[]; description: string
}
export interface DemoAsset {
  path?: string; asset_id?: string; download_url?: string; available?: boolean
  title?: string; media_type?: string; size_bytes?: number; source_url?: string
  [key: string]: unknown
}
export interface DemoGraphReference {
  graph_id:string|null; title:string; state:'ready'|'disabled'|'missing'|'ambiguous'|'unavailable'
  ready:boolean; enabled:boolean; available:boolean; note:string; asset_id:string|null; download_url:string|null
  candidates:Array<{graph_id:string;title:string;ready:boolean;enabled:boolean}>
}
export interface DemoSample {
  sample_id?: string; id: string; title: string; dataset: Dataset; input_mode?: InputMode
  description?: string; expectation?: string; available?: boolean; raw_input?: DemoAsset
  evidence?: DemoAsset; normal_reference?: DemoAsset; raw_options?: RecordValue
  demo_id?: string; source?: string; graph_ref?:DemoGraphReference
  [key: string]: unknown
}
export interface DemoGroup {
  id: string; dataset: Dataset; title: string; purpose: string; capability_id: string
  materials: DemoAsset[]; working_graph: DemoAsset; samples: DemoSample[]; graph_ref?:DemoGraphReference
  sources?: RecordValue[]; models?: RecordValue[]; [key: string]: unknown
}
export interface DemoLibrary { demos: DemoGroup[]; samples: DemoSample[] }
export interface AnalysisSummary {
  run_id: string; title: string; created_at: string; status: string; dataset: Dataset
  input_mode: InputMode; reasoner_id: ReasonerId; graph_id: string; graph_title: string; case_count: number
}
export interface AnalysisCase {
  case_id: string; display_name: string; evidence_frames: RecordValue[]; results: RecordValue[]
  generated_evidence: RecordValue; visual_evidence: RecordValue[]; observation_locations: RecordValue[]
  [key: string]: unknown
}
export interface AnalysisRun extends AnalysisSummary {
  cases: AnalysisCase[]; working_graph_snapshot: RecordValue; artifacts: RecordValue
  [key: string]: unknown
}
export interface InferenceInput {
  file: File; reference_file?: File; graph_id: string; reasoner_id: ReasonerId
  input_mode: InputMode; dataset: Dataset; object_name?: string; model_preset?: string
  semantic_mode?: string; windows?: number[][]; title?: string; top_k?: number
}
export const DEFAULT_BACKEND = import.meta.env.VITE_API_BASE_URL ?? 'http://127.0.0.1:8000'

export const apiConnection = reactive({ available: false, error: '' })

export class ApiError extends Error {
  status: number
  constructor(message: string, status: number) { super(message); this.name = 'ApiError'; this.status = status }
}

export function apiUrl(base: string, path: string) {
  if (/^(data:|blob:|https?:)/.test(path)) return path
  return `${resolveApiBaseUrl(base).replace(/\/+$/, '')}/${path.replace(/^\/+/, '')}`
}

export async function request<T>(base: string, path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try { response = await fetch(apiUrl(base, path), init) }
  catch (error) {
    const detail = error instanceof Error ? error.message : String(error)
    apiConnection.available = false; apiConnection.error = `后端服务不可用：${detail}`
    throw new ApiError(`无法连接后端服务。请确认服务已启动，再重试。${detail ? `（${detail}）` : ''}`, 0)
  }
  apiConnection.available = true; apiConnection.error = ''
  if (!response.ok) {
    const body = await response.text()
    let message = body || `请求失败（${response.status}）`
    try {
      const parsed = JSON.parse(body)
      const detail = parsed.detail ?? parsed.message ?? parsed.error
      message = typeof detail === 'string' ? detail : detail ? JSON.stringify(detail) : message
    } catch { /* Non-JSON failures preserve the server's text. */ }
    throw new ApiError(message, response.status)
  }
  return response.json() as Promise<T>
}
const json = (body: unknown, method = 'POST'): RequestInit => ({
  method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
})

export function workbenchApi(base: string) {
  const get = <T>(path: string) => request<T>(base, path)
  const post = <T>(path: string, body?: unknown) => request<T>(base, path, body === undefined ? { method: 'POST' } : json(body))
  return {
    graphs: () => get<{ graphs: GraphSummary[] }>('/api/kg/working-graphs'),
    graph: (id: string) => get<WorkingGraphPackage>(`/api/kg/working-graphs/${encodeURIComponent(id)}/package`),
    saveGraph: (id: string, body: WorkingGraphPackage) => request<GraphSummary>(base, `/api/kg/working-graphs/${encodeURIComponent(id)}/package`, json(body, 'PUT')),
    importGraph: (body: WorkingGraphPackage) => post<GraphSummary>('/api/kg/working-graphs/import', body),
    enableGraph: (id: string, enabled: boolean) => post<GraphSummary>(`/api/kg/working-graphs/${encodeURIComponent(id)}/enable`, { enabled }),
    authoringCapabilities: () => get<{capabilities:Record<Dataset,AuthoringCapability>}>('/api/authoring/capabilities'),
    reasoners: () => get<{ reasoners: Reasoner[] }>('/api/reasoners'),
    demos: () => get<DemoLibrary>('/api/demo-library'),
    importDemoMaterials: (id: string) => post<{ materials: KGMaterialRecord[] }>(`/api/demo-library/${encodeURIComponent(id)}/materials`),
    materials: () => get<{ materials: KGMaterialRecord[] }>('/api/kg/materials'),
    chunks: (id: string) => get<{ chunks: KGMaterialChunkRecord[] }>(`/api/kg/materials/${encodeURIComponent(id)}/chunks`),
    uploadMaterial: (file: File, fields: { title: string; scenario: string; notes?: string }) => {
      const form = new FormData(); form.append('file', file)
      Object.entries(fields).forEach(([key, value]) => { if (value) form.append(key, value) })
      return request<{ material: KGMaterialRecord }>(base, '/api/kg/materials/upload', { method: 'POST', body: form })
    },
    registerUrl: (body: RecordValue) => post<{ material: KGMaterialRecord }>('/api/kg/materials/register-url', body),
    parseMaterials: (material_ids: string[], force = false) => post<WorkTask>('/api/tasks/material-parse', { material_ids, force }),
    buildGraph: (body: { material_ids: string[]; dataset: Dataset; title: string; capability_id: string; enable_when_ready: boolean; max_repairs?: number }) => post<WorkTask>('/api/tasks/material-build', body),
    tasks: () => get<{ tasks: WorkTask[] }>('/api/tasks?limit=50'),
    task: (id: string) => get<WorkTask>(`/api/tasks/${encodeURIComponent(id)}?after_sequence=0`),
    retryTask: (id: string) => post<WorkTask>(`/api/tasks/${encodeURIComponent(id)}/retry`),
    analyses: () => get<{ runs: AnalysisSummary[] }>('/api/analyses'),
    analysis: (id: string) => get<AnalysisRun>(`/api/analyses/${encodeURIComponent(id)}`),
    infer: (input: InferenceInput) => {
      const form = new FormData()
      Object.entries(input).forEach(([key, value]) => {
        if (value === undefined || value === null || value === '') return
        if (value instanceof File) form.append(key, value)
        else form.append(key, Array.isArray(value) ? JSON.stringify(value) : String(value))
      })
      return request<WorkTask>(base, '/api/tasks/inference', { method: 'POST', body: form })
    },
    inferDemo: (body: { sample_id: string; graph_id: string; reasoner_id: ReasonerId; input_variant: 'raw' | 'evidence'; top_k: number }) => post<WorkTask>('/api/tasks/inference/demo', body),
  }
}
