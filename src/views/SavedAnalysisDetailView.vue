<script setup lang="ts">
import { IconArrowLeft, IconCheck, IconDashboard, IconDownload, IconList, IconRefresh } from '@arco-design/web-vue/es/icon'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ApiError } from '@/api/client'
import SavedRunOverview from '@/components/saved-analysis/SavedRunOverview.vue'
import SavedRunProducts from '@/components/saved-analysis/SavedRunProducts.vue'
import SavedRunEvidence from '@/components/saved-analysis/SavedRunEvidence.vue'
import SavedRunReasoning from '@/components/saved-analysis/SavedRunReasoning.vue'
import SavedRunGraph from '@/components/saved-analysis/SavedRunGraph.vue'
import { chooseSavedPath, datasetLabel, detailTab, detailTabs, factOnPath, getPathObs, inputLabel, pathForFact, reasonerLabel, savedCandidateRanks, stageForTab, strings, text, type DetailTab, type PathFocus } from '@/components/saved-analysis/presentation'
import { savedAnalysisRoute } from '@/services/analysis-entry'
import { useAppPreferences } from '@/services/app-preferences'
import { getLocalSessionEventName, getLocalSessionMeta } from '@/services/rootlens-data'
import { readSavedAnalysis, type SavedAnalysis } from '@/services/saved-analysis-reader'
import { savedTentativeCandidates, traceRows } from '@/services/unified-reasoning-display'

const route = useRoute(), router = useRouter()
const { preferences, updatePreferences } = useAppPreferences()
const replay = ref(getLocalSessionMeta()?.source === 'import')
const updateReplay = () => { replay.value = getLocalSessionMeta()?.source === 'import' }
const saved = shallowRef<SavedAnalysis | null>(null)
const loading = ref(false)
const failure = ref('')
const failureDetail = ref('')
const downloading = ref(false)
const downloadError = ref('')
const scrollHost = ref<HTMLElement | null>(null)
const runId = computed(() => text(route.params.runId))
const frameIntent = computed(() => text(route.query.case_id))
const tab = computed(() => detailTab(route.query.tab))
const stage = computed(() => stageForTab(tab.value))
const frame = computed(() => frameIntent.value ? saved.value?.framesById.get(frameIntent.value) ?? null : saved.value?.frames[0] ?? null)
const run = computed(() => saved.value?.run ?? null)
const isReady = computed(() => !!run.value && !!frame.value)
const selected = ref(emptyFocus())
const candidateId = computed(() => selected.value.candidateId || (frame.value ? text(savedCandidateRanks(frame.value)[0]?.candidate_id) : ''))
const candidate = computed(() => frame.value?.candidatesById.get(candidateId.value) ?? null)
let revision = 0

function emptyFocus() {
  return { candidateId: '', pathId: '', edgeId: '', nodeId: '', obsId: '', factId: '', tentativeCandidateId: '' }
}
const status = computed(() => {
  const value = run.value?.status
  return value === 'completed' ? { label: '已完成', color: 'green' }
    : value === 'failed' ? { label: '失败', color: 'red' }
      : value === 'interrupted' ? { label: '已中断', color: 'orange' }
        : { label: text(value) || '状态未保存', color: 'gray' }
})
const creationTime = computed(() => {
  const value = run.value?.created_at
  if (!value || !Number.isFinite(Date.parse(value))) return value ?? ''
  return new Intl.DateTimeFormat('zh-CN', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false }).format(new Date(value))
})
const flow = computed(() => [
  { id: 'input' as const, number: '01', title: '输入', note: inputLabel(run.value?.input_mode), child: '输入文件与配置', state: run.value?.input_mode ? 'done' : 'missing' },
  { id: 'backbone' as const, number: '02', title: 'Backbone', note: saved.value?.backbone.state === 'skipped' ? '跳过 · 使用已有观测' : saved.value?.backbone.state === 'measured' ? '原始输入测量' : '阶段未记录', child: saved.value?.backbone.state === 'skipped' ? '未执行新提取' : '保存产物与范围', state: saved.value?.backbone.state === 'skipped' ? 'skip' : saved.value?.backbone.state === 'measured' ? 'done' : 'missing' },
  { id: 'evidence' as const, number: '03', title: 'Adapter / Evidence', note: run.value?.input_mode === 'evidence' ? '校验并沿用观测' : '本次保存的观测', child: '观测值与原始引用', state: frame.value ? 'done' : 'missing' },
  { id: 'reasoning' as const, number: '04', title: 'KG 解释器', note: frame.value?.result ? '保存的推理结果' : '未保存推理结果', child: '', state: frame.value?.result ? 'done' : 'missing' },
])

