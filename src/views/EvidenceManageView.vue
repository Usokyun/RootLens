<script setup lang="ts">
import {
  IconBulb,
  IconInfoCircle,
  IconLaunch,
  IconRefresh,
  IconRelation,
  IconStorage,
  IconUpload,
} from '@arco-design/web-vue/es/icon'
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import type {
  DashboardBootstrap,
  RankedRootCause,
  RunCaseDetail,
  RunDetail,
  RunSummary,
  UploadMode,
} from '@/api/contracts'
import SectionCardTitle from '@/components/layout/SectionCardTitle.vue'
import WorkbenchHero from '@/components/layout/WorkbenchHero.vue'
import { useAppPreferences } from '@/services/app-preferences'
import { buildLocalImportResult } from '@/services/browser-runtime'
import { clearImportedSession, getImportedSessionSummary, getLocalSessionEventName, getLocalSessionMeta, saveImportedSession } from '@/services/rootlens-data'
import { getRootLensService } from '@/services/rootlens-service'
import { restoreSessionImportFile } from '@/services/session-export'
import { filterObservationBrowseItems, buildObservationBrowseItems, collectObservationModalities, collectObservationSources, findObservationBrowseItem, selectVisualEvidenceForObservation, type ObservationBrowseItem, type ObservationConfidenceBand, type ObservationModality } from '@/services/evidence-observation'
import { formatClaimBoundaryCopy, formatScoringMethodLabel } from '@/services/ui-copy'
import { useWorkbenchState } from '@/services/workbench-state'

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
const { preferences } = useAppPreferences()
const { state: workbenchState, updateState } = useWorkbenchState()
const isMockMode = computed(() => preferences.value.dataSourceMode === 'mock')

const loading = ref(false)
const uploadLoading = ref(false)
const bootstrap = ref<DashboardBootstrap | null>(null)
const runs = ref<RunSummary[]>([])
const runDetail = ref<RunDetail | null>(null)
const errorMessage = ref('')
const uploadMessage = ref('')
const uploadInputRef = ref<HTMLInputElement | null>(null)
const uploadDragActive = ref(false)
const uploadDragDepth = ref(0)

const replayModalVisible = ref(false)
const replayImportLoading = ref(false)
const replayRuntimeInputRef = ref<HTMLInputElement | null>(null)
const replayGraphsInputRef = ref<HTMLInputElement | null>(null)
const replayWorkspaceInputRef = ref<HTMLInputElement | null>(null)
const importedSessionMeta = ref(getLocalSessionMeta())
const importedSessionSummary = ref(getImportedSessionSummary())
const replayWarnings = ref<string[]>([])

const replayImportForm = reactive({
  runtimeFile: null as File | null,
  graphsFile: null as File | null,
  workspaceFile: null as File | null,
})

const observationDetailModalVisible = ref(false)

