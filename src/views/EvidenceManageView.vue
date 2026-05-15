<script setup lang="ts">
import { IconLaunch, IconRefresh, IconUpload } from '@arco-design/web-vue/es/icon'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import type { DashboardBootstrap, RunCaseDetail, RunDetail, RunSummary, UploadMode } from '@/api/contracts'
import HoverInfoDock from '@/components/layout/HoverInfoDock.vue'
import WorkbenchHero from '@/components/layout/WorkbenchHero.vue'
import { useAppPreferences } from '@/services/app-preferences'
import { getRootLensService } from '@/services/rootlens-service'
import { useWorkbenchState } from '@/services/workbench-state'

interface EvidenceRow {
  key: string
  runId: string
  caseId: string
  caseLabel: string
  graphDatasetId: string
  facet: string
  title: string
  hint: string
  confidence: number | null
  rawRefCount: number
  observation: Record<string, unknown>
}

const router = useRouter()
const { preferences } = useAppPreferences()
const { state: workbenchState, updateState } = useWorkbenchState()

const loading = ref(false)
const uploadLoading = ref(false)
const bootstrap = ref<DashboardBootstrap | null>(null)
const runs = ref<RunSummary[]>([])
const runDetail = ref<RunDetail | null>(null)
const errorMessage = ref('')
const uploadMessage = ref('')
const selectedObservationKey = ref<string | null>(null)

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

const evidenceRows = computed<EvidenceRow[]>(() => {
  const currentRunId = activeRun.value?.run_id ?? selectedRunId.value ?? 'run'
  return (runDetail.value?.cases ?? []).flatMap((caseItem) => buildEvidenceRows(currentRunId, caseItem))
})

const filteredEvidenceRows = computed(() => {
  const keyword = evidenceFilter.keyword.trim().toLowerCase()

  return evidenceRows.value.filter((item) => {
    if (evidenceFilter.graph !== 'all' && item.graphDatasetId !== evidenceFilter.graph) {
      return false
    }

    if (evidenceFilter.facet !== 'all' && item.facet !== evidenceFilter.facet) {
      return false
    }

    if (!keyword) {
      return true
    }

    return [item.caseLabel, item.title, item.hint, item.facet]
      .join(' ')
      .toLowerCase()
      .includes(keyword)
  })
})

const selectedObservation = computed(() => {
  return filteredEvidenceRows.value.find((item) => item.key === selectedObservationKey.value) ?? filteredEvidenceRows.value[0] ?? null
})

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
    label: 'Evidence 数',
    value: filteredEvidenceRows.value.length,
    hint: '按当前筛选可见的 observation',
    tone: 'amber' as const,
  },
])

const workspaceTags = computed(() => [
  {
    label: preferences.value.dataSourceMode === 'backend' ? '后端模式' : '模拟模式',
    color: 'arcoblue' as const,
  },
  {
    label: activeRun.value?.dataset ?? '未选择运行',
    color: 'green' as const,
  },
  {
    label: activeCase.value?.case_label ?? activeCase.value?.case_id ?? '未选择案例',
    color: 'gold' as const,
  },
])

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

