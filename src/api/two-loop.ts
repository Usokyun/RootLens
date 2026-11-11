import { buildUrl, jsonInit, requestJson } from '@/api/client'
import type { WorkingGraphSummary } from '@/api/contracts'

export type Dataset = WorkingGraphSummary['dataset']
export type ReasonerId = 'unified_abduction' | 'tep_rootkgd'
export type InputMode = 'evidence' | 'records' | 'image' | 'process' | 'wafer'
export type InputVariant = 'raw' | 'evidence'
export type TaskStatus = 'queued' | 'running' | 'completed' | 'failed' | 'interrupted'
export interface TaskEvent {
  sequence: number
  at: string
  stage: string
  label: string
  completed?: number | null
  total?: number | null
  unit?: string | null
}
export interface WorkTask {
  task_id: string
  kind: string
  status: TaskStatus
  title: string
  created_at: string
  updated_at: string
  stage: string
  stage_label: string
  progress: { completed?: number | null; total?: number | null; unit?: string | null; indeterminate?: boolean } | null
  events: TaskEvent[]
  next_sequence?: number
  request?: Record<string, unknown>
  result: Record<string, unknown> | null
  error: { stage?: string; message: string; type?: string } | null
  retry_of?: string | null
}
export interface Reasoner {
  reasoner_id: ReasonerId
  title: string
  datasets: Dataset[]
  description: string
}
export interface AuthoringCapability {
  capability_id: string
  features: Array<Record<string, unknown>>
  [key: string]: unknown
}
export interface DemoAsset {
  asset_id?: string
  path?: string
  title?: string
  available?: boolean
  download_url?: string
  media_type?: string
}
export interface DemoGraphReference {
  graph_id: string | null
  title: string
  state: 'ready' | 'disabled' | 'missing' | 'ambiguous' | 'unavailable'
  ready: boolean
  enabled: boolean
  available: boolean
  note: string
  asset_id: string | null
  download_url: string | null
  candidates: Array<{ graph_id: string; title: string; ready: boolean; enabled: boolean }>
}
export interface DemoSample {
  id: string
  sample_id?: string
  title: string
  dataset: Dataset
  demo_id?: string
  input_mode?: InputMode
  expectation?: string
  recommended?: boolean
  available?: boolean
  raw_input?: DemoAsset
  evidence?: DemoAsset
  normal_reference?: DemoAsset
  raw_options?: Record<string, unknown>
  graph_ref?: DemoGraphReference
}
export interface DemoGroup {
  id: string
  dataset: Dataset
  title: string
  purpose: string
  capability_id: string
  materials: DemoAsset[]
  working_graph: DemoAsset
  samples: DemoSample[]
  graph_ref?: DemoGraphReference
}
export interface DemoLibrary { demos: DemoGroup[]; samples: DemoSample[] }

export interface InferenceInput {
  file: File
  reference_file?: File
  graph_id: string
  reasoner_id: ReasonerId
  input_mode: InputMode
  dataset: Dataset
  object_name?: string
  model_preset?: string
  semantic_mode?: 'disabled' | 'vlm'
  windows?: [number, number][]
  sampling_seconds?: number
  title?: string
  top_k: number
}
export interface DemoInferenceInput {
  sample_id: string
  graph_id: string
  reasoner_id: ReasonerId
  input_variant: InputVariant
  top_k: number
}

/** URLs from the service are already rooted under /api; use the same proxy as JSON requests. */
export function backendResourceUrl(base: string, path: string | null | undefined) {
  return path?.startsWith('/api/') ? buildUrl(base, path) : null
}

export function createTwoLoopClient(base: string) {
  const get = <T>(path: string, query?: URLSearchParams) => requestJson<T>(base, path, undefined, query)
  return {
    task: (id: string, afterSequence = 0) => get<WorkTask>(
      `/api/tasks/${encodeURIComponent(id)}`,
      new URLSearchParams({ after_sequence: String(afterSequence) }),
    ),
    listTasks: (limit = 50) => get<{ tasks: WorkTask[] }>('/api/tasks', new URLSearchParams({ limit: String(limit) })),
    retryTask: (id: string) => requestJson<WorkTask>(base, `/api/tasks/${encodeURIComponent(id)}/retry`, { method: 'POST' }),
    demos: () => get<DemoLibrary>('/api/demo-library'),
    reasoners: () => get<{ reasoners: Reasoner[] }>('/api/reasoners'),
    authoringCapabilities: () => get<{ capabilities: Record<Dataset, AuthoringCapability> }>('/api/authoring/capabilities'),
    infer: ({ file, reference_file, ...options }: InferenceInput) => {
      const form = new FormData()
      form.append('file', file)
      if (reference_file) form.append('reference_file', reference_file)
      for (const [key, value] of Object.entries(options)) {
        if (value === undefined || value === '') continue
        form.append(key, Array.isArray(value) ? JSON.stringify(value) : String(value))
      }
      return requestJson<WorkTask>(base, '/api/tasks/inference', { method: 'POST', body: form })
    },
    inferDemo: (input: DemoInferenceInput) => requestJson<WorkTask>(base, '/api/tasks/inference/demo', jsonInit('POST', input)),
  }
}

export type TaskClient = Pick<ReturnType<typeof createTwoLoopClient>, 'task' | 'retryTask'>
