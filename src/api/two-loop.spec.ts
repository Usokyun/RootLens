import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/api/client'
import { createTwoLoopClient } from '@/api/two-loop'

const base = 'http://127.0.0.1:8012'
const response = (body: unknown = {}) => ({ ok: true, json: async () => body })
afterEach(() => vi.unstubAllGlobals())

describe('two-loop transport', () => {
  it('reads the demo directory without writing, and uses separate explicit actions for the graph and materials', async () => {
    const fetch = vi.fn().mockResolvedValue(response())
    vi.stubGlobal('fetch', fetch)
    const api = createTwoLoopClient(base)
    await api.demos()
    expect(fetch.mock.calls).toEqual([[`${base}/api/demo-library`, undefined]])
    await api.installDemoGraph('tep-graded')
    await api.addDemoMaterials('tep-graded')
    expect(fetch.mock.calls.slice(1)).toEqual([
      [`${base}/api/demo-library/tep-graded/working-graph`, { method: 'POST' }],
      [`${base}/api/demo-library/tep-graded/materials`, { method: 'POST' }],
    ])
  })
  it('reads incremental task events and makes retry a separate explicit POST', async () => {
    const fetch = vi.fn().mockResolvedValue(response())
    vi.stubGlobal('fetch', fetch)
    const api = createTwoLoopClient(base)
    await api.task('task/a', 19)
    await api.listTasks(12)
    await api.retryTask('task/a')
    expect(fetch.mock.calls).toEqual([
      [`${base}/api/tasks/task%2Fa?after_sequence=19`, undefined],
      [`${base}/api/tasks?limit=12`, undefined],
      [`${base}/api/tasks/task%2Fa/retry`, { method: 'POST' }],
    ])
  })
  it('sends original TEP file, reference, one-based windows and the selected engine unchanged', async () => {
    const fetch = vi.fn().mockResolvedValue(response({ task_id: 'task-real-shape', status: 'queued', next_sequence: 1, events: [] }))
    vi.stubGlobal('fetch', fetch)
    const file = new File(['sample'], 'd04.dat'), reference = new File(['normal'], 'd00.dat')
    const task = await createTwoLoopClient(base).infer({ file, reference_file: reference, dataset: 'tep', input_mode: 'process',
      reasoner_id: 'tep_rootkgd', graph_id: 'graph-tep', top_k: 8, windows: [[1, 100], [161, 260]], sampling_seconds: 180 })
    const [url, request] = fetch.mock.calls[0]!
    expect(url).toBe(`${base}/api/tasks/inference`)
    expect(request.method).toBe('POST')
    expect(Object.fromEntries(request.body)).toEqual({ file, reference_file: reference, dataset: 'tep', input_mode: 'process',
      reasoner_id: 'tep_rootkgd', graph_id: 'graph-tep', top_k: '8', windows: '[[1,100],[161,260]]', sampling_seconds: '180' })
    expect(task.task_id).toBe('task-real-shape')
  })
  it('preserves the Wafer JSONL filename and never sends its raw upload as Evidence or records', async () => {
    const fetch = vi.fn().mockResolvedValue(response())
    vi.stubGlobal('fetch', fetch)
    const file = new File(['{"waferMap":[[0,1,2]]}\n'], 'sample.jsonl')
    await createTwoLoopClient(base).infer({ file, dataset: 'wafer', input_mode: 'wafer', reasoner_id: 'graded_abduction', graph_id: 'graph-wafer', top_k: 5 })
    const body = fetch.mock.calls[0]![1].body as FormData
    expect((body.get('file') as File).name).toBe('sample.jsonl')
    expect(body.get('input_mode')).toBe('wafer')
    expect(body.has('reference_file')).toBe(false)
    expect(body.has('semantic_mode')).toBe(false)
  })
  it('submits the selected demo variant without changing an explicitly selected graph', async () => {
    const fetch = vi.fn().mockResolvedValue(response())
    vi.stubGlobal('fetch', fetch)
    const input = { sample_id: 'mvtec-bottle-006-graded', graph_id: 'chosen-other', reasoner_id: 'graded_abduction', input_variant: 'evidence', top_k: 8 } as const
    await createTwoLoopClient(base).inferDemo(input)
    expect(fetch.mock.calls[0]![0]).toBe(`${base}/api/tasks/inference/demo`)
    expect(JSON.parse(fetch.mock.calls[0]![1].body)).toEqual(input)
  })
  it('keeps the actual backend error, and does not retry an unconfirmed submission', async () => {
    const fetch = vi.fn().mockResolvedValueOnce({ ok: false, status: 400, text: async () => '{"detail":"所选工作图未启用"}' })
      .mockRejectedValueOnce(new Error('socket closed'))
    vi.stubGlobal('fetch', fetch)
    const api = createTwoLoopClient(base)
    await expect(api.task('one')).rejects.toMatchObject({ name: 'ApiError', status: 400, message: '所选工作图未启用' })
    await expect(api.inferDemo({ sample_id: 'one', graph_id: 'g', reasoner_id: 'graded_abduction', input_variant: 'evidence', top_k: 5 })).rejects.toBeInstanceOf(ApiError)
    expect(fetch).toHaveBeenCalledTimes(2)
  })
})
