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
  it('uses exact persistent graph package, mutation and import endpoints', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })
    vi.stubGlobal('fetch', fetch)
    const client = createApiClient('https://example.com')
    const body = { schema_version: 'rootlens-working-graph.v2', title: 'Common', dataset: 'mvtec',
      build_id: 'test', knowledge: { value_bindings: [] } } as const
    await client.getWorkingGraphPackage('graph/1')
    await client.mutateWorkingGraph('graph/1', { delete_node_ids: ['P'], cascade: true })
    await client.importWorkingGraphPackage(body)
    expect(fetch.mock.calls.map(call => call[0])).toEqual([
      'https://example.com/api/kg/working-graphs/graph%2F1/package',
      'https://example.com/api/kg/working-graphs/graph%2F1',
      'https://example.com/api/kg/working-graphs/import',
    ])
    expect(fetch.mock.calls[1]![1].method).toBe('PATCH')
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
    const input = { sample_id: 'bottle-rim-break', graph_id: 'g', reasoner_id: 'unified_abduction', input_variant: 'evidence', top_k: 5 } as const
    await createTwoLoopClient('https://example.com').inferDemo(input)
    expect(fetch.mock.calls[0]![0]).toBe('https://example.com/api/tasks/inference/demo')
    expect(JSON.parse(fetch.mock.calls[0]![1].body)).toEqual(input)
  })
})

describe('explicit graph history reads', () => {
  const native = { run_id: 'new-analysis', title: '新结果', created_at: '2026-11-11', status: 'completed', dataset: 'mvtec', input_mode: 'evidence', cases: [] }
  const archive = { run_id: 'old-run', created_at: '2026-11-10' }
  const base = 'https://history.example'

  it('opens an explicit saved analysis before any catalog read', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => native })
    vi.stubGlobal('fetch', fetch)
    const detail = await createApiClient(base).getRun(native.run_id, 'analysis-v2')
    expect(detail.run).toMatchObject({ run_id: native.run_id, source_contract: 'analysis-v2' })
    expect(fetch.mock.calls.map(call => call[0])).toEqual([`${base}/api/analyses/${native.run_id}`])
  })
  it('keeps source identity on actual native and archived catalog rows and reads the requested archive', async () => {
    const fetch = vi.fn(async (url: string) => ({ ok: true, json: async () => url.endsWith('/api/runs') ? [archive]
      : url.endsWith('/api/analyses') ? { runs: [native] } : { run: archive } }))
    vi.stubGlobal('fetch', fetch)
    const client = createApiClient(base)
    const runs = await client.listRuns()
    expect(runs.map(item => [item.run_id, item.source_contract])).toEqual([['new-analysis', 'analysis-v2'], ['old-run', 'legacy-run']])
    await expect(client.getRun('old-run', 'legacy-run')).resolves.toMatchObject({ run: { ...archive, source_contract: 'legacy-run' } })
    expect(fetch.mock.calls.map(call => call[0])).toEqual([`${base}/api/runs`, `${base}/api/analyses`, `${base}/api/runs/old-run`])
  })
  it('does not probe the alternate source when the requested saved run is missing', async () => {
    const fetch = vi.fn().mockResolvedValue({ ok: false, status: 404, text: async () => '{"detail":"记录不存在"}' })
    vi.stubGlobal('fetch', fetch)
    await expect(createApiClient(base).getRun('missing', 'analysis-v2')).rejects.toThrow('记录不存在')
    expect(fetch.mock.calls.map(call => call[0])).toEqual([`${base}/api/analyses/missing`])
  })
  it('surfaces an analyses index failure instead of presenting another source as the full result', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => url.endsWith('/api/runs') ? { ok: true, json: async () => [] }
      : { ok: false, status: 503, text: async () => '分析服务不可用' }))
    await expect(createApiClient(base).listRuns()).rejects.toThrow('分析服务不可用')
  })
})
