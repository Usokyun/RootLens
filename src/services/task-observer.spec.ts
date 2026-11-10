import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, h, type App } from 'vue'
import type { WorkTask } from '@/api/workbench'
const mocks = vi.hoisted(() => ({ task:vi.fn(), retryTask:vi.fn(), rememberTask:vi.fn() }))
vi.mock('@/services/workspace', () => ({ api: () => ({ task:mocks.task, retryTask:mocks.retryTask }), rememberTask:mocks.rememberTask }))
import { useTaskObserver } from '@/services/task-observer'
import TaskProgress from '@/components/ui/TaskProgress.vue'
const baseTask: WorkTask = { task_id:'task-a',kind:'inference',status:'queued',title:'真实分析',created_at:'2026-11-10',updated_at:'2026-11-10',stage:'queued',stage_label:'排队',progress:null,events:[],result:null,error:null }
let app: App | null = null
function setupObserver(done = vi.fn()) {
  let observer!: ReturnType<typeof useTaskObserver>
  app = createApp({ setup() { observer=useTaskObserver(done);return()=>h('div') } });app.mount(document.createElement('div'))
  return { observer, done }
}
beforeEach(() => { vi.useFakeTimers(); vi.clearAllMocks() })
afterEach(() => { app?.unmount();app=null;vi.useRealTimers() })
describe('server task observer', () => {
  it('polls real stages, completes once and stops polling', async () => {
    const running = { ...baseTask,status:'running',stage:'measurement',stage_label:'实际测量',progress:{completed:1,total:3,unit:'窗口'} } as WorkTask
    const complete = { ...baseTask,status:'completed',result:{run_id:'run-a'} } as WorkTask
    mocks.task.mockResolvedValueOnce(running).mockResolvedValue(complete)
    const {observer,done}=setupObserver();observer.observe(baseTask)
    await vi.advanceTimersByTimeAsync(0);expect(observer.task.value?.progress).toEqual({completed:1,total:3,unit:'窗口'})
    await vi.advanceTimersByTimeAsync(1200);expect(done).toHaveBeenCalledOnce();expect(done).toHaveBeenCalledWith(complete)
    await vi.advanceTimersByTimeAsync(6000);expect(mocks.task).toHaveBeenCalledTimes(2)
  })
  it('does not invent a failed/completed status when the progress connection is lost', async () => {
    mocks.task.mockRejectedValue(new Error('连接断开'))
    const {observer}=setupObserver();observer.observe({...baseTask,status:'running'})
    await vi.advanceTimersByTimeAsync(0)
    expect(observer.connectionError.value).toBe('连接断开');expect(observer.task.value?.status).toBe('running')
    await vi.advanceTimersByTimeAsync(6000);expect(mocks.task).toHaveBeenCalledOnce()
  })
  it('retries explicitly as a new task and preserves the original reference', async () => {
    mocks.task.mockResolvedValue({...baseTask,status:'failed',error:{message:'模型失败'}})
    const {observer}=setupObserver();observer.observe({...baseTask,status:'failed'})
    await vi.advanceTimersByTimeAsync(0)
    const next={...baseTask,task_id:'task-retry',retry_of:'task-a'}
    mocks.retryTask.mockResolvedValue(next);mocks.task.mockResolvedValue(next)
    await observer.retry();expect(mocks.retryTask).toHaveBeenCalledWith('task-a');expect(observer.task.value?.task_id).toBe('task-retry')
  })
  it('does not draw a fabricated percentage for an LLM stage', () => {
    const element=document.createElement('div')
    app=createApp(TaskProgress,{task:{...baseTask,status:'running',stage_label:'LLM制作',progress:{indeterminate:true}}});app.mount(element)
    expect(element.textContent).toContain('LLM制作');expect(element.textContent).not.toContain('%')
    expect(element.querySelector('.is-indeterminate')).not.toBeNull()
  })
})

describe('stale server progress', () => {
  it('stops animating progress and shows state uncertainty during a connection error', () => {
    const element=document.createElement('div')
    app=createApp(TaskProgress,{task:{...baseTask,status:'running',stage_label:'LLM制作',progress:{indeterminate:true}},connectionError:'连接断开'});app.mount(element)
    expect(element.textContent).toContain('状态待确认')
    expect(element.textContent).toContain('重新连接')
    expect(element.querySelector('.task-progress__track')).toBeNull()
  })
})
