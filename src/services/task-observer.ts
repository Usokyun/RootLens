import { onBeforeUnmount, ref, shallowRef } from 'vue'
import type { TaskClient, TaskStatus, WorkTask } from '@/api/two-loop'

export const taskStatusLabels: Record<TaskStatus, string> = {
  queued: '排队中', running: '处理中', completed: '已完成', failed: '失败', interrupted: '已中断',
}
export function taskIsActive(task: WorkTask | null | undefined) {
  return task?.status === 'queued' || task?.status === 'running'
}
export function taskCanRetry(task: WorkTask | null | undefined) {
  return task?.status === 'failed' || task?.status === 'interrupted'
}

function mergeTaskEvents(previous: WorkTask, next: WorkTask): WorkTask {
  const events = new Map(previous.events.map((event) => [event.sequence, event]))
  next.events.forEach((event) => events.set(event.sequence, event))
  return { ...next, events: [...events.values()].sort((a, b) => a.sequence - b.sequence) }
}

/** One observer per view. Bind a task to its original API; changing sources clears the observer. */
export function useTaskObserver(getClient: () => TaskClient, onComplete?: (task: WorkTask) => void | Promise<void>) {
  const task = shallowRef<WorkTask | null>(null)
  const connectionError = ref('')
  const retrying = ref(false)
  let client: TaskClient | null = null
  let generation = 0
  let readingGeneration: number | null = null
  let deliveringGeneration: number | null = null
  let delivered = false
  let timer: ReturnType<typeof setTimeout> | undefined

  function stop() { if (timer !== undefined) clearTimeout(timer); timer = undefined }
  function errorText(error: unknown) { return error instanceof Error ? error.message : String(error) }
  async function publish(next: WorkTask, version: number) {
    task.value = next
    connectionError.value = ''
    if (taskIsActive(next)) {
      timer = setTimeout(() => void refresh(), 1200)
    } else if (next.status === 'completed' && !delivered && deliveringGeneration !== version) {
      deliveringGeneration = version
      try {
        await onComplete?.(next)
        if (version === generation) delivered = true
      } catch (error) {
        if (version === generation) connectionError.value = errorText(error)
      } finally {
        if (deliveringGeneration === version) deliveringGeneration = null
      }
    }
  }
  function attach(next: WorkTask, boundClient: TaskClient) {
    stop()
    const version = ++generation
    client = boundClient
    delivered = false
    retrying.value = false
    void publish(next, version)
  }
  function observe(next: WorkTask) { attach(next, getClient()) }
  async function refresh() {
    const current = task.value, boundClient = client, version = generation
    if (!current || !boundClient || readingGeneration === version) return
    stop()
    readingGeneration = version
    try {
      const sequence = current.next_sequence ?? current.events.at(-1)?.sequence ?? 0
      const next = await boundClient.task(current.task_id, sequence)
      if (version !== generation) return
      if (next.task_id !== current.task_id) throw new Error('服务返回的任务编号与当前任务不一致。')
      await publish(mergeTaskEvents(current, next), version)
    } catch (error) {
      if (version === generation) connectionError.value = errorText(error)
    } finally {
      if (readingGeneration === version) readingGeneration = null
    }
  }
  async function retry() {
    const current = task.value, boundClient = client, version = generation
    if (!current || !boundClient || !taskCanRetry(current) || retrying.value) return
    retrying.value = true
    connectionError.value = ''
    try {
      const next = await boundClient.retryTask(current.task_id)
      if (version === generation) attach(next, boundClient)
    } catch (error) {
      if (version === generation) connectionError.value = errorText(error)
    } finally {
      if (version === generation) retrying.value = false
    }
  }
  function clear() {
    stop()
    generation += 1
    client = null
    task.value = null
    connectionError.value = ''
    retrying.value = false
    delivered = false
  }
  onBeforeUnmount(clear)
  return { task, connectionError, retrying, observe, refresh, retry, clear }
}
