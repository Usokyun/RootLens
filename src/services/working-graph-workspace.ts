import { onBeforeUnmount, onMounted, ref, type InjectionKey, type ShallowRef } from 'vue'
import type { WorkingGraphPackage, WorkingGraphSummary } from '@/api/contracts'
import { savedAnalysisIntent, savedAnalysisRoute } from '@/services/analysis-entry'
import { getLocalSessionEventName, getLocalSessionMeta } from '@/services/rootlens-data'

export const workingGraphLeaveGuardKey: InjectionKey<ShallowRef<(() => Promise<boolean>) | null>> = Symbol('working-graph-leave')

export function useGraphReplay() {
  const replay = ref(getLocalSessionMeta()?.source === 'import')
  const sync = () => { replay.value = getLocalSessionMeta()?.source === 'import' }
  onMounted(() => window.addEventListener(getLocalSessionEventName(), sync))
  onBeforeUnmount(() => window.removeEventListener(getLocalSessionEventName(), sync))
  return replay
}

export const workingGraphRoute = (graphId: string) => ({ name: 'graphs', query: { graph: graphId } } as const)
export const graphArchiveRoute = (runId?: string, frameId?: string | null) => ({
  name: 'graph-archive',
  query: { ...(runId ? { run_id: runId } : {}), ...(frameId ? { case_id: frameId } : {}) },
} as const)

export function graphRequest(query: Record<string, unknown>) {
  if (!Object.prototype.hasOwnProperty.call(query, 'graph')) return { kind: 'default' } as const
  const value = query.graph
  return typeof value === 'string' && value.length > 0 && value === value.trim()
    ? { kind: 'exact', id: value } as const
    : { kind: 'invalid' } as const
}

/** Old explicitly typed Run links enter the appropriate archive, never the workbench canvas. */
export function graphRunRedirect(query: Record<string, unknown>) {
  if (graphRequest(query).kind !== 'default') return null
  const native = savedAnalysisIntent(query)
  if (native) return savedAnalysisRoute('evidence', native.runId, native.frameId, 'graph')
  if (query.source === 'legacy-run' && typeof query.run_id === 'string' && query.run_id.trim()) {
    return graphArchiveRoute(query.run_id, typeof query.case_id === 'string' ? query.case_id : null)
  }
  return null
}

const unified = (graph: WorkingGraphSummary) => graph.knowledge?.schema_version === 'rootlens-knowledge-package.v2'
export function defaultWorkingGraph(graphs: WorkingGraphSummary[], rememberedId: string | null) {
  const ready = graphs.filter(graph => graph.status === 'ready')
  return ready.find(graph => graph.graph_id === rememberedId)
    ?? ready.find(graph => graph.enabled === true && unified(graph))
    ?? ready.find(unified)
    ?? ready[0]
    ?? null
}

export function workingGraphAccess(graph: WorkingGraphSummary | null, graphPackage: WorkingGraphPackage | null) {
  const editable = graph?.status === 'ready' && graphPackage?.schema_version === 'rootlens-working-graph.v2'
  return {
    editable,
    canEnable: editable && graph?.enabled === false,
    canAnalyze: editable && graph?.enabled === true,
  }
}

export const graphScenes = { mvtec: 'MVTec', tep: 'TEP', wafer: 'Wafer' } as const
export function graphScene(dataset: string | null | undefined) {
  if (!dataset) return '未记录场景'
  return graphScenes[dataset as keyof typeof graphScenes] ?? dataset
}

function storageKey(baseUrl: string) {
  return `rootlens.working-graph:${baseUrl.trim().replace(/\/+$/, '')}`
}
export function rememberedWorkingGraph(baseUrl: string) {
  try { return window.sessionStorage.getItem(storageKey(baseUrl)) } catch { return null }
}
export function rememberWorkingGraph(baseUrl: string, graphId: string) {
  try { window.sessionStorage.setItem(storageKey(baseUrl), graphId) } catch { /* Viewing does not require storage. */ }
}
