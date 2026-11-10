import { afterEach, describe, expect, it, vi } from 'vitest'

import { createApiClient, resolveApiBaseUrl } from '@/api/client'

afterEach(() => vi.unstubAllGlobals())

describe('resolveApiBaseUrl', () => {
  it('routes the default local backend through the same-origin proxy during local frontend development', () => {
    expect(resolveApiBaseUrl('http://127.0.0.1:8000', 'http://127.0.0.1:5174')).toBe(
      'http://127.0.0.1:5174',
    )
  })

  it('keeps custom loopback ports direct to avoid proxying the wrong backend', () => {
    expect(resolveApiBaseUrl('http://127.0.0.1:9000', 'http://127.0.0.1:5174')).toBe(
      'http://127.0.0.1:9000',
    )
  })

  it('keeps external API origins direct', () => {
    expect(resolveApiBaseUrl('https://example.com', 'http://127.0.0.1:5174')).toBe('https://example.com')
  })
})

describe('working graph API', () => {
  it('uses persistent package, mutation, import and replay endpoints', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })
    vi.stubGlobal('fetch', fetch)
    const client = createApiClient('https://example.com')
    const body = { schema_version: 'rootlens-working-graph.v1', title: 'Wafer', dataset: 'wafer',
      build_id: 'test', nodes: [], edges: [], profiles: {} } as const
    await client.getWorkingGraphPackage('graph/1')
    await client.mutateWorkingGraph('graph/1', { delete_node_ids: ['P'], cascade: true })
    await client.importWorkingGraphPackage({ ...body, nodes: [], edges: [] })
    await client.exportRunReplay('run/1')
    expect(fetch.mock.calls.map(call => call[0])).toEqual([
      'https://example.com/api/kg/working-graphs/graph%2F1/package',
      'https://example.com/api/kg/working-graphs/graph%2F1',
      'https://example.com/api/kg/working-graphs/import',
      'https://example.com/api/runs/run%2F1/replay',
    ])
    expect(fetch.mock.calls[1][1].method).toBe('PATCH')
  })
  it('selects the requested graph and activates a compiler build', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ graphs: [] }) })
    vi.stubGlobal('fetch', fetch)
    const client = createApiClient('https://example.com')
    await client.listWorkingGraphs()
    await client.kgStudio('graph:1')
    await client.activateWorkingGraph('build/1', 'Capsule')
    expect(fetch.mock.calls[0][0]).toBe('https://example.com/api/kg/working-graphs')
    expect(fetch.mock.calls[1][0]).toBe('https://example.com/api/kg/studio?graph_id=graph%3A1')
    expect(fetch.mock.calls[2][0]).toBe('https://example.com/api/kg/construction/builds/build%2F1/activate')
    expect(JSON.parse(fetch.mock.calls[2][1].body)).toEqual({ title: 'Capsule', dataset: 'mvtec', compact_runtime: true })
  })

  it('sends opt-in semantics and graph selection without changing legacy defaults', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })
    vi.stubGlobal('fetch', fetch)
    const client = createApiClient('https://example.com')
    const request = { file: new File(['public'], 'input.png'), mode: 'image' as const, top_k: 5 }
    await client.uploadRun({ ...request, graph_id: 'graph-1', semantic_mode: 'vlm' })
    expect(fetch.mock.calls[0][1].body.get('semantic_mode')).toBe('vlm')
    expect(fetch.mock.calls[0][1].body.get('graph_id')).toBe('graph-1')
    await client.uploadRun(request)
    expect(fetch.mock.calls[1][1].body.has('semantic_mode')).toBe(false)
    expect(fetch.mock.calls[1][1].body.has('graph_id')).toBe(false)
  })

  it('opts into the unified contract explicitly and preserves its canonical package', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })
    vi.stubGlobal('fetch', fetch)
    const client = createApiClient('https://example.com')
    await client.activateWorkingGraph('build/2', 'Unified', 'mvtec', 'unified-v2')
    expect(JSON.parse(fetch.mock.calls[0][1].body).target_contract).toBe('unified-v2')
    const body = { schema_version: 'rootlens-working-graph.v2' as const, title: 'Common',
      dataset: 'mvtec', build_id: 'test', knowledge: { value_bindings: [] } }
    await client.importWorkingGraphPackage(body)
    expect(JSON.parse(fetch.mock.calls[1][1].body)).toEqual(body)
  })
})
