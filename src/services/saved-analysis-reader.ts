/** Native saved analyses only. No live KG, legacy Run, or reasoning calls. */
import { requestJson } from '@/api/client'
import type { PathGraph, PathGraphPath, RunCaseDetail, VisualEvidenceItem } from '@/api/contracts'
import { backendResourceUrl } from '@/api/two-loop'
import { analysisSnapshotView } from './analysis-snapshot-view'
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
  /** The same exact path/orientation bridge used by the original graph page. */
  caseDetail: RunCaseDetail | null
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
  detail: RunCaseDetail | undefined,
  singleFrame: boolean,
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
  const processTrends = singleFrame && scope?.kind === 'time_window' ? savedCurves(outer.process_trends) : []
  const waferGrid = singleFrame && scope?.kind === 'spatial_grid' ? savedGrid(outer.wafer_map) : null
  const attachedMedia = (detail?.visual_evidence ?? []).filter((item) => (
    item.available && item.url?.startsWith(`${runPath}/artifacts/`)
  ))
  const media = attachedMedia.map((item) => ({ ...item, url: backendResourceUrl(baseUrl, item.url) }))
  const pathGraph = detail?.path_graph ?? { paths: [], path_count: 0, node_count: 0, edge_count: 0 }
  const paths = pathGraph.paths
  return {
    id,
    label: detail?.case_label ?? text(outer.display_name) ?? id,
    sampleId: text(outer.case_id) ?? id,
    frame,
    result,
    scope,
    caseDetail: detail ? { ...detail, visual_evidence: attachedMedia, process_trends: processTrends, wafer_map: waferGrid } : null,
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
  const projected = analysisSnapshotView(run)
  const projectedByFrame = new Map(projected.cases.map((item) => [item.case_id, item]))
  const framesById = new Map<string, SavedAnalysisFrame>()
  for (const outer of traceRows(run.cases)) {
    const frames = traceRows(outer.evidence_frames)
    const results = traceRows(outer.results)
    const resultByFrame = index(results, 'case_id')
    if (resultByFrame.size !== results.length) throw new Error(`分析 ${id} 有无标识或重复的保存结果。`)
    for (const rawFrame of frames) {
      const frameId = text(rawFrame.case_id)
      if (!frameId || framesById.has(frameId)) throw new Error(`分析 ${id} 有无标识或重复的 EvidenceFrame。`)
      const result = resultByFrame.get(frameId) as SavedReasoningResult | undefined
      if (result?.graph_id && run.graph_id && result.graph_id !== run.graph_id) {
        throw new Error(`分析 ${id} 的 Frame ${frameId} 与保存图身份不一致。`)
      }
      framesById.set(frameId, frameProjection(rawFrame as SavedEvidenceFrame, result ?? null, outer,
        result ? projectedByFrame.get(frameId) : undefined, frames.length === 1, baseUrl, runPath))
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
