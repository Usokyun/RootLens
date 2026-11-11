import { createApp } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import type { TaskClient, WorkTask } from '@/api/two-loop'
import { useTaskObserver } from '@/services/task-observer'

const mounts: ReturnType<typeof createApp>[] = []
afterEach(() => { mounts.splice(0).forEach((app) => app.unmount()); vi.useRealTimers() })
function task(id: string, status: WorkTask['status'], sequence = 1): WorkTask {
  return { task_id: id, kind: 'inference', status, title: '真实状态', created_at: '', updated_at: '', stage: status, stage_label: status,
    progress: status === 'running' ? { completed: 1, total: 3, unit: '窗口', indeterminate: false } : { indeterminate: true },
    events: [{ sequence, at: '', stage: status, label: status }], next_sequence: sequence,
    result: status === 'completed' ? { run_id: 'saved-run' } : null, error: status === 'failed' ? { message: '原任务失败' } : null }
}
function observer(getClient: () => TaskClient, completed?: (task: WorkTask) => void | Promise<void>) {
  let value!: ReturnType<typeof useTaskObserver>
  const app = createApp({ setup() { value = useTaskObserver(getClient, completed); return () => null } })
  app.mount(document.createElement('div'))
  mounts.push(app)
  return value
}
function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

describe('shared source-scoped task observation', () => {
  it('merges actual incremental events and delivers a terminal result once without retrying', async () => {
    vi.useFakeTimers()
    const api = { task: vi.fn().mockResolvedValueOnce(task('id', 'running', 2)).mockResolvedValue(task('id', 'completed', 3)), retryTask: vi.fn() }
    const completed = vi.fn()
    const view = observer(() => api, completed)
    view.observe(task('id', 'queued'))
    await vi.advanceTimersByTimeAsync(1200)
    expect(api.task).toHaveBeenCalledWith('id', 1)
    expect(view.task.value?.progress).toMatchObject({ completed: 1, total: 3 })
    await vi.advanceTimersByTimeAsync(1200)
    expect(api.task).toHaveBeenLastCalledWith('id', 2)
    expect(view.task.value?.events.map((event) => event.sequence)).toEqual([1, 2, 3])
    expect(completed).toHaveBeenCalledOnce()
    await view.refresh()
    await vi.advanceTimersByTimeAsync(5000)
    expect(api.task).toHaveBeenCalledTimes(3)
    expect(completed).toHaveBeenCalledOnce()
    expect(api.retryTask).not.toHaveBeenCalled()
  })
  it('pauses GET on disconnection, then refreshes and retries only a failed task when asked', async () => {
    vi.useFakeTimers()
    const api = { task: vi.fn().mockRejectedValueOnce(new Error('服务不可用')).mockResolvedValue(task('id', 'failed', 2)),
      retryTask: vi.fn().mockResolvedValue(task('new-task', 'queued')) }
    const view = observer(() => api)
    view.observe(task('id', 'running'))
    await vi.advanceTimersByTimeAsync(5000)
    expect(view.connectionError.value).toBe('服务不可用')
    expect(api.task).toHaveBeenCalledOnce()
    await view.retry()
    expect(api.retryTask).not.toHaveBeenCalled()
    await view.refresh()
    expect(view.task.value?.error?.message).toBe('原任务失败')
    await view.retry()
    expect(api.retryTask).toHaveBeenCalledExactlyOnceWith('id')
    expect(view.task.value?.task_id).toBe('new-task')
  })
  it('cannot publish a late old-source result after clearing and observing another service', async () => {
    const response = deferred<WorkTask>()
    const old = { task: vi.fn().mockReturnValue(response.promise), retryTask: vi.fn() }
    const next = { task: vi.fn(), retryTask: vi.fn() }
    let client = old
    const complete = vi.fn()
    const view = observer(() => client, complete)
    view.observe(task('old-id', 'running'))
    const pending = view.refresh()
    view.clear()
    client = next
    view.observe(task('new-id', 'queued'))
    response.resolve(task('old-id', 'completed', 2))
    await pending
    expect(view.task.value?.task_id).toBe('new-id')
    expect(complete).not.toHaveBeenCalled()
  })
  it('does not repeat a retry POST on double click or bind its response to a new source', async () => {
    const response = deferred<WorkTask>()
    const api = { task: vi.fn(), retryTask: vi.fn().mockReturnValue(response.promise) }
    const view = observer(() => api)
    view.observe(task('original', 'interrupted'))
    const pending = view.retry()
    await view.retry()
    view.clear()
    response.resolve(task('retry', 'queued'))
    await pending
    expect(api.retryTask).toHaveBeenCalledExactlyOnceWith('original')
    expect(view.task.value).toBeNull()
  })
})
