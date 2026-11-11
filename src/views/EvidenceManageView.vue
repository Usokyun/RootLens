<script setup lang="ts">
import MeasuredEvidenceDetails from "@/components/evidence/MeasuredEvidenceDetails.vue"
import UnifiedReasoningDetails from '@/components/evidence/UnifiedReasoningDetails.vue'
import {
  IconBulb,
  IconInfoCircle,
  IconLaunch,
  IconRefresh,
  IconRelation,
  IconStorage,
} from '@arco-design/web-vue/es/icon'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type {
  RankedRootCause,
  RunCaseDetail,
  RunDetail,
  RunSummary,
  VisualEvidenceItem,
} from '@/api/contracts'
import SectionCardTitle from '@/components/layout/SectionCardTitle.vue'
import { newAnalysisIntent } from '@/services/analysis-entry'
import { useAppPreferences } from '@/services/app-preferences'
import { clearImportedSession, getImportedSessionSummary, getLocalSessionEventName, getLocalSessionMeta } from '@/services/rootlens-data'
import { mockBackend } from '@/services/mock-backend'
import { filterObservationBrowseItems, buildObservationBrowseItems, collectObservationModalities, collectObservationSources, findObservationBrowseItem, selectVisualEvidenceForObservation, type ObservationBrowseItem, type ObservationConfidenceBand, type ObservationModality } from '@/services/evidence-observation'
import {
  formatClaimBoundaryCopy,
  formatScoringMethodLabel,
  resolveRunReasoningSummary,
  resolveVisualEvidenceUrl,
} from '@/services/ui-copy'
import { loadedRunSelectionPatch, sourceSelectionReset, useWorkbenchState } from '@/services/workbench-state'

interface CaseEvidenceEntry {
  key: string
  caseId: string
  caseLabel: string
  dataset: string
  graphDatasetId: string
  observationCount: number
  facetSummary: string
  evidenceSummary: string
  hint: string
  rawRefCount: number
  topCandidate: string
  reviewStatus: string
  pathCount: number
  searchableText: string
  facetKeys: string[]
}

const router = useRouter()
const route = useRoute()
const { preferences } = useAppPreferences()
const { state: workbenchState, updateState } = useWorkbenchState()
const emit = defineEmits<{ 'import-replay': [] }>()
const blockedAnalysisIntent = computed(() => !!newAnalysisIntent(route.query))

let sourceRevision = 0
let workspaceRevision = 0
let runReadRevision = 0
const workspaceLoading = ref(false)
const runLoading = ref(false)
const loading = computed(() => workspaceLoading.value || runLoading.value)
const runs = ref<RunSummary[]>([])
const runDetail = ref<RunDetail | null>(null)
const errorMessage = ref('')
const importedSessionMeta = ref(getLocalSessionMeta())
const importedSessionSummary = ref(getImportedSessionSummary())
const observationDetailModalVisible = ref(false)

const evidenceFilter = reactive({
  graph: workbenchState.value.evidenceFilterGraph ?? 'all',
  modality: workbenchState.value.evidenceFilterModality ?? 'all',
  source: workbenchState.value.evidenceFilterSource ?? 'all',
  confidenceBand: workbenchState.value.evidenceFilterConfidenceBand,
  timeFrom: workbenchState.value.evidenceFilterTimeFrom ?? '',
  timeTo: workbenchState.value.evidenceFilterTimeTo ?? '',
  keyword: workbenchState.value.evidenceFilterKeyword ?? '',
})

const isReplaySessionActive = computed(() => importedSessionMeta.value?.source === 'import')
const replaySourceModeLabel = computed(() => {
  switch (importedSessionSummary.value?.sourceMode) {
    case 'graphs+evidence':
      return '历史导入格式'
    case 'graphs-only':
      return '图谱不完整'
    case 'runtime':
      return '完整回放'
    default:
      return '--'
  }
})
const evidenceClaimBoundaryCopy = computed(() =>
  formatClaimBoundaryCopy(runDetail.value?.claim_boundary),
)

const selectedObservationId = computed(() => workbenchState.value.selectedObservationId)
const normalizedObservationFilters = computed(() => ({
  graph: evidenceFilter.graph === 'all' ? null : evidenceFilter.graph,
  modality: evidenceFilter.modality === 'all' ? null : (evidenceFilter.modality as ObservationModality),
  source: evidenceFilter.source === 'all' ? null : evidenceFilter.source,
  keyword: evidenceFilter.keyword.trim() || null,
  confidenceBand: evidenceFilter.confidenceBand as ObservationConfidenceBand,
  timeFrom: evidenceFilter.timeFrom || null,
  timeTo: evidenceFilter.timeTo || null,
}))

const selectedRunId = computed(() => workbenchState.value.selectedRunId)
const activeCaseId = computed(() => workbenchState.value.selectedCaseId)
const activeRun = computed(() => runDetail.value?.run ?? null)
const activeCase = computed(() => {
  if (!runDetail.value) {
    return null
  }

  return runDetail.value.cases.find((item) => item.case_id === activeCaseId.value) ?? runDetail.value.cases[0] ?? null
})

const activeCandidate = computed(() => {
  const list = activeCase.value?.ranked_root_causes ?? []
  return list.find((item) => item.ranking_id === workbenchState.value.selectedCandidateId) ?? list[0] ?? null
})

const graphOptions = computed(() => {
  const options = new Set<string>()
  for (const caseItem of runDetail.value?.cases ?? []) {
    const graphId = getCaseGraphDatasetId(caseItem)
    if (graphId) {
      options.add(graphId)
    }
  }
  return [...options]
})

const observationItemsByCase = computed(
  () =>
    new Map((runDetail.value?.cases ?? []).map((caseItem) => [caseItem.case_id, buildObservationBrowseItems(caseItem)])),
)

