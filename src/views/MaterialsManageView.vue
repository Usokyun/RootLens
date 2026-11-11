<script setup lang="ts">
import { IconHistory, IconPlus, IconRefresh, IconRelation, IconSearch, IconSettings } from '@arco-design/web-vue/es/icon'
import { computed, onBeforeUnmount, reactive, ref, shallowRef, watch } from 'vue'
import { useRouter } from 'vue-router'

import { createApiClient } from '@/api/client'
import type { KGMaterialRecord } from '@/api/contracts'
import { changeMaterialArchive, listArchivedMaterials } from '@/api/material-archive'
import { materialBuildBlocker, materialCapabilities, type MaterialBuildScenario } from '@/api/material-tasks'
import { createTwoLoopClient, type DemoGroup, type WorkTask } from '@/api/two-loop'
import MaterialDetails from '@/components/materials/MaterialDetails.vue'
import MaterialImportDialog from '@/components/materials/MaterialImportDialog.vue'
import TaskStatusPanel from '@/components/tasks/TaskStatusPanel.vue'
import { useAppPreferences } from '@/services/app-preferences'
import {
  formatMaterialDate, materialError, materialListSource, materialScenarios, materialStatus,
  materialStatuses, materialTypeLabel, materialTypes, scenarioLabel, type MaterialStatus,
} from '@/services/material-presentation'
import { materialTaskGraphId, materialTaskIds, useMaterialSourceTasks } from '@/services/material-source-tasks'
import { taskCanRetry, taskIsActive, taskStatusLabels } from '@/services/task-observer'

const { preferences } = useAppPreferences()
const router = useRouter()
const backendUrl = computed(() => preferences.value.apiBaseUrl)
const reader = computed(() => createApiClient(backendUrl.value))
const scenes = materialScenarios.filter((scene) => scene.value !== 'shared')

type LibraryView = 'active' | 'archive'
function emptyLibrary() {
  return { rows: [] as KGMaterialRecord[], loading: false, loaded: false, error: '' }
}
const library = reactive({ active: emptyLibrary(), archive: emptyLibrary() })
const listRequests = { active: 0, archive: 0 }
const libraryView = ref<LibraryView>('active')
const currentLibrary = computed(() => library[libraryView.value])
const filters = reactive({ keyword: '', scene: 'all', type: 'all', status: 'all', sort: 'recent' })
const hasFilters = computed(() => Boolean(filters.keyword.trim() || filters.scene !== 'all' || filters.type !== 'all' || filters.status !== 'all'))
const focusedId = ref<string | null>(null)
const selectedIds = ref<string[]>([])
const detailRevision = ref(0)
const notice = ref('')
const importVisible = ref(false)
const demoVisible = ref(false)
const demoGroups = shallowRef<DemoGroup[]>([])
const demoLoading = ref(false)
const demoAdding = ref('')
const demoError = ref('')
const buildVisible = ref(false)
const historyVisible = ref(false)
const historyTab = ref<'build' | 'parse'>('build')
const taskDialogId = ref<string | null>(null)
const fromHistory = ref(false)
const archiveTarget = ref<KGMaterialRecord | null>(null)
const archiveBusy = ref(false)
const archiveError = ref('')
const buildScope = ref<KGMaterialRecord[]>([])
const buildForm = reactive({ title: '', dataset: '' as MaterialBuildScenario | '', allowRepair: true })
const submittingIds = ref<string[]>([])
let sourceRevision = 0

const sourceTasks = useMaterialSourceTasks(() => backendUrl.value, refreshTaskMaterials)
const {
  task: sourceTask, history: sourceHistory, historyLoading: sourceHistoryLoading, historyError: sourceHistoryError,
  submitError: sourceSubmitError, submitting: sourceSubmitting, busy: sourceBusy,
  resultGraphId: sourceGraphId, connectionError: sourceConnectionError, retrying: sourceRetrying,
} = sourceTasks

const activeIds = computed(() => new Set([
  ...(taskIsActive(sourceTask.value) ? materialTaskIds(sourceTask.value) : []),
  ...submittingIds.value,
]))

function displayedStatus(material: KGMaterialRecord): MaterialStatus {
  const status = materialStatus(material)
  if (libraryView.value === 'active' && activeIds.value.has(material.material_id)
    && (sourceTask.value?.kind === 'material_parse' || (status !== 'ready'
      && (!sourceTask.value || ['queued', 'parsing'].includes(sourceTask.value.stage))))) return 'running'
  return status
}

