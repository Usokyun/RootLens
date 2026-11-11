import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { KGMaterialRecord } from '@/api/contracts'
import { submitMaterialBuild, submitMaterialParse, type MaterialBuildOptions } from '@/api/material-tasks'
import { createTwoLoopClient, type WorkTask } from '@/api/two-loop'
import { taskIsActive, useTaskObserver } from '@/services/task-observer'

type MaterialSelection = Pick<KGMaterialRecord, 'material_id' | 'scenario'>

function isMaterialTask(task: WorkTask): boolean {
  return task.kind === 'material_build' || task.kind === 'material_parse'
}

function parsedMaterials(task: WorkTask): string[] {
  const ids = task.result?.material_ids
  return Array.isArray(ids) ? ids.filter((id): id is string => typeof id === 'string') : []
}

/** Material-specific submit/history; polling and retries are shared with analysis. */
export function useMaterialSourceTasks(
  backendUrl: () => string | null,
  onParsed: (materialIds: string[]) => void | Promise<void>,
) {
  const history = ref<WorkTask[]>([])
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
    if (completed.kind === 'material_parse') await onParsed(parsedMaterials(completed))
  })
  const task = observer.task
  const busy = computed(() => submitting.value !== null || observer.retrying.value || taskIsActive(task.value))
  const resultGraphId = computed(() => {
    const current = task.value
    if (current?.kind !== 'material_build' || current.status !== 'completed') return null
    const id = current.result?.graph_id
    return typeof id === 'string' && id.trim() ? id : null
  })

  function remember(item: WorkTask) {
    history.value = [item, ...history.value.filter(({ task_id }) => task_id !== item.task_id)]
      .sort((a, b) => b.created_at.localeCompare(a.created_at))
  }

  watch(task, (next) => { if (next && isMaterialTask(next)) remember(next) })

  async function refreshHistory(resume = false) {
    const url = backendUrl()
    if (!url) return
    const request = ++historyRequest
    historyError.value = ''
    try {
      const data = await createTwoLoopClient(url).listTasks(200)
      if (request !== historyRequest || backendUrl() !== url) return
      history.value = data.tasks.filter(isMaterialTask)
      if (task.value) remember(task.value)
      else if (resume) {
        const active = history.value.find(taskIsActive)
        if (active) observer.observe(active)
      }
    } catch (error) {
      if (request === historyRequest && backendUrl() === url) historyError.value = String(error instanceof Error ? error.message : error)
    }
  }

  function viewTask(item: WorkTask) {
    if (!backendUrl() || !isMaterialTask(item)) return
    submitError.value = ''
    observer.observe(item)
  }

  async function submit(kind: NonNullable<typeof submitting.value>, start: (url: string) => Promise<WorkTask>) {
    const url = backendUrl()
    if (!url || busy.value) return
    const current = generation
    submitting.value = kind
    submitError.value = ''
    observer.clear()
    try {
      const next = await start(url)
      if (current === generation && backendUrl() === url) observer.observe(next)
    } catch (error) {
      if (current === generation && backendUrl() === url) submitError.value = error instanceof Error ? error.message : String(error)
    } finally {
      if (current === generation) submitting.value = null
    }
  }

  function build(materials: MaterialSelection[], options: MaterialBuildOptions) {
    return submit('material_build', (url) => submitMaterialBuild(url, materials, options))
  }

  function parse(materialId: string, force = false) {
    return submit('material_parse', (url) => submitMaterialParse(url, materialId, force))
  }

  watch(backendUrl, () => {
    generation += 1
    historyRequest += 1
    observer.clear()
    history.value = []
    historyError.value = ''
    submitError.value = ''
    submitting.value = null
    void refreshHistory(true)
  }, { immediate: true })

  onBeforeUnmount(() => { generation += 1; historyRequest += 1 })

  return { ...observer, history, historyError, submitError, submitting, busy, resultGraphId, refreshHistory, viewTask, build, parse }
}