const uploadForm = reactive({
  mode: 'records' as UploadMode,
  dataset: '',
  topK: 5,
  file: null as File | null,
  objectName: '',
  defectType: '',
  modelPreset: 'auto',
})

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
      return '图谱 + Evidence'
    case 'graphs-only':
      return '仅图谱'
    case 'runtime':
      return '完整回放'
    default:
      return '--'
  }
})
const evidenceClaimBoundaryCopy = computed(() =>
  formatClaimBoundaryCopy(runDetail.value?.claim_boundary ?? bootstrap.value?.claim_boundary),
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

const observationModalityOptions = computed(() => collectObservationModalities(caseEvidenceEntriesObservationItems.value))
const observationSourceOptions = computed(() => collectObservationSources(caseEvidenceEntriesObservationItems.value))
const selectedObservationVisualEvidence = computed(() =>
  selectVisualEvidenceForObservation(activeObservation.value, activeCase.value?.visual_evidence ?? []),
)

const uploadAccept = computed(() => {
  const modeConfig = bootstrap.value?.upload_modes.find((item) => item.mode === uploadForm.mode)
  return modeConfig?.accepted_extensions.join(',') ?? ''
})

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

const totalObservationCount = computed(() => {
  return caseEvidenceEntries.value.reduce((total, item) => total + item.observationCount, 0)
})

const activeObservationDetailCount = computed(() => filteredActiveObservationItems.value.length)

const activeRootCauseList = computed(() => activeCase.value?.ranked_root_causes ?? [])

const heroMetrics = computed(() => [
  {
    label: '运行记录',
    value: runs.value.length,
    hint: '当前可切换的运行数',
    tone: 'blue' as const,
  },
  {
    label: 'Case 数',
    value: activeRun.value?.case_count ?? 0,
    hint: '当前运行内的案例数',
    tone: 'teal' as const,
  },
  {
    label: 'Evidence Observation',
    value: totalObservationCount.value,
    hint: '当前 run 内汇总的 observation 数',
    tone: 'amber' as const,
  },
])

const runStatusHelp = computed(() => [
  isMockMode.value
    ? '当前为论文演示 mock 模式：左侧仅保留预设 case 说明，右侧固定展示唯一 demo run。'
    : '左侧提交 record，右侧用紧凑列表切换当前 Run。',
  evidenceClaimBoundaryCopy.value,
])

const rootCauseListHelp = '跟随当前 Case 切换候选根因，点击后同步当前选择。'

const caseEvidenceListHelp =
  '一行一个 Case 入口，hover 查看 evidence 明细，点击即可联动根因区。'

const observationDrilldownHelp =
  '按当前过滤条件查看当前 Case 的 observation；点选后可打开详情，并带着上下文跳转图谱探索。'

const mockPresetCaseCount = computed(() => caseEvidenceEntries.value.length)

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

function formatUploadModeLabel(mode: UploadMode | undefined | null) {
  switch (mode) {
    case 'records':
      return '批量记录'
    case 'evidence':
      return '单条证据'
    case 'image':
      return '图像'
    default:
      return '--'
  }
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

function setUploadFile(file: File | null) {
  uploadForm.file = file
}

function handleUploadFileChange(event: Event) {
  const input = event.target as HTMLInputElement | null
  setUploadFile(input?.files?.[0] ?? null)
}

function openUploadPicker() {
  uploadInputRef.value?.click()
}

function resetUploadDragState() {
  uploadDragDepth.value = 0
  uploadDragActive.value = false
}

function handleUploadDragEnter(event: DragEvent) {
  event.preventDefault()
  uploadDragDepth.value += 1
  uploadDragActive.value = true
}

function handleUploadDragOver(event: DragEvent) {
  event.preventDefault()
  uploadDragActive.value = true
}

function handleUploadDragLeave(event: DragEvent) {
  event.preventDefault()
  uploadDragDepth.value = Math.max(0, uploadDragDepth.value - 1)
  if (uploadDragDepth.value === 0) {
    uploadDragActive.value = false
  }
}

function handleUploadDrop(event: DragEvent) {
  event.preventDefault()
  const [file] = event.dataTransfer?.files ?? []
  setUploadFile(file ?? null)
  resetUploadDragState()
}

function syncImportedSessionState() {
  importedSessionMeta.value = getLocalSessionMeta()
  importedSessionSummary.value = getImportedSessionSummary()
}

function handleLocalSessionChange() {
  syncImportedSessionState()
  void refreshWorkspace()
}

function resetReplayImportForm() {
  replayImportForm.runtimeFile = null
  replayImportForm.graphsFile = null
  replayImportForm.workspaceFile = null
  replayWarnings.value = []
}

function openReplayAssetsModal() {
  resetReplayImportForm()
  replayModalVisible.value = true
}

function setReplayImportFile(kind: 'runtimeFile' | 'graphsFile' | 'workspaceFile', file: File | null) {
  replayImportForm[kind] = file
}

function handleReplayFileChange(kind: 'runtimeFile' | 'graphsFile' | 'workspaceFile', event: Event) {
  const input = event.target as HTMLInputElement | null
  setReplayImportFile(kind, input?.files?.[0] ?? null)
}

function openReplayFilePicker(kind: 'runtimeFile' | 'graphsFile' | 'workspaceFile') {
  if (kind === 'runtimeFile') {
    replayRuntimeInputRef.value?.click()
    return
  }

  if (kind === 'graphsFile') {
    replayGraphsInputRef.value?.click()
    return
  }

  replayWorkspaceInputRef.value?.click()
}

async function readSessionImportSchema(file: File) {
  try {
    const payload = JSON.parse(await file.text()) as Record<string, unknown>
    return typeof payload.schema_version === 'string' ? payload.schema_version : null
  } catch {
    throw new Error('附加恢复文件不是合法 JSON。')
  }
}

async function handleReplayImport() {
  const assetFiles = [replayImportForm.runtimeFile, replayImportForm.graphsFile].filter(
    (file): file is File => Boolean(file),
  )
  const workspaceFile = replayImportForm.workspaceFile

  if (!assetFiles.length && !workspaceFile) {
    errorMessage.value = '请至少选择一份回放资产或工作区恢复文件。'
    return
  }

  replayImportLoading.value = true
  errorMessage.value = ''
  uploadMessage.value = ''

  try {
    const messages: string[] = []
    const warnings: string[] = []

    if (assetFiles.length) {
      const importResult = await buildLocalImportResult(assetFiles)
      saveImportedSession({
        graphs: importResult.graphs,
        runtime: importResult.runtime,
        summary: `导入回放资产：${importResult.summary.datasets.length} 个 dataset，${importResult.summary.cases.length} 个 case。`,
        importSummary: importResult.summary,
      })
      syncImportedSessionState()
      messages.push(
        `已导入回放资产：${importResult.summary.datasets.length} 个 dataset，${importResult.summary.cases.length} 个 case。`,
      )
      warnings.push(...importResult.summary.warnings)
    }

    if (workspaceFile) {
      const schemaVersion = await readSessionImportSchema(workspaceFile)
      if (assetFiles.length && schemaVersion === 'rootlens-session-export.v1') {
        throw new Error('完整 session bundle 请单独导入，不要与 runtime/graphs 原始资产混合。')
      }

      const restoreResult = await restoreSessionImportFile(workspaceFile)
      syncImportedSessionState()
      messages.push(restoreResult.summary)
      warnings.push(...restoreResult.warnings)
    }

    replayWarnings.value = warnings
    replayModalVisible.value = false
    uploadMessage.value = [
      messages.join(' '),
      warnings.length ? `警告：${warnings.join('；')}` : '',
    ]
      .filter(Boolean)
      .join(' ')

    await refreshWorkspace()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    replayImportLoading.value = false
  }
}

async function handleSwitchToLiveUpload() {
  if (!isReplaySessionActive.value) {
    return
  }

  clearImportedSession()
  syncImportedSessionState()
  replayWarnings.value = []
  uploadMessage.value = '已退出回放会话，恢复当前实时/演示数据视图。'
  await refreshWorkspace()
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

function setSelectedRun(runId: string) {
  updateState({
    selectedRunId: runId,
    selectedCaseId: null,
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
  loading.value = true
  errorMessage.value = ''

  try {
    const detail = await getRootLensService().getRun(runId)
    runDetail.value = detail
    setSelectedRun(runId)
    const nextCaseId =
      detail.cases.find((item) => item.case_id === workbenchState.value.selectedCaseId)?.case_id ??
      detail.cases[0]?.case_id ??
      null
    setSelectedCase(nextCaseId)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    loading.value = false
  }
}

async function refreshWorkspace() {
  syncImportedSessionState()
  loading.value = true
  errorMessage.value = ''

  try {
    const [bootstrapPayload, runSummaries] = await Promise.all([
      getRootLensService().bootstrap(),
      getRootLensService().listRuns(),
    ])
    bootstrap.value = bootstrapPayload
    runs.value = runSummaries
    uploadForm.mode = bootstrapPayload.upload_modes[0]?.mode ?? 'records'

    const nextRunId =
      runSummaries.find((item) => item.run_id === selectedRunId.value)?.run_id ?? runSummaries[0]?.run_id ?? null

    if (nextRunId) {
      await loadRun(nextRunId)
      return
    }

    runDetail.value = null
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    loading.value = false
  }
}

async function handleUpload() {
  if (isMockMode.value) {
    uploadMessage.value = '论文演示 mock 模式不开放上传，请切换到 backend 模式后再提交真实数据。'
    return
  }

  if (!uploadForm.file) {
    uploadMessage.value = '请选择一个本地文件。'
    return
  }

  uploadLoading.value = true
  uploadMessage.value = ''
  errorMessage.value = ''

  try {
    const detail = await getRootLensService().uploadRun({
      file: uploadForm.file,
      mode: uploadForm.mode,
      dataset: uploadForm.dataset || undefined,
      object_name: uploadForm.objectName || undefined,
      defect_type: uploadForm.defectType || undefined,
      model_preset: uploadForm.modelPreset || undefined,
      top_k: uploadForm.topK,
    })

    uploadMessage.value = `已生成运行：${detail.run.run_id}`
    await refreshWorkspace()
    await loadRun(detail.run.run_id)
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  } finally {
    uploadLoading.value = false
  }
}

function openGraphExplore(caseId: string, observationId: string | null = null) {
  const runId = activeRun.value?.run_id ?? selectedRunId.value
  if (!runId) {
    return
  }

  updateState({
    selectedRunId: runId,
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
  () => [preferences.value.dataSourceMode, preferences.value.apiBaseUrl],
  () => {
    void refreshWorkspace()
  },
)

watch(
  () => workbenchState.value.selectedRunId,
  (runId) => {
    if (runId && runId !== runDetail.value?.run.run_id) {
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
  window.removeEventListener(getLocalSessionEventName(), handleLocalSessionChange as EventListener)
})
</script>

<template>
  <div class="rl-page rl-screen" :class="{ 'rl-page--motion': preferences.enablePageEntranceMotion }">
    <WorkbenchHero
      eyebrow="证据与审阅"
      title="上传运行并快速筛选 Evidence"
      :metrics="heroMetrics"
    >
      <template #actions>
        <a-button size="small" @click="refreshWorkspace">
          <template #icon>
            <icon-refresh />
          </template>
          刷新视图
        </a-button>
      </template>
    </WorkbenchHero>

    <a-alert v-if="errorMessage" class="rl-alert" type="error" :title="errorMessage" />
    <a-alert v-if="uploadMessage" class="rl-alert" type="success" :title="uploadMessage" />

    <section class="workspace-shell workspace-shell--evidence">
      <div class="workspace-evidence-layout">
        <div class="workspace-evidence-main">
          <article class="rl-section-card workspace-run-card">
            <header class="rl-section-card__header">
              <div>
                <h3 class="rl-section-card__title">
                  <SectionCardTitle title="上传与运行状态" :help="runStatusHelp">
                    <icon-upload />
                  </SectionCardTitle>
                </h3>
              </div>
              <a-tag :color="isReplaySessionActive ? 'arcoblue' : isMockMode ? 'gold' : 'green'">
                {{ isReplaySessionActive ? '回放会话' : isMockMode ? '论文演示模式' : formatUploadModeLabel(uploadForm.mode) }}
              </a-tag>
            </header>
            <div class="rl-section-card__body workspace-split-card workspace-split-card--run-status workspace-run-card__body">
              <section class="workspace-stack workspace-stack--fill workspace-upload-form-stack">
                <div class="workspace-session-source-strip" role="tablist" aria-label="切换 Evidence 会话来源">
                  <button
                    type="button"
                    class="workspace-session-source-strip__item"
                    :class="{ 'workspace-session-source-strip__item--active': !isReplaySessionActive }"
                    @click="handleSwitchToLiveUpload"
                  >
                    实时上传
                  </button>
                  <button
                    type="button"
                    class="workspace-session-source-strip__item"
                    :class="{ 'workspace-session-source-strip__item--active': isReplaySessionActive }"
                    @click="openReplayAssetsModal"
                  >
                    回放资产
                  </button>
                </div>


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
                        <strong>{{ formatDateTime(importedSessionMeta?.updatedAt ?? null) }}</strong>
                      </div>
                    </div>

                    <a-alert
                      v-if="(importedSessionSummary?.warnings.length ?? 0) || replayWarnings.length"
                      type="warning"
                      :show-icon="false"
                      :title="[...(importedSessionSummary?.warnings ?? []), ...replayWarnings].join('；')"
                    />

                    <div class="rl-form-actions rl-form-actions--dual">
                      <a-button size="small" @click="openReplayAssetsModal">替换回放资产</a-button>
                      <a-button size="small" status="warning" @click="handleSwitchToLiveUpload">退出回放</a-button>
                    </div>
                  </div>
                </div>

                <div v-else-if="isMockMode" class="rl-section-card workspace-demo-mode-card">
                  <div class="rl-section-card__body workspace-stack workspace-stack--fill">
                    <div class="workspace-claim-note">
                      <span class="workspace-summary-label">
                        <icon-storage />
                        <span>Mock Mode</span>
                      </span>
                      <strong>当前为论文演示静态快照，不开放上传。</strong>
                    </div>
                    <div class="workspace-summary-list workspace-summary-list--two-col">
                      <div class="workspace-summary-list__item">
                        <span class="workspace-summary-label">
                          <icon-bulb />
                          <span>预设 Case</span>
                        </span>
                        <strong>{{ mockPresetCaseCount }}</strong>
                      </div>
                      <div class="workspace-summary-list__item">
                        <span class="workspace-summary-label">
                          <icon-relation />
                          <span>切换方式</span>
                        </span>
                        <strong>从右侧列表选择 case</strong>
                      </div>
                    </div>
                    <a-alert
                      type="info"
                      title="需要真实上传、批量 run 历史或联调后端能力时，请先把顶部模式切换到 backend。"
                    />
                  </div>
                </div>

                <div v-else class="workspace-stack workspace-stack--fill workspace-upload-form-stack">
                  <div class="workspace-form-row workspace-form-row--three">
                    <div class="rl-form-field">
                      <span class="workspace-field-label">
                        <icon-storage />
                        <span>模式</span>
                      </span>
                      <a-select v-model="uploadForm.mode">
                        <a-option v-for="item in bootstrap?.upload_modes ?? []" :key="item.mode" :value="item.mode">
                          {{ formatUploadModeLabel(item.mode) }}
                        </a-option>
                      </a-select>
                    </div>
                    <div class="rl-form-field">
                      <span class="workspace-field-label">
                        <icon-relation />
                        <span>数据集</span>
                      </span>
                      <a-select v-model="uploadForm.dataset" allow-clear>
                        <a-option value="">自动</a-option>
                        <a-option v-for="dataset in bootstrap?.supported_datasets ?? []" :key="dataset" :value="dataset">
                          {{ dataset }}
                        </a-option>
                      </a-select>
                    </div>
                    <div class="rl-form-field">
                      <span class="workspace-field-label">
                        <icon-bulb />
                        <span>候选数</span>
                      </span>
                      <a-input-number v-model="uploadForm.topK" :min="1" :max="20" />
                    </div>
                  </div>

                  <div v-if="uploadForm.mode === 'image'" class="workspace-form-row workspace-form-row--three">
                    <div class="rl-form-field">
                      <span class="workspace-field-label">
                        <icon-storage />
                        <span>对象</span>
                      </span>
                      <a-input v-model="uploadForm.objectName" placeholder="例如 bottle" />
                    </div>
                    <div class="rl-form-field">
                      <span class="workspace-field-label">
                        <icon-info-circle />
                        <span>缺陷类型</span>
                      </span>
                      <a-input v-model="uploadForm.defectType" placeholder="例如 scratch" />
                    </div>
                    <div class="rl-form-field">
                      <span class="workspace-field-label">
                        <icon-bulb />
                        <span>预设</span>
                      </span>
                      <a-input v-model="uploadForm.modelPreset" placeholder="auto" />
                    </div>
                  </div>

                  <div class="rl-form-field workspace-dropzone-field">
                    <span class="workspace-field-label">
                      <icon-upload />
                      <span>文件</span>
                    </span>
                    <div
                      class="rl-file-dropzone rl-file-dropzone--fill"
                      :class="{ 'rl-file-dropzone--active': uploadDragActive }"
                      @dragenter="handleUploadDragEnter"
                      @dragover="handleUploadDragOver"
                      @dragleave="handleUploadDragLeave"
                      @drop="handleUploadDrop"
                    >
                      <input
                        ref="uploadInputRef"
                        class="rl-file-input-native"
                        type="file"
                        :accept="uploadAccept"
                        @change="handleUploadFileChange"
                      />
                      <div class="rl-file-dropzone__content rl-file-dropzone__content--fill">
                        <div class="rl-file-dropzone__copy">
                          <strong>{{ uploadForm.file?.name ?? '拖动文件到这里，或点击按钮选择文件' }}</strong>
                          <span>{{ uploadAccept || '支持 JSON / JSONL / CSV / 图像输入' }}</span>
                        </div>
                        <a-button size="small" @click="openUploadPicker">选择文件</a-button>
                      </div>
                    </div>
                  </div>
                </div>
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
                  <div class="workspace-scroll-list workspace-scroll-list--run-list workspace-scroll-list--fill">
                    <button
                      v-for="run in runs"
                      :key="run.run_id"
                      type="button"
                      class="workspace-basic-list-item workspace-basic-list-item--run"
                      :class="{ 'workspace-basic-list-item--active': run.run_id === activeRun?.run_id }"
                      :title="`${run.run_id} · ${formatDateTime(run.created_at)}`"
                      @click="loadRun(run.run_id)"
                    >
                      <strong class="workspace-basic-list-item__primary">{{ run.label }}</strong>
                      <div class="workspace-basic-list-item__meta workspace-basic-list-item__meta--run">
                        <span>{{ run.run_id }}</span>
                        <span>{{ getRunPhaseLabel(run) }}</span>
                        <span>{{ formatRunStatus(run.status) }}</span>
                        <span>{{ run.case_count }} case</span>
                      </div>
                    </button>
                    <a-empty v-if="!runs.length && !loading">暂无运行记录</a-empty>
                  </div>
                </div>
                <div class="rl-form-actions workspace-run-list-panel__actions">
                  <template v-if="isReplaySessionActive">
                    <span class="workspace-subtle">当前正在浏览回放会话；切回“实时上传”后恢复当前实时/演示数据视图。</span>
                    <a-button size="small" status="warning" @click="handleSwitchToLiveUpload">退出回放</a-button>
                  </template>
                  <template v-else>
                    <span v-if="isMockMode" class="workspace-subtle">mock 模式固定为 1 个论文演示 run</span>
                    <a-button type="primary" :loading="uploadLoading" :disabled="isMockMode" @click="handleUpload">
                      <template #icon>
                        <icon-upload />
                      </template>
                      {{ isMockMode ? '切到 Backend 后可上传' : '上传并生成 Run' }}
                    </a-button>
                  </template>
                </div>
              </section>
            </div>
          </article>

          <article class="rl-section-card workspace-root-cause-card workspace-root-cause-card--evidence">
            <header class="rl-section-card__header">
              <div>
                <h3 class="rl-section-card__title">
                  <SectionCardTitle title="根因列表" :help="rootCauseListHelp">
                    <icon-bulb />
                  </SectionCardTitle>
                </h3>
              </div>
              <div class="rl-inline-tags">
                <a-tag color="arcoblue">{{ activeCase?.case_label ?? activeCase?.case_id ?? '--' }}</a-tag>
                <a-tag color="gold">{{ activeRootCauseList.length }} 条</a-tag>
              </div>
            </header>
            <div class="rl-section-card__body workspace-root-cause-card__body workspace-root-cause-card__body--plain">
              <div class="workspace-scroll-list workspace-scroll-list--fill">
                <button
                  v-for="candidate in activeRootCauseList"
                  :key="candidate.ranking_id"
                  type="button"
                  class="workspace-basic-list-item workspace-basic-list-item--root-cause"
                  :class="{ 'workspace-basic-list-item--active': candidate.ranking_id === activeCandidate?.ranking_id }"
                  @click="selectCandidate(candidate.ranking_id)"
                >
                  <span class="workspace-basic-list-item__primary">#{{ candidate.rank }} {{ candidate.candidate_name }}</span>
                  <span>{{ formatScore(candidate.score) }}</span>
                  <span>{{ formatScoringMethodLabel(candidate.scoring_method) }}</span>
                  <span>{{ normalizeText(candidate.candidate_role, 'candidate') }}</span>
                </button>
                <a-empty v-if="!activeRootCauseList.length">当前 Case 没有候选根因</a-empty>
              </div>
            </div>
          </article>
        </div>

        <aside class="workspace-evidence-aside">
          <article class="rl-section-card workspace-evidence-card">
            <header class="rl-section-card__header">
              <div>
                <h3 class="rl-section-card__title">
                  <SectionCardTitle
                    title="Case / Evidence 列表"
                    :help="caseEvidenceListHelp"
                  >
                    <icon-relation />
                  </SectionCardTitle>
                </h3>
              </div>
              <a-tag color="green">{{ filteredCaseEvidenceEntries.length }}</a-tag>
            </header>
            <div class="rl-section-card__body workspace-evidence-card__body">
              <div class="workspace-inline-filters workspace-inline-filters--two-col">
                <div class="rl-form-field">
                  <span class="workspace-field-label">
                    <icon-relation />
                    <span>图谱</span>
                  </span>
                  <a-select v-model="evidenceFilter.graph">
                    <a-option value="all">全部图谱</a-option>
                    <a-option v-for="graphId in graphOptions" :key="graphId" :value="graphId">
                      {{ graphId }}
                    </a-option>
                  </a-select>
                </div>
                <div class="rl-form-field">
                  <span class="workspace-field-label">
                    <icon-bulb />
                    <span>Modality</span>
                  </span>
                  <a-select v-model="evidenceFilter.modality">
                    <a-option value="all">全部</a-option>
                    <a-option v-for="modality in observationModalityOptions" :key="modality" :value="modality">
                      {{ formatObservationModalityLabel(modality) }}
                    </a-option>
                  </a-select>
                </div>
                <div class="rl-form-field">
                  <span class="workspace-field-label">
                    <icon-storage />
                    <span>Source</span>
                  </span>
                  <a-select v-model="evidenceFilter.source">
                    <a-option value="all">全部来源</a-option>
                    <a-option v-for="source in observationSourceOptions" :key="source" :value="source">
                      {{ source }}
                    </a-option>
                  </a-select>
                </div>
                <div class="rl-form-field">
                  <span class="workspace-field-label">
                    <icon-info-circle />
                    <span>Confidence</span>
                  </span>
                  <a-select v-model="evidenceFilter.confidenceBand">
                    <a-option value="all">全部</a-option>
                    <a-option value="high">高</a-option>
                    <a-option value="medium">中</a-option>
                    <a-option value="low">低</a-option>
                  </a-select>
                </div>
                <div class="rl-form-field workspace-inline-filters__wide">
                  <span class="workspace-field-label">
                    <icon-storage />
                    <span>时间范围</span>
                  </span>
                  <div class="workspace-form-row workspace-form-row--two">
                    <a-input v-model="evidenceFilter.timeFrom" type="datetime-local" placeholder="开始时间" />
                    <a-input v-model="evidenceFilter.timeTo" type="datetime-local" placeholder="结束时间" />
                  </div>
                </div>
                <div class="rl-form-field workspace-inline-filters__wide">
                  <span class="workspace-field-label">
                    <icon-info-circle />
                    <span>关键字</span>
                  </span>
                  <a-input v-model="evidenceFilter.keyword" placeholder="搜索 obs / source / hint / ref / variable / event" />
                </div>
              </div>

              <div class="workspace-scroll-list workspace-scroll-list--fill">
                <div
                  v-for="item in filteredCaseEvidenceEntries"
                  :key="item.key"
                  role="button"
                  tabindex="0"
                  class="workspace-basic-list-item workspace-basic-list-item--case-evidence"
                  :class="{ 'workspace-basic-list-item--active': item.caseId === activeCase?.case_id }"
                  @click="setSelectedCase(item.caseId)"
                  @keydown.enter.prevent="setSelectedCase(item.caseId)"
                >
                  <strong class="workspace-basic-list-item__primary">{{ item.caseLabel }}</strong>
                  <span>{{ item.dataset }}</span>
                  <a-tooltip position="left">
                    <span class="workspace-basic-list-item__tooltip-anchor">
                      {{ item.evidenceSummary }}
                    </span>
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
                  <span>{{ item.topCandidate }}</span>
                  <span>{{ item.reviewStatus }}</span>
                  <a-button size="mini" type="text" @click.stop="openGraphExplore(item.caseId)">
                    <template #icon>
                      <icon-launch />
                    </template>
                    图谱探索
                  </a-button>
                </div>
                <a-empty v-if="!filteredCaseEvidenceEntries.length">没有匹配的 Case / Evidence 条目</a-empty>
              </div>
            </div>
          </article>

          <article class="rl-section-card workspace-root-cause-summary-card workspace-observation-card">
            <header class="rl-section-card__header">
              <div>
                <h3 class="rl-section-card__title">
                  <SectionCardTitle
                    title="Observation Drilldown"
                    :help="observationDrilldownHelp"
                  >
                    <icon-info-circle />
                  </SectionCardTitle>
                </h3>
              </div>
              <div class="rl-inline-tags">
                <a-tag color="arcoblue">{{ activeCase?.case_label ?? activeCase?.case_id ?? '--' }}</a-tag>
                <a-tag color="gold">{{ activeObservationDetailCount }}</a-tag>
              </div>
            </header>
            <div class="rl-section-card__body workspace-observation-card__body">
              <div class="workspace-summary-list workspace-summary-list--two-col">
                <div class="workspace-summary-list__item">
                  <span class="workspace-summary-label">
                    <icon-relation />
                    <span>Current Case</span>
                  </span>
                  <strong>{{ activeCase?.case_label ?? activeCase?.case_id ?? '--' }}</strong>
                </div>
                <div class="workspace-summary-list__item">
                  <span class="workspace-summary-label">
                    <icon-bulb />
                    <span>Selected Obs</span>
                  </span>
                  <strong>{{ activeObservation?.id ?? '--' }}</strong>
                </div>
              </div>

              <div class="workspace-scroll-list workspace-scroll-list--fill workspace-scroll-list--observation">
                <button
                  v-for="item in filteredActiveObservationItems"
                  :key="item.id"
                  type="button"
                  class="workspace-basic-list-item workspace-basic-list-item--observation"
                  :class="{ 'workspace-basic-list-item--active': item.id === selectedObservationId }"
                  @click="setSelectedObservation(item.id)"
                >
                  <div class="workspace-basic-list-item__head">
                    <strong>{{ item.title }}</strong>
                    <span>{{ formatScore(item.confidence) }}</span>
                  </div>
                  <div class="workspace-basic-list-item__meta">
                    <span>{{ formatObservationModalityLabel(item.modality) }}</span>
                    <span>{{ item.source }}</span>
                    <span>{{ item.timeLabel }}</span>
                  </div>
                  <div class="workspace-basic-list-item__meta workspace-basic-list-item__meta--observation">
                    <span>{{ item.linkedEntityCount }} linked</span>
                    <span>{{ item.rawRefCount }} refs</span>
                    <a-button size="mini" type="text" @click.stop="openObservationDetail(item.id)">详情</a-button>
                  </div>
                </button>
                <a-empty v-if="!filteredActiveObservationItems.length">当前 Case 没有匹配的 observation</a-empty>
              </div>

              <div class="rl-form-actions rl-form-actions--dual">
                <a-button size="small" :disabled="!activeObservation" @click="openObservationDetail(activeObservation?.id ?? null)">查看详情</a-button>
                <a-button size="small" :disabled="!activeObservation || !activeCase" @click="activeCase?.case_id && openGraphExplore(activeCase.case_id, activeObservation?.id ?? null)">图谱探索</a-button>
              </div>
            </div>
          </article>
        </aside>
      </div>
    </section>
  </div>

  <a-modal
    v-model:visible="replayModalVisible"
    title="导入回放资产"
    :footer="false"
    :mask-closable="!replayImportLoading"
    :esc-to-close="!replayImportLoading"
    class="workspace-replay-modal"
  >
    <div class="workspace-stack workspace-stack--tight">
      <div class="workspace-replay-import-field">
        <div>
          <strong>rootlens-runtime.json</strong>
          <span>可选；用于恢复 case、evidence 与 RCA 运行时。</span>
        </div>
        <input ref="replayRuntimeInputRef" class="rl-file-input-native" type="file" accept=".json" @change="handleReplayFileChange('runtimeFile', $event)" />
        <a-button size="small" @click="openReplayFilePicker('runtimeFile')">{{ replayImportForm.runtimeFile?.name ?? '选择文件' }}</a-button>
      </div>

      <div class="workspace-replay-import-field">
        <div>
          <strong>unified-graphs.json</strong>
          <span>可选；用于恢复图谱探索工作台。</span>
        </div>
        <input ref="replayGraphsInputRef" class="rl-file-input-native" type="file" accept=".json" @change="handleReplayFileChange('graphsFile', $event)" />
        <a-button size="small" @click="openReplayFilePicker('graphsFile')">{{ replayImportForm.graphsFile?.name ?? '选择文件' }}</a-button>
      </div>

      <div class="workspace-replay-import-field">
        <div>
          <strong>workspace export / session bundle</strong>
          <span>可选；支持恢复 analyst workspace，或单独导入完整 bundle。</span>
        </div>
        <input ref="replayWorkspaceInputRef" class="rl-file-input-native" type="file" accept=".json" @change="handleReplayFileChange('workspaceFile', $event)" />
        <a-button size="small" @click="openReplayFilePicker('workspaceFile')">{{ replayImportForm.workspaceFile?.name ?? '选择文件' }}</a-button>
      </div>

      <a-alert
        type="info"
        :show-icon="false"
        title="若同时导入 runtime/graphs 与 workspace export，会先恢复回放资产，再叠加 workspace；完整 session bundle 请单独导入。"
      />

      <div class="rl-form-actions rl-form-actions--dual">
        <a-button type="primary" :loading="replayImportLoading" @click="handleReplayImport">导入并切换到回放</a-button>
        <a-button :disabled="replayImportLoading" @click="replayModalVisible = false">取消</a-button>
      </div>
    </div>
  </a-modal>

  <a-modal
    v-model:visible="observationDetailModalVisible"
    title="Observation 详情"
    :footer="false"
    width="880px"
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

      <template v-if="activeObservation.modality === 'image'">
        <div class="workspace-summary-list workspace-summary-list--two-col">
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label"><icon-storage /><span>Object</span></span>
            <strong>{{ readObservationTextField(activeObservation, 'object') }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label"><icon-info-circle /><span>Anomaly</span></span>
            <strong>{{ readObservationTextField(activeObservation, 'anomaly_type') }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label"><icon-relation /><span>Location</span></span>
            <strong>{{ readObservationTextField(activeObservation, 'location') }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label"><icon-bulb /><span>Severity</span></span>
            <strong>{{ readObservationNumberField(activeObservation, 'severity') }}</strong>
          </div>
        </div>
        <div v-if="selectedObservationVisualEvidence.length" class="workspace-observation-visual-grid">
          <div v-for="item in selectedObservationVisualEvidence" :key="item.artifact_id" class="rl-visual-card">
            <img v-if="item.preview_path || item.url" :src="item.preview_path || item.url || undefined" :alt="item.title" />
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
            <span class="workspace-summary-label"><icon-storage /><span>Variable</span></span>
            <strong>{{ readObservationTextField(activeObservation, 'variable_name') }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label"><icon-info-circle /><span>Direction</span></span>
            <strong>{{ readObservationTextField(activeObservation, 'direction') }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label"><icon-bulb /><span>Contribution</span></span>
            <strong>{{ readObservationNumberField(activeObservation, 'contribution') }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label"><icon-relation /><span>Time Window</span></span>
            <strong>{{ activeObservation.timeLabel }}</strong>
          </div>
        </div>
      </template>

      <template v-else-if="activeObservation.modality === 'log'">
        <div class="workspace-summary-list workspace-summary-list--two-col">
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label"><icon-storage /><span>Event Code</span></span>
            <strong>{{ readObservationTextField(activeObservation, 'event_code') }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label"><icon-info-circle /><span>Event Type</span></span>
            <strong>{{ readObservationTextField(activeObservation, 'event_type') }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label"><icon-relation /><span>Equipment</span></span>
            <strong>{{ readObservationTextField(activeObservation, 'equipment') }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span class="workspace-summary-label"><icon-bulb /><span>Time</span></span>
            <strong>{{ activeObservation.timeLabel }}</strong>
          </div>
        </div>
        <div class="workspace-claim-note workspace-claim-note--compact">
          <span class="workspace-summary-label"><icon-info-circle /><span>Message</span></span>
          <strong>{{ readObservationTextField(activeObservation, 'message') }}</strong>
        </div>
      </template>

      <div class="workspace-claim-note workspace-claim-note--compact">
        <span class="workspace-summary-label"><icon-bulb /><span>Linked entity hints</span></span>
        <strong>{{ activeObservation.linkedEntityHints.length ? activeObservation.linkedEntityHints.join(', ') : '—' }}</strong>
      </div>

      <div v-if="activeObservation.rawEvidenceRefs.length" class="workspace-observation-ref-list">
        <div v-for="refItem in activeObservation.rawEvidenceRefs" :key="refItem.refId" class="workspace-observation-ref">
          <strong>{{ refItem.label }}</strong>
          <span>{{ refItem.role }}</span>
          <span>{{ refItem.filePath }}</span>
        </div>
      </div>
      <a-empty v-else>当前 observation 没有 raw refs</a-empty>

      <div class="rl-form-actions rl-form-actions--dual">
        <a-button type="primary" @click="activeCase?.case_id && openGraphExplore(activeCase.case_id, activeObservation.id)">图谱探索</a-button>
        <a-button @click="observationDetailModalVisible = false">关闭</a-button>
      </div>
    </div>
    <a-empty v-else>当前没有选中的 observation</a-empty>
  </a-modal>
</template>