import { requestJson } from '@/api/client'
import type { PathGraph, PathGraphPath, VisualEvidenceItem } from '@/api/contracts'
import { backendResourceUrl } from '@/api/two-loop'
import { traceRecord, traceRows, type TraceRecord } from './unified-reasoning-display'

export type SavedAnalysisRun = TraceRecord & {
  run_id: string
  title?: string
  created_at?: string
  status?: string
  dataset?: string
  input_mode?: string
  reasoner_id?: string
  graph_id?: string
  graph_title?: string
  source_filename?: string
  input_snapshot?: TraceRecord
  working_graph_snapshot?: TraceRecord
}

export type SavedEvidenceFrame = TraceRecord & {
  case_id: string
  task: TraceRecord
  subjects: TraceRecord[]
  scopes: TraceRecord[]
  assets: TraceRecord[]
  procedures: TraceRecord[]
  references: TraceRecord[]
  observations: TraceRecord[]
}

export type SavedReasoningResult = TraceRecord & {
  case_id: string
  outcome?: string
  reason?: string
  scoring_method?: string
  ranked_root_causes?: TraceRecord[]
  candidate_evaluations?: TraceRecord[]
  grounded_facts?: TraceRecord[]
  top_k_paths?: TraceRecord[]
  proof_graph?: TraceRecord
}

export interface SavedProcessTrend {
  channel: string
  samples: number[]
}

export interface SavedAnalysisFrame {
  id: string
  label: string
  sampleId: string
  frame: SavedEvidenceFrame
  result: SavedReasoningResult | null
  scope: TraceRecord | null
  pathGraph: PathGraph
  media: VisualEvidenceItem[]
  processTrends: SavedProcessTrend[]
  waferGrid: number[][] | null
  locationsByObsId: ReadonlyMap<string, TraceRecord>
  observationsById: ReadonlyMap<string, TraceRecord>
  candidatesById: ReadonlyMap<string, TraceRecord>
  pathsById: ReadonlyMap<string, PathGraphPath>
  pathsByCandidateId: ReadonlyMap<string, readonly PathGraphPath[]>
  pathsByEdgeId: ReadonlyMap<string, readonly PathGraphPath[]>
  pathsByObsId: ReadonlyMap<string, readonly PathGraphPath[]>
}

export interface SavedAnalysis {
  run: SavedAnalysisRun
  frames: SavedAnalysisFrame[]
  framesById: ReadonlyMap<string, SavedAnalysisFrame>
  evidenceUrl: string | null
  backbone: {
    state: 'measured' | 'skipped' | 'not_recorded'
    /** Reusing an attached image, grid or curve does not execute the Backbone. */
    inherited: boolean
  }
}

function text(value: unknown) {
  return typeof value === 'string' && value ? value : null
}

function index(rows: TraceRecord[], key: string) {
  return new Map(rows.flatMap((row): [string, TraceRecord][] => {
    const id = text(row[key])
    return id ? [[id, row]] : []
  }))
}

function byPathKeys(paths: PathGraphPath[], keys: (path: PathGraphPath) => readonly unknown[]) {
  const grouped = new Map<string, PathGraphPath[]>()
  for (const path of paths) {
    for (const key of new Set(keys(path))) {
      if (typeof key !== 'string' || !key) continue
      const existing = grouped.get(key)
      if (existing) existing.push(path)
      else grouped.set(key, [path])
    }
  }
  return grouped
}

function strings(value: unknown): string[] {
  return Array.isArray(value) ? value.filter((item): item is string => typeof item === 'string') : []
}