const filtered = computed(() => {
  const term = filters.keyword.trim().toLocaleLowerCase()
  return currentLibrary.value.rows.filter((material) =>
    (filters.scene === 'all' || material.scenario === filters.scene)
    && (filters.type === 'all' || material.source_type === filters.type)
    && (filters.status === 'all' || displayedStatus(material) === filters.status)
    && (!term || [material.title, materialListSource(material), material.notes, material.material_id, material.source_id]
      .some((value) => value?.toLocaleLowerCase().includes(term))),
  ).sort((left, right) => {
    if (filters.sort === 'title') return left.title.localeCompare(right.title, 'zh-CN')
    if (filters.sort === 'type') return left.source_type.localeCompare(right.source_type)
    const a = Date.parse(left.updated_at ?? left.created_at ?? '') || 0
    const b = Date.parse(right.updated_at ?? right.created_at ?? '') || 0
    return filters.sort === 'oldest' ? a - b : b - a
  })
})
const focused = computed(() => filtered.value.find((material) => material.material_id === focusedId.value) ?? null)
const selected = computed(() => library.active.rows.filter((material) => selectedIds.value.includes(material.material_id)))
const visibleSelectedCount = computed(() => filtered.value.filter(({ material_id }) => selectedIds.value.includes(material_id)).length)
const pending = computed(() => selected.value.filter((material) => materialStatus(material) !== 'ready'))
const selectionSummary = computed(() => {
  const counts: Record<MaterialStatus, number> = { ready: 0, pending: 0, failed: 0, running: 0 }
  for (const material of selected.value) counts[displayedStatus(material)] += 1
  const hidden = selected.value.length - visibleSelectedCount.value
  const summary = (['ready', 'pending', 'failed', 'running'] as const)
    .flatMap((status) => counts[status] ? [counts[status] + ' 份' + materialStatuses[status].label] : [])
  if (hidden > 0) summary.push(hidden + ' 份不在当前列表')
  return summary.join(' · ')
})
const selectedScene = computed(() => {
  const nonShared = new Set(selected.value.map((material) => material.scenario).filter((scene) => scene !== 'shared'))
  return nonShared.size === 1 ? scenarioLabel([...nonShared][0]!) : ''
})
const knownMaterials = computed(() => [...library.active.rows, ...library.archive.rows])
const buildPending = computed(() => buildScope.value.filter((material) => materialStatus(material) !== 'ready').length)
const buildBlocker = computed(() => {
  if (buildScope.value.some(({ material_id }) => !library.active.rows.some((material) => material.material_id === material_id))) {
    return '素材清单已变化，请关闭后重新选材。'
  }
  if (new Set(buildScope.value.map(({ scenario }) => scenario).filter((scene) => scene !== 'shared')).size > 1) {
    return '一次只能生成一个场景的图谱。请调整选材，可保留共享素材。'
  }
  if (!buildForm.dataset) return '请选择图谱场景。'
  return materialBuildBlocker(buildScope.value, { ...buildForm, dataset: buildForm.dataset })
})
const taskDialogRecord = computed(() => {
  const id = taskDialogId.value
  if (!id) return null
  return sourceTask.value?.task_id === id ? sourceTask.value : sourceHistory.value.find((task) => task.task_id === id) ?? null
})
const dialogGraphId = computed(() => materialTaskGraphId(taskDialogRecord.value))
const dialogGraph = computed(() => {
  const graph = taskDialogRecord.value?.result?.graph
  return graph && typeof graph === 'object' ? graph as Record<string, unknown> : null
})
const dialogSourceIds = computed(() => materialTaskIds(taskDialogRecord.value))
const taskIsTracked = computed(() => taskDialogRecord.value?.task_id === sourceTask.value?.task_id)
const displayedHistory = computed(() => sourceHistory.value.filter((task) =>
  task.kind === (historyTab.value === 'parse' ? 'material_parse' : 'material_build')))
const taskHeading = computed(() => {
  const task = taskDialogRecord.value
  if (task?.kind === 'material_parse') return '提取进度'
  if (dialogGraphId.value) return '工作图已生成'
  if (taskCanRetry(task)) return '构图未完成'
  return '构图进度'
})
const bannerLabel = computed(() => {
  const task = sourceTask.value
  if (!task) return ''
  if (sourceGraphId.value) return '工作图已生成'
  if (task.status === 'completed') return '构图任务已完成'
  if (taskCanRetry(task)) return (task.kind === 'material_parse' ? '提取' : '构图') + taskStatusLabels[task.status]
  return task.stage_label || taskStatusLabels[task.status]
})

function resetFilters() {
  Object.assign(filters, { keyword: '', scene: 'all', type: 'all', status: 'all', sort: 'recent' })
}
function toggleSelection(id: string, checked: boolean) {
  selectedIds.value = checked ? [...new Set([...selectedIds.value, id])] : selectedIds.value.filter((current) => current !== id)
}
function toggleVisible(checked: boolean) {
  const ids = filtered.value.map(({ material_id }) => material_id)
  selectedIds.value = checked ? [...new Set([...selectedIds.value, ...ids])] : selectedIds.value.filter((id) => !ids.includes(id))
}

async function refreshMaterials(view: LibraryView = libraryView.value) {
  const base = backendUrl.value
  const revision = sourceRevision
  const request = ++listRequests[view]
  const state = library[view]
  const stillCurrent = () => revision === sourceRevision && request === listRequests[view]
  state.loading = true
  state.error = ''
  try {
    const response = view === 'archive' ? await listArchivedMaterials(base) : await reader.value.listKGMaterials()
    if (!stillCurrent()) return
    state.rows = response.materials
    state.loaded = true
    if (view === 'active') {
      const existing = new Set(response.materials.map(({ material_id }) => material_id))
      selectedIds.value = selectedIds.value.filter((id) => existing.has(id))
    }
  } catch (error) {
    if (stillCurrent()) state.error = materialError(error)
  } finally {
    if (stillCurrent()) state.loading = false
  }
}

async function refreshTaskMaterials(ids: string[]) {
  const revision = sourceRevision
  await refreshMaterials('active')
  if (revision === sourceRevision && focusedId.value && ids.includes(focusedId.value)) detailRevision.value += 1
}

function changeLibrary(view: LibraryView) {
  libraryView.value = view
  resetFilters()
  void refreshMaterials(view)
}

function applyMaterialChanges(records: KGMaterialRecord[], archived: boolean) {
  // An older list response must not undo a successfully acknowledged write.
  const ids = new Set(records.map(({ material_id }) => material_id))
  for (const key of ['active', 'archive'] as const) {
    listRequests[key] += 1
    library[key].loading = false
    const rest = library[key].rows.filter((record) => !ids.has(record.material_id))
    library[key].rows = key === (archived ? 'archive' : 'active') ? [...records, ...rest] : rest
  }
  if (archived) selectedIds.value = selectedIds.value.filter((id) => !ids.has(id))
}