async function load() {
  const version = ++revision
  saved.value = null; failure.value = ''; failureDetail.value = ''; loading.value = false
  downloading.value = false; downloadError.value = ''
  if (!runId.value) {
    failure.value = '链接未指定有效的保存分析。'
    return
  }
  if (replay.value) {
    failure.value = '请先在运行列表退出成品回放，再查看这次后端分析。'
    return
  }
  if (preferences.value.dataSourceMode !== 'backend') {
    failure.value = '此分析保存在后端。切换到 Backend 后查看。'
    return
  }
  loading.value = true
  try {
    const data = await readSavedAnalysis(preferences.value.apiBaseUrl, runId.value)
    if (version !== revision) return
    saved.value = data
    if (!frameIntent.value && data.frames[0]) setQuery({ case_id: data.frames[0].id })
  } catch (error) {
    if (version !== revision) return
    if (error instanceof ApiError) {
      failure.value = error.status === 404 ? '找不到这次保存分析。'
        : error.status === 401 || error.status === 403 ? '当前连接无权读取这次分析。'
          : error.status === 0 ? '无法连接后端服务。' : `读取分析失败（${error.status}）。`
    } else failure.value = '无法读取这次分析。'
    failureDetail.value = error instanceof Error ? error.message : String(error)
  } finally { if (version === revision) loading.value = false }
}
watch([runId, replay, () => preferences.value.dataSourceMode, () => preferences.value.apiBaseUrl], () => void load(), { immediate: true })
onMounted(() => window.addEventListener(getLocalSessionEventName(), updateReplay))
onBeforeUnmount(() => { revision += 1; window.removeEventListener(getLocalSessionEventName(), updateReplay) })
watch(() => frame.value?.id, () => { selected.value = emptyFocus(); if (scrollHost.value) scrollHost.value.scrollTop = 0 }, { flush: 'sync' })
watch(tab, () => { if (scrollHost.value) scrollHost.value.scrollTop = 0 })

async function downloadEvidence() {
  const url = saved.value?.evidenceUrl, version = revision
  if (!url || downloading.value) return
  downloading.value = true; downloadError.value = ''
  try {
    const response = await fetch(url)
    if (!response.ok) throw new Error(`HTTP ${response.status}`)
    const payload = await response.blob()
    if (version !== revision) return
    const href = URL.createObjectURL(payload)
    const anchor = document.createElement('a')
    anchor.href = href; anchor.download = 'evidence-frames.json'
    anchor.click()
    setTimeout(() => URL.revokeObjectURL(href), 1000)
  } catch (error) {
    if (version === revision) downloadError.value = `下载 Evidence 失败${error instanceof Error ? `（${error.message}）` : ''}，可重试。`
  } finally { if (version === revision) downloading.value = false }
}

