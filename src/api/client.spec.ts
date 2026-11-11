import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApiClient, resolveApiBaseUrl } from '@/api/client'
import { createTwoLoopClient } from '@/api/two-loop'

afterEach(() => vi.unstubAllGlobals())

describe('resolveApiBaseUrl', () => {
  it('routes the default local backend through the same-origin proxy during local frontend development', () => {
    expect(resolveApiBaseUrl('http://127.0.0.1:8000', 'http://127.0.0.1:5174')).toBe('http://127.0.0.1:5174')
  })
  it('keeps custom loopback ports direct to avoid proxying the wrong backend', () => {
    expect(resolveApiBaseUrl('http://127.0.0.1:9000', 'http://127.0.0.1:5174')).toBe('http://127.0.0.1:9000')
  })
  it('keeps external API origins direct', () => {
    expect(resolveApiBaseUrl('https://example.com', 'http://127.0.0.1:5174')).toBe('https://example.com')
  })
})

describe('working graph API', () => {
  it('reads, saves and imports only complete v2 work packages', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })
    vi.stubGlobal('fetch', fetch)
    const client = createApiClient('https://example.com')
    const body = { schema_version: 'rootlens-working-graph.v2', title: 'Common', dataset: 'mvtec',
      build_id: 'test', knowledge: { value_bindings: [] } } as const
    await client.getWorkingGraphPackage('graph/1')
    await client.saveWorkingGraphPackage('graph/1', body)
    await client.importWorkingGraphPackage(body)
    expect(fetch.mock.calls.map(call => call[0])).toEqual([
      'https://example.com/api/kg/working-graphs/graph%2F1/package',
      'https://example.com/api/kg/working-graphs/graph%2F1/package',
      'https://example.com/api/kg/working-graphs/import',
    ])
    expect(fetch.mock.calls[1]![1].method).toBe('PUT')
    expect(JSON.parse(fetch.mock.calls[1]![1].body)).toEqual(body)
    expect(JSON.parse(fetch.mock.calls[2]![1].body)).toEqual(body)
  })
  it('selects and enables the exact registered graph', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ graphs: [] }) })
    vi.stubGlobal('fetch', fetch)
    const client = createApiClient('https://example.com')
    await client.listWorkingGraphs()
    await client.kgStudio('graph:1')
    await client.enableWorkingGraph('graph/1', true)
    expect(fetch.mock.calls.map(call => call[0])).toEqual([
      'https://example.com/api/kg/working-graphs',
      'https://example.com/api/kg/studio?graph_id=graph%3A1',
      'https://example.com/api/kg/working-graphs/graph%2F1/enable',
    ])
    expect(JSON.parse(fetch.mock.calls[2]![1].body)).toEqual({ enabled: true })
  })
})

describe('current inference task submissions', () => {
  it('uploads a raw process sample with its reference and exact windows to the task API', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ task_id: 'task-1' }) })
    vi.stubGlobal('fetch', fetch)
    const file = new File(['public'], 'series.dat'), reference_file = new File(['normal'], 'normal.dat')
    await createTwoLoopClient('https://example.com').infer({
      file, reference_file, dataset: 'tep', input_mode: 'process', graph_id: 'g', reasoner_id: 'tep_rootkgd',
      top_k: 5, windows: [[1, 100], [161, 260]],
    })
    expect(fetch.mock.calls[0]![0]).toBe('https://example.com/api/tasks/inference')
    const { method, body } = fetch.mock.calls[0]![1] as { method: string; body: FormData }
    expect(method).toBe('POST')
    expect((body.get('file') as File).name).toBe('series.dat')
    expect((body.get('reference_file') as File).name).toBe('normal.dat')
    expect(body.get('windows')).toBe('[[1,100],[161,260]]')
    expect(body.get('graph_id')).toBe('g')
    expect(body.get('reasoner_id')).toBe('tep_rootkgd')
  })
  it('submits a registered demo asset through the same inference task family', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ task_id: 'task-2' }) })
    vi.stubGlobal('fetch', fetch)
    const input = { sample_id: 'mvtec-bottle-006-graded', graph_id: 'g', reasoner_id: 'graded_abduction', input_variant: 'evidence', top_k: 5 } as const
    await createTwoLoopClient('https://example.com').inferDemo(input)
    expect(fetch.mock.calls[0]![0]).toBe('https://example.com/api/tasks/inference/demo')
    expect(JSON.parse(fetch.mock.calls[0]![1].body)).toEqual(input)
  })
})