function handleAdded(records: KGMaterialRecord[]) {
  applyMaterialChanges(records, false)
  libraryView.value = 'active'
  resetFilters()
  focusedId.value = records[0]?.material_id ?? focusedId.value
  detailRevision.value += 1
  notice.value = '已添加 ' + records.length + ' 份素材。'
  void refreshMaterials('active')
}

async function openDemoMaterials() {
  if (demoLoading.value || demoAdding.value) return
  const revision = sourceRevision
  const base = backendUrl.value
  demoVisible.value = true
  demoLoading.value = true
  demoError.value = ''
  demoGroups.value = []
  try {
    const result = await createTwoLoopClient(base).demos()
    if (revision === sourceRevision) demoGroups.value = result.demos.filter(group => group.materials.length)
  } catch (error) {
    if (revision === sourceRevision) demoError.value = materialError(error)
  } finally {
    if (revision === sourceRevision) demoLoading.value = false
  }
}

async function addDemoMaterials(group: DemoGroup) {
  if (!demoVisible.value || demoAdding.value || !demoGroups.value.includes(group)
    || !group.materials.length || group.materials.some(asset => asset.available !== true)) return
  const revision = sourceRevision
  const base = backendUrl.value
  demoAdding.value = group.id
  demoError.value = ''
  try {
    const { materials } = await createTwoLoopClient(base).addDemoMaterials(group.id)
    if (revision !== sourceRevision) return
    const active = materials.filter(record => !record.archived_at)
    const archived = materials.length - active.length
    if (active.length) handleAdded(active)
    if (archived) {
      if (!active.length) changeLibrary('archive')
      notice.value = [active.length ? `素材库中可用 ${active.length} 份。` : '', `${archived} 份已移出，恢复后可选作构图素材。`].filter(Boolean).join('')
    } else if (active.length) {
      notice.value = `${active.length} 份演示素材已在素材库中。可勾选后提取内容或生成工作图。`
    } else {
      demoError.value = '后端没有返回演示素材。'
      return
    }
    demoVisible.value = false
  } catch (error) {
    if (revision === sourceRevision) demoError.value = materialError(error)
  } finally {
    if (revision === sourceRevision) demoAdding.value = ''
  }
}

function requestArchive() {
  if (!focused.value || activeIds.value.has(focused.value.material_id)) return
  archiveError.value = ''
  archiveTarget.value = focused.value
}
function dismissArchive() {
  if (!archiveBusy.value) archiveTarget.value = null
}
async function mutateArchive(material: KGMaterialRecord | null, action: 'archive' | 'restore') {
  const base = backendUrl.value
  if (!material || archiveBusy.value || (action === 'archive' && activeIds.value.has(material.material_id))) return
  const revision = sourceRevision
  archiveBusy.value = true
  archiveError.value = ''
  notice.value = ''
  try {
    const result = await changeMaterialArchive(base, material.material_id, action)
    if (revision !== sourceRevision) return
    applyMaterialChanges([result.material], action === 'archive')
    if (action === 'restore') {
      libraryView.value = 'active'
      resetFilters()
      focusedId.value = result.material.material_id
      detailRevision.value += 1
    }
    archiveTarget.value = null
    notice.value = action === 'archive' ? '已移出「' + material.title + '」。' : '已恢复「' + material.title + '」。'
    void refreshMaterials('active')
  } catch (error) {
    if (revision === sourceRevision) archiveError.value = materialError(error)
  } finally {
    if (revision === sourceRevision) archiveBusy.value = false
  }
}

async function extractMaterials(materials: KGMaterialRecord[], force = false) {
  if (sourceBusy.value || archiveBusy.value || libraryView.value !== 'active' || !materials.length) return
  const revision = sourceRevision
  notice.value = ''
  const ids = materials.map(({ material_id }) => material_id)
  submittingIds.value = ids
  try {
    await sourceTasks.parse(ids, force)
  } finally {
    if (revision === sourceRevision) submittingIds.value = []
  }
}

function requestBuild() {
  if (sourceBusy.value || archiveBusy.value || !selected.value.length || libraryView.value !== 'active') return
  buildScope.value = [...selected.value]
  const nonShared = new Set(buildScope.value.map((material) => material.scenario).filter((scene) => scene !== 'shared'))
  const single = nonShared.size === 1 ? [...nonShared][0] : undefined
  buildForm.dataset = single && Object.hasOwn(materialCapabilities, single) ? single as MaterialBuildScenario : ''
  buildForm.title = buildForm.dataset ? scenarioLabel(buildForm.dataset) + ' 工作图' : '新建工作图'
  buildForm.allowRepair = true
  sourceSubmitError.value = ''
  buildVisible.value = true
}
async function submitBuild() {
  if (sourceBusy.value || archiveBusy.value || buildBlocker.value || !buildForm.dataset) return
  const revision = sourceRevision
  notice.value = ''
  submittingIds.value = buildScope.value.map(({ material_id }) => material_id)
  try {
    const task = await sourceTasks.build(buildScope.value, { ...buildForm, dataset: buildForm.dataset })
    if (revision === sourceRevision && task) {
      buildVisible.value = false
      showTask(task)
    }
  } finally {
    if (revision === sourceRevision) submittingIds.value = []
  }
}

function openGraph(graphId: string) {
  void router.push({ name: 'graphs', query: { graph: graphId } })
}
function showTask(task: WorkTask, historical = false) {
  if (historical && taskIsActive(task) && !sourceBusy.value) sourceTasks.viewTask(task)
  fromHistory.value = historical
  historyVisible.value = false
  taskDialogId.value = task.task_id
  if (historical && library.archive.loaded === false && library.archive.loading === false) void refreshMaterials('archive')
}
function closeTask(back = false) {
  taskDialogId.value = null
  if (back && fromHistory.value) historyVisible.value = true
}
async function retryTask() {
  const task = taskDialogRecord.value
  if (!task || !taskCanRetry(task) || sourceBusy.value || archiveBusy.value) return
  const revision = sourceRevision
  if (!taskIsTracked.value) sourceTasks.viewTask(task)
  submittingIds.value = materialTaskIds(task)
  try {
    await sourceTasks.retry()
    if (revision === sourceRevision && taskDialogId.value === task.task_id && sourceTask.value) taskDialogId.value = sourceTask.value.task_id
  } finally {
    if (revision === sourceRevision) submittingIds.value = []
  }
}