const activeObservationItems = computed(() => {
  if (!activeCase.value) {
    return []
  }

  return observationItemsByCase.value.get(activeCase.value.case_id) ?? []
})

const filteredActiveObservationItems = computed(() =>
  filterObservationBrowseItems(activeObservationItems.value, normalizedObservationFilters.value),
)

const activeObservation = computed(() =>
  findObservationBrowseItem(activeObservationItems.value, selectedObservationId.value),
)

const activeVisualRegion = computed(() =>
  activeObservation.value?.rawObservation.value_type === 'visual_region.v1'
    ? toRecord(activeObservation.value.rawObservation.value) : null,
)
const activeRegionMeasurements = computed(() => {
  const region = activeVisualRegion.value
  if (!region) return []
  const value = (input: unknown) => typeof input === 'number' && Number.isFinite(input)
    ? Number(input.toPrecision(5)).toString()
    : Array.isArray(input) ? input.map(value => typeof value === 'number' ? Number(value.toFixed(2)) : value).join(', ') : normalizeText(input, '--')
  return [
    ['面积占比（检测网格）', value(region.area_ratio)],
    ['长宽比 / 离心率', `${value(region.aspect_ratio)} / ${value(region.eccentricity)}`],
    [`bbox（${value(region.image_shape)}）`, value(region.bbox_xyxy)],
    [`原图 bbox（${value(region.original_image_shape)}）`, value(region.image_bbox_xyxy)],
    ['语义来源', value(region.semantic_source)],
    ['语义状态', value(region.semantic_status)],
  ]
})

const observationModalityOptions = computed(() => collectObservationModalities(caseEvidenceEntriesObservationItems.value))
const observationSourceOptions = computed(() => collectObservationSources(caseEvidenceEntriesObservationItems.value))
const selectedObservationVisualEvidence = computed(() =>
  selectVisualEvidenceForObservation(activeObservation.value, activeCase.value?.visual_evidence ?? []),
)

function evidenceMediaUrl(item: VisualEvidenceItem) {
  const url = resolveVisualEvidenceUrl(item)
  return url?.startsWith('/api/') ? null : url
}

const caseEvidenceEntriesObservationItems = computed(() =>
  (runDetail.value?.cases ?? []).flatMap((caseItem) => buildObservationBrowseItems(caseItem)),
)

const caseEvidenceEntries = computed<CaseEvidenceEntry[]>(() => {
  return (runDetail.value?.cases ?? []).map((caseItem) => buildCaseEvidenceEntry(caseItem))
})

const filteredCaseEvidenceEntries = computed(() => {
  return caseEvidenceEntries.value.filter((item) => {
    const observationItems = observationItemsByCase.value.get(item.caseId) ?? []
    return filterObservationBrowseItems(observationItems, normalizedObservationFilters.value).length > 0
  })
})

const activeObservationDetailCount = computed(() => filteredActiveObservationItems.value.length)

const activeRootCauseList = computed(() => activeCase.value?.ranked_root_causes ?? [])

const activeReasoningSummary = computed(() =>
  resolveRunReasoningSummary(runDetail.value, activeCase.value),
)

const runStatusHelp = computed(() => [
  isReplaySessionActive.value
    ? '当前为成品回放：切换记录可查看已保存的结果。'
    : '当前为内置 Demo：可查看成品示例，不执行分析。',
  evidenceClaimBoundaryCopy.value,
])

const rootCauseListHelp = '跟随当前 Case 切换候选根因，点击后同步当前选择。'

const caseEvidenceListHelp =
  '一行一个 Case 入口，hover 查看 evidence 明细，点击即可联动根因区。'

const observationDrilldownHelp =
  '按当前过滤条件查看当前 Case 的 observation；点选后可打开详情，并带着上下文跳转根因与图谱。'

function toRecord(value: unknown) {
  return value && typeof value === 'object' && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null
}

function normalizeText(value: unknown, fallback = '--') {
  return typeof value === 'string' && value.trim().length ? value.trim() : fallback
}

