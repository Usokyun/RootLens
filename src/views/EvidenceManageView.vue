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
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import type {
  DashboardBootstrap,
  RankedRootCause,
  RunCaseDetail,
  RunDetail,
  RunSummary,
  UploadMode,
} from '@/api/contracts'
import WorkbenchHero from '@/components/layout/WorkbenchHero.vue'
import { useAppPreferences } from '@/services/app-preferences'
import { getRootLensService } from '@/services/rootlens-service'
import { formatScoringMethodLabel } from '@/services/ui-copy'
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
  graph: 'all',
  facet: 'all',
  keyword: '',
})

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

const uploadAccept = computed(() => {
  const modeConfig = bootstrap.value?.upload_modes.find((item) => item.mode === uploadForm.mode)
  return modeConfig?.accepted_extensions.join(',') ?? ''
})

const caseEvidenceEntries = computed<CaseEvidenceEntry[]>(() => {
  return (runDetail.value?.cases ?? []).map((caseItem) => buildCaseEvidenceEntry(caseItem))
})

const filteredCaseEvidenceEntries = computed(() => {
  const keyword = evidenceFilter.keyword.trim().toLowerCase()

  return caseEvidenceEntries.value.filter((item) => {
    if (evidenceFilter.graph !== 'all' && item.graphDatasetId !== evidenceFilter.graph) {
      return false
    }

    if (evidenceFilter.facet !== 'all' && !item.facetKeys.includes(evidenceFilter.facet)) {
      return false
    }

    if (!keyword) {
      return true
    }

    return item.searchableText.includes(keyword)
  })
})

const totalObservationCount = computed(() => {
  return caseEvidenceEntries.value.reduce((total, item) => total + item.observationCount, 0)
})

const activeCaseEvidenceEntry = computed(() => {
  if (!activeCase.value) {
    return null
  }

  return caseEvidenceEntries.value.find((item) => item.caseId === activeCase.value?.case_id) ?? null
})

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

function getSupportingEvidenceCount(candidate: RankedRootCause | null) {
  return Array.isArray(candidate?.supporting_evidence) ? candidate.supporting_evidence.length : 0
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

function setSelectedRun(runId: string) {
  updateState({
    selectedRunId: runId,
    selectedCaseId: null,
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

function openGraphExplore(caseId: string) {
  const runId = activeRun.value?.run_id ?? selectedRunId.value
  if (!runId) {
    return
  }

  updateState({
    selectedRunId: runId,
    selectedCaseId: caseId,
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

onMounted(() => {
  void refreshWorkspace()
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
                <h3 class="rl-section-card__title workspace-title-with-icon">
                  <icon-upload />
                  <span>上传与运行状态</span>
                </h3>
                <p class="rl-section-card__desc">
                  {{
                    isMockMode
                      ? '当前为论文演示 mock 模式：左侧仅保留预设 case 说明，右侧固定展示唯一 demo run。'
                      : '左侧提交 record，右侧用紧凑列表切换当前 Run。'
                  }}
                </p>
              </div>
              <a-tag :color="isMockMode ? 'gold' : 'green'">
                {{ isMockMode ? '论文演示模式' : formatUploadModeLabel(uploadForm.mode) }}
              </a-tag>
            </header>
            <div class="rl-section-card__body workspace-split-card workspace-split-card--run-status workspace-run-card__body">
              <section v-if="isMockMode" class="workspace-stack workspace-stack--fill workspace-upload-form-stack">
                <div class="rl-section-card workspace-demo-mode-card">
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
              </section>

              <section v-else class="workspace-stack workspace-stack--fill workspace-upload-form-stack">
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
                  <span v-if="isMockMode" class="workspace-subtle">mock 模式固定为 1 个论文演示 run</span>
                  <a-button type="primary" :loading="uploadLoading" :disabled="isMockMode" @click="handleUpload">
                    <template #icon>
                      <icon-upload />
                    </template>
                    {{ isMockMode ? '切到 Backend 后可上传' : '上传并生成 Run' }}
                  </a-button>
                </div>
              </section>
            </div>
          </article>

          <article class="rl-section-card workspace-root-cause-card workspace-root-cause-card--evidence">
            <header class="rl-section-card__header">
              <div>
                <h3 class="rl-section-card__title workspace-title-with-icon">
                  <icon-bulb />
                  <span>根因列表</span>
                </h3>
                <p class="rl-section-card__desc">跟随当前 Case 切换候选根因，点击后同步当前选择。</p>
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
                <h3 class="rl-section-card__title workspace-title-with-icon">
                  <icon-relation />
                  <span>Case / Evidence 列表</span>
                </h3>
                <p class="rl-section-card__desc">一行一个 Case 入口，hover 查看 evidence 明细，点击即可联动根因区。</p>
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
                    <icon-storage />
                    <span>Facet</span>
                  </span>
                  <a-select v-model="evidenceFilter.facet">
                    <a-option value="all">全部</a-option>
                    <a-option value="variable">variable</a-option>
                    <a-option value="image_defect">image_defect</a-option>
                    <a-option value="log_event">log_event</a-option>
                  </a-select>
                </div>
                <div class="rl-form-field workspace-inline-filters__wide">
                  <span class="workspace-field-label">
                    <icon-info-circle />
                    <span>关键字</span>
                  </span>
                  <a-input v-model="evidenceFilter.keyword" placeholder="搜索 case / evidence / hint / root cause" />
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

          <article class="rl-section-card workspace-root-cause-summary-card">
            <header class="rl-section-card__header">
              <div>
                <h3 class="rl-section-card__title workspace-title-with-icon">
                  <icon-info-circle />
                  <span>当前根因摘要</span>
                </h3>
                <p class="rl-section-card__desc">默认展示当前 Case 的已选候选；若未点选则展示 Top1。</p>
              </div>
            </header>
            <div class="rl-section-card__body rl-kv-grid workspace-root-cause-summary-card__body">
              <div>
                <span class="workspace-summary-label">
                  <icon-bulb />
                  <span>Candidate</span>
                </span>
                <strong>{{ activeCandidate?.candidate_name ?? '--' }}</strong>
              </div>
              <div>
                <span class="workspace-summary-label">
                  <icon-info-circle />
                  <span>Score</span>
                </span>
                <strong>{{ formatScore(activeCandidate?.score) }}</strong>
              </div>
              <div>
                <span class="workspace-summary-label">
                  <icon-storage />
                  <span>Method</span>
                </span>
                <strong>{{ formatScoringMethodLabel(activeCandidate?.scoring_method) }}</strong>
              </div>
              <div>
                <span class="workspace-summary-label">
                  <icon-relation />
                  <span>Role</span>
                </span>
                <strong>{{ normalizeText(activeCandidate?.candidate_role, 'candidate') }}</strong>
              </div>
              <div>
                <span class="workspace-summary-label">
                  <icon-upload />
                  <span>Supporting Evidence</span>
                </span>
                <strong>{{ getSupportingEvidenceCount(activeCandidate) }}</strong>
              </div>
              <div>
                <span class="workspace-summary-label">
                  <icon-info-circle />
                  <span>Case</span>
                </span>
                <strong>{{ activeCaseEvidenceEntry?.caseLabel ?? '--' }}</strong>
              </div>
            </div>
          </article>
        </aside>
      </div>
    </section>
  </div>
</template>