function showHistory() {
  historyTab.value = 'build'
  historyVisible.value = true
  void sourceTasks.refreshHistory(true)
}
function selectHistoryTab(value: string | number) {
  if (value === 'build' || value === 'parse') historyTab.value = value
}
function sourceTitle(id: string) {
  return knownMaterials.value.find((record) => record.material_id === id)?.title ?? id
}

watch(filtered, (rows) => {
  if (!rows.some(({ material_id }) => material_id === focusedId.value)) focusedId.value = rows[0]?.material_id ?? null
})
watch(
  backendUrl,
  () => {
    sourceRevision += 1
    Object.assign(library.active, emptyLibrary())
    Object.assign(library.archive, emptyLibrary())
    libraryView.value = 'active'
    resetFilters()
    selectedIds.value = []
    focusedId.value = null
    submittingIds.value = []
    detailRevision.value += 1
    notice.value = ''
    importVisible.value = buildVisible.value = historyVisible.value = false
    demoVisible.value = demoLoading.value = false
    demoAdding.value = demoError.value = ''
    demoGroups.value = []
    taskDialogId.value = null
    archiveTarget.value = null
    archiveError.value = ''
    archiveBusy.value = false
    void refreshMaterials('active')
  },
  { immediate: true },
)
onBeforeUnmount(() => { sourceRevision += 1 })
</script>

