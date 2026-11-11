import { createApp, h, nextTick, ref, type App } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { materialBuildBlocker, submitMaterialBuild, type MaterialBuildOptions } from '@/api/material-tasks'
import type { WorkTask } from '@/api/two-loop'
import { useMaterialSourceTasks } from '@/services/material-source-tasks'

const base = 'https://material-fixture.test'
const selection = [{ material_id: 'public-source', scenario: 'mvtec' }]
const options: MaterialBuildOptions = { title: ' 公开资料工作图 ', dataset: 'mvtec', allowRepair: true }

function task(update: Partial<WorkTask> = {}): WorkTask {
  return {
    task_id: 'task-build', kind: 'material_build', status: 'queued', title: '公开资料工作图',
    created_at: '2026-11-11T01:00:00Z', updated_at: '2026-11-11T01:00:00Z',
    stage: 'queued', stage_label: '排队中', progress: { indeterminate: true },
    events: [], request: { material_ids: ['public-source'] }, result: null, error: null, ...update,
  }
}

function json(value: unknown, status = 200) {
  return new Response(JSON.stringify(value), { status })
}

function intercept(handler: (url: URL, init?: RequestInit) => Response | Promise<Response>) {
  const fetcher = vi.fn(async (input: string, init?: RequestInit) => handler(new URL(input), init))
  vi.stubGlobal('fetch', fetcher)
  return fetcher
}

let app: App | undefined
function mount(url = ref<string | null>(base), onParsed = vi.fn()) {
  let state!: ReturnType<typeof useMaterialSourceTasks>
  app = createApp({ setup() { state = useMaterialSourceTasks(() => url.value, onParsed); return () => h('div') } })
  app.mount(document.createElement('div'))
  return { state, url, onParsed }
}

afterEach(() => {
  app?.unmount()
  app = undefined
  vi.unstubAllGlobals()
})

