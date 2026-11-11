<script setup lang="ts">
import { IconClockCircle, IconHistory, IconPlus, IconRefresh, IconRight, IconSearch } from '@arco-design/web-vue/es/icon'
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { createTwoLoopClient, type SavedAnalysisListItem, type WorkTask } from '@/api/two-loop'
import NewAnalysisDialog from '@/components/evidence/NewAnalysisDialog.vue'
import TaskStatusPanel from '@/components/tasks/TaskStatusPanel.vue'
import { type AnalysisDraftSeed } from '@/services/analysis-draft'
import { newAnalysisIntent, savedAnalysisRoute } from '@/services/analysis-entry'
import {
  analysisTaskStages, buildAnalysisHistory, completedAnalysisId, emptyAnalysisFilters, filterAnalysisHistory,
  rememberAnalysisList, restoreAnalysisList, type AnalysisHistoryRow,
} from '@/services/analysis-history'
import { taskCanRetry, taskIsActive, taskStatusLabels, useTaskObserver } from '@/services/task-observer'
import { sourceSelectionReset, updateWorkbenchState } from '@/services/workbench-state'

// EvidenceHomeView keys this instance by backend address; it never follows another source’s task.
const props = defineProps<{ baseUrl: string }>()
const emit = defineEmits<{ 'import-replay': [] }>()
const base = props.baseUrl
const service = createTwoLoopClient(base)
const router = useRouter(), route = useRoute()
const previous = restoreAnalysisList(base)
const filters = reactive(previous.filters)
const history = shallowRef<SavedAnalysisListItem[]>([])
const tasks = shallowRef<WorkTask[]>([])
const indexLoading = ref(true)
const listError = ref(''), taskListError = ref('')
const dialogVisible = ref(false)
const seed = shallowRef<AnalysisDraftSeed>({})
const root = ref<HTMLElement | null>(null)
const taskSection = ref<HTMLElement | null>(null)
let scroller: HTMLElement | null = null
let scrollTop = previous.scrollTop
let selectedTaskId = previous.taskId
let restoringScroll = true
let followCompletion = false
let readRevision = 0
let disposed = false

const observer = useTaskObserver(() => service, async (finished) => {
  rememberTask(finished)
  const id = completedAnalysisId(finished)
  if (!id) return
  if (followCompletion && route.name === 'evidence' && !disposed) {
    followCompletion = false
    await openAnalysis(id)
  }
})
const { task, connectionError, retrying } = observer
const activeTasks = computed(() => tasks.value.filter(taskIsActive))
const rows = computed(() => filterAnalysisHistory(buildAnalysisHistory(history.value, tasks.value), filters))
const steps = computed(() => task.value ? analysisTaskStages(task.value) : [])
const activeCount = computed(() => taskListError.value ? null : activeTasks.value.length)
const resultId = computed(() => completedAnalysisId(task.value))
const missingResult = computed(() => task.value?.status === 'completed' && !resultId.value)
const creationBlocked = computed(() => taskIsActive(task.value) || retrying.value)
const datasetLabels: Record<string, string> = { mvtec: 'MVTec', tep: 'TEP', wafer: 'Wafer' }
const reasonerLabels: Record<string, string> = { unified_abduction: '统一条件溯因', tep_rootkgd: 'RootKGD', graded_abduction: '分级解释溯因' }
const inputLabels: Record<string, string> = { image: '原始样本', process: '原始样本', wafer: '原始样本', evidence: '中间 Evidence', records: '测量记录' }
const date = new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
function createdAt(value: string) {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime()) ? '未记录' : date.format(parsed)
}
function statusColor(status: WorkTask['status']) {
  return status === 'completed' ? 'green' : status === 'failed' || status === 'interrupted' ? 'red' : 'arcoblue'
}
function persistPosition() { rememberAnalysisList(base, { filters, scrollTop, taskId: selectedTaskId }) }
function recordScroll() {
  if (restoringScroll) return
  scrollTop = scroller?.scrollTop ?? 0
  persistPosition()
}
watch([() => filters.search, () => filters.dataset, () => filters.status], persistPosition)
function rememberTask(next: WorkTask) {
  if (next.kind !== 'inference') return
  tasks.value = [next, ...tasks.value.filter(item => item.task_id !== next.task_id)]
    .sort((a, b) => b.created_at.localeCompare(a.created_at))
  if (task.value?.task_id === next.task_id) {
    selectedTaskId = next.task_id
    persistPosition()
  }
}
watch(task, value => { if (value) rememberTask(value) })