<template>
  <div class="rl-page rl-screen materials-page" :class="{ 'rl-page--motion': preferences.enablePageEntranceMotion }">
    <header class="materials-page__heading">
      <div>
        <h1>素材库</h1>
        <p>管理知识图谱的来源资料</p>
      </div>
      <a-space wrap>
        <a-button @click="showHistory"><template #icon><IconHistory /></template>构图记录</a-button>
        <a-button @click="openDemoMaterials">添加演示素材</a-button>
        <a-button :type="selected.length ? 'secondary' : 'primary'" @click="importVisible = true">
          <template #icon><IconPlus /></template>添加素材
        </a-button>
      </a-space>
    </header>

    <div v-if="sourceTask && (sourceTask.kind === 'material_build' || sourceTask.status !== 'completed')" class="materials-task-banner" :class="'materials-task-banner--' + sourceTask.status" aria-live="polite">
      <div>
        <strong>{{ bannerLabel }}</strong>
        <span v-if="taskCanRetry(sourceTask) && sourceTask.stage_label"> · {{ sourceTask.stage_label }}</span>
        <span class="materials-task-banner__title">{{ sourceTask.title }}</span>
      </div>
      <a-space wrap>
        <a-button type="text" @click="showTask(sourceTask)">{{ taskIsActive(sourceTask) ? '查看进度' : '查看结果' }}</a-button>
        <a-button v-if="sourceGraphId" @click="openGraph(sourceGraphId)">打开图谱</a-button>
      </a-space>
    </div>
    <a-alert v-if="notice" type="success" closable @close="notice = ''">{{ notice }}</a-alert>
    <a-alert v-if="sourceSubmitError && !buildVisible" type="error">{{ sourceSubmitError }}</a-alert>
    <a-alert v-if="archiveError && !archiveTarget" type="error">{{ archiveError }}</a-alert>

    <section class="rl-section-card materials-workspace" aria-label="素材工作区">
      <div class="materials-workspace__columns">
        <section class="materials-library" aria-label="素材列表" :aria-busy="currentLibrary.loading">
          <div class="materials-library__filters">
            <a-input
              v-model="filters.keyword" class="materials-library__search" allow-clear
              :input-attrs="{ 'aria-label': '搜索素材' }" placeholder="搜索名称或来源"
            >
              <template #prefix><IconSearch /></template>
            </a-input>
            <div id="materials-filter-scene" v-control-label="'筛选场景'" class="materials-library__filter">
              <a-select v-model="filters.scene">
                <a-option value="all">全部场景</a-option>
                <a-option v-for="scene in materialScenarios" :key="scene.value" :value="scene.value">{{ scene.label }}</a-option>
              </a-select>
            </div>
            <div id="materials-filter-status" v-control-label="'筛选提取状态'" class="materials-library__filter">
              <a-select v-model="filters.status">
                <a-option value="all">全部状态</a-option>
                <a-option v-for="(status, key) in materialStatuses" :key="key" :value="key">{{ status.label }}</a-option>
              </a-select>
            </div>
            <a-popover trigger="click" position="br">
              <a-button aria-label="更多筛选"><template #icon><IconSettings /></template></a-button>
              <template #content>
                <div class="materials-filter-options">
                  <label for="materials-filter-type-input">类型</label>
                  <div id="materials-filter-type" v-control-label="'筛选素材类型'">
                    <a-select v-model="filters.type">
                      <a-option value="all">全部类型</a-option>
                      <a-option v-for="type in materialTypes" :key="type.value" :value="type.value">{{ type.label }}</a-option>
                    </a-select>
                  </div>
                  <label for="materials-filter-sort-input">排序</label>
                  <div id="materials-filter-sort" v-control-label="'排序'">
                    <a-select v-model="filters.sort">
                      <a-option value="recent">最近更新</a-option>
                      <a-option value="oldest">最早更新</a-option>
                      <a-option value="title">按名称</a-option>
                      <a-option value="type">按类型</a-option>
                    </a-select>
                  </div>
                </div>
              </template>
            </a-popover>
          </div>

          <div class="materials-library__meta">
            <div>
              <strong>{{ libraryView === 'active' ? '素材列表' : '已移出素材' }}</strong>
              <span v-if="currentLibrary.loaded || filtered.length"> · {{ filtered.length }} 份</span>
            </div>
            <a-space>
              <a-button type="text" size="mini" aria-label="刷新素材列表" :loading="currentLibrary.loading" @click="refreshMaterials()">
                <template #icon><IconRefresh /></template>
              </a-button>
              <a-button v-if="libraryView === 'active'" type="text" size="mini" @click="changeLibrary('archive')">已移出</a-button>
              <a-button v-else type="text" size="mini" @click="changeLibrary('active')">返回素材库</a-button>
            </a-space>
          </div>

          <a-alert v-if="currentLibrary.error" type="error" class="materials-library__error">
            {{ currentLibrary.error }} <a-button type="text" size="mini" @click="refreshMaterials()">重新读取</a-button>
          </a-alert>

          <div v-if="filtered.length" class="materials-library__rows">
            <table class="materials-library__table">
              <thead>
                <tr>
                  <th v-if="libraryView === 'active'" scope="col" class="materials-library__check">
                    <input
                      type="checkbox"
                      aria-label="选择当前列表中的全部素材"
                      :checked="visibleSelectedCount === filtered.length"
                      :indeterminate="visibleSelectedCount > 0 && visibleSelectedCount < filtered.length"
                      @change="toggleVisible(($event.target as HTMLInputElement).checked)"
                    />
                  </th>
                  <th scope="col">素材名称</th>
                  <th scope="col" class="materials-library__scene">场景</th>
                  <th scope="col" class="materials-library__status">提取状态</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="material in filtered"
                  :key="material.material_id"
                  :data-material-id="material.material_id"
                  :class="{ 'materials-library__row--focused': material.material_id === focusedId }"
                >
                  <td v-if="libraryView === 'active'" class="materials-library__check">
                    <input
                      type="checkbox"
                      :checked="selectedIds.includes(material.material_id)"
                      :aria-label="'选择素材 ' + material.title"
                      @change="toggleSelection(material.material_id, ($event.target as HTMLInputElement).checked)"
                    />
                  </td>
                  <td>
                    <button
                      type="button" class="materials-library__name"
                      :aria-label="'查看素材 ' + material.title"
                      :aria-pressed="material.material_id === focusedId"
                      aria-controls="materials-focused-detail"
                      @click="focusedId = material.material_id"
                    >
                      <span class="materials-library__format">{{ materialTypeLabel(material.source_type) }}</span>
                      <span class="materials-library__name-text">
                        <strong :title="material.title">{{ material.title }}</strong>
                        <span :title="materialListSource(material)">
                          <span class="materials-library__mobile-scene">{{ scenarioLabel(material.scenario) }} · </span>
                          {{ materialListSource(material) || material.material_id }}
                        </span>
                      </span>
                    </button>
                  </td>
                  <td class="materials-library__scene">{{ scenarioLabel(material.scenario) }}</td>
                  <td class="materials-library__status">
                    <a-tag
                      :color="materialStatuses[displayedStatus(material)].color"
                      :class="'materials-status--' + displayedStatus(material)"
                    >{{ materialStatuses[displayedStatus(material)].label }}</a-tag>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else-if="currentLibrary.loading" class="materials-library__empty"><a-spin /> 正在读取素材…</div>
          <div v-else-if="!currentLibrary.error" class="materials-library__empty">
            <strong>{{ hasFilters ? '没有匹配的素材' : (libraryView === 'archive' ? '没有已移出的素材' : '还没有素材') }}</strong>
            <a-button v-if="hasFilters" type="text" size="small" @click="resetFilters">清除筛选</a-button>
            <span v-else-if="libraryView === 'active'">添加演示素材、上传文件或登记网址后，素材会显示在这里。</span>
          </div>
        </section>

        <aside id="materials-focused-detail" class="materials-workspace__detail" aria-label="素材详情">
          <MaterialDetails
            v-if="focused" :key="focused.material_id"
            :material="focused" :reader="reader" :revision="detailRevision" :status="displayedStatus(focused)"
            :archived="libraryView === 'archive'" :archive-blocked="activeIds.has(focused.material_id)"
            :mutation-busy="archiveBusy" :task-busy="sourceBusy"
            @archive="requestArchive" @restore="mutateArchive(focused, 'restore')"
            @parse="extractMaterials([focused], materialStatus(focused) === 'ready')"
          />
          <div v-else class="materials-library__empty"><strong>素材详情</strong><span>选择一份素材查看内容。</span></div>
        </aside>
      </div>

      <footer v-if="libraryView === 'active'" class="materials-selection" aria-label="构图选材">
        <div aria-live="polite">
          <strong>构图选材</strong>
          <b v-if="selected.length">已选 {{ selected.length }} 份{{ selectedScene ? ' · ' + selectedScene : '' }}</b>
          <p v-if="selected.length">{{ selectionSummary }}</p>
          <p v-else>勾选本次构图使用的素材。</p>
        </div>
        <a-space wrap>
          <a-button v-if="selected.length" type="text" @click="selectedIds = []">清空</a-button>
          <a-button v-if="pending.length" :disabled="sourceBusy || archiveBusy" @click="extractMaterials(pending)">批量提取</a-button>
          <a-button type="primary" :disabled="!selected.length || sourceBusy || archiveBusy" @click="requestBuild">
            <template #icon><IconRelation /></template>生成知识图谱
          </a-button>
        </a-space>
      </footer>
    </section>
  </div>

  <MaterialImportDialog v-model:visible="importVisible" :backend-url="backendUrl" @added="handleAdded" />

  <a-modal v-model:visible="demoVisible" title="添加演示素材" width="min(520px, calc(100vw - 32px))"
    :footer="false" :mask-closable="false" :closable="!demoAdding" :esc-to-close="!demoAdding">
    <div class="materials-dialog__body">
      <p class="materials-dialog__note">将发布资料加入素材库。提取和构图由您另行发起。</p>
      <a-alert v-if="demoError" type="error">{{ demoError }}
        <a-button v-if="!demoGroups.length" size="mini" type="text" @click="openDemoMaterials">重读目录</a-button>
      </a-alert>
      <div v-if="demoLoading" role="status"><a-spin /> 正在读取演示目录…</div>
      <ul v-else-if="demoGroups.length" class="materials-dialog__scope">
        <li v-for="group in demoGroups" :key="group.id">
          <span><strong>{{ scenarioLabel(group.dataset) }}</strong> · {{ group.materials.length }} 份资料</span>
          <a-button :data-demo-materials-id="group.id" :loading="demoAdding === group.id"
            :disabled="!!demoAdding || group.materials.some(asset => asset.available !== true)"
            @click="addDemoMaterials(group)">{{ group.materials.some(asset => asset.available !== true) ? '资料不可用' : '添加' }}</a-button>
        </li>
      </ul>
      <p v-else-if="!demoError" class="materials-dialog__note">目录中没有可添加的演示素材。</p>
    </div>
  </a-modal>

  <a-modal
    :visible="Boolean(archiveTarget)" title="移出素材库？" width="min(480px, calc(100vw - 32px))"
    :mask-closable="false" :esc-to-close="!archiveBusy" :closable="!archiveBusy" @cancel="dismissArchive"
  >
    <div class="materials-dialog__body">
      <p><strong>{{ archiveTarget?.title }}</strong> 将不再用于新构图。</p>
      <p class="materials-dialog__note">原文件、提取结果和历史图谱的来源记录会保留。可在「已移出」中恢复。</p>
      <a-alert v-if="archiveError" type="error">{{ archiveError }}</a-alert>
    </div>
    <template #footer>
      <a-space>
        <a-button :disabled="archiveBusy" @click="dismissArchive">取消</a-button>
        <a-button type="primary" status="danger" :loading="archiveBusy" @click="mutateArchive(archiveTarget, 'archive')">确认移出</a-button>
      </a-space>
    </template>
  </a-modal>

  <a-modal
    v-model:visible="buildVisible" title="生成知识图谱" width="min(510px, calc(100vw - 32px))"
    :mask-closable="false" :esc-to-close="!sourceSubmitting" :closable="!sourceSubmitting" :footer="false"
  >
    <form class="materials-dialog__body" @submit.prevent="submitBuild">
      <h3>本次使用 {{ buildScope.length }} 份素材</h3>
      <ul class="materials-dialog__scope">
        <li v-for="material in buildScope" :key="material.material_id">
          <span>{{ material.title }}</span>
          <a-tag
            :color="materialStatuses[materialStatus(material)].color"
            :class="'materials-status--' + materialStatus(material)"
          >{{ materialStatuses[materialStatus(material)].label }}</a-tag>
        </li>
      </ul>
      <a-alert v-if="buildPending" type="info">{{ buildPending }} 份素材需先提取内容，已提取的内容直接复用。</a-alert>
      <div class="materials-dialog__field">
        <label for="materials-graph-title">图谱名称</label>
        <a-input v-model="buildForm.title" :input-attrs="{ id: 'materials-graph-title', 'aria-label': '图谱名称' }" :disabled="!!sourceSubmitting" />
      </div>
      <div class="materials-dialog__field">
        <label for="materials-graph-scene-input">图谱场景</label>
        <div id="materials-graph-scene" v-control-label="'图谱场景'">
          <a-select v-model="buildForm.dataset" placeholder="选择图谱场景" :disabled="!!sourceSubmitting">
            <a-option v-for="scene in scenes" :key="scene.value" :value="scene.value">{{ scene.buildLabel }}</a-option>
          </a-select>
        </div>
      </div>
      <details class="materials-dialog__advanced">
        <summary>高级设置</summary>
        <a-checkbox v-model="buildForm.allowRepair" :disabled="!!sourceSubmitting">校验失败时允许自动修复一次</a-checkbox>
      </details>
      <a-alert v-if="buildBlocker || sourceSubmitError" :type="sourceSubmitError ? 'error' : 'warning'">{{ sourceSubmitError || buildBlocker }}</a-alert>
      <footer class="materials-dialog__actions">
        <span class="materials-dialog__note">最多 {{ buildForm.allowRepair ? 2 : 1 }} 次模型调用</span>
        <a-space>
          <a-button :disabled="!!sourceSubmitting" @click="buildVisible = false">取消</a-button>
          <a-button type="primary" html-type="submit" :disabled="!!buildBlocker || archiveBusy || (sourceBusy && !sourceSubmitting)" :loading="sourceSubmitting === 'material_build'">
            开始构图
          </a-button>
        </a-space>
      </footer>
    </form>
  </a-modal>

  <a-modal v-model:visible="historyVisible" title="构图记录" width="min(620px, calc(100vw - 32px))" :footer="false">
    <a-tabs :active-key="historyTab" @change="selectHistoryTab">
      <a-tab-pane key="build" title="构图任务" />
      <a-tab-pane key="parse" title="提取任务" />
    </a-tabs>
    <div class="materials-dialog__body materials-history">
      <a-alert v-if="sourceHistoryError" type="error">{{ sourceHistoryError }} <a-button type="text" size="mini" @click="sourceTasks.refreshHistory(true)">重新读取</a-button></a-alert>
      <div v-else-if="sourceHistoryLoading && !displayedHistory.length" class="materials-library__empty"><a-spin /> 正在读取任务…</div>
      <a-empty v-else-if="!displayedHistory.length" :description="historyTab === 'build' ? '暂无构图任务' : '暂无提取任务'" />
      <ul v-if="displayedHistory.length" class="materials-history__rows">
        <li v-for="item in displayedHistory" :key="item.task_id">
          <button type="button" :data-task-id="item.task_id" @click="showTask(item, true)">
            <span><strong>{{ item.title }}</strong><small>{{ materialTaskIds(item).length }} 份素材 · {{ formatMaterialDate(item.updated_at) }}</small></span>
            <a-tag :color="item.status === 'completed' ? 'green' : taskCanRetry(item) ? 'red' : 'arcoblue'">{{ taskStatusLabels[item.status] }}</a-tag>
          </button>
        </li>
      </ul>
      <footer class="materials-dialog__actions"><a-button @click="historyVisible = false">关闭</a-button></footer>
    </div>
  </a-modal>

  <a-modal :visible="Boolean(taskDialogRecord)" :title="taskHeading" width="min(540px, calc(100vw - 32px))" :footer="false" @cancel="closeTask()">
    <div v-if="taskDialogRecord" class="materials-dialog__body">
      <TaskStatusPanel
        :task="taskDialogRecord"
        :connection-error="taskIsTracked ? sourceConnectionError : undefined"
        :retrying="taskIsTracked && sourceRetrying"
        @refresh="sourceTasks.refresh"
        @retry="retryTask"
      />
      <div v-if="dialogGraphId" class="materials-result">
        <div class="materials-result__stats">
          <span v-if="typeof dialogGraph?.node_count === 'number'"><strong>{{ dialogGraph.node_count }}</strong> 个节点</span>
          <span v-if="typeof dialogGraph?.edge_count === 'number'"><strong>{{ dialogGraph.edge_count }}</strong> 条关系</span>
          <span v-if="dialogSourceIds.length"><strong>{{ dialogSourceIds.length }}</strong> 份来源</span>
          <a-tag v-if="dialogGraph?.enabled === false">生成时未启用</a-tag>
        </div>
        <ul v-if="dialogSourceIds.length" class="materials-dialog__scope">
          <li v-for="id in dialogSourceIds" :key="id">{{ sourceTitle(id) }}</li>
        </ul>
        <p class="materials-dialog__note">在图谱页查看或编辑，启用后可用于新分析。</p>
      </div>
      <a-alert v-else-if="taskDialogRecord.kind === 'material_build' && taskDialogRecord.status === 'completed'" type="error">
        后端未返回工作图编号，无法打开结果。
        <a-button v-if="taskIsTracked" size="mini" type="text" @click="sourceTasks.refresh">重新读取状态</a-button>
      </a-alert>
      <p v-if="taskCanRetry(taskDialogRecord) && taskDialogRecord.kind === 'material_build'" class="materials-dialog__note">
        重试会保留原输入与设置、另建任务，并可能再次调用模型。
      </p>
      <a-alert v-if="taskCanRetry(taskDialogRecord) && sourceBusy && !sourceRetrying" type="info">当前有素材任务进行中，结束后可重试。</a-alert>
      <footer class="materials-dialog__actions">
        <a-button @click="closeTask(true)">{{ fromHistory ? '返回构图记录' : '返回素材库' }}</a-button>
        <a-button v-if="dialogGraphId" type="primary" @click="openGraph(dialogGraphId)">打开图谱</a-button>
      </footer>
    </div>
  </a-modal>

