import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError, apiConnection, apiUrl, request, workbenchApi } from '@/api/workbench'

afterEach(() => vi.unstubAllGlobals())
function successfulFetch() {
  const fetch = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) })
  vi.stubGlobal('fetch', fetch)
  return fetch
}
describe('double-loop API client', () => {
  it('submits actual parse/build jobs with the one-repair policy, then reads and retries the original task', async () => {
    const fetch = successfulFetch(), api = workbenchApi('https://backend.example')
    await api.parseMaterials(['source-a'])
    await api.buildGraph({ material_ids: ['source-a'], dataset: 'tep', title: '过程知识', capability_id: 'process-window-v2', enable_when_ready: false, max_repairs: 1 })
    await api.task('task/1'); await api.retryTask('task/1')
    expect(fetch.mock.calls.map((c) => c[0])).toEqual([
      'https://backend.example/api/tasks/material-parse', 'https://backend.example/api/tasks/material-build',
      'https://backend.example/api/tasks/task%2F1?after_sequence=0', 'https://backend.example/api/tasks/task%2F1/retry',
    ])
    expect(JSON.parse(fetch.mock.calls[1]![1].body)).toEqual(expect.objectContaining({ max_repairs: 1, enable_when_ready: false }))
  })
  it('uploads native process data, reference, explicit graph/engine and full one-based windows without changing their values', async () => {
    const fetch = successfulFetch(), api = workbenchApi('https://backend.example')
    const file = new File(['1,2'], 'window.dat'), normal = new File(['3,4'], 'normal.dat')
    await api.infer({ file, reference_file: normal, dataset: 'tep', graph_id: 'graph-a', reasoner_id: 'tep_rootkgd', input_mode: 'process', windows: [[1,100],[161,260]], top_k: 8 })
    const form = fetch.mock.calls[0]![1].body as FormData
    expect(form.get('file')).toBe(file); expect(form.get('reference_file')).toBe(normal)
    expect(form.get('input_mode')).toBe('process'); expect(form.get('graph_id')).toBe('graph-a')
    expect(form.get('reasoner_id')).toBe('tep_rootkgd'); expect(form.get('windows')).toBe('[[1,100],[161,260]]')
    expect(form.get('top_k')).toBe('8'); expect(form.has('semantic_mode')).toBe(false)
  })
  it('keeps demonstration input variants distinct and never opens a saved run in place of inference', async () => {
    const fetch = successfulFetch(), api = workbenchApi('https://backend.example')
    await api.inferDemo({ sample_id: 'sample-a', graph_id: 'graph-a', reasoner_id: 'unified_abduction', input_variant: 'raw', top_k: 8 })
    await api.inferDemo({ sample_id: 'sample-a', graph_id: 'graph-a', reasoner_id: 'unified_abduction', input_variant: 'evidence', top_k: 8 })
    expect(fetch.mock.calls.map((c) => c[0])).toEqual(Array(2).fill('https://backend.example/api/tasks/inference/demo'))
    expect(JSON.parse(fetch.mock.calls[0]![1].body).input_variant).toBe('raw')
    expect(JSON.parse(fetch.mock.calls[1]![1].body).input_variant).toBe('evidence')
  })
  it('separates saving knowledge from enabling it for new runs', async () => {
    const fetch = successfulFetch(), api = workbenchApi('https://backend.example')
    const pkg = { schema_version: 'rootlens-working-graph.v2' as const, title: '知识', dataset: 'mvtec', build_id: 'build-a', knowledge: { entities: [] } }
    await api.saveGraph('graph/1', pkg); await api.enableGraph('graph/1', true)
    expect(fetch.mock.calls[0]![0]).toBe('https://backend.example/api/kg/working-graphs/graph%2F1/package')
    expect(fetch.mock.calls[0]![1].method).toBe('PUT')
    expect(JSON.parse(fetch.mock.calls[0]![1].body)).toEqual(pkg)
    expect(fetch.mock.calls[1]![0]).toBe('https://backend.example/api/kg/working-graphs/graph%2F1/enable')
    expect(JSON.parse(fetch.mock.calls[1]![1].body)).toEqual({ enabled: true })
  })
})
describe('API failures and asset URLs', () => {
  it('retains a useful server error instead of returning mock success', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: false, status: 422, text: async () => '{"detail":"正常参考缺失"}' }))
    await expect(request('https://backend.example','/api/tasks/inference')).rejects.toEqual(new ApiError('正常参考缺失', 422))
  })
  it('marks an unavailable service disconnected and returns a retryable connection message', async () => {
    apiConnection.available = true
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    await expect(request('https://backend.example','/api/tasks')).rejects.toThrow('无法连接后端服务')
    expect(apiConnection.available).toBe(false)
    expect(apiConnection.error).toContain('后端服务不可用')
  })
  it('preserves a complete asset URL, and resolves API-relative media through the chosen backend', () => {
    expect(apiUrl('https://backend.example/','/api/analyses/a/artifacts/image.png')).toBe('https://backend.example/api/analyses/a/artifacts/image.png')
    expect(apiUrl('https://backend.example','data:image/png;base64,abc')).toBe('data:image/png;base64,abc')
  })
})