function setQuery(patch: { tab?: DetailTab; case_id?: string }) {
  const nextTab = patch.tab ?? tab.value
  void router.replace(savedAnalysisRoute('evidence', runId.value, patch.case_id ?? frameIntent.value, nextTab === 'overview' ? undefined : nextTab))
}
function showTab(next: DetailTab) { if (next !== tab.value) setQuery({ tab: next }) }
function chooseFrame(value: unknown) {
  if (typeof value === 'string' && saved.value?.framesById.has(value) && value !== frameIntent.value) setQuery({ case_id: value })
}
function onTabKey(event: KeyboardEvent) {
  const current = detailTabs.findIndex(item => item.id === tab.value)
  const next = event.key === 'ArrowRight' ? (current + 1) % detailTabs.length : event.key === 'ArrowLeft' ? (current + detailTabs.length - 1) % detailTabs.length
    : event.key === 'Home' ? 0 : event.key === 'End' ? detailTabs.length - 1 : -1
  if (next === -1) return
  event.preventDefault()
  const item = detailTabs[next]!
  showTab(item.id)
  void nextTick(() => document.getElementById(`saved-analysis-tab-${item.id}`)?.focus())
}
function selectCandidate(id: string) {
  if (frame.value?.candidatesById.has(id) && (id !== candidateId.value || selected.value.tentativeCandidateId)) selected.value = { ...emptyFocus(), candidateId: id }
}
function selectPath(focus: PathFocus, to?: DetailTab, nodeId = focus.nodeId ?? '') {
  const active = frame.value, path = active?.pathsById.get(focus.pathId)
  if (!active || !path) return
  const edgeId = focus.edgeId && path.edges.some(edge => edge.edge_id === focus.edgeId) ? focus.edgeId : ''
  const obs = getPathObs(active, path)
  const obsId = obs.includes(focus.obsId ?? '') ? focus.obsId! : obs.includes(selected.value.obsId) ? selected.value.obsId : obs[0] ?? ''
  const fact = factOnPath(active, path, obsId, edgeId)
  selected.value = { ...emptyFocus(), candidateId: text(path.target_entity_id) || candidateId.value, pathId: path.path_id, edgeId, nodeId,
    obsId, factId: text(fact?.fact_id) }
  if (to) showTab(to)
}
function selectObservation(id: string, toEvidence = false, explicitGraph = false) {
  const active = frame.value
  if (!active?.observationsById.has(id)) return
  if (selected.value.tentativeCandidateId && !explicitGraph) {
    selected.value = { ...selected.value, obsId: id }
    if (toEvidence) showTab('evidence')
    return
  }
  const observedPaths = active.pathsByObsId.get(id) ?? []
  const paths = candidateId.value ? observedPaths.filter(path => path.target_entity_id === candidateId.value) : observedPaths
  const path = chooseSavedPath(paths, selected.value.pathId, candidateId.value)
  if (path) {
    const fact = factOnPath(active, path, id)
    const link = fact ? pathForFact(active, text(path.target_entity_id), fact) : null
    const edgeId = link?.pathId === path.path_id && link.obsId === id ? link.edgeId : undefined
    selectPath({ pathId: path.path_id, obsId: id, edgeId })
  } else selected.value = { ...emptyFocus(), candidateId: candidateId.value, obsId: id }
  if (toEvidence) showTab('evidence')
}
function onGraphSelect(pick: { type: 'edge' | 'node'; id: string } | null) {
  const active = frame.value
  if (!active) return
  if (!pick) { selected.value = { ...emptyFocus(), candidateId: candidateId.value }; return }
  const paths = pick.type === 'edge' ? active.pathsByEdgeId.get(pick.id) ?? [] : active.pathGraph.paths.filter(path => path.nodes.some(node => node.node_id === pick.id))
  const path = chooseSavedPath(paths, selected.value.pathId, candidateId.value)
  if (path) selectPath({ pathId: path.path_id, edgeId: pick.type === 'edge' ? pick.id : undefined }, undefined, pick.type === 'node' ? pick.id : '')
}
function graphFocus(focus: PathFocus) { selectPath(focus, 'graph') }
function graphForObservation(id: string) {
  selectObservation(id, false, true)
  if (selected.value.pathId) showTab('graph')
}
function observeFromGraph(id: string) {
  // Keep the user's explicit graph selection. Its observation belongs to the
  // saved path; the graph inspector states when there is no edge-level link.
  if (selected.value.pathId) selectPath({ pathId: selected.value.pathId, edgeId: selected.value.edgeId, nodeId: selected.value.nodeId, obsId: id }, 'evidence')
}
function reasonFromGraph() { showTab('reasoning') }
function observeFromReason(id: string, focus?: PathFocus) {
  if (focus && frame.value?.observationsById.has(id)) selectPath({ ...focus, obsId: id }, 'evidence')
  else selectObservation(id, true)
}
function observeTentative(candidate: string, id: string) {
  const current = frame.value
  const row = savedTentativeCandidates(current?.result).find(item => item.candidate_id === candidate)
  if (!current?.observationsById.has(id) || !traceRows(row?.condition_checks).some(check =>
    ['support_obs_ids', 'counter_obs_ids', 'unknown_obs_ids'].some(key => strings(check[key]).includes(id)))) return
  selected.value = { ...emptyFocus(), obsId: id, tentativeCandidateId: candidate }
  showTab('evidence')
}
function toList() { void router.push({ name: 'evidence' }) }
</script>

