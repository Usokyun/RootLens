import { onBeforeUnmount, ref } from 'vue'
import type { WorkTask } from '@/api/workbench'
import { api, rememberTask } from '@/services/workspace'

/** Poll only server-reported stages. No client-side progress simulation. */
export function useTaskObserver(onComplete: (task: WorkTask) => void | Promise<void>) {
  const task = ref<WorkTask | null>(null)
  const connectionError = ref('')
  const retrying = ref(false)
  let timer: ReturnType<typeof setTimeout> | undefined
  let generation = 0
  let completedId = ''
  let disposed = false
  function stop() { if (timer) clearTimeout(timer); timer = undefined }
  async function update(id: string, gen: number) {
    try {
      const next = await api().task(id)
      if (gen !== generation || disposed) return
      connectionError.value = ''; task.value = next; rememberTask(next)
      if (next.status === 'completed') {
        if (completedId !== next.task_id) { completedId = next.task_id; await onComplete(next) }
      } else if (next.status === 'running' || next.status === 'queued') {
        timer = setTimeout(() => void update(id, gen), 1200)
      }
    } catch (error) {
      if (gen !== generation || disposed) return
      connectionError.value = error instanceof Error ? error.message : String(error)
    }
  }
  function observe(next: WorkTask) {
    stop(); generation += 1; task.value = next; connectionError.value = ''; rememberTask(next)
    void update(next.task_id, generation)
  }
  function clear() { stop(); generation += 1; task.value = null; connectionError.value = ''; completedId = '' }
  async function refresh() { if (task.value) { stop(); await update(task.value.task_id, generation) } }
  async function retry() {
    if (!task.value) return
    retrying.value = true
    try { observe(await api().retryTask(task.value.task_id)) }
    catch (error) { connectionError.value = error instanceof Error ? error.message : String(error) }
    finally { retrying.value = false }
  }
  onBeforeUnmount(() => { disposed = true; generation += 1; stop() })
  return { task, connectionError, retrying, observe, refresh, retry, clear }
}
