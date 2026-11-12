import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApiClient } from '@/api/client'
import type { KGConstructionGraphPayload } from '@/api/contracts'
import { buildConstructionGraphDataset, constructionGraphLocation } from '@/services/construction-graph'

export function snapshot(): KGConstructionGraphPayload {
  return {
    status: 'ok', build_id: 'mvtec-build', title: 'MVTec snapshot', read_only: true, truncated: false,
    claim_boundary: 'candidate only', candidate_dir: 'runs/mvtec-build', nodes_path: 'nodes.csv', edges_path: 'edges.csv',
    source_registry_path: '', node_count: 3, edge_count: 1, scenario_counts: { mvtec: 1 }, review_status_counts: { auto: 1 },
    source_counts: { manual: 1 }, confidence_summary: {}, validation_summary: null, sources: [], source_documents: [], review_targets: [], note: 'read-only',
    graph_nodes: ['Scratch', 'Contact', 'Isolated'].map(id => ({ node_id: id, label: id, node_type: 'RootCause', scenario: 'mvtec', description: 'candidate' })),
    graph_edges: [{ edge_id: 'Scratch|CAUSE|Contact|mvtec', target_key: 'edge:Scratch|CAUSE|Contact|mvtec', head: 'Scratch', relation: 'CAUSE', tail: 'Contact', scenario: 'mvtec', source: 'manual', evidence: 'candidate mechanism', confidence: .66, weight: .3, review_status: 'auto' }],
  }
}

afterEach(() => vi.unstubAllGlobals())

describe('construction snapshot display', () => {
  it('deep links a build without reusing analysis run or case IDs', () => {
    expect(constructionGraphLocation('mvtec-build')).toEqual({ name: 'graphs', query: { build_id: 'mvtec-build' } })
  })
  it('keeps isolated nodes, stable edge IDs and provenance without mutating input', () => {
    const payload = snapshot()
    const before = JSON.stringify(payload)
    const dataset = buildConstructionGraphDataset(payload)
    expect(dataset.nodes.map(node => [node.id, node.inDegree, node.outDegree])).toEqual([
      ['Scratch', 0, 1], ['Contact', 1, 0], ['Isolated', 0, 0],
    ])
    expect(dataset.edges[0]).toMatchObject({ id: payload.graph_edges[0]!.edge_id, confidence: .66, attributes: { source: 'manual', evidence: 'candidate mechanism', review_status: 'auto', build_id: 'mvtec-build' } })
    expect(dataset.metadata).toMatchObject({ read_only: true, build_id: 'mvtec-build' })
    expect(dataset.sourceFiles.map(source => source.path)).toEqual(['nodes.csv', 'edges.csv'])
    expect(JSON.stringify(payload)).toBe(before)
  })
  it('supports an empty graph and nullable provenance paths', () => {
    const payload = { ...snapshot(), graph_nodes: [], graph_edges: [], candidate_dir: null, nodes_path: null, edges_path: null }
    expect(buildConstructionGraphDataset(payload)).toMatchObject({ nodes: [], edges: [], projectRoot: '' })
  })
  it('requests the selected backend build with URL encoding', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => snapshot() })
    vi.stubGlobal('fetch', fetch)
    await createApiClient('http://127.0.0.1:8000').getKGConstructionGraph('build with space')
    expect(fetch.mock.calls[0]![0]).toBe(`${window.location.origin}/api/kg/construction/builds/build%20with%20space/graph`)
  })
  it('propagates preview failures rather than silently loading another graph', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: false, text: async () => 'unknown construction build' })
    vi.stubGlobal('fetch', fetch)
    await expect(createApiClient('http://127.0.0.1:8000').getKGConstructionGraph('missing')).rejects.toThrow('unknown construction build')
    expect(fetch).toHaveBeenCalledTimes(1)
  })
})