async function readIndex() {
  const revision = ++readRevision
  indexLoading.value = true
  const results = await Promise.allSettled([service.listAnalyses(), service.listTasks(100)])
  if (disposed || revision !== readRevision) return
  const [runs, taskRecords] = results
  if (runs.status === 'fulfilled') {
    history.value = runs.value.runs
    listError.value = ''
  } else listError.value = runs.reason instanceof Error ? runs.reason.message : String(runs.reason)
  if (taskRecords.status === 'fulfilled') {
    tasks.value = taskRecords.value.tasks.filter(item => item.kind === 'inference')
    taskListError.value = ''
    // An index response can be older than the poll currently displayed.
    const shown = task.value
    if (shown) {
      const recorded = tasks.value.find(item => item.task_id === shown.task_id)
      if (!recorded || shown.updated_at >= recorded.updated_at) rememberTask(shown)
    } else {
      const recent = tasks.value.find(item => item.task_id === selectedTaskId && item.status !== 'completed')
      const active = recent ?? activeTasks.value[0]
      if (active) focusTask(active)
    }
  } else taskListError.value = taskRecords.reason instanceof Error ? taskRecords.reason.message : String(taskRecords.reason)
  indexLoading.value = false
}
async function refresh() {
  await Promise.all([readIndex(), observer.refresh()])
}
function focusTask(value: WorkTask, follow = false) {
  followCompletion = follow
  selectedTaskId = value.task_id
  persistPosition()
  observer.observe(value)
  rememberTask(value)
}
function selectActive(value: unknown) {
  const item = activeTasks.value.find(current => current.task_id === value)
  if (item) focusTask(item)
}
async function openAnalysis(runId: string) {
  if (restoringScroll) persistPosition()
  else recordScroll()
  await router.push(savedAnalysisRoute('evidence', runId))
}
function openRow(row: AnalysisHistoryRow) {
  followCompletion = false
  if (row.runId) void openAnalysis(row.runId)
  else if (row.task) {
    focusTask(row.task)
    void nextTick(() => taskSection.value?.scrollIntoView({ block: 'nearest' }))
  }
}
async function retryTask() {
  if (!taskCanRetry(task.value) || retrying.value) return
  followCompletion = true
  await observer.retry()
}
function openNew(seedValue: AnalysisDraftSeed = {}) {
  seed.value = seedValue
  dialogVisible.value = true
}
function consumeGraphIntent() {
  const intent = newAnalysisIntent(route.query)
  if (route.name !== 'evidence' || !intent) return
  followCompletion = false
  updateWorkbenchState(sourceSelectionReset())
  openNew({ graphId: intent.graphId, graphOrigin: 'explicit' })
  void router.replace({ name: 'evidence' })
}
function handleSubmitted(value: WorkTask) {
  if (disposed) return
  dialogVisible.value = false
  focusTask(value, true)
  void nextTick(() => taskSection.value?.scrollIntoView({ block: 'nearest' }))
}
watch([() => route.query.intent, () => route.query.graph], consumeGraphIntent)
onMounted(async () => {
  scroller = root.value?.closest<HTMLElement>('.ads-brain-workbench-layout__content') ?? null
  scroller?.addEventListener('scroll', recordScroll, { passive: true })
  consumeGraphIntent()
  await readIndex()
  await nextTick()
  if (disposed) return
  if (scroller) scroller.scrollTop = scrollTop
  restoringScroll = false
})
onBeforeUnmount(() => {
  disposed = true
  readRevision += 1
  scroller?.removeEventListener('scroll', recordScroll)
  persistPosition()
})
</script>