<template>
  <section class="saved-analysis-detail" aria-label="保存运行详情">
    <header class="saved-run-toolbar">
      <div class="saved-run-toolbar__identity">
        <a-button size="mini" type="text" class="saved-run-back" @click="toList"><IconArrowLeft /> 返回运行列表</a-button>
        <div class="saved-run-title-line">
          <h1 :title="run?.title ?? runId">{{ run?.title || '保存运行详情' }}</h1>
          <a-tag v-if="run" size="small" :color="status.color">{{ status.label }}</a-tag>
        </div>
        <div v-if="run" class="saved-run-meta">{{ [datasetLabel(run.dataset), inputLabel(run.input_mode), reasonerLabel(run.reasoner_id), creationTime].filter(Boolean).join(' · ') }}</div>
        <div v-if="downloadError" class="saved-run-download-error" role="status">{{ downloadError }}</div>
      </div>
      <div v-if="saved" class="saved-run-toolbar__actions">
        <a-select v-if="saved.frames.length > 1 || (frameIntent && !frame && saved.frames.length)" :model-value="frame?.id" v-control-label="'分析范围'" aria-label="分析范围" placeholder="选择保存范围" size="small" class="saved-run-frame-select" @change="chooseFrame">
          <a-option v-for="item in saved.frames" :key="item.id" :value="item.id">{{ item.label }}</a-option>
        </a-select>
        <a-tag v-else-if="frame" size="small" :title="frame.id">{{ frame.label }}</a-tag>
        <a-button v-if="saved.evidenceUrl" :loading="downloading" size="small" title="下载本次分析全部保存 Frame" @click="downloadEvidence"><IconDownload /> 下载 Evidence</a-button>
        <a-tooltip v-else content="此保存分析没有可下载的 Evidence 附件"><a-button size="small" disabled><IconDownload /> 下载 Evidence</a-button></a-tooltip>
      </div>
    </header>

    <div v-if="loading" class="saved-run-empty" aria-live="polite"><a-spin /> 正在读取这次保存分析…</div>
    <div v-else-if="failure" class="saved-run-empty" role="alert">
      <a-alert type="warning" :title="failure"><span v-if="failureDetail">{{ failureDetail }}</span></a-alert>
      <a-button v-if="!replay && runId && preferences.dataSourceMode !== 'backend'" size="small" type="primary" @click="updatePreferences({ dataSourceMode: 'backend' })">切换 Backend</a-button>
      <a-button v-else-if="!replay && runId" size="small" @click="load"><IconRefresh /> 重读此分析</a-button>
    </div>
    <div v-else-if="!isReady || !frame || !saved" class="saved-run-empty" role="status">
      <a-alert type="warning" :title="frameIntent && saved?.frames.length ? '这次分析未保存所选 Frame。' : '这次分析没有可查看的保存 Frame。'">
        <span v-if="frameIntent && saved?.frames.length">请在上方选择这次分析自己的保存范围。</span>
      </a-alert>
    </div>
    <div v-else class="saved-run-workspace">
      <nav class="saved-run-flow" aria-label="流程索引">
        <h2><IconList /> 流程索引</h2>
        <button class="saved-run-flow-item saved-run-flow-overview" type="button" :aria-current="stage === 'overview' ? 'step' : undefined" @click="showTab('overview')">
          <span class="saved-run-flow-num"><IconDashboard /></span><strong>总览</strong>
        </button>
        <template v-for="step in flow" :key="step.id">
          <button class="saved-run-flow-item" type="button" :aria-current="stage === step.id ? 'step' : undefined" @click="showTab(step.id)">
            <span class="saved-run-flow-num">{{ step.number }}</span><span class="saved-run-flow-copy"><strong>{{ step.title }}</strong><small>{{ step.note }}</small></span>
            <span v-if="step.state === 'done'" class="saved-run-step-done" title="已保存"><IconCheck /></span>
            <span v-else class="saved-run-muted" :title="step.state === 'skip' ? '跳过' : '未保存'">{{ step.state === 'skip' ? '—' : '·' }}</span>
          </button>
          <div v-if="stage === step.id" class="saved-run-flow-child">
            <template v-if="step.id === 'reasoning'">
              <button type="button" :class="{ active: tab === 'reasoning' }" @click="showTab('reasoning')">保存解释</button>
              <button type="button" :class="{ active: tab === 'graph' }" @click="showTab('graph')">本次图谱</button>
            </template>
            <span v-else>{{ step.child }}</span>
          </div>
        </template>
        <p class="saved-run-flow-foot" :title="frame.id">{{ frame.label }} · 保存分析</p>
      </nav>
      <div class="saved-run-right">
        <nav class="saved-run-tabs" role="tablist" aria-label="运行详情" @keydown="onTabKey">
          <button v-for="item in detailTabs" :id="`saved-analysis-tab-${item.id}`" :key="item.id" type="button" role="tab"
            :aria-selected="tab === item.id" :tabindex="tab === item.id ? 0 : -1" aria-controls="saved-analysis-panel" @click="showTab(item.id)">{{ item.label }}</button>
        </nav>
        <div id="saved-analysis-panel" ref="scrollHost" class="saved-run-scroll" role="tabpanel" :aria-labelledby="`saved-analysis-tab-${tab}`" tabindex="0">
          <div class="saved-run-content" :key="frame.id">
            <SavedRunOverview v-if="tab === 'overview'" :analysis="saved" :frame="frame" :candidate="candidate" @tab="showTab" @observation="id => selectObservation(id, true)" />
            <SavedRunProducts v-else-if="tab === 'input' || tab === 'backbone'" :tab="tab" :analysis="saved" :frame="frame" @tab="showTab" />
            <SavedRunEvidence v-else-if="tab === 'evidence'" :analysis="saved" :frame="frame" :candidate="selected.tentativeCandidateId ? null : candidate" :observation-id="selected.obsId" @observation="selectObservation" @graph="graphForObservation" @reasoning="showTab('reasoning')" />
            <SavedRunReasoning v-else-if="tab === 'reasoning'" :analysis="saved" :frame="frame" :candidate="candidate" :fact-id="selected.factId" :path-id="selected.pathId"
              :tentative-candidate-id="selected.tentativeCandidateId" @candidate="selectCandidate" @observation="observeFromReason" @tentative-observation="observeTentative" @graph="graphFocus" @tab="showTab" />
            <SavedRunGraph v-else :analysis="saved" :frame="frame" :candidate="candidate" :path-id="selected.pathId" :edge-id="selected.edgeId" :node-id="selected.nodeId" :observation-id="selected.obsId"
              @select="onGraphSelect" @path="selectPath" @observation="observeFromGraph" @reasoning="reasonFromGraph" />
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style src="@/components/saved-analysis/detail.css"></style>