/** Project only paths and directions saved in this result. The working graph is never queried. */
function savedPaths(result: SavedReasoningResult | null): PathGraph {
  const owners = new Map<string, Set<string>>()
  for (const row of [...traceRows(result?.ranked_root_causes), ...traceRows(result?.graded_candidates)]) {
    const candidate = text(row.candidate_id)
    if (!candidate) continue
    for (const path of traceRows(row.explanation_paths)) {
      const id = text(path.path_id)
      if (!id) continue
      const ids = owners.get(id) ?? new Set<string>()
      ids.add(candidate)
      owners.set(id, ids)
    }
  }
  const names = traceRecord(result?.display_labels)
  const paths = traceRows(result?.top_k_paths).map((path): PathGraphPath => {
    const id = text(path.path_id) ?? ''
    const nodes = strings(path.nodes)
    const labels = strings(path.node_names)
    const known = owners.get(id)
    const target = text(path.candidate_id) ?? (known?.size === 1 ? [...known][0] : null)
    const source = nodes[0] === target ? nodes.at(-1) : nodes[0]
    const views = traceRows(path.source_edge_views)
    const originals = index(traceRows(path.source_edges), 'edge_id')
    if (views.length && views.length !== Math.max(0, nodes.length - 1)) {
      throw new Error(`保存路径 ${id} 的源边与节点数量不一致。`)
    }
    const edges = views.map((view, i) => {
      const edgeId = text(view.edge_id)
      const head = view.reverse === true ? nodes[i + 1] : nodes[i]
      const tail = view.reverse === true ? nodes[i] : nodes[i + 1]
      const original = edgeId ? originals.get(edgeId) : undefined
      if (!edgeId || typeof view.reverse !== 'boolean' || !head || !tail || (original && (original.head !== head || original.tail !== tail))) {
        throw new Error(`保存路径 ${id} 的源边与原方向不一致。`)
      }
      return {
        edge_id: edgeId, target_key: edgeId, source_node_id: head, target_node_id: tail,
        relation: text(original?.relation) ?? '源边（类型未保存）',
        source: text(original?.source), evidence: text(original?.evidence), review_status: text(original?.review_status),
        confidence: typeof original?.confidence === 'number' ? original.confidence : null,
      }
    })
    return {
      path_id: id, target_key: id, target_entity_id: target, source_entity_id: source,
      score: typeof path.score === 'number' ? path.score : null,
      confidence: typeof path.confidence === 'number' ? path.confidence : null,
      supporting_evidence: strings(path.path_kind === 'graded_contribution' ? path.observation_ids : path.support_obs_ids),
      nodes: nodes.map((node, i) => ({
        node_id: node, label: labels[i] ?? text(names[node]) ?? node,
        role: node === target ? 'target' : node === source ? 'source' : 'intermediate',
      })),
      edges,
    }
  })
  return {
    paths, path_count: paths.length,
    node_count: new Set(paths.flatMap(path => path.nodes.map(node => node.node_id))).size,
    edge_count: new Set(paths.flatMap(path => path.edges.map(edge => edge.edge_id))).size,
  }
}

function savedCurves(value: unknown): SavedProcessTrend[] {
  return traceRows(value).flatMap((row) => {
    const channel = text(row.channel)
    return channel && Array.isArray(row.samples) && row.samples.length && row.samples.every(Number.isFinite)
      ? [{ channel, samples: row.samples as number[] }]
      : []
  })
}

function savedGrid(value: unknown): number[][] | null {
  if (!Array.isArray(value) || !value.length || !Array.isArray(value[0]) || !value[0].length) return null
  const width = value[0].length
  return value.every((row) => Array.isArray(row) && row.length === width
    && row.every((cell) => cell === 0 || cell === 1 || cell === 2)) ? value as number[][] : null
}