function getRunProgress(run: RunSummary) {
  if (runDetail.value?.run.run_id === run.run_id) {
    const steps = runDetail.value.workflow_steps.length
    const completed = runDetail.value.workflow_steps.filter((step) => step.status === 'completed').length
    if (steps > 0) {
      return Math.round((completed / steps) * 100)
    }
  }

  return run.status === 'completed' ? 100 : 0
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

function getCaseEvidenceCount(caseItem: RunCaseDetail) {
  const evidence = toRecord(caseItem.generated_evidence)
  const observations = Array.isArray(evidence?.observations) ? evidence?.observations : []
  return observations.length
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

function buildEvidenceRows(runId: string, caseItem: RunCaseDetail): EvidenceRow[] {
  const evidence = toRecord(caseItem.generated_evidence)
  const observations = Array.isArray(evidence?.observations) ? evidence?.observations : []
  const graphDatasetId = getCaseGraphDatasetId(caseItem)
  const caseLabel = caseItem.case_label ?? caseItem.case_id

  return observations
    .map((item, index) => {
      const observation = toRecord(item)
      if (!observation) {
        return null
      }

      const facet = normalizeText(observation.facet, 'unknown')
      const linkedHints = Array.isArray(observation.linked_entity_hints)
        ? observation.linked_entity_hints.map((hint) => String(hint))
        : []
      const rawRefs = Array.isArray(observation.raw_evidence_refs) ? observation.raw_evidence_refs : []

      return {
        key: `${caseItem.case_id}:${normalizeText(observation.obs_id, String(index))}`,
        runId,
        caseId: caseItem.case_id,
        caseLabel,
        graphDatasetId,
        facet,
        title: buildObservationTitle(observation, facet),
        hint: linkedHints[0] ?? '--',
        confidence: typeof observation.confidence === 'number' ? observation.confidence : null,
        rawRefCount: rawRefs.length,
        observation,
      }
    })
    .filter((item): item is EvidenceRow => item !== null)
}

function formatConfidence(value: number | null) {
  return typeof value === 'number' ? value.toFixed(2) : '--'
}

function handleUploadFileChange(event: Event) {
  const input = event.target as HTMLInputElement | null
  uploadForm.file = input?.files?.[0] ?? null
}

function setSelectedRun(runId: string) {
  updateState({
    selectedRunId: runId,
    selectedCaseId: null,
    selectedCandidateId: null,
    selectedPathId: null,
    selectedReviewTargetKey: null,
  })
}

function setSelectedCase(caseId: string | null) {
  updateState({
    selectedCaseId: caseId,
    selectedCandidateId: null,
    selectedPathId: null,
    selectedReviewTargetKey: null,
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
  })

  void router.push({
    name: 'graphs',
    query: {
      run_id: runId,
      case_id: caseId,
    },
  })
}

watch(filteredEvidenceRows, (rows) => {
  if (!rows.length) {
    selectedObservationKey.value = null
    return
  }

  if (!rows.some((item) => item.key === selectedObservationKey.value)) {
    selectedObservationKey.value = rows[0].key
  }
})

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
      <template #badges>
        <a-tag v-for="tag in workspaceTags" :key="tag.label" size="small" :color="tag.color">
          {{ tag.label }}
        </a-tag>
      </template>
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

    <section class="workspace-shell">
      <div class="workspace-shell__main">
        <article class="rl-section-card">
          <header class="rl-section-card__header">
            <div>
              <h3 class="rl-section-card__title">上传与运行状态</h3>
              <p class="rl-section-card__desc">左侧提交 record，右侧只看后端阶段、进度和运行状态。</p>
            </div>
            <a-tag color="green">{{ formatUploadModeLabel(uploadForm.mode) }}</a-tag>
          </header>
          <div class="rl-section-card__body workspace-split-card workspace-split-card--run-status">
            <section class="workspace-stack">
              <div class="workspace-form-row workspace-form-row--three">
                <div class="rl-form-field">
                  <span>模式</span>
                  <a-select v-model="uploadForm.mode">
                    <a-option v-for="item in bootstrap?.upload_modes ?? []" :key="item.mode" :value="item.mode">
                      {{ formatUploadModeLabel(item.mode) }}
                    </a-option>
                  </a-select>
                </div>
                <div class="rl-form-field">
                  <span>数据集</span>
                  <a-select v-model="uploadForm.dataset" allow-clear>
                    <a-option value="">自动</a-option>
                    <a-option v-for="dataset in bootstrap?.supported_datasets ?? []" :key="dataset" :value="dataset">
                      {{ dataset }}
                    </a-option>
                  </a-select>
                </div>
                <div class="rl-form-field">
                  <span>候选数</span>
                  <a-input-number v-model="uploadForm.topK" :min="1" :max="20" />
                </div>
              </div>

              <div v-if="uploadForm.mode === 'image'" class="workspace-form-row workspace-form-row--three">
                <div class="rl-form-field">
                  <span>对象</span>
                  <a-input v-model="uploadForm.objectName" placeholder="例如 bottle" />
                </div>
                <div class="rl-form-field">
                  <span>缺陷类型</span>
                  <a-input v-model="uploadForm.defectType" placeholder="例如 scratch" />
                </div>
                <div class="rl-form-field">
                  <span>预设</span>
                  <a-input v-model="uploadForm.modelPreset" placeholder="auto" />
                </div>
              </div>

              <div class="rl-form-field">
                <span>文件</span>
                <input type="file" @change="handleUploadFileChange" />
              </div>

              <div class="rl-form-actions">
                <a-button type="primary" :loading="uploadLoading" @click="handleUpload">
                  <template #icon>
                    <icon-upload />
                  </template>
                  上传并生成 Run
                </a-button>
              </div>
            </section>

            <section class="workspace-stack">
              <button
                v-for="run in runs"
                :key="run.run_id"
                type="button"
                class="workspace-status-item"
                :class="{ 'workspace-status-item--active': run.run_id === activeRun?.run_id }"
                @click="loadRun(run.run_id)"
              >
                <div class="workspace-status-item__head">
                  <strong>{{ run.label }}</strong>
                  <span>{{ formatRunStatus(run.status) }}</span>
                </div>
                <div class="workspace-status-item__subhead">
                  <span>{{ run.run_id }}</span>
                  <span>{{ getRunPhaseLabel(run) }}</span>
                </div>
                <div class="workspace-progress">
                  <div class="workspace-progress__bar" :style="{ width: `${getRunProgress(run)}%` }" />
                </div>
                <div class="workspace-status-item__meta">
                  <span>{{ run.case_count }} 个 case</span>
                  <span>{{ formatDateTime(run.created_at) }}</span>
                </div>
              </button>
              <a-empty v-if="!runs.length && !loading">暂无运行记录</a-empty>
            </section>
          </div>
        </article>

        <article class="rl-section-card">
          <header class="rl-section-card__header">
            <div>
              <h3 class="rl-section-card__title">当前 Run 下的 Case 审阅表</h3>
              <p class="rl-section-card__desc">选定 case 后可直接跳转到图谱探索。</p>
            </div>
            <div class="rl-inline-tags">
              <a-tag color="arcoblue">{{ activeRun?.run_id ?? '--' }}</a-tag>
              <a-tag color="gold">{{ runDetail?.cases.length ?? 0 }} 个案例</a-tag>
            </div>
          </header>
          <div class="rl-section-card__body workspace-table-card">
            <div class="workspace-table-wrap">
              <table class="workspace-table">
                <thead>
                  <tr>
                    <th>Case</th>
                    <th>Dataset</th>
                    <th>Evidence</th>
                    <th>Top1 根因</th>
                    <th>路径数</th>
                    <th>反馈状态</th>
                    <th>操作</th>
                  </tr>
                </thead>
                <tbody>
                  <tr
                    v-for="caseItem in runDetail?.cases ?? []"
                    :key="caseItem.case_id"
                    :class="{ 'workspace-table__row--active': caseItem.case_id === activeCase?.case_id }"
                    @click="setSelectedCase(caseItem.case_id)"
                  >
                    <td>
                      <strong>{{ caseItem.case_label ?? caseItem.case_id }}</strong>
                    </td>
                    <td>{{ caseItem.dataset ?? '--' }}</td>
                    <td>{{ getCaseEvidenceCount(caseItem) }}</td>
                    <td>{{ getCaseTopCandidate(caseItem) }}</td>
                    <td>{{ caseItem.path_graph?.path_count ?? 0 }}</td>
                    <td>{{ getCaseReviewStatus(caseItem) }}</td>
                    <td>
                      <a-button size="mini" type="text" @click.stop="openGraphExplore(caseItem.case_id)">
                        <template #icon>
                          <icon-launch />
                        </template>
                        图谱探索
                      </a-button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <a-empty v-if="!(runDetail?.cases.length)">当前没有 case</a-empty>
          </div>
        </article>
      </div>

      <aside class="workspace-shell__aside">
        <article class="rl-section-card">
          <header class="rl-section-card__header">
            <div>
              <h3 class="rl-section-card__title">Evidence 筛选</h3>
              <p class="rl-section-card__desc">基于图谱、run、facet 和关键字快速过滤。</p>
            </div>
          </header>
          <div class="rl-section-card__body workspace-stack">
            <div class="rl-form-field">
              <span>图谱</span>
              <a-select v-model="evidenceFilter.graph">
                <a-option value="all">全部图谱</a-option>
                <a-option v-for="graphId in graphOptions" :key="graphId" :value="graphId">
                  {{ graphId }}
                </a-option>
              </a-select>
            </div>
            <div class="rl-form-field">
              <span>Run</span>
              <a-input :model-value="activeRun?.run_id ?? '--'" disabled />
            </div>
            <div class="rl-form-field">
              <span>Facet</span>
              <a-select v-model="evidenceFilter.facet">
                <a-option value="all">全部</a-option>
                <a-option value="variable">variable</a-option>
                <a-option value="image_defect">image_defect</a-option>
                <a-option value="log_event">log_event</a-option>
              </a-select>
            </div>
            <div class="rl-form-field">
              <span>关键字</span>
              <a-input v-model="evidenceFilter.keyword" placeholder="搜索 observation / hint" />
            </div>
          </div>
        </article>

        <article class="rl-section-card">
          <header class="rl-section-card__header">
            <div>
              <h3 class="rl-section-card__title">Evidence 列表</h3>
              <p class="rl-section-card__desc">当前 run 内按筛选条件可见的 observation。</p>
            </div>
            <a-tag color="green">{{ filteredEvidenceRows.length }}</a-tag>
          </header>
          <div class="rl-section-card__body workspace-stack workspace-stack--tight">
            <button
              v-for="item in filteredEvidenceRows"
              :key="item.key"
              type="button"
              class="workspace-list-item"
              :class="{ 'workspace-list-item--active': item.key === selectedObservation?.key }"
              @click="selectedObservationKey = item.key"
            >
              <div class="workspace-list-item__head">
                <strong>{{ item.title }}</strong>
                <span>{{ item.facet }}</span>
              </div>
              <div class="workspace-list-item__meta">
                <span>{{ item.caseLabel }}</span>
                <span>conf {{ formatConfidence(item.confidence) }}</span>
              </div>
            </button>
            <a-empty v-if="!filteredEvidenceRows.length">没有匹配的 evidence</a-empty>
          </div>
        </article>

        <article class="rl-section-card">
          <header class="rl-section-card__header">
            <div>
              <h3 class="rl-section-card__title">当前 Evidence 摘要</h3>
              <p class="rl-section-card__desc">展示 linked hints、raw refs 和所属上下文。</p>
            </div>
          </header>
          <div class="rl-section-card__body rl-kv-grid">
            <div>
              <span>Case</span>
              <strong>{{ selectedObservation?.caseLabel ?? '--' }}</strong>
            </div>
            <div>
              <span>Facet</span>
              <strong>{{ selectedObservation?.facet ?? '--' }}</strong>
            </div>
            <div>
              <span>图谱</span>
              <strong>{{ selectedObservation?.graphDatasetId ?? '--' }}</strong>
            </div>
            <div>
              <span>Raw Refs</span>
              <strong>{{ selectedObservation?.rawRefCount ?? 0 }}</strong>
            </div>
            <div>
              <span>Hint</span>
              <strong>{{ selectedObservation?.hint ?? '--' }}</strong>
            </div>
            <div>
              <span>置信度</span>
              <strong>{{ formatConfidence(selectedObservation?.confidence ?? null) }}</strong>
            </div>
          </div>
        </article>
      </aside>

      <HoverInfoDock title="证据提示" label="EVID" subtitle="额外挂件，用于放说明、统计和告警。">
        <div class="workspace-summary-list">
          <div class="workspace-summary-list__item">
            <span>当前图谱</span>
            <strong>{{ evidenceFilter.graph === 'all' ? '全部图谱' : evidenceFilter.graph }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span>当前 Run</span>
            <strong>{{ activeRun?.run_id ?? '--' }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span>Observation 总量</span>
            <strong>{{ evidenceRows.length }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span>筛选后可见</span>
            <strong>{{ filteredEvidenceRows.length }}</strong>
          </div>
        </div>
      </HoverInfoDock>
    </section>
  </div>
</template>
