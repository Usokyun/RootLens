import { describe, expect, it } from 'vitest'
import type { WorkingGraphSummary } from '@/api/contracts'
import { defaultWorkingGraph, graphRequest, rememberWorkingGraph, rememberedWorkingGraph, workingGraphAccess } from './working-graph-workspace'

const graph = (id: string, status: WorkingGraphSummary['status'], enabled: boolean, v2 = true): WorkingGraphSummary => ({
  graph_id: id, title: id, dataset: 'mvtec', build_id: id, status, enabled, node_count: 1, edge_count: 0,
  knowledge: v2 ? { schema_version: 'rootlens-knowledge-package.v2' } : null,
})
const pkg = { schema_version: 'rootlens-working-graph.v2', graph_id: 'current', title: '当前图', dataset: 'mvtec', build_id: 'g', knowledge: {} } as const

describe('working graph route and catalog', () => {
  it('treats an explicit empty or repeated graph ID as invalid rather than picking another graph', () => {
    expect(graphRequest({})).toEqual({ kind: 'default' })
    expect(graphRequest({ graph: 'exact-graph' })).toEqual({ kind: 'exact', id: 'exact-graph' })
    expect(graphRequest({ graph: '' })).toEqual({ kind: 'invalid' })
    expect(graphRequest({ graph: ['one', 'two'] })).toEqual({ kind: 'invalid' })
  })

  it('remembers a valid ready graph for the same backend; otherwise prioritizes a ready enabled v2 graph', () => {
    const rows = [graph('failed', 'failed', true), graph('v1', 'ready', true, false),
      graph('pending-enable', 'ready', false), graph('current', 'ready', true)]
    rememberWorkingGraph('https://one.example/', 'pending-enable')
    expect(defaultWorkingGraph(rows, rememberedWorkingGraph('https://one.example'))?.graph_id).toBe('pending-enable')
    expect(defaultWorkingGraph(rows, rememberedWorkingGraph('https://two.example'))?.graph_id).toBe('current')
    expect(defaultWorkingGraph(rows, 'failed')?.graph_id).toBe('current')
    expect(defaultWorkingGraph(rows, 'v1')?.graph_id).toBe('current')
    expect(defaultWorkingGraph([rows[0]!], null)).toBeNull()
  })

  it('requires the actual ready v2 package and explicit enablement to hand off a graph', () => {
    expect(workingGraphAccess(graph('current', 'ready', true), pkg)).toEqual({ editable: true, canEnable: false, canAnalyze: true })
    expect(workingGraphAccess(graph('current', 'ready', false), pkg)).toEqual({ editable: true, canEnable: true, canAnalyze: false })
    expect(workingGraphAccess(graph('current', 'loading', true), pkg).canAnalyze).toBe(false)
    expect(workingGraphAccess(graph('current', 'ready', true), null).canAnalyze).toBe(false)
    expect(workingGraphAccess(graph('current', 'ready', true, false), pkg).canAnalyze).toBe(false)
  })
})