<template>
  <section ref="root" class="analysis-list rl-page rl-screen" aria-label="运行与证据列表">
    <header class="analysis-list-title">
      <div><h1>运行与证据</h1><p class="workspace-subtle">发起分析，查看执行阶段与已保存结果。</p></div>
      <a-space wrap>
        <a-button type="text" @click="emit('import-replay')">导入回放</a-button>
        <a-button type="primary" :disabled="creationBlocked" @click="openNew()"><template #icon><IconPlus /></template>新建分析</a-button>
      </a-space>
    </header>

    <section ref="taskSection" class="rl-section-card" aria-label="分析任务">
      <header class="rl-section-card__header analysis-list-card-head">
        <h2 class="rl-section-card__title"><IconClockCircle /> {{ task && !taskIsActive(task) ? '最近查看任务' : '进行中' }}</h2>
        <a-tag v-if="activeCount !== null && !indexLoading && (!task || taskIsActive(task))" :color="activeCount ? 'arcoblue' : undefined">{{ activeCount }}</a-tag>
        <div class="analysis-list-actions">
          <div v-if="activeTasks.length > 1 || (activeTasks.length && task && !taskIsActive(task))" class="analysis-task-choice">
            <a-select aria-label="选择进行中的任务" :model-value="taskIsActive(task) ? task?.task_id : undefined" placeholder="进行中的任务" @change="selectActive">
              <a-option v-for="item in activeTasks" :key="item.task_id" :value="item.task_id">{{ item.title }}</a-option>
            </a-select>
          </div>
          <a-button :loading="indexLoading" @click="refresh"><template #icon><IconRefresh /></template>刷新</a-button>
        </div>
      </header>
      <div class="rl-section-card__body analysis-task-body">
        <a-alert v-if="taskListError" type="warning">任务列表读取失败：{{ taskListError }}</a-alert>
        <template v-if="task">
          <TaskStatusPanel :task="task" :connection-error="connectionError" :retrying="retrying" @refresh="observer.refresh" @retry="retryTask">
            <template #actions>
              <a-button v-if="resultId" type="outline" @click="openAnalysis(resultId)">打开本次分析 <IconRight /></a-button>
            </template>
          </TaskStatusPanel>
          <a-alert v-if="missingResult" type="warning">任务已完成，服务未返回保存分析编号。</a-alert>
          <ol class="analysis-task-stages" aria-label="后端阶段记录">
            <li v-for="(step, index) in steps" :key="step.key" :data-stage-state="step.state" :aria-current="step.state === 'active' ? 'step' : undefined">
              <span class="analysis-task-number">{{ index + 1 }}</span>
              <span><strong>{{ step.label }}</strong><small>{{ { active: '当前阶段', recorded: '已记录', stopped: '停止于此', unseen: '未记录' }[step.state] }}</small></span>
            </li>
          </ol>
        </template>
        <p v-else-if="indexLoading" class="workspace-subtle"><a-spin :size="12" /> 正在读取分析任务…</p>
        <p v-else-if="!taskListError" class="workspace-subtle">当前没有运行中的分析。</p>
      </div>
    </section>

    <section class="rl-section-card" aria-label="历史记录">
      <header class="rl-section-card__header analysis-list-card-head">
        <h2 class="rl-section-card__title"><IconHistory /> 历史记录</h2><span class="workspace-subtle">{{ rows.length }} 条</span>
      </header>
      <div class="analysis-list-filters" aria-label="历史筛选">
        <a-input v-model="filters.search" :input-attrs="{ 'aria-label': '搜索历史' }" placeholder="搜索分析名称或样本" allow-clear class="analysis-history-search"><template #prefix><IconSearch /></template></a-input>
        <div class="analysis-history-filter">
          <a-select v-model="filters.dataset" aria-label="筛选场景">
            <a-option value="all">全部场景</a-option><a-option value="mvtec">MVTec</a-option><a-option value="tep">TEP</a-option><a-option value="wafer">Wafer</a-option>
          </a-select>
        </div>
        <div class="analysis-history-filter">
          <a-select v-model="filters.status" aria-label="筛选运行状态">
            <a-option value="all">全部状态</a-option><a-option value="completed">已完成</a-option><a-option value="failed">失败</a-option><a-option value="interrupted">已中断</a-option>
          </a-select>
        </div>
        <a-button type="text" @click="Object.assign(filters, emptyAnalysisFilters())">清除筛选</a-button>
      </div>
      <a-alert v-if="listError" type="error" class="analysis-list-error">保存记录读取失败：{{ listError }}</a-alert>
      <a-table :data="rows" :loading="indexLoading" row-key="id" :bordered="false" :pagination="false" class="analysis-history-table" @row-click="openRow">
        <template #columns>
          <a-table-column title="分析">
            <template #cell="{ record }">
              <button class="analysis-history-name" type="button" @click.stop="openRow(record)">{{ record.title }}</button>
              <span v-if="record.dataset || record.filename" class="analysis-history-meta workspace-subtle">{{ [datasetLabels[record.dataset] ?? record.dataset, record.filename].filter(Boolean).join(' · ') }}</span>
            </template>
          </a-table-column>
          <a-table-column title="输入" :width="134"><template #cell="{ record }"><span class="analysis-history-input">{{ inputLabels[record.inputMode] ?? '未记录' }}</span></template></a-table-column>
          <a-table-column title="解释器" :width="122"><template #cell="{ record }">{{ reasonerLabels[record.reasoner] ?? '未记录' }}</template></a-table-column>
          <a-table-column title="运行状态" :width="94"><template #cell="{ record }"><a-tag :color="statusColor(record.status)">{{ taskStatusLabels[record.status as WorkTask['status']] }}</a-tag></template></a-table-column>
          <a-table-column title="保存结论" :width="180"><template #cell="{ record }"><a-tag v-if="record.conclusion.color" :color="record.conclusion.color">{{ record.conclusion.label }}</a-tag><span v-else class="workspace-subtle">{{ record.conclusion.label }}</span></template></a-table-column>
          <a-table-column title="创建时间" :width="119"><template #cell="{ record }"><span class="workspace-subtle analysis-history-time">{{ createdAt(record.createdAt) }}</span></template></a-table-column>
          <a-table-column title="操作" :width="76"><template #cell="{ record }"><a-button type="text" size="mini" @click.stop="openRow(record)">{{ record.runId ? '打开' : '任务' }} <IconRight /></a-button></template></a-table-column>
        </template>
        <template #empty><a-empty :description="listError ? '保存记录未能读取' : '没有符合筛选的历史记录'" /></template>
      </a-table>
    </section>

    <NewAnalysisDialog v-model:visible="dialogVisible" :base-url="base" :seed="seed" :submission-blocked="creationBlocked" @submitted="handleSubmitted" />
  </section>