function formatDateTime(value: string | undefined | null) {
  if (!value) {
    return '--'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString('zh-CN', {
    hour12: false,
  })
}

function formatRunStatus(status: string | undefined | null) {
  switch (status) {
    case 'completed':
      return '已完成'
    case 'failed':
      return '失败'
    default:
      return status ?? '--'
  }
}

function formatScore(value: number | null | undefined) {
  return typeof value === 'number' ? value.toFixed(3) : '--'
}

function formatObservationModalityLabel(value: ObservationModality | null | undefined) {
  switch (value) {
    case 'image':
      return 'image'
    case 'time_series':
      return 'time_series'
    case 'log':
      return 'log'
    case 'document':
      return 'document'
    default:
      return '--'
  }
}

function readObservationTextField(observation: ObservationBrowseItem | null, key: string, fallback = '--') {
  if (!observation) {
    return fallback
  }

  return normalizeText(observation.rawObservation[key], fallback)
}

function readObservationNumberField(observation: ObservationBrowseItem | null, key: string) {
  if (!observation) {
    return '--'
  }

  const value = observation.rawObservation[key]
  return typeof value === 'number' && Number.isFinite(value) ? value.toFixed(3) : '--'
}

function getRunPhaseLabel(run: RunSummary) {
  if (runDetail.value?.run.run_id === run.run_id) {
    const step = [...runDetail.value.workflow_steps].reverse().find((item) => item.status === 'completed')
    return step?.title ?? formatRunStatus(run.status)
  }

  return run.status === 'completed' ? '运行完成' : '运行失败'
}

function getCaseGraphDatasetId(caseItem: RunCaseDetail) {
  const evidence = toRecord(caseItem.generated_evidence)
  return normalizeText(evidence?.graph_dataset_id, 'default-graph')
}

function getCaseTopCandidate(caseItem: RunCaseDetail) {
  return caseItem.ranked_root_causes?.[0]?.candidate_name ?? '--'
}

function getCaseReviewStatus(caseItem: RunCaseDetail) {
  return caseItem.review_targets?.length ? '可审阅' : '无反馈目标'
}

function buildObservationTitle(observation: Record<string, unknown>, facet: string) {
  switch (facet) {
    case 'variable':
      return `${normalizeText(observation.variable_name)} / ${normalizeText(observation.direction, 'unknown')}`
    case 'image_defect':
      return `${normalizeText(observation.object)} / ${normalizeText(observation.anomaly_type)}`
    case 'log_event':
      return `${normalizeText(observation.event_code, normalizeText(observation.event_type))} / ${normalizeText(observation.equipment)}`
    default:
      return normalizeText(observation.obs_id, '未命名 observation')
  }
}

function buildCaseEvidenceEntry(caseItem: RunCaseDetail): CaseEvidenceEntry {
  const evidence = toRecord(caseItem.generated_evidence)
  const observations = Array.isArray(evidence?.observations) ? evidence?.observations : []
  const graphDatasetId = getCaseGraphDatasetId(caseItem)
  const caseLabel = caseItem.case_label ?? caseItem.case_id
  const dataset = caseItem.dataset ?? '--'
  const facetCount = new Map<string, number>()
  const titles: string[] = []
  const hints: string[] = []
  let rawRefCount = 0

  for (const item of observations) {
    const observation = toRecord(item)
    if (!observation) {
      continue
    }

    const facet = normalizeText(observation.facet, 'unknown')
    facetCount.set(facet, (facetCount.get(facet) ?? 0) + 1)
    titles.push(buildObservationTitle(observation, facet))

    const linkedHints = Array.isArray(observation.linked_entity_hints)
      ? observation.linked_entity_hints.map((hint) => String(hint))
      : []
    if (linkedHints[0]) {
      hints.push(linkedHints[0])
    }

    const rawRefs = Array.isArray(observation.raw_evidence_refs) ? observation.raw_evidence_refs : []
    rawRefCount += rawRefs.length
  }

  const facetKeys = [...facetCount.keys()]
  const facetSummary = facetKeys.length
    ? facetKeys.map((facet) => `${facet}${(facetCount.get(facet) ?? 0) > 1 ? `×${facetCount.get(facet)}` : ''}`).join(' / ')
    : '--'
  const evidenceSummary = titles.length
    ? `${titles[0]}${titles.length > 1 ? ` 等 ${titles.length} 条` : ''}`
    : '暂无 evidence'
  const hint = hints[0] ?? '--'

  return {
    key: caseItem.case_id,
    caseId: caseItem.case_id,
    caseLabel,
    dataset,
    graphDatasetId,
    observationCount: observations.length,
    facetSummary,
    evidenceSummary,
    hint,
    rawRefCount,
    topCandidate: getCaseTopCandidate(caseItem),
    reviewStatus: getCaseReviewStatus(caseItem),
    pathCount: caseItem.path_graph?.path_count ?? 0,
    searchableText: [caseLabel, dataset, graphDatasetId, facetSummary, evidenceSummary, hint, getCaseTopCandidate(caseItem)]
      .join(' ')
      .toLowerCase(),
    facetKeys,
  }
}

function syncImportedSessionState() {
  importedSessionMeta.value = getLocalSessionMeta()
  importedSessionSummary.value = getImportedSessionSummary()
}

function handleLocalSessionChange() {
  clearSourceView()
  syncImportedSessionState()
  void refreshWorkspace()
}

function setSelectedObservation(observationId: string | null) {
  updateState({
    selectedObservationId: observationId,
  })
}

function openObservationDetail(observationId: string | null) {
  if (!observationId) {
    return
  }

  setSelectedObservation(observationId)
  observationDetailModalVisible.value = true
}

function setSelectedCase(caseId: string | null) {
  updateState({
    selectedCaseId: caseId,
    selectedObservationId: null,
    selectedCandidateId: null,
    selectedPathId: null,
    selectedReviewTargetKey: null,
    selectedGraphNodeId: null,
    subgraphMode: 'path',
    selectedSubgraphNodeId: null,
    selectedSubgraphEdgeId: null,
  })

}

function findBestPathId(caseItem: RunCaseDetail | null, candidate: RankedRootCause | null) {
  const graph = caseItem?.path_graph
  if (!graph || !candidate) {
    return null
  }

  return (
    graph.paths.find((item) => item.target_entity_id === candidate.candidate_id)?.path_id ??
    graph.paths.find((item) => item.path_id === candidate.ranking_id.replace(/^ranking:/, ''))?.path_id ??
    graph.paths.find((item) =>
      item.nodes.some(
        (node) =>
          node.node_id === candidate.candidate_id ||
          node.label === candidate.candidate_name,
      ),
    )?.path_id ??
    graph.paths[0]?.path_id ??
    null
  )
}

function selectCandidate(candidateId: string) {
  const candidate = activeRootCauseList.value.find((item) => item.ranking_id === candidateId) ?? null

  updateState({
    selectedCandidateId: candidateId,
    selectedPathId: findBestPathId(activeCase.value, candidate),
    selectedGraphNodeId: null,
    subgraphMode: 'path',
    selectedSubgraphNodeId: null,
    selectedSubgraphEdgeId: null,
  })
}

async function loadRun(runId: string) {
  const revision = ++runReadRevision
  const fromSource = sourceRevision
  const isCurrent = () => revision === runReadRevision && fromSource === sourceRevision
  runLoading.value = true
  errorMessage.value = ''
  if (activeRun.value?.run_id !== runId) runDetail.value = null

  try {
    const detail = await mockBackend.getRun(runId)
    if (!isCurrent()) return
    const caseIds = detail.cases.map((item) => item.case_id)
    runDetail.value = detail
    updateState({ ...loadedRunSelectionPatch(workbenchState.value, runId, caseIds), selectedRunSource: null })
  } catch (error) {
    if (isCurrent()) errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    if (isCurrent()) runLoading.value = false
  }
}

function clearSourceView() {
  sourceRevision += 1
  runReadRevision += 1
  runLoading.value = false
  runDetail.value = null
  runs.value = []
}

async function refreshWorkspace() {
  const revision = ++workspaceRevision
  const fromSource = sourceRevision
  const selectedAtStart = runReadRevision
  const isCurrent = () => revision === workspaceRevision && fromSource === sourceRevision
  workspaceLoading.value = true
  errorMessage.value = ''

  try {
    const records = await mockBackend.listRuns()
    if (!isCurrent()) return
    runs.value = records
    if (selectedAtStart !== runReadRevision) return
    const next = records.find((item) => item.run_id === selectedRunId.value) ?? records[0]
    if (next) await loadRun(next.run_id)
    else runDetail.value = null
  } catch (error) {
    if (isCurrent()) errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    if (isCurrent()) workspaceLoading.value = false
  }
}

function openGraphExplore(caseId: string, observationId: string | null = null) {
  const runId = activeRun.value?.run_id ?? selectedRunId.value
  if (!runId) {
    return
  }

  updateState({
    selectedRunId: runId,
    selectedRunSource: null,
    selectedCaseId: caseId,
    selectedObservationId:
      observationId ?? (caseId === activeCase.value?.case_id ? selectedObservationId.value : null),
    selectedGraphNodeId: null,
    subgraphMode: 'path',
    selectedSubgraphNodeId: null,
    selectedSubgraphEdgeId: null,
  })

  void router.push({
    name: 'graphs',
    query: {
      run_id: runId,
      case_id: caseId,
    },
  })
}

watch(
  [() => preferences.value.dataSourceMode, () => preferences.value.apiBaseUrl],
  () => {
    clearSourceView()
    updateState(sourceSelectionReset())
    void refreshWorkspace()
  },
)

watch(
  () => workbenchState.value.selectedRunId,
  (runId) => {
    if (runId && runId !== runDetail.value?.run.run_id && runs.value.some(item => item.run_id === runId)) {
      void loadRun(runId)
    }
  },
)

watch(
  () => [
    evidenceFilter.graph,
    evidenceFilter.modality,
    evidenceFilter.source,
    evidenceFilter.keyword,
    evidenceFilter.confidenceBand,
    evidenceFilter.timeFrom,
    evidenceFilter.timeTo,
  ],
  () => {
    updateState({
      evidenceFilterGraph: normalizedObservationFilters.value.graph,
      evidenceFilterModality: normalizedObservationFilters.value.modality,
      evidenceFilterSource: normalizedObservationFilters.value.source,
      evidenceFilterKeyword: normalizedObservationFilters.value.keyword,
      evidenceFilterConfidenceBand: normalizedObservationFilters.value.confidenceBand,
      evidenceFilterTimeFrom: normalizedObservationFilters.value.timeFrom,
      evidenceFilterTimeTo: normalizedObservationFilters.value.timeTo,
    })
  },
)

watch(activeObservationItems, (items) => {
  if (selectedObservationId.value && !items.some((item) => item.id === selectedObservationId.value)) {
    updateState({ selectedObservationId: null })
  }
})

onMounted(() => {
  syncImportedSessionState()
  window.addEventListener(getLocalSessionEventName(), handleLocalSessionChange as EventListener)
  void refreshWorkspace()
})

onBeforeUnmount(() => {
  sourceRevision += 1
  runReadRevision += 1
  window.removeEventListener(getLocalSessionEventName(), handleLocalSessionChange as EventListener)
})
</script>

<template>
  <div
    class="rl-page rl-screen"
    :class="{ 'rl-page--motion': preferences.enablePageEntranceMotion }"
  >
    <a-alert v-if="errorMessage" class="rl-alert" type="error" :title="errorMessage" />
    <a-alert v-if="blockedAnalysisIntent" class="rl-alert" type="info"
      :title="isReplaySessionActive ? '请退出回放并切换到 Backend，再用所选工作图分析。' : '请切换到 Backend，再用所选工作图分析。'" />

    <section class="workspace-shell workspace-shell--evidence">
      <div class="workspace-evidence-layout">
        <div class="workspace-evidence-row">
          <article class="rl-section-card workspace-run-card">
            <header class="rl-section-card__header">
              <div>
                <h3 class="rl-section-card__title">
                  <SectionCardTitle title="成品运行" :help="runStatusHelp">
                    <icon-storage />
                  </SectionCardTitle>
                </h3>
              </div>
              <div class="rl-panel-actions">
                <a-tag :color="isReplaySessionActive ? 'arcoblue' : 'gold'">{{ isReplaySessionActive ? '回放会话' : '内置 Demo' }}</a-tag>
                <a-button :loading="loading" @click="refreshWorkspace">
                  <template #icon><icon-refresh /></template>
                  刷新视图
                </a-button>
              </div>
            </header>
            <div
              class="rl-section-card__body workspace-split-card workspace-split-card--run-status workspace-run-card__body"
            >
              <section class="workspace-stack workspace-stack--fill workspace-upload-form-stack">
                <div v-if="isReplaySessionActive" class="rl-section-card workspace-session-card">
                  <div class="rl-section-card__body workspace-stack workspace-stack--tight">
                    <div class="workspace-summary-list workspace-summary-list--two-col">
                      <div class="workspace-summary-list__item">
                        <span class="workspace-summary-label">
                          <icon-storage />
                          <span>Source mode</span>
                        </span>
                        <strong>{{ replaySourceModeLabel }}</strong>
                      </div>
                      <div class="workspace-summary-list__item">
                        <span class="workspace-summary-label">
                          <icon-relation />
                          <span>Datasets</span>
                        </span>
                        <strong>{{ importedSessionSummary?.datasets.length ?? 0 }}</strong>
                      </div>
                      <div class="workspace-summary-list__item">
                        <span class="workspace-summary-label">
                          <icon-bulb />
                          <span>Cases</span>
                        </span>
                        <strong>{{ importedSessionSummary?.cases.length ?? 0 }}</strong>
                      </div>
                      <div class="workspace-summary-list__item">
                        <span class="workspace-summary-label">
                          <icon-info-circle />
                          <span>Imported at</span>
                        </span>
                        <strong>
                          {{ formatDateTime(importedSessionMeta?.updatedAt ?? null) }}
                        </strong>
                      </div>
                    </div>

                    <a-alert
                      v-if="importedSessionSummary?.warnings.length"
                      type="warning"
                      :show-icon="false"
                      :title="importedSessionSummary?.warnings.join('；')"
                    />

                    <div class="rl-form-actions rl-form-actions--dual">
                      <a-button size="small" @click="emit('import-replay')">替换回放资产</a-button>
                      <a-button size="small" status="warning" @click="clearImportedSession">
                        退出回放
                      </a-button>
                    </div>
                  </div>
                </div>

                <div v-else class="workspace-stack workspace-stack--tight">
                  <a-alert type="info" title="内置 Demo 只展示成品。要提交新分析，请切换到 Backend。" />
                  <div class="rl-form-actions"><a-button size="small" @click="emit('import-replay')">导入回放</a-button></div>
                </div>
                <a-alert
                  v-if="activeReasoningSummary.fallbackApplied"
                  type="info"
                  :show-icon="false"
                  :title="
                    activeReasoningSummary.fallbackReason
                      ? `当前结果已回退到通用路径推理：${activeReasoningSummary.fallbackReason}`
                      : '当前结果已回退到通用路径推理'
                  "
                />
              </section>
              <section class="workspace-run-list-panel">
                <div class="workspace-run-list-panel__header">
                  <strong class="workspace-title-with-icon workspace-run-list-panel__title">
                    <icon-storage />
                    <span>Run 列表</span>
                  </strong>
                  <a-tag color="arcoblue">{{ runs.length }}</a-tag>
                </div>
                <div class="workspace-run-list-panel__body">
                  <div
                    class="workspace-scroll-list workspace-scroll-list--run-list workspace-scroll-list--fill"
                  >
                    <button
                      v-for="run in runs"
                      :key="run.run_id"
                      type="button"
                      class="workspace-basic-list-item workspace-basic-list-item--run"
                      :class="{
                        'workspace-basic-list-item--active': run.run_id === activeRun?.run_id,
                      }"
                      :title="`${run.run_id} · ${formatDateTime(run.created_at)}`"
                      @click="loadRun(run.run_id)"
                    >
                      <strong class="workspace-basic-list-item__primary">{{ run.label }}</strong>
                      <div
                        class="workspace-basic-list-item__meta workspace-basic-list-item__meta--run"
                      >
                        <span>{{ run.run_id }}</span>
                        <span>{{ getRunPhaseLabel(run) }}</span>
                        <span>{{ formatRunStatus(run.status) }}</span>
                        <span>{{ run.case_count }} case</span>
                      </div>
                    </button>
                    <a-empty v-if="!runs.length && !loading">暂无运行记录</a-empty>
                  </div>
                </div>
              </section>
            </div>
          </article>

          <article class="rl-section-card workspace-evidence-card">
            <header class="rl-section-card__header">
              <div>
                <h3 class="rl-section-card__title">
                  <SectionCardTitle title="Case / Evidence 列表" :help="caseEvidenceListHelp">
                    <icon-relation />
                  </SectionCardTitle>
                </h3>
              </div>
              <a-tag color="green">{{ filteredCaseEvidenceEntries.length }}</a-tag>
            </header>
            <div class="rl-section-card__body workspace-evidence-card__body">
              <a-form
                id="evidence-form-2"
                :model="evidenceFilter"
                layout="horizontal"
                label-align="left"
                :label-col-props="{ flex: '64px' }"
                :wrapper-col-props="{ flex: '1' }"
                class="workspace-inline-filters workspace-inline-filters--two-col workspace-form workspace-form--compact-filters"
              >
                <a-form-item
                  field="graph"
                  label="图谱"
                  :label-attrs="{ for: 'evidence-evidenceFilter-graph-input' }"
                  class="workspace-form-item"
                >
                  <div
                    id="evidence-evidenceFilter-graph"
                    v-control-label="'图谱'"
                    class="workspace-control"
                  >
                    <a-select aria-label="图谱" v-model="evidenceFilter.graph">
                      <a-option value="all">全部图谱</a-option>
                      <a-option v-for="graphId in graphOptions" :key="graphId" :value="graphId">
                        {{ graphId }}
                      </a-option>
                    </a-select>
                  </div>
                </a-form-item>
                <a-form-item
                  field="modality"
                  label="模态"
                  :label-attrs="{ for: 'evidence-evidenceFilter-modality-input' }"
                  class="workspace-form-item"
                >
                  <div
                    id="evidence-evidenceFilter-modality"
                    v-control-label="'模态'"
                    class="workspace-control"
                  >
                    <a-select aria-label="模态" v-model="evidenceFilter.modality">
                      <a-option value="all">全部</a-option>
                      <a-option
                        v-for="modality in observationModalityOptions"
                        :key="modality"
                        :value="modality"
                      >
                        {{ formatObservationModalityLabel(modality) }}
                      </a-option>
                    </a-select>
                  </div>
                </a-form-item>
                <a-form-item
                  field="source"
                  label="来源"
                  :label-attrs="{ for: 'evidence-evidenceFilter-source-input' }"
                  class="workspace-form-item"
                >
                  <div
                    id="evidence-evidenceFilter-source"
                    v-control-label="'来源'"
                    class="workspace-control"
                  >
                    <a-select aria-label="来源" v-model="evidenceFilter.source">
                      <a-option value="all">全部来源</a-option>
                      <a-option
                        v-for="source in observationSourceOptions"
                        :key="source"
                        :value="source"
                      >
                        {{ source }}
                      </a-option>
                    </a-select>
                  </div>
                </a-form-item>
                <a-form-item
                  field="confidenceBand"
                  label="置信度"
                  :label-attrs="{ for: 'evidence-evidenceFilter-confidenceBand-input' }"
                  class="workspace-form-item"
                >
                  <div
                    id="evidence-evidenceFilter-confidenceBand"
                    v-control-label="'置信度'"
                    class="workspace-control"
                  >
                    <a-select aria-label="置信度" v-model="evidenceFilter.confidenceBand">
                      <a-option value="all">全部</a-option>
                      <a-option value="high">高</a-option>
                      <a-option value="medium">中</a-option>
                      <a-option value="low">低</a-option>
                    </a-select>
                  </div>
                </a-form-item>
                <a-form-item
                  label="时间范围"
                  :label-attrs="{ for: 'evidence-evidenceFilter-timeFrom-input' }"
                  class="workspace-form-item workspace-inline-filters__wide"
                >
                  <div class="workspace-form-row workspace-time-range">
                    <a-input
                      :input-attrs="{
                        id: 'evidence-evidenceFilter-timeFrom-input',
                        'aria-label': '开始时间',
                      }"
                      id="evidence-evidenceFilter-timeFrom"
                      aria-label="开始时间"
                      v-model="evidenceFilter.timeFrom"
                      type="datetime-local"
                      placeholder="开始时间"
                    />
                    <a-input
                      :input-attrs="{
                        id: 'evidence-evidenceFilter-timeFrom-1-input',
                        'aria-label': '结束时间',
                      }"
                      id="evidence-evidenceFilter-timeFrom-1"
                      aria-label="结束时间"
                      v-model="evidenceFilter.timeTo"
                      type="datetime-local"
                      placeholder="结束时间"
                    />
                  </div>
                </a-form-item>
                <a-form-item
                  field="keyword"
                  label="关键字"
                  :label-attrs="{ for: 'evidence-evidenceFilter-keyword-input' }"
                  class="workspace-form-item workspace-inline-filters__wide"
                >
                  <a-input
                    :input-attrs="{
                      id: 'evidence-evidenceFilter-keyword-input',
                      'aria-label': '关键字',
                    }"
                    id="evidence-evidenceFilter-keyword"
                    aria-label="关键字"
                    v-model="evidenceFilter.keyword"
                    placeholder="搜索 obs / source / hint / ref / variable / event"
                  />
                </a-form-item>
              </a-form>

              <div class="workspace-scroll-list workspace-scroll-list--fill workspace-scroll-list--case-evidence">
                <div
                  v-for="item in filteredCaseEvidenceEntries"
                  :key="item.key"
                  class="workspace-basic-list-item workspace-basic-list-item--with-action workspace-basic-list-item--case-evidence"
                  :class="{
                    'workspace-basic-list-item--active': item.caseId === activeCase?.case_id,
                  }"
                >
                  <a-tooltip position="left" :trigger="['hover', 'focus']">
                    <button
                      type="button"
                      class="workspace-basic-list-item__select"
                      :aria-pressed="item.caseId === activeCase?.case_id"
                      :aria-label="`选择 Case ${item.caseLabel}`"
                      @click="setSelectedCase(item.caseId)"
                    >
                      <strong class="workspace-basic-list-item__primary" :title="item.caseLabel">
                        {{ item.caseLabel }}
                      </strong>
                      <span class="workspace-basic-list-item__meta">
                        <span>{{ item.dataset }}</span>
                        <span class="workspace-basic-list-item__tooltip-anchor">
                          {{ item.evidenceSummary }}
                        </span>
                        <span :title="item.topCandidate">{{ item.topCandidate }}</span>
                        <span>{{ item.reviewStatus }}</span>
                      </span>
                    </button>
                    <template #content>
                      <div class="workspace-tooltip-card">
                        <div class="workspace-tooltip-card__row">
                          <span>图谱</span>
                          <strong>{{ item.graphDatasetId }}</strong>
                        </div>
                        <div class="workspace-tooltip-card__row">
                          <span>Observation</span>
                          <strong>{{ item.observationCount }}</strong>
                        </div>
                        <div class="workspace-tooltip-card__row">
                          <span>Facet</span>
                          <strong>{{ item.facetSummary }}</strong>
                        </div>
                        <div class="workspace-tooltip-card__row">
                          <span>Hint</span>
                          <strong>{{ item.hint }}</strong>
                        </div>
                        <div class="workspace-tooltip-card__row">
                          <span>Raw Refs</span>
                          <strong>{{ item.rawRefCount }}</strong>
                        </div>
                      </div>
                    </template>
                  </a-tooltip>
                  <a-button
                    size="mini"
                    type="text"
                    :aria-label="`查看 ${item.caseLabel} 的根因与图谱`"
                    @click="openGraphExplore(item.caseId)"
                  >
                    <template #icon>
                      <icon-launch />
                    </template>
                    根因与图谱
                  </a-button>
                </div>
                <a-empty v-if="!filteredCaseEvidenceEntries.length">
                  没有匹配的 Case / Evidence 条目
                </a-empty>
              </div>
            </div>
          </article>
        </div>

        <div class="workspace-evidence-row">
          <article
            class="rl-section-card workspace-root-cause-card workspace-root-cause-card--evidence"
          >
            <header class="rl-section-card__header">
              <div>
                <h3 class="rl-section-card__title">
                  <SectionCardTitle title="根因列表" :help="rootCauseListHelp">
                    <icon-bulb />
                  </SectionCardTitle>
                </h3>
              </div>
              <div class="rl-inline-tags">
                <UnifiedReasoningDetails :metadata="activeCase?.reasoning_metadata" :candidate-id="activeCandidate?.candidate_id" :query-id="activeCandidate?.scoring_details?.query_id" />
                <a-tag color="arcoblue">
                  {{ activeCase?.case_label ?? activeCase?.case_id ?? '--' }}
                </a-tag>
                <a-tag color="gold">{{ activeRootCauseList.length }} 条</a-tag>
              </div>
            </header>
            <div
              class="rl-section-card__body workspace-root-cause-card__body workspace-root-cause-card__body--plain"
            >
              <div class="workspace-scroll-list workspace-scroll-list--fill">
                <button
                  v-for="candidate in activeRootCauseList"
                  :key="candidate.ranking_id"
                  type="button"
                  class="workspace-basic-list-item workspace-basic-list-item--root-cause"
                  :class="{
                    'workspace-basic-list-item--active':
                      candidate.ranking_id === activeCandidate?.ranking_id,
                  }"
                  @click="selectCandidate(candidate.ranking_id)"
                >
                  <span class="workspace-basic-list-item__primary">
                    #{{ candidate.rank }} {{ candidate.candidate_name }}
                  </span>
                  <span>{{ formatScore(candidate.score) }}</span>
                  <span>{{ formatScoringMethodLabel(candidate.scoring_method) }}</span>
                  <span>{{ normalizeText(candidate.candidate_role, 'candidate') }}</span>
                </button>
                <a-empty v-if="!activeRootCauseList.length">当前 Case 没有候选根因</a-empty>
              </div>
            </div>
          </article>

          <article
            class="rl-section-card workspace-root-cause-summary-card workspace-observation-card"
          >
            <header class="rl-section-card__header">
              <div>
                <h3 class="rl-section-card__title">
                  <SectionCardTitle title="Observation Drilldown" :help="observationDrilldownHelp">
                    <icon-info-circle />
                  </SectionCardTitle>
                </h3>
              </div>
              <div class="rl-inline-tags">
                <a-tag color="arcoblue">
                  {{ activeCase?.case_label ?? activeCase?.case_id ?? '--' }}
                </a-tag>
                <a-tag color="gold">{{ activeObservationDetailCount }}</a-tag>
              </div>
            </header>
            <div class="rl-section-card__body workspace-observation-card__body">
              <div class="workspace-observation-toolbar">
                <div class="workspace-observation-toolbar__selection" aria-live="polite">
                  <span>当前选择</span>
                  <strong :title="activeObservation?.id">{{ activeObservation?.id ?? '未选择' }}</strong>
                </div>
                <div class="rl-inline-tags">
                  <a-button
                    size="mini"
                    :disabled="!activeObservation"
                    @click="openObservationDetail(activeObservation?.id ?? null)"
                  >
                    查看详情
                  </a-button>
                  <a-button
                    size="mini"
                    :disabled="!activeObservation || !activeCase"
                    @click="
                      activeCase?.case_id &&
                      openGraphExplore(activeCase.case_id, activeObservation?.id ?? null)
                    "
                  >
                    根因与图谱
                  </a-button>
                </div>
              </div>

              <div
                class="workspace-scroll-list workspace-scroll-list--fill workspace-scroll-list--observation"
              >
                <div
                  v-for="item in filteredActiveObservationItems"
                  :key="item.id"
                  class="workspace-basic-list-item workspace-basic-list-item--with-action workspace-basic-list-item--observation"
                  :class="{
                    'workspace-basic-list-item--active': item.id === selectedObservationId,
                  }"
                >
                  <button
                    type="button"
                    class="workspace-basic-list-item__select"
                    :aria-pressed="item.id === selectedObservationId"
                    :aria-label="`选择 Observation ${item.title}`"
                    @click="setSelectedObservation(item.id)"
                  >
                    <span class="workspace-basic-list-item__head">
                      <strong class="workspace-basic-list-item__primary" :title="item.title">
                        {{ item.title }}
                      </strong>
                      <span :title="`置信度 ${formatScore(item.confidence)}`">
                        {{ formatScore(item.confidence) }}
                      </span>
                    </span>
                    <span class="workspace-basic-list-item__meta">
                      <span>{{ formatObservationModalityLabel(item.modality) }}</span>
                      <span
                        v-if="item.source !== item.modality && item.source !== '--'"
                        :title="`Source: ${item.source}`"
                      >{{ item.source }}</span>
                      <span v-if="item.timestamp" :title="item.timeLabel">{{ item.timeLabel }}</span>
                      <span>{{ item.linkedEntityCount }} linked</span>
                      <span>{{ item.rawRefCount }} refs</span>
                    </span>
                  </button>
                  <a-button
                    size="mini"
                    type="text"
                    :aria-label="`查看 ${item.title} 的 Observation 详情`"
                    @click="openObservationDetail(item.id)"
                  >
                    详情
                  </a-button>
                </div>
                <a-empty v-if="!filteredActiveObservationItems.length">
                  当前 Case 没有匹配的 observation
                </a-empty>
              </div>
            </div>
          </article>
        </div>
      </div>
    </section>
  </div>

  <a-modal
    v-model:visible="observationDetailModalVisible"
    title="Observation 详情"
    :footer="false"
    width="min(880px, calc(100vw - 24px))"
    class="workspace-observation-modal"
  >
    <div v-if="activeObservation" class="workspace-stack workspace-stack--tight">
      <div class="workspace-summary-list workspace-summary-list--two-col">
        <div class="workspace-summary-list__item">
          <span class="workspace-summary-label">
            <icon-storage />
            <span>Obs ID</span>
          </span>
          <strong>{{ activeObservation.id }}</strong>
        </div>
        <div class="workspace-summary-list__item">
          <span class="workspace-summary-label">
            <icon-bulb />
            <span>Modality</span>
          </span>
          <strong>{{ formatObservationModalityLabel(activeObservation.modality) }}</strong>
        </div>
        <div class="workspace-summary-list__item">
          <span class="workspace-summary-label">
            <icon-relation />
            <span>Source</span>
          </span>
          <strong>{{ activeObservation.source }}</strong>
        </div>
        <div class="workspace-summary-list__item">
          <span class="workspace-summary-label">
            <icon-info-circle />
            <span>Confidence</span>
          </span>
          <strong>{{ formatScore(activeObservation.confidence) }}</strong>
        </div>
      </div>

      <MeasuredEvidenceDetails :observation="activeObservation.rawObservation" />
      <template v-if="activeObservation.modality === 'image'">
        <div class="workspace-summary-list workspace-summary-list--two-col">
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label">
              <icon-storage />
              <span>Object</span>
            </span>
            <strong>{{ readObservationTextField(activeObservation, 'object') }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label">
              <icon-info-circle />
              <span>Anomaly</span>
            </span>
            <strong>{{ readObservationTextField(activeObservation, 'anomaly_type') }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label">
              <icon-relation />
              <span>Location</span>
            </span>
            <strong>{{ readObservationTextField(activeObservation, 'location') }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label">
              <icon-bulb />
              <span>Severity</span>
            </span>
            <strong>{{ readObservationNumberField(activeObservation, 'severity') }}</strong>
          </div>
        </div>
        <div v-if="activeRegionMeasurements.length" class="workspace-summary-list workspace-summary-list--two-col">
          <div v-for="[label, value] in activeRegionMeasurements" :key="label" class="workspace-summary-list__item">
            <span class="workspace-summary-label">{{ label }}</span>
            <strong>{{ value }}</strong>
          </div>
        </div>
        <p v-if="activeVisualRegion?.semantic_description">{{ activeVisualRegion.semantic_description }}</p>
        <div
          v-if="selectedObservationVisualEvidence.length"
          class="workspace-observation-visual-grid"
        >
          <div
            v-for="item in selectedObservationVisualEvidence"
            :key="item.artifact_id"
            class="rl-visual-card"
          >
            <img
              v-if="evidenceMediaUrl(item)"
              :src="evidenceMediaUrl(item) ?? undefined"
              :alt="item.title"
            />
            <div>
              <strong>{{ item.title }}</strong>
              <span>{{ item.kind }}</span>
            </div>
          </div>
        </div>
        <a-empty v-else>当前 observation 暂无可视资源</a-empty>
      </template>

      <template v-else-if="activeObservation.modality === 'time_series'">
        <div class="workspace-summary-list workspace-summary-list--two-col">
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label">
              <icon-storage />
              <span>Variable</span>
            </span>
            <strong>{{ readObservationTextField(activeObservation, 'variable_name') }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label">
              <icon-info-circle />
              <span>Direction</span>
            </span>
            <strong>{{ readObservationTextField(activeObservation, 'direction') }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label">
              <icon-bulb />
              <span>Contribution</span>
            </span>
            <strong>{{ readObservationNumberField(activeObservation, 'contribution') }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label">
              <icon-relation />
              <span>Time Window</span>
            </span>
            <strong>{{ activeObservation.timeLabel }}</strong>
          </div>
        </div>
      </template>

      <template v-else-if="activeObservation.modality === 'log'">
        <div class="workspace-summary-list workspace-summary-list--two-col">
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label">
              <icon-storage />
              <span>Event Code</span>
            </span>
            <strong>{{ readObservationTextField(activeObservation, 'event_code') }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label">
              <icon-info-circle />
              <span>Event Type</span>
            </span>
            <strong>{{ readObservationTextField(activeObservation, 'event_type') }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label">
              <icon-relation />
              <span>Equipment</span>
            </span>
            <strong>{{ readObservationTextField(activeObservation, 'equipment') }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label">
              <icon-bulb />
              <span>Time</span>
            </span>
            <strong>{{ activeObservation.timeLabel }}</strong>
          </div>
        </div>
        <div class="workspace-claim-note workspace-claim-note--compact">
          <span class="workspace-summary-label">
            <icon-info-circle />
            <span>Message</span>
          </span>
          <strong>{{ readObservationTextField(activeObservation, 'message') }}</strong>
        </div>
      </template>

      <div class="workspace-claim-note workspace-claim-note--compact">
        <span class="workspace-summary-label">
          <icon-bulb />
          <span>Linked entity hints</span>
        </span>
        <strong>
          {{
            activeObservation.linkedEntityHints.length
              ? activeObservation.linkedEntityHints.join(', ')
              : '—'
          }}
        </strong>
      </div>

      <div v-if="activeObservation.rawEvidenceRefs.length" class="workspace-observation-ref-list">
        <div
          v-for="refItem in activeObservation.rawEvidenceRefs"
          :key="refItem.refId"
          class="workspace-observation-ref"
        >
          <strong>{{ refItem.label }}</strong>
          <span>{{ refItem.role }}</span>
          <span>{{ refItem.filePath }}</span>
        </div>
      </div>
      <a-empty v-else>当前 observation 没有 raw refs</a-empty>

      <div class="rl-form-actions rl-form-actions--dual">
        <a-button
          type="primary"
          @click="activeCase?.case_id && openGraphExplore(activeCase.case_id, activeObservation.id)"
        >
          根因与图谱
        </a-button>
        <a-button @click="observationDetailModalVisible = false">关闭</a-button>
      </div>
    </div>
    <a-empty v-else>当前没有选中的 observation</a-empty>
  </a-modal>
</template>
