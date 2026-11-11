import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { KGMaterialRecord } from '@/api/contracts'
import { submitMaterialBuild, submitMaterialParse, type MaterialBuildOptions } from '@/api/material-tasks'
import { createTwoLoopClient, type WorkTask } from '@/api/two-loop'
import { taskCanRetry, taskIsActive, useTaskObserver } from '@/services/task-observer'

type MaterialSelection = Pick<KGMaterialRecord, 'material_id' | 'scenario'>

function isMaterialTask(task: WorkTask): boolean {
  return task.kind === 'material_build' || task.kind === 'material_parse'
}

export function materialTaskIds(task: WorkTask | null | undefined): string[] {
  const ids = task?.request?.material_ids
  return Array.isArray(ids) ? ids.filter((id): id is string => typeof id === 'string') : []
}

export function materialTaskGraphId(task: WorkTask | null | undefined): string | null {
  if (task?.kind !== 'material_build' || task.status !== 'completed') return null
  const id = task.result?.graph_id
  return typeof id === 'string' && id.trim() ? id : null
}

/** Material-specific submit/history; polling and retries are shared with analysis. */
export function useMaterialSourceTasks(
  backendUrl: () => string | null,
  onMaterialsChanged: (materialIds: string[]) => void | Promise<void>,
) {
  const history = ref<WorkTask[]>([])
  const historyLoading = ref(false)
  const historyError = ref('')
  const submitError = ref('')
  const submitting = ref<'material_parse' | 'material_build' | null>(null)
  let generation = 0
  let historyRequest = 0

  function backendClient() {
    const url = backendUrl()
    if (!url) throw new Error('请切换 Backend 并退出成品回放后处理素材。')
    return createTwoLoopClient(url)
  }

  const observer = useTaskObserver(backendClient, async (completed) => {
    const parsed = completed.result?.material_ids
    const ids = completed.kind === 'material_parse' && Array.isArray(parsed)
      ? parsed.filter((id): id is string => typeof id === 'string')
      : materialTaskIds(completed)
    if (ids.length) await onMaterialsChanged(ids)
  })
  const task = observer.task
  const busy = computed(() => submitting.value !== null || observer.retrying.value || taskIsActive(task.value))
  const resultGraphId = computed(() => materialTaskGraphId(task.value))

  function remember(item: WorkTask) {
    history.value = [item, ...history.value.filter(({ task_id }) => task_id !== item.task_id)]
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
  }

  watch(task, (next, previous) => {
    if (!next || !isMaterialTask(next)) return
    remember(next)
    if (previous?.task_id !== next.task_id || !taskIsActive(previous)) return
    // A batch can write earlier materials before failing; a build also persists
    // the parsed sources before it starts generating knowledge.
    const movedPastParsing = next.kind === 'material_build' && taskIsActive(next)
      && ['queued', 'parsing'].includes(previous.stage) && !['queued', 'parsing'].includes(next.stage)
    if (!taskCanRetry(next) && !movedPastParsing) return
    const ids = materialTaskIds(next)
    const current = generation
    if (ids.length) void Promise.resolve()
      .then(() => { if (current === generation) return onMaterialsChanged(ids) })
      .catch((error) => {
        if (current === generation && task.value?.task_id === next.task_id) {
          observer.connectionError.value = error instanceof Error ? error.message : String(error)
        }
      })
  })

  async function refreshHistory(resume = false) {
    const url = backendUrl()
    if (!url) return
    const request = ++historyRequest
    historyError.value = ''
    historyLoading.value = true
    try {
      const data = await createTwoLoopClient(url).listTasks(200)
      if (request !== historyRequest || backendUrl() !== url) return
      history.value = data.tasks.filter(isMaterialTask)
      if (task.value) remember(task.value)
      else if (resume && !submitting.value) {
        const active = history.value.find(taskIsActive)
        if (active) observer.observe(active)
      }
    } catch (error) {
      if (request === historyRequest && backendUrl() === url) historyError.value = String(error instanceof Error ? error.message : error)
    } finally {
      if (request === historyRequest && backendUrl() === url) historyLoading.value = false
    }
  }

  function viewTask(item: WorkTask) {
    if (!backendUrl() || !isMaterialTask(item)) return
    submitError.value = ''
    observer.observe(item)
  }

  async function submit(kind: NonNullable<typeof submitting.value>, start: (url: string) => Promise<WorkTask>): Promise<WorkTask | null> {
    const url = backendUrl()
    if (!url || busy.value) return null
    const current = generation
    submitting.value = kind
    submitError.value = ''
    observer.clear()
    try {
      const next = await start(url)
      if (current === generation && backendUrl() === url) {
        observer.observe(next)
        return next
      }
    } catch (error) {
      if (current === generation && backendUrl() === url) submitError.value = error instanceof Error ? error.message : String(error)
    } finally {
      if (current === generation) submitting.value = null
    }
    return null
  }

  function build(materials: MaterialSelection[], options: MaterialBuildOptions) {
    return submit('material_build', (url) => submitMaterialBuild(url, materials, options))
  }

  function parse(materialIds: string | readonly string[], force = false) {
    return submit('material_parse', (url) => submitMaterialParse(url, materialIds, force))
  }

  watch(backendUrl, () => {
    generation += 1
    historyRequest += 1
    observer.clear()
    history.value = []
    historyLoading.value = false
    historyError.value = ''
    submitError.value = ''
    submitting.value = null
    void refreshHistory(true)
  }, { immediate: true })

  onBeforeUnmount(() => { generation += 1; historyRequest += 1 })

  return { ...observer, history, historyLoading, historyError, submitError, submitting, busy, resultGraphId, refreshHistory, viewTask, build, parse }
}