</template>

<style scoped>
.analysis-list { display: grid; gap: 14px; max-width: 1550px; margin: 0 auto; padding: 4px 6px 14px; }
.analysis-list-title { display: flex; align-items: center; justify-content: space-between; gap: 12px; flex-wrap: wrap; }
.analysis-list-title h1 { margin: 0 0 5px; font-size: 21px; line-height: 1.35; }
.analysis-list-title p { margin: 0; }
.analysis-list-card-head { justify-content: flex-start; gap: 8px; }
.analysis-list-card-head .rl-section-card__title { display: flex; align-items: center; gap: 7px; }
.analysis-list-card-head .arco-icon { color: rgb(var(--primary-6)); }
.analysis-list-actions { display: flex; gap: 8px; margin-left: auto; align-items: center; }
.analysis-task-choice { width: min(244px, 26vw); }
.analysis-task-body { display: grid; gap: 9px; }
.analysis-task-body p { margin: 0; }
.analysis-task-stages { list-style: none; margin: 2px 0 0; padding: 0; display: grid; grid-template-columns: repeat(5, minmax(0,1fr)); gap: 8px; }
.analysis-task-stages li { min-width: 0; display: flex; align-items: flex-start; gap: 7px; border: 1px solid transparent; border-radius: 3px; background: var(--color-fill-1); padding: 7px 8px; }
.analysis-task-stages strong, .analysis-task-stages small { display: block; }
.analysis-task-stages strong { font-size: 12px; font-weight: 550; }
.analysis-task-stages small { color: var(--color-text-3); margin-top: 1px; }
.analysis-task-number { flex: 0 0 19px; height: 19px; display: grid; place-items: center; border-radius: 50%; font-size: 11px; background: var(--color-fill-3); }
.analysis-task-stages li[data-stage-state='active'] { background: var(--color-primary-light-1); border-color: rgb(var(--primary-3)); }
.analysis-task-stages li[data-stage-state='active'] .analysis-task-number { background: rgb(var(--primary-6)); color: white; }
.analysis-task-stages li[data-stage-state='stopped'] { border-color: rgb(var(--red-3)); }
.analysis-list-filters { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; padding: 10px 12px; border-bottom: 1px solid var(--color-border-2); }
.analysis-history-search { width: min(286px, 40vw); }
.analysis-history-filter { flex: 0 0 108px; min-width: 0; }
.analysis-list-error { margin: 8px 12px; }
.analysis-history-table :deep(.arco-table-tr) { cursor: pointer; }
.analysis-history-table :deep(.arco-table-td-content) { overflow-wrap: anywhere; }
.analysis-history-name { padding: 0; text-align: left; color: #16334d; font: inherit; font-weight: 550; background: none; border: 0; cursor: pointer; }
.analysis-history-name:hover { color: rgb(var(--primary-6)); }
.analysis-history-meta { display: block; margin-top: 2px; }
.analysis-history-input { white-space: nowrap; }
.analysis-history-time { font-variant-numeric: tabular-nums; white-space: nowrap; }
@media (max-width: 960px) { .analysis-list { padding-inline: 0; } .analysis-task-stages { grid-template-columns: repeat(3, minmax(0,1fr)); } }
</style>