describe('original material page task contract', () => {
  it.each([
    ['mvtec', 'visual-region-v2'], ['tep', 'process-window-v2'], ['wafer', 'spatial-grid-v2'],
  ] as const)('submits the matching %s capability with an explicit repair bound', async (dataset, capability) => {
    const fetcher = intercept(() => json(task(), 202))
    await submitMaterialBuild(base, [{ material_id: 'actual', scenario: dataset }, { material_id: 'shared', scenario: 'shared' }], {
      ...options, dataset, allowRepair: false,
    })
    expect(fetcher).toHaveBeenCalledOnce()
    const [url, init] = fetcher.mock.calls[0]!
    expect(url).toBe(`${base}/api/tasks/material-build`)
    expect(init?.method).toBe('POST')
    expect(JSON.parse(String(init?.body))).toEqual({
      material_ids: ['actual', 'shared'], dataset, title: '公开资料工作图', capability_id: capability,
      enable_when_ready: false, max_repairs: 0, candidate_limit: null,
    })
  })

  it('does not submit mixed scene materials, empty selections or empty titles', () => {
    const fetcher = intercept(() => json(task()))
    expect(materialBuildBlocker([], options)).toContain('至少一份')
    expect(materialBuildBlocker(selection, { ...options, title: ' ' })).toContain('图谱名')
    expect(() => submitMaterialBuild(base, [...selection, { material_id: 'tep', scenario: 'tep' }], options)).toThrow('其他场景')
    expect(fetcher).not.toHaveBeenCalled()
  })

  it('uses actual parse/LLM/validation stages and selects only the returned graph', async () => {
    const realStages = [
      task({ status: 'running', stage: 'parsing', stage_label: '解析原始资料', progress: { completed: 1, total: 2, indeterminate: false } }),
      task({ status: 'running', stage: 'llm', stage_label: 'LLM 领域蓝图', progress: { indeterminate: true } }),
      task({ status: 'running', stage: 'validation', stage_label: '自动校验', progress: { indeterminate: true } }),
      task({ status: 'completed', stage: 'completed', result: { graph_id: 'exact-new-graph', build_id: 'task-build' } }),
    ]
    const fetcher = intercept((url) => {
      if (url.pathname === '/api/tasks') return json({ tasks: [] })
      if (url.pathname === '/api/tasks/material-build') return json(task(), 202)
      if (url.pathname === '/api/tasks/task-build') return json(realStages.shift())
      throw new Error(`Unexpected ${url.pathname}`)
    })
    const { state } = mount()
    await Promise.all([state.build(selection, options), state.build(selection, options)])
    expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
    expect(JSON.parse(String(fetcher.mock.calls.find(([, init]) => init?.method === 'POST')?.[1]?.body))).toMatchObject({ max_repairs: 1, enable_when_ready: false })
    expect(state.task.value?.status).toBe('queued')
    await state.refresh()
    expect(state.task.value?.progress).toMatchObject({ completed: 1, total: 2, indeterminate: false })
    await state.refresh()
    expect(state.task.value?.stage).toBe('llm')
    expect(state.task.value?.progress).toEqual({ indeterminate: true })
    expect(state.resultGraphId.value).toBeNull()
    await state.refresh()
    expect(state.task.value?.stage).toBe('validation')
    await state.refresh()
    expect(state.resultGraphId.value).toBe('exact-new-graph')
  })

  it('keeps a failed task and only creates a fresh retry on an explicit action', async () => {
    const failed = task({ status: 'failed', stage: 'validation', error: { stage: 'validation', message: 'fixture validation failure' } })
    const fetcher = intercept((url) => {
      if (url.pathname === '/api/tasks') return json({ tasks: [] })
      if (url.pathname === '/api/tasks/material-build') return json(task(), 202)
      if (url.pathname === '/api/tasks/task-build') return json(failed)
      if (url.pathname === '/api/tasks/task-build/retry') return json(task({ task_id: 'retry-1', retry_of: 'task-build' }), 202)
      throw new Error(`Unexpected ${url.pathname}`)
    })
    const { state } = mount()
    await state.build(selection, options)
    await state.refresh()
    expect(state.task.value?.error?.message).toBe('fixture validation failure')
    expect(state.resultGraphId.value).toBeNull()
    expect(fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')).toHaveLength(1)
    await state.retry()
    await nextTick()
    expect(state.task.value).toMatchObject({ task_id: 'retry-1', retry_of: 'task-build' })
    expect(state.history.value.find((row) => row.task_id === 'task-build')?.status).toBe('failed')
  })

  it('refreshes only the actual parsed material result without selecting a graph', async () => {
    const queued = task({ task_id: 'parse-1', kind: 'material_parse' })
    const fetcher = intercept((url) => {
      if (url.pathname === '/api/tasks') return json({ tasks: [] })
      if (url.pathname === '/api/tasks/material-parse') return json(queued, 202)
      if (url.pathname === '/api/tasks/parse-1') return json({ ...queued, status: 'completed', result: { material_ids: ['public-source'] } })
      throw new Error(`Unexpected ${url.pathname}`)
    })
    const { state, onParsed } = mount()
    await state.parse('public-source', true)
    await state.refresh()
    expect(JSON.parse(String(fetcher.mock.calls.find(([, init]) => init?.method === 'POST')?.[1]?.body))).toEqual({ material_ids: ['public-source'], force: true })
    expect(onParsed).toHaveBeenCalledExactlyOnceWith(['public-source'])
    expect(state.resultGraphId.value).toBeNull()
  })

  it('submits one batch without overwrite and reads back possibly persisted items after a later item fails', async () => {
    const queued = task({
      task_id: 'batch-parse', kind: 'material_parse',
      request: { material_ids: ['parsed-first', 'failed-second'] },
    })
    const fetcher = intercept((url) => {
      if (url.pathname === '/api/tasks') return json({ tasks: [] })
      if (url.pathname === '/api/tasks/material-parse') return json(queued, 202)
      if (url.pathname === '/api/tasks/batch-parse') return json({
        ...queued, status: 'failed', stage: 'parsing', error: { message: 'source has no readable text' },
      })
      throw new Error(`Unexpected ${url.pathname}`)
    })
    const { state, onParsed } = mount()
    await state.parse(['parsed-first', 'failed-second', 'parsed-first'])
    await state.refresh()
    await nextTick()

    const posts = fetcher.mock.calls.filter(([, init]) => init?.method === 'POST')
    expect(posts).toHaveLength(1)
    expect(JSON.parse(String(posts[0]?.[1]?.body))).toEqual({
      material_ids: ['parsed-first', 'failed-second'], force: false,
    })
    expect(onParsed).toHaveBeenCalledExactlyOnceWith(['parsed-first', 'failed-second'])
    expect(state.task.value?.status).toBe('failed')
  })

  it('selects the real historical graph and does not synthesize an absent result id', async () => {
    const historical = task({ status: 'completed', result: { graph_id: 'historical-actual-id' } })
    const unrelated = task({ task_id: 'inference', kind: 'inference' })
    const fetcher = intercept(() => json({ tasks: [historical, unrelated] }))
    const { state } = mount()
    await state.refreshHistory(true)
    expect(state.history.value.map((row) => row.task_id)).toEqual(['task-build'])
    expect(state.task.value).toBeNull()
    state.viewTask(historical)
    expect(state.resultGraphId.value).toBe('historical-actual-id')
    state.viewTask(task({ task_id: 'missing-id', status: 'completed', result: {} }))
    expect(state.resultGraphId.value).toBeNull()
    expect(fetcher.mock.calls.every(([, init]) => !init?.method)).toBe(true)
  })

  it('never submits from Demo or Replay, and drops a late task from an old source', async () => {
    let release!: (response: Response) => void
    const fetcher = intercept((url) => url.pathname === '/api/tasks' ? json({ tasks: [] })
      : new Promise((resolve) => { release = resolve }))
    const { state, url } = mount(ref<string | null>(null))
    await state.build(selection, options)
    await state.parse('public-source')
    expect(fetcher).not.toHaveBeenCalled()
    url.value = base
    await nextTick()
    const submitting = state.build(selection, options)
    url.value = null
    await nextTick()
    release(json(task({ status: 'completed', result: { graph_id: 'old-source-id' } }), 202))
    await submitting
    expect(state.task.value).toBeNull()
    expect(state.resultGraphId.value).toBeNull()
    expect(state.history.value).toHaveLength(0)
  })
})