function frameProjection(
  frame: SavedEvidenceFrame,
  result: SavedReasoningResult | null,
  outer: TraceRecord,
  frameCount: number,
  frameIndex: number,
  baseUrl: string,
  runPath: string,
): SavedAnalysisFrame {
  const id = frame.case_id
  const scope = traceRows(frame.scopes).find((s) => s.scope_id === traceRecord(frame.task).scope_id) ?? null
  const observationsById = index(traceRows(frame.observations), 'obs_id')
  const locationsByObsId = index(traceRows(outer.observation_locations)
    .filter((location) => typeof location.obs_id === 'string' && observationsById.has(location.obs_id)), 'obs_id')
  // Curves/grid currently live on the enclosing sample without a separate Frame
  // key. Do not attribute a sample-level payload to several different windows.
  const processTrends = frameCount === 1 && scope?.kind === 'time_window' ? savedCurves(outer.process_trends) : []
  const waferGrid = frameCount === 1 && scope?.kind === 'spatial_grid' ? savedGrid(outer.wafer_map) : null
  const attachedMedia = result ? traceRows(outer.visual_evidence).filter(item => {
    if (item.available !== true || !text(item.url)?.startsWith(`${runPath}/artifacts/`)) return false
    const meta = traceRecord(item.metadata)
    if (meta.scope_id && meta.scope_id !== scope?.scope_id) return false
    if (item.source_key !== 'roi_path') return true
    const linked = text(meta.obs_id)
    return linked ? [...observationsById.keys()].some(id => id === linked || id.startsWith(`${linked}:`))
      : frameCount === 1 || !!meta.scope_id
  }) as unknown as VisualEvidenceItem[] : []
  const media = attachedMedia.map((item) => ({ ...item, url: backendResourceUrl(baseUrl, item.url) }))
  const pathGraph = savedPaths(result)
  const label = scope?.kind === 'time_window' ? `样本 ${scope.sample_start}–${scope.sample_end}`
    : scope?.kind === 'image_region' ? `区域 ${frameIndex + 1}` : text(outer.display_name) ?? id
  const paths = pathGraph.paths
  return {
    id,
    label,
    sampleId: text(outer.case_id) ?? id,
    frame,
    result,
    scope,
    pathGraph,
    media,
    processTrends,
    waferGrid,
    locationsByObsId,
    observationsById,
    candidatesById: index([...traceRows(result?.ranked_root_causes), ...traceRows(result?.candidate_evaluations)], 'candidate_id'),
    pathsById: new Map(paths.map((path) => [path.path_id, path])),
    pathsByCandidateId: byPathKeys(paths, (path) => [path.target_entity_id]),
    pathsByEdgeId: byPathKeys(paths, (path) => path.edges.map((edge) => edge.edge_id)),
    pathsByObsId: byPathKeys(paths, (path) => path.supporting_evidence
      .filter((key) => typeof key === 'string' && observationsById.has(key))),
  }
}

export function projectSavedAnalysis(raw: unknown, baseUrl: string): SavedAnalysis {
  const run = traceRecord(raw) as SavedAnalysisRun
  const id = text(run.run_id)
  if (!id || !Array.isArray(run.cases)) throw new Error('响应缺少保存分析的身份或样本。')
  const runPath = `/api/analyses/${encodeURIComponent(id)}`
  const framesById = new Map<string, SavedAnalysisFrame>()
  for (const outer of traceRows(run.cases)) {
    const frames = traceRows(outer.evidence_frames)
    const results = traceRows(outer.results)
    const resultByFrame = index(results, 'case_id')
    if (resultByFrame.size !== results.length) throw new Error(`分析 ${id} 有无标识或重复的保存结果。`)
    for (const resultId of resultByFrame.keys()) {
      if (!frames.some(frame => frame.case_id === resultId)) throw new Error(`已保存分析 ${id} 的问题 ${resultId} 缺少对应 EvidenceFrame。`)
    }
    for (const [frameIndex, rawFrame] of frames.entries()) {
      const frameId = text(rawFrame.case_id)
      if (!frameId || framesById.has(frameId)) throw new Error(`分析 ${id} 有无标识或重复的 EvidenceFrame。`)
      const result = resultByFrame.get(frameId) as SavedReasoningResult | undefined
      if (result?.graph_id && run.graph_id && result.graph_id !== run.graph_id) {
        throw new Error(`分析 ${id} 的 Frame ${frameId} 与保存图身份不一致。`)
      }
      framesById.set(frameId, frameProjection(rawFrame as SavedEvidenceFrame, result ?? null, outer,
        frames.length, frameIndex, baseUrl, runPath))
    }
  }
  const frames = [...framesById.values()]
  const measured = run.input_mode === 'image' || run.input_mode === 'process' || run.input_mode === 'wafer'
  const skipped = run.input_mode === 'evidence' || run.input_mode === 'records'
  return {
    run,
    frames,
    framesById,
    evidenceUrl: run.evidence_download_url === `${runPath}/evidence`
      ? backendResourceUrl(baseUrl, run.evidence_download_url)
      : null,
    backbone: {
      state: measured ? 'measured' : skipped ? 'skipped' : 'not_recorded',
      inherited: skipped && frames.some((frame) => frame.media.length || frame.processTrends.length || frame.waferGrid),
    },
  }
}

export async function readSavedAnalysis(baseUrl: string, runId: string): Promise<SavedAnalysis> {
  const raw = await requestJson<unknown>(baseUrl, `/api/analyses/${encodeURIComponent(runId)}`)
  if (traceRecord(raw).run_id !== runId) throw new Error('后端没有返回请求的保存分析。')
  return projectSavedAnalysis(raw, baseUrl)
}
