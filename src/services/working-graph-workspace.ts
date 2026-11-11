import type { InjectionKey, ShallowRef } from 'vue'
import type { WorkingGraphPackage, WorkingGraphSummary } from '@/api/contracts'

export const workingGraphLeaveGuardKey: InjectionKey<ShallowRef<(() => Promise<boolean>) | null>> = Symbol('working-graph-leave')

export const workingGraphRoute = (graphId: string) => ({ name: 'graphs', query: { graph: graphId } } as const)

export function graphRequest(query: Record<string, unknown>) {
  if (!Object.prototype.hasOwnProperty.call(query, 'graph')) return { kind: 'default' } as const
  const value = query.graph
  return typeof value === 'string' && value.length > 0 && value === value.trim()
    ? { kind: 'exact', id: value } as const
    : { kind: 'invalid' } as const
}

export const isCurrentWorkingGraph = (graph: WorkingGraphSummary) => graph.knowledge?.schema_version === 'rootlens-knowledge-package.v2'
export function defaultWorkingGraph(graphs: WorkingGraphSummary[], rememberedId: string | null) {
  const ready = graphs.filter(graph => graph.status === 'ready' && isCurrentWorkingGraph(graph))
  return ready.find(graph => graph.graph_id === rememberedId)
    ?? ready.find(graph => graph.enabled === true)
    ?? ready[0]
    ?? null
}

export function workingGraphAccess(graph: WorkingGraphSummary | null, graphPackage: WorkingGraphPackage | null) {
  const editable = !!graph && graph.status === 'ready' && isCurrentWorkingGraph(graph)
    && graphPackage?.schema_version === 'rootlens-working-graph.v2'
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
