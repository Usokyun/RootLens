<script setup lang="ts">
import { Message, Modal } from '@arco-design/web-vue'
import { IconDown, IconRefresh, IconSearch } from '@arco-design/web-vue/es/icon'
import { computed, inject, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { isNavigationFailure, onBeforeRouteLeave, onBeforeRouteUpdate, useRoute, useRouter } from 'vue-router'
import { ApiError, createApiClient } from '@/api/client'
import type { KGStudioPayload, WorkingGraphPackage, WorkingGraphSummary } from '@/api/contracts'
import WorkingGraphEditor from '@/components/graphs/WorkingGraphEditor.vue'
import WorkingGraphInspector from '@/components/graphs/WorkingGraphInspector.vue'
import WorkingGraphNetwork from '@/components/graphs/WorkingGraphNetwork.vue'
import { newAnalysisRoute } from '@/services/analysis-entry'
import { editableWorkingGraphNode } from '@/services/working-graph-edit'
import type { WorkingGraphSelection } from '@/services/working-graph-view'
import {
  defaultWorkingGraph, graphRequest, graphScene, graphScenes, isCurrentWorkingGraph, rememberedWorkingGraph,
  rememberWorkingGraph, workingGraphAccess, workingGraphLeaveGuardKey, workingGraphRoute,
} from '@/services/working-graph-workspace'

const props = defineProps<{ baseUrl: string; connectionChanged: boolean }>()
const emit = defineEmits<{ 'switch-source': [] }>()
const route = useRoute(), router = useRouter()
const guard = inject(workingGraphLeaveGuardKey, null)
const base = props.baseUrl // This instance and every request are bound to one Backend.
const service = createApiClient(base)

const catalog = shallowRef<WorkingGraphSummary[]>([])
const catalogLoading = ref(true)
const catalogError = ref('')
const studio = shallowRef<KGStudioPayload | null>(null)
const graphPackage = shallowRef<WorkingGraphPackage | null>(null)
const graphLoading = ref(false)
const graphError = ref('')
const packageError = ref('')
const notice = ref('')
const selection = ref<WorkingGraphSelection>(null)
const pickerOpen = ref(false)
const pickerSearch = ref('')
const pickerScene = ref<string>('all')

type EditorMode = 'node' | 'package' | 'import'
const editorMode = ref<EditorMode | null>(null)
const editorNodeId = ref<string | null>(null)
const editorDirty = ref(false)
const editorError = ref('')
const writing = ref<'save' | 'import' | 'enable' | null>(null)
const enableDialog = ref(false)
const enableTarget = shallowRef<{ id: string; title: string } | null>(null)
const enableError = ref('')

const request = computed(() => graphRequest(route.query))
const graphId = computed(() => request.value.kind === 'exact' ? request.value.id : null)
const registered = computed(() => catalog.value.find(row => row.graph_id === graphId.value) ?? null)
const title = computed(() => graphPackage.value?.title || registered.value?.title || (graphId.value ? '工作图' : '知识图谱工作台'))
const scene = computed(() => graphPackage.value?.dataset || registered.value?.dataset || null)
const access = computed(() => workingGraphAccess(registered.value, graphPackage.value))
const visibleCatalog = computed(() => {
  const term = pickerSearch.value.trim().toLocaleLowerCase()
  const matches = catalog.value.filter(row => (pickerScene.value === 'all' || row.dataset === pickerScene.value)
    && (!term || [row.title, row.graph_id, row.dataset, graphScene(row.dataset)].some(value => value.toLocaleLowerCase().includes(term))))
  const current = matches.find(row => row.graph_id === graphId.value)
  return current ? [current, ...matches.filter(row => row !== current)] : matches
})
const status = computed(() => registered.value ? registryStatus(registered.value) : null)

let catalogRevision = 0
let graphRevision = 0
let alive = true
let confirmation: Promise<boolean> | null = null

function registryStatus(row: WorkingGraphSummary) {
  if (row.status === 'failed') return { label: '不可用', color: 'red' }
  if (row.status === 'loading') return { label: '准备中', color: 'arcoblue' }
  if (row.enabled === true) return { label: '已启用', color: 'green' }
  if (row.enabled === false) return { label: '待启用', color: 'orange' }
  return { label: '状态未记录', color: 'gray' }
}

function textOf(error: unknown) { return error instanceof Error ? error.message : String(error) }
function isMissingGraph(error: unknown) {
  return error instanceof ApiError && (error.status === 404 || (error.status === 400 && /^unknown working graph:/i.test(error.message)))
}
function isCurrent(id: string | null) { return alive && route.name === 'graphs' && graphId.value === id }

function applyDefault() {
  if (props.connectionChanged || !isCurrent(null) || request.value.kind !== 'default') return
  const row = defaultWorkingGraph(catalog.value, rememberedWorkingGraph(base))
  if (row) void router.replace(workingGraphRoute(row.graph_id))
}

async function readCatalog() {
  const version = ++catalogRevision
  catalogLoading.value = true
  catalogError.value = ''
  try {
    const result = await service.listWorkingGraphs()
    if (!alive || version !== catalogRevision) return
    catalog.value = result.graphs.filter(isCurrentWorkingGraph)
    applyDefault()
  } catch (error) {
    if (!alive || version !== catalogRevision) return
    catalog.value = []
    catalogError.value = textOf(error)
  } finally { if (alive && version === catalogRevision) catalogLoading.value = false }
}

function setRegistered(row: WorkingGraphSummary) {
  catalogRevision += 1
  catalogLoading.value = false
  const index = catalog.value.findIndex(item => item.graph_id === row.graph_id)
  catalog.value = index === -1 ? [row, ...catalog.value]
    : catalog.value.map(item => item.graph_id === row.graph_id ? row : item)
}

function previewContains(next: Exclude<WorkingGraphSelection, null>) {
  const preview = studio.value
  return !!preview && (next.type === 'node'
    ? preview.graph_nodes.some(node => node.node_id === next.id)
    : preview.graph_edges.some(edge => edge.edge_id === next.id))
}
function select(next: WorkingGraphSelection) {
  if (next && !previewContains(next)) return
  selection.value = next
}

async function readGraph(id: string) {
  const version = ++graphRevision
  if (studio.value?.graph_id !== id) {
    studio.value = null
    graphPackage.value = null
  }
  graphError.value = ''
  packageError.value = ''
  graphLoading.value = true
  const [projection, capsule] = await Promise.allSettled([
    service.kgStudio(id),
    service.getWorkingGraphPackage(id),
  ])
  if (!isCurrent(id) || version !== graphRevision) return
  graphLoading.value = false
  if (capsule.status === 'fulfilled' && capsule.value.schema_version !== 'rootlens-working-graph.v2') {
    studio.value = null
    graphPackage.value = null
    graphError.value = '该链接未返回当前格式的工作图。请从图谱目录选择。'
    return
  }
  if (projection.status === 'fulfilled' && projection.value.graph_id === id) {
    studio.value = projection.value
    if (selection.value && !previewContains(selection.value)) selection.value = null
  } else {
    studio.value = null
    graphError.value = projection.status === 'fulfilled' ? '后端返回的图与所选编号不同。'
      : isMissingGraph(projection.reason) ? '当前后端找不到这张工作图。'
        : textOf(projection.reason)
  }
  if (capsule.status === 'fulfilled' && capsule.value.schema_version === 'rootlens-working-graph.v2' && capsule.value.graph_id === id) {
    graphPackage.value = capsule.value
  } else {
    graphPackage.value = null
    packageError.value = capsule.status === 'fulfilled' ? '后端返回的图包与所选编号不同。' : textOf(capsule.reason)
  }
  if (studio.value && graphPackage.value) rememberWorkingGraph(base, id)
}

watch([() => route.name, graphId], ([name, id], previous) => {
  if (name !== 'graphs') return
  if (id !== previous?.[1]) {
    selection.value = null
    notice.value = ''
  }
  if (id) void readGraph(id)
  else {
    graphRevision += 1
    studio.value = null
    graphPackage.value = null
    graphLoading.value = false
    graphError.value = ''
    packageError.value = ''
    if (!catalogLoading.value) applyDefault()
  }
}, { immediate: true })

async function refresh() {
  if (writing.value || editorMode.value) return
  const id = graphId.value
  await Promise.all([readCatalog(), id ? readGraph(id) : Promise.resolve()])
}

function openPicker() {
  pickerSearch.value = ''
  pickerScene.value = 'all'
  pickerOpen.value = true
  void readCatalog()
}
async function pickGraph(id: string) {
  if (id === graphId.value) { pickerOpen.value = false; return }
  const failure = await router.push(workingGraphRoute(id))
  if (!isNavigationFailure(failure)) pickerOpen.value = false
}

function closeEditor() {
  if (writing.value) return
  editorMode.value = null
  editorNodeId.value = null
  editorDirty.value = false
  editorError.value = ''
}
function openEditor(mode: EditorMode, id: string | null = null) {
  if (writing.value || (mode !== 'import' && graphLoading.value)) return
  if (mode === 'node' && (!access.value.editable || !id || !editableWorkingGraphNode(graphPackage.value, id))) return
  if (mode === 'package' && !graphPackage.value) return
  if (mode === 'package' && !access.value.editable) {
    Message.info('当前图还不能编辑。可先导出完整图包。')
    return
  }
  editorMode.value = mode
  editorNodeId.value = id
  editorDirty.value = false
  editorError.value = ''
}
function exportGraph() {
  const data = graphPackage.value
  if (!data || !graphId.value) return
  const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' }))
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `rootlens-${graphId.value.replace(/[^a-zA-Z0-9_-]/g, '-')}.json`
  anchor.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
function packageAction(action: unknown) {
  if (action === 'import' || action === 'package') openEditor(action)
  else if (action === 'export') exportGraph()
}

function confirmDiscard() {
  if (confirmation) return confirmation
  confirmation = new Promise<boolean>(resolve => {
    Modal.confirm({
      title: '放弃未保存的更改？',
      content: '当前图谱草稿没有保存。离开后，这些更改将丢失。',
      okText: '放弃更改',
      cancelText: '继续编辑',
      maskClosable: false,
      onOk: () => resolve(true),
      onCancel: () => resolve(false),
      onClose: () => resolve(false),
    })
  }).finally(() => { confirmation = null })
  return confirmation
}
async function allowLeave() {
  if (writing.value) { Message.warning('正在保存图谱，请等操作完成。'); return false }
  if (editorDirty.value && !await confirmDiscard()) return false
  closeEditor()
  enableDialog.value = false
  return true
}
onBeforeRouteLeave(allowLeave)
onBeforeRouteUpdate((to, from) => to.query.graph === from.query.graph ? true : allowLeave())
function beforeUnload(event: BeforeUnloadEvent) {
  if (!editorDirty.value && !writing.value) return
  event.preventDefault()
  event.returnValue = ''
}
onMounted(() => {
  if (guard) guard.value = allowLeave
  window.addEventListener('beforeunload', beforeUnload)
  void readCatalog()
})
onBeforeUnmount(() => {
  alive = false
  if (guard?.value === allowLeave) guard.value = null
  window.removeEventListener('beforeunload', beforeUnload)
})

async function submitEditor(input: { kind: 'save' | 'import'; package: WorkingGraphPackage }) {
  const id = graphId.value
  const mode = editorMode.value
  if (writing.value || !mode || !isCurrent(id)) return
  if (input.package.schema_version !== 'rootlens-working-graph.v2') {
    editorError.value = '只能写入 v2 工作图包。'
    return
  }
  if (input.kind === 'save' && (mode === 'import' || !id || !access.value.editable)) {
    editorError.value = '当前工作图不可保存。'
    return
  }
  if (input.kind === 'import' && mode !== 'import') return
  writing.value = input.kind
  editorError.value = ''
  notice.value = ''
  try {
    const row = input.kind === 'import'
      ? await service.importWorkingGraphPackage(input.package)
      : await service.saveWorkingGraphPackage(id!, input.package)
    if (!isCurrent(id)) return
    if (!row.graph_id || (input.kind === 'save' ? row.graph_id !== id : row.graph_id === id)) {
      throw new Error('后端未返回正确的工作图编号。')
    }
    setRegistered(row)
    writing.value = null
    closeEditor()
    if (input.kind === 'import') {
      Message.success('已登记为新图，启用后可用于新分析。')
      await router.push(workingGraphRoute(row.graph_id))
    } else {
      notice.value = '已保存工作图；历史分析保持原快照。'
      await readGraph(row.graph_id)
    }
  } catch (error) {
    if (isCurrent(id)) editorError.value = textOf(error)
  } finally { if (isCurrent(id)) writing.value = null }
}
function openEnableDialog() {
  const id = graphId.value
  if (!id || !access.value.canEnable || graphLoading.value || writing.value || editorMode.value) return
  enableTarget.value = { id, title: title.value }
  enableError.value = ''
  enableDialog.value = true
}
async function enableGraph() {
  const target = enableTarget.value
  if (!target || !isCurrent(target.id) || !access.value.canEnable || graphLoading.value || writing.value) {
    enableError.value = '当前图谱状态已变化。请关闭此窗口后重新确认。'
    return false
  }
  const id = target.id
  writing.value = 'enable'
  enableError.value = ''
  notice.value = ''
  try {
    const row = await service.enableWorkingGraph(id, true)
    if (!isCurrent(id)) return false
    if (row.graph_id !== id || row.enabled !== true) throw new Error('后端未确认启用所选工作图。')
    setRegistered(row)
    notice.value = '已启用这张图，可以发起新分析。'
    await readGraph(id)
    return true
  } catch (error) {
    if (isCurrent(id)) enableError.value = textOf(error)
    return false
  } finally { if (isCurrent(id)) writing.value = null }
}
function analyze() {
  const id = graphId.value
  if (id && access.value.canAnalyze && !graphLoading.value && !writing.value && !editorMode.value) void router.push(newAnalysisRoute(id))
}
</script>

<template>
  <section class="graph-workbench" aria-label="知识图谱工作台">
    <header class="graph-workbench__header">
      <div class="graph-workbench__identity">
        <div class="graph-workbench__eyebrow">
          <span>当前工作图</span>
        </div>
        <div class="graph-workbench__name">
          <h2>{{ title }}</h2>
          <a-tag v-if="status" :color="status.color">{{ status.label }}</a-tag>
        </div>
        <p v-if="scene">{{ graphScene(scene) }}</p>
      </div>
      <div class="graph-workbench__actions">
        <a-button type="outline" :disabled="!!writing" @click="openPicker">切换图谱 <IconDown /></a-button>
        <a-dropdown trigger="click" @select="packageAction">
          <a-button type="text" :disabled="!!writing || graphLoading">导入 / 导出 <IconDown /></a-button>
          <template #content>
            <a-doption value="import">导入工作图包</a-doption>
            <a-doption value="export" :disabled="!graphPackage">导出当前图包</a-doption>
            <a-doption value="package" :disabled="!access.editable">查看工作图包</a-doption>
          </template>
        </a-dropdown>
        <a-button v-if="access.canAnalyze" type="primary" :disabled="!!writing || graphLoading" @click="analyze">用这张图分析</a-button>
        <a-button v-else-if="access.canEnable || writing === 'enable'" type="primary" :loading="writing === 'enable'" :disabled="graphLoading" @click="openEnableDialog">启用工作图</a-button>
      </div>
    </header>

    <a-alert v-if="connectionChanged" type="warning">
      连接设置已变化。当前图与草稿仍绑定原地址 {{ base }}。
      <a-button type="text" size="mini" @click="emit('switch-source')">切换到当前连接</a-button>
    </a-alert>
    <a-alert v-if="notice" type="success">{{ notice }}</a-alert>
    <a-alert v-if="catalogError" type="warning">
      图谱目录读取失败：{{ catalogError }}
      <a-button type="text" size="mini" @click="readCatalog">重试目录</a-button>
    </a-alert>
    <a-alert v-if="packageError && studio" type="warning">
      图谱可查看；完整包未能读取：{{ packageError }}
      <a-button type="text" size="mini" @click="refresh">重新读取</a-button>
    </a-alert>

    <div v-if="studio" class="graph-workbench__layout" :key="graphId ?? 'empty'" :aria-busy="graphLoading">
      <div class="graph-workbench__network">
        <WorkingGraphNetwork :studio="studio" :selection="selection" @select="select" />
      </div>
      <div class="graph-workbench__inspector">
        <WorkingGraphInspector :studio="studio" :graph-package="graphPackage" :selection="selection"
          @select="select" @edit-node="openEditor('node', $event)" @open-package="openEditor('package')" />
      </div>
    </div>
    <div v-else class="graph-workbench__empty" aria-live="polite">
      <a-spin v-if="graphLoading || (catalogLoading && !graphId)" :size="20" />
      <span v-if="graphLoading || (catalogLoading && !graphId)" class="workspace-subtle">正在读取工作图…</span>
      <template v-else-if="graphError">
        <a-empty :description="graphError" />
        <a-button @click="refresh"><template #icon><IconRefresh /></template>重新读取</a-button>
      </template>
      <a-empty v-else-if="request.kind === 'invalid'" description="链接里的工作图编号无效。请明确选择一张图。" />
      <a-empty v-else description="尚未选择可用工作图。可切换、导入，或从素材与构图生成。" />
    </div>

    <a-modal v-model:visible="pickerOpen" title="切换工作图" width="min(540px, calc(100vw - 24px))" :footer="false">
      <div class="graph-picker">
        <p class="graph-picker__description">只切换正在查看的图，不改变启用状态。</p>
        <div class="graph-picker__filters">
          <a-input v-model="pickerSearch" allow-clear placeholder="搜索图名、场景或图 ID"
            :input-attrs="{ 'aria-label': '搜索工作图' }">
            <template #prefix><IconSearch /></template>
          </a-input>
          <a-select v-model="pickerScene" aria-label="工作图场景筛选">
            <a-option value="all">全部场景</a-option>
            <a-option v-for="(label, key) in graphScenes" :key="key" :value="key">{{ label }}</a-option>
          </a-select>
        </div>
        <a-alert v-if="catalogError" type="warning">{{ catalogError }} <a-button size="mini" type="text" @click="readCatalog">重试</a-button></a-alert>
        <div v-if="catalogLoading && !catalog.length" class="graph-picker__loading"><a-spin :size="14" /> 正在读取图谱目录…</div>
        <div v-else class="graph-picker__list" aria-label="工作图目录">
          <button v-for="row in visibleCatalog" :key="row.graph_id" type="button" class="graph-picker__row"
            :class="{ 'graph-picker__row--current': row.graph_id === graphId }" :aria-current="row.graph_id === graphId ? 'true' : undefined"
            @click="pickGraph(row.graph_id)">
            <span class="graph-picker__row-copy"><strong>{{ row.title }}</strong>
              <small>{{ graphScene(row.dataset) }} · {{ row.node_count }} 节点 · {{ row.edge_count }} 关系<template v-if="row.graph_id === graphId"> · 当前图</template></small>
            </span>
            <a-tag :color="registryStatus(row).color">{{ registryStatus(row).label }}</a-tag>
          </button>
          <a-empty v-if="!visibleCatalog.length && !catalogError" :description="catalog.length ? '没有符合条件的工作图' : '暂无工作图'" />
        </div>
        <footer class="graph-picker__footer">
          <span class="workspace-subtle">{{ visibleCatalog.length }} / {{ catalog.length }} 张工作图</span>
          <a-button @click="pickerOpen = false">返回</a-button>
        </footer>
      </div>
    </a-modal>
    <a-modal v-model:visible="enableDialog" title="启用工作图" width="min(440px, calc(100vw - 24px))"
      ok-text="确认启用" cancel-text="取消" :mask-closable="false" :esc-to-close="!writing" :closable="!writing"
      :cancel-button-props="{ disabled: writing === 'enable' }"
      :on-before-ok="enableGraph">
      <p>启用「{{ enableTarget?.title }}」后，新分析可以选择这张图。已保存分析不会改变。</p>
      <a-alert v-if="enableError" type="error">{{ enableError }}</a-alert>
    </a-modal>
    <WorkingGraphEditor :mode="editorMode" :graph-package="graphPackage" :node-id="editorNodeId"
      :busy="writing === 'save' || writing === 'import'" :error="editorError"
      @submit="submitEditor" @close="closeEditor" @dirty-change="editorDirty = $event" />
  </section>
</template>

<style scoped>
.graph-workbench {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
  min-height: 0;
  padding: 14px;
  overflow: auto;
  color: var(--color-text-1);
}
.graph-workbench__header { display: flex; align-items: center; justify-content: space-between; gap: 12px 20px; flex-wrap: wrap; }
.graph-workbench__identity { flex: 1 1 300px; min-width: 0; }
.graph-workbench__eyebrow { display: flex; align-items: center; flex-wrap: wrap; gap: 4px; color: var(--color-text-3); font-size: 12px; }
.graph-workbench__eyebrow :deep(.arco-btn) { font-size: 12px; }
.graph-workbench__name { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; margin-top: 2px; }
.graph-workbench__name h2 { margin: 0; font-size: 21px; line-height: 1.4; min-width: 0; overflow-wrap: anywhere; }
.graph-workbench__identity p { margin: 4px 0 0; color: var(--color-text-2); font-size: 12px; }
.graph-workbench__actions { display: flex; align-items: center; flex-wrap: wrap; gap: 6px 9px; }
.graph-workbench__layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(258px, 304px);
  grid-template-rows: minmax(0, 1fr);
  flex: 1 0 460px;
  min-height: 460px;
  gap: 10px;
}
.graph-workbench__network, .graph-workbench__inspector {
  display: flex;
  flex-direction: column;
  min-width: 0;
  min-height: 0;
}
.graph-workbench__empty {
  flex: 1 0 300px;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  text-align: center;
  border: 1px solid var(--color-border-2);
  border-radius: 4px;
  background: var(--color-bg-2);
  padding: 16px;
}
.graph-picker { display: grid; gap: 12px; }
.graph-picker__description { margin: 0; color: var(--color-text-2); font-size: 12px; }
.graph-picker__filters { display: grid; grid-template-columns: minmax(0, 1fr) 104px; gap: 8px; }
.graph-picker__list { max-height: min(42vh, 360px); overflow-y: auto; }
.graph-picker__loading { display: flex; align-items: center; justify-content: center; gap: 6px; padding: 20px; color: var(--color-text-2); }
.graph-picker__row {
  border: 0;
  border-bottom: 1px solid var(--color-border-2);
  border-radius: 2px;
  background: transparent;
  color: var(--color-text-1);
  text-align: start;
  width: 100%;
  min-width: 0;
  padding: 8px;
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  cursor: pointer;
}
.graph-picker__row:last-child { border-bottom: 0; }
.graph-picker__row:hover { background: var(--color-fill-2); }
.graph-picker__row:focus-visible { outline: 2px solid rgb(var(--primary-6)); outline-offset: -2px; }
.graph-picker__row--current { background: var(--color-primary-light-1); }
.graph-picker__row-copy { min-width: 0; overflow-wrap: anywhere; }
.graph-picker__row-copy strong, .graph-picker__row-copy small { display: block; }
.graph-picker__row-copy small { color: var(--color-text-2); margin-top: 2px; }
.graph-picker__row :deep(.arco-tag) { flex: 0 0 auto; }
.graph-picker__footer { display: flex; justify-content: space-between; align-items: center; gap: 8px; }
@media (max-width: 820px) {
  .graph-workbench__layout { grid-template-columns: minmax(0, 1fr); grid-template-rows: minmax(480px, auto) auto; flex: none; }
}
@media (max-width: 560px) {
  .graph-workbench { padding: 10px; gap: 10px; }
  .graph-workbench__identity { flex-basis: 100%; }
  .graph-workbench__name h2 { font-size: 18px; }
  .graph-workbench__layout { grid-template-rows: minmax(510px, auto) auto; }
}
@media (max-width: 360px) {
  .graph-picker__filters { grid-template-columns: minmax(0, 1fr); }
}
</style>