</template>

<style scoped>
.materials-page { padding: 7px 8px 18px; }
.materials-page__heading { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: 12px; }
.materials-page__heading h1 { margin: 0; font-size: 23px; line-height: 1.38; font-weight: 600; color: var(--color-text-1); }
.materials-page__heading p { margin: 3px 0 0; font-size: 13px; color: var(--color-text-2); }
.materials-workspace__columns { display: grid; grid-template-columns: minmax(0, 1fr) minmax(290px, .58fr); }
.materials-workspace__detail { display: flex; min-width: 0; border-left: 1px solid var(--rl-border); background: var(--rl-bg-soft); }
.materials-library { min-width: 0; }
.materials-library__filters { display: flex; flex-wrap: wrap; align-items: center; gap: 7px; padding: 13px 13px 5px; }
.materials-library__search { flex: 1 1 160px; width: auto; }
.materials-library__filter { flex: 0 1 102px; min-width: 92px; }
.materials-library__meta { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 4px 8px; min-height: 32px; padding: 0 13px 2px; font-size: 12px; color: var(--color-text-2); }
.materials-library__meta strong { color: var(--color-text-1); font-weight: 600; }
.materials-filter-options { display: grid; gap: 5px; width: 148px; }
.materials-filter-options label { color: var(--color-text-2); font-size: 12px; }
.materials-library__error { width: auto; margin: 0 12px 8px; }
.materials-library__rows { max-height: clamp(280px, 56vh, 540px); overflow: auto; }
.materials-library__table { width: 100%; border-spacing: 0; table-layout: fixed; text-align: left; }
.materials-library__table th, .materials-library__table td { border-bottom: 1px solid var(--rl-border); padding: 0 6px; }
.materials-library__table th { position: sticky; top: 0; z-index: 1; height: 34px; background: var(--color-fill-1); color: var(--color-text-2); font-size: 12px; font-weight: 500; }
.materials-library__table tbody tr:hover { background: var(--color-fill-1); }
.materials-library__table tbody .materials-library__row--focused { background: rgb(var(--primary-1)); }
.materials-library__table .materials-library__check { width: 40px; text-align: center; }
.materials-library__check input { width: 14px; height: 14px; margin: 0; accent-color: rgb(var(--primary-6)); vertical-align: middle; cursor: pointer; }
.materials-library__table .materials-library__scene { width: 73px; color: var(--color-text-2); font-size: 12px; }
.materials-library__table .materials-library__status { width: 92px; padding-right: 9px; }
.materials-status--ready { color: rgb(var(--green-8)); }
.materials-status--pending { color: rgb(var(--gold-9)); }
.materials-status--failed { color: rgb(var(--red-8)); }
.materials-library__name { display: flex; width: 100%; align-items: center; gap: 8px; min-height: 54px; padding: 6px 0; text-align: left; border: 0; background: transparent; color: var(--color-text-1); font: inherit; cursor: pointer; }
.materials-library__name:focus-visible { outline: 2px solid rgb(var(--primary-6)); outline-offset: -2px; border-radius: 3px; }
.materials-library__format { flex: 0 0 34px; display: grid; place-items: center; height: 26px; border-radius: 3px; font-size: 10px; font-weight: 600; background: rgb(var(--primary-1)); color: rgb(var(--primary-6)); }
.materials-library__name-text { display: grid; min-width: 0; gap: 2px; }
.materials-library__name-text > * { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.materials-library__name-text strong { font-size: 13px; font-weight: 600; }
.materials-library__name-text > span { font-size: 12px; color: var(--color-text-2); }
.materials-library__mobile-scene { display: none; }
.materials-library__empty { display: grid; align-content: start; justify-items: start; gap: 6px; padding: 20px 13px; color: var(--color-text-2); font-size: 13px; }
.materials-library__empty strong { color: var(--color-text-1); }
.materials-selection { border-top: 1px solid var(--rl-border); display: flex; justify-content: space-between; flex-wrap: wrap; align-items: center; gap: 8px 14px; padding: 10px 13px; background: var(--rl-bg-soft); }
.materials-selection b { margin-left: 7px; color: rgb(var(--primary-6)); font-size: 13px; font-weight: 600; }
.materials-selection p { margin: 2px 0 0; color: var(--color-text-2); font-size: 12px; }
.materials-task-banner { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 4px 12px; min-height: 42px; padding: 6px 10px 6px 12px; border: 1px solid var(--rl-border); border-radius: 4px; background: rgb(var(--primary-1)); font-size: 13px; }
.materials-task-banner--completed { background: rgb(var(--green-1)); }
.materials-task-banner--failed, .materials-task-banner--interrupted { background: rgb(var(--red-1)); }
.materials-task-banner__title { margin-left: 7px; color: var(--color-text-2); overflow-wrap: anywhere; }
.materials-dialog__body { display: grid; gap: 12px; min-width: 0; }
.materials-dialog__body p, .materials-dialog__body h3 { margin: 0; }
.materials-dialog__body h3 { font-size: 14px; font-weight: 600; }
.materials-dialog__note { color: var(--color-text-2); font-size: 12px; line-height: 1.55; }
.materials-dialog__scope { margin: 0; padding: 0 10px; max-height: 145px; overflow: auto; list-style: none; border: 1px solid var(--rl-border); border-radius: 3px; }
.materials-dialog__scope li { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 4px 10px; padding: 7px 0; overflow-wrap: anywhere; }
.materials-dialog__scope li + li { border-top: 1px solid var(--rl-border); }
.materials-dialog__field { display: grid; gap: 5px; }
.materials-dialog__field label, .materials-dialog__advanced { color: var(--color-text-2); font-size: 13px; }
.materials-dialog__advanced summary { cursor: pointer; }
.materials-dialog__advanced :deep(.arco-checkbox) { padding-block: 6px; }
.materials-dialog__actions { display: flex; justify-content: flex-end; align-items: center; flex-wrap: wrap; gap: 8px; padding-top: 10px; border-top: 1px solid var(--rl-border); }
.materials-dialog__actions > .materials-dialog__note { margin-right: auto; }
.materials-history { padding-top: 8px; }
.materials-history__rows { margin: 0; padding: 0; list-style: none; max-height: 48vh; overflow: auto; }
.materials-history__rows button { width: 100%; display: flex; justify-content: space-between; align-items: center; gap: 8px; border: 0; border-bottom: 1px solid var(--rl-border); background: var(--color-bg-1); padding: 8px 6px; text-align: left; color: var(--color-text-1); font: inherit; cursor: pointer; }
.materials-history__rows button:hover { background: var(--color-fill-1); }
.materials-history__rows strong, .materials-history__rows small { display: block; overflow-wrap: anywhere; }
.materials-history__rows small { color: var(--color-text-2); margin-top: 2px; }
.materials-result { display: grid; gap: 8px; }
.materials-result__stats { display: flex; flex-wrap: wrap; align-items: center; gap: 8px 18px; padding: 8px 10px; background: var(--color-fill-1); border-radius: 3px; }
.materials-result__stats strong { font-size: 16px; }
@media (max-width: 960px) {
  .materials-page { padding-inline: 2px; }
  .materials-workspace__columns { grid-template-columns: minmax(0, 1fr); }
  .materials-workspace__detail { border-left: 0; border-top: 1px solid var(--rl-border); }
}
@media (max-width: 600px) {
  .materials-library__filters { padding-inline: 8px; }
  .materials-library__search { flex-basis: 100%; }
  .materials-library__filter { flex: 1 1 90px; min-width: 0; }
  .materials-library__table .materials-library__scene { display: none; }
  .materials-library__mobile-scene { display: inline; }
  .materials-library__table .materials-library__check { width: 30px; }
  .materials-library__table .materials-library__status { width: 78px; padding-right: 4px; }
}
</style>
