<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { useRouter } from 'vue-router'

import SessionBlockerCard from '@/components/workflow/SessionBlockerCard.vue'
import {
  buildAnalysisWorkspaceScope,
  getAnalysisWorkspaceEventName,
  getCaseFeedbackEntries,
  hasDraftCase,
  loadAnalysisWorkspace,
  overlayWorkspaceCases,
  type AnalysisWorkspaceStorage,
} from '@/services/analysis-workspace'
import {
  buildCaseFocus,
  buildObservationFocus,
  getAnalysisFocusEventName,
  loadAnalysisFocus,
  saveAnalysisFocus,
  type AnalysisFocusState,
} from '@/services/analysis-focus'
import {
  getImportedSessionSummary,
  getLocalSessionEventName,
  getLocalSessionMeta,
  loadRootLensRuntime,
} from '@/services/rootlens-data'
import { buildWorkflowSnapshot } from '@/services/workflow'
import type {
  EvidenceObservation,
  ImageDefectObservation,
  LogEventObservation,
  ObservationFacet,
  RootLensRuntimeCase,
  VariableObservation,
} from '@/types/rootlens'

type FacetFilter = ObservationFacet | 'all'

const schemaVersion = ref('')
const cases = shallowRef<RootLensRuntimeCase[]>([])
const baseCases = shallowRef<RootLensRuntimeCase[]>([])
const activeCase = shallowRef<RootLensRuntimeCase | null>(null)
const workspaceState = shallowRef<AnalysisWorkspaceStorage | null>(null)
const focusState = shallowRef<AnalysisFocusState | null>(null)
const loading = ref(true)
const errorMessage = ref('')
const activeCaseId = ref('')
const facetFilter = ref<FacetFilter>('all')
const selectedObservationId = ref('')
const facetOptions: FacetFilter[] = ['all', 'variable', 'image_defect', 'log_event']
const sessionMeta = ref(getLocalSessionMeta())
const importSummary = ref(getImportedSessionSummary())
const router = useRouter()

const sessionLabel = computed(() =>
  sessionMeta.value?.source === 'import' ? '本地导入' : '内置示例',
)
const sessionSummary = computed(() => sessionMeta.value?.summary ?? '使用内置示例数据')
const analysisWorkspaceScope = computed(() => buildAnalysisWorkspaceScope(sessionMeta.value))
const workflow = computed(() => buildWorkflowSnapshot(sessionMeta.value, importSummary.value))
const canOpenGraphs = computed(() => workflow.value.hasGraphs)
const pageBlocker = computed(() => {
  if (workflow.value.hasCases) {
    return null
  }

  if (workflow.value.hasGraphs) {
    return {
      title: '当前会话只有图谱，没有 runtime case',
      description:
        'Evidence 工作台消费的是 runtime case。你当前已经有统一图谱，但还没有导入 evidence/case 文件，所以这里只能先等待 case 生成。',
      hints: [
        '回到系统入口后选择“追加 Evidence”，导入 evidence*.json 或 case*.json。',
        '如果只想检查图结构，图谱工作台仍然可用。',
      ],
      actions: [
        { key: 'import', label: '去追加 Evidence', type: 'primary' as const },
        { key: 'graphs', label: '查看图谱', type: 'outline' as const },
      ],
    }
  }

  return {
    title: '当前会话还没有可审查的 Evidence',
    description:
      'Evidence 工作台需要 runtime case。请先导入图谱，再导入 evidence/case 文件，或者直接恢复完整 bundle。',
    hints: [
      '完整回放会同时恢复 graphs 和 runtime。',
      'graphs-only 会让图谱页可用，但 Evidence / RCA 仍然不可用。',
    ],
    actions: [
      { key: 'import', label: '返回系统入口', type: 'primary' as const },
    ],
  }
})

function resolveActiveCase(
  currentCases: RootLensRuntimeCase[],
  caseId: string,
): RootLensRuntimeCase | null {
  return currentCases.find((item) => item.case_id === caseId) ?? currentCases[0] ?? null
}

const isDraftCase = computed(() =>
  activeCase.value ? hasDraftCase(workspaceState.value, activeCase.value.case_id) : false,
)
const feedbackCount = computed(() =>
  activeCase.value ? getCaseFeedbackEntries(workspaceState.value, activeCase.value.case_id).length : 0,
)
const observations = computed(() => activeCase.value?.evidence.observations ?? [])
const highlightedObservationIds = computed(() => new Set(focusState.value?.highlighted_obs_ids ?? []))

const filteredObservations = computed(() => {
  if (facetFilter.value === 'all') {
    return observations.value
  }

  return observations.value.filter((item) => item.facet === facetFilter.value)
})

const selectedObservation = computed<EvidenceObservation | null>(() => {
  return (
    filteredObservations.value.find((item) => item.obs_id === selectedObservationId.value) ??
    observations.value.find((item) => item.obs_id === selectedObservationId.value) ??
    filteredObservations.value[0] ??
    observations.value[0] ??
    null
  )
})

const observationCounts = computed(() => {
  const counts = {
    all: observations.value.length,
    variable: 0,
    image_defect: 0,
    log_event: 0,
  }

  for (const observation of observations.value) {
    counts[observation.facet] += 1
  }

  return counts
})

function refreshWorkspaceState() {
  workspaceState.value = loadAnalysisWorkspace(analysisWorkspaceScope.value)
}

function refreshFocusState() {
  focusState.value = loadAnalysisFocus(analysisWorkspaceScope.value)
}

function syncSelectedObservationFromFocus() {
  if (!activeCase.value) {
    selectedObservationId.value = ''
    return
  }

  const focusObservationId = focusState.value?.selected_observation_id

  if (
    focusObservationId &&
    activeCase.value.evidence.observations.some((item) => item.obs_id === focusObservationId)
  ) {
    selectedObservationId.value = focusObservationId
    return
  }

  const highlightedObservationId = focusState.value?.highlighted_obs_ids.find((obsId) =>
    activeCase.value?.evidence.observations.some((item) => item.obs_id === obsId),
  )

  if (highlightedObservationId) {
    selectedObservationId.value = highlightedObservationId
    return
  }

  if (!activeCase.value.evidence.observations.some((item) => item.obs_id === selectedObservationId.value)) {
    selectedObservationId.value = activeCase.value.evidence.observations[0]?.obs_id ?? ''
  }
}

function hydrateCases() {
  const currentCaseId = activeCaseId.value
  const focusedCaseId = focusState.value?.active_case_id

  cases.value = overlayWorkspaceCases(baseCases.value, workspaceState.value)
  activeCaseId.value = cases.value.some((item) => item.case_id === focusedCaseId)
    ? (focusedCaseId as string)
    : cases.value.some((item) => item.case_id === currentCaseId)
      ? currentCaseId
      : cases.value[0]?.case_id ?? ''
  activeCase.value = resolveActiveCase(cases.value, activeCaseId.value)
  syncSelectedObservationFromFocus()
}

function persistCaseFocus(caseItem: RootLensRuntimeCase | null) {
  if (!caseItem) {
    return
  }

  focusState.value = saveAnalysisFocus(
    analysisWorkspaceScope.value,
    buildCaseFocus(caseItem, 'evidence'),
  )
}

function persistObservationFocus(observation: EvidenceObservation | null) {
  if (!activeCase.value || !observation) {
    return
  }

  focusState.value = saveAnalysisFocus(
    analysisWorkspaceScope.value,
    buildObservationFocus(activeCase.value, observation, 'evidence'),
  )
}

async function loadRuntimeData() {
  loading.value = true
  errorMessage.value = ''

  try {
    const previousCaseId = activeCaseId.value
    const payload = await loadRootLensRuntime()
    schemaVersion.value = payload.schema_version
    baseCases.value = payload.cases
    refreshWorkspaceState()
    refreshFocusState()

    if (focusState.value?.selected_observation_id || focusState.value?.highlighted_obs_ids.length) {
      facetFilter.value = 'all'
    }

    activeCaseId.value = payload.cases.some((item) => item.case_id === focusState.value?.active_case_id)
      ? (focusState.value?.active_case_id as string)
      : payload.cases.some((item) => item.case_id === previousCaseId)
        ? previousCaseId
        : payload.cases[0]?.case_id ?? ''
    hydrateCases()
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'failed to load rootlens runtime bundle'
  } finally {
    loading.value = false
  }
}

function refreshSessionMeta() {
  sessionMeta.value = getLocalSessionMeta()
  importSummary.value = getImportedSessionSummary()
}

function handleSessionChange() {
  refreshSessionMeta()
  refreshFocusState()
  void loadRuntimeData()
}

function handleWorkspaceChange(event: Event) {
  const customEvent = event as CustomEvent<{ sessionScope?: string }>

  if (
    customEvent.detail?.sessionScope &&
    customEvent.detail.sessionScope !== analysisWorkspaceScope.value
  ) {
    return
  }

  refreshWorkspaceState()
  hydrateCases()
}

function handleFocusChange(event: Event) {
  const customEvent = event as CustomEvent<{ sessionScope?: string }>

  if (
    customEvent.detail?.sessionScope &&
    customEvent.detail.sessionScope !== analysisWorkspaceScope.value
  ) {
    return
  }

  refreshFocusState()

  if (focusState.value?.selected_observation_id || focusState.value?.highlighted_obs_ids.length) {
    facetFilter.value = 'all'
  }

  hydrateCases()
}

function handleCaseChange(value: string | number | boolean) {
  activeCaseId.value = String(value)
  activeCase.value = resolveActiveCase(cases.value, activeCaseId.value)
  facetFilter.value = 'all'
  syncSelectedObservationFromFocus()
  persistCaseFocus(activeCase.value)
}

function selectObservation(obsId: string) {
  selectedObservationId.value = obsId
  const observation = observations.value.find((item) => item.obs_id === obsId) ?? null
  persistObservationFocus(observation)
}

function locateSelectedObservation() {
  if (!canOpenGraphs.value) {
    return
  }

  persistObservationFocus(selectedObservation.value)
  void router.push({
    name: 'graphs',
  })
}

function openSelectedObservationInReasoning() {
  persistObservationFocus(selectedObservation.value)
  void router.push({
    name: 'reasoning',
  })
}

function handleBlockerAction(actionKey: string) {
  if (actionKey === 'import') {
    void router.push({
      name: 'import',
    })
    return
  }

  if (actionKey === 'graphs') {
    void router.push({
      name: 'graphs',
    })
  }
}

function facetLabel(facet: FacetFilter) {
  switch (facet) {
    case 'all':
      return '全部'
    case 'variable':
      return '变量'
    case 'image_defect':
      return '图像缺陷'
    case 'log_event':
      return '日志事件'
  }
}

function facetColor(facet: ObservationFacet) {
  switch (facet) {
    case 'variable':
      return 'arcoblue'
    case 'image_defect':
      return 'orangered'
    case 'log_event':
      return 'gold'
  }
}

function observationTitle(observation: EvidenceObservation) {
  if (observation.facet === 'variable') {
    return observation.variable_name
  }

  if (observation.facet === 'image_defect') {
    return `${observation.object} / ${observation.anomaly_type}`
  }

  return observation.event_code
}

function observationSummary(observation: EvidenceObservation) {
  if (observation.facet === 'variable') {
    return `contribution ${observation.contribution.toFixed(2)} · ${observation.direction}`
  }

  if (observation.facet === 'image_defect') {
    return `${observation.location} · severity ${observation.severity.toFixed(2)}`
  }

  return `${observation.event_type} · ${observation.equipment}`
}

function isVariableObservation(
  observation: EvidenceObservation | null,
): observation is VariableObservation {
  return observation?.facet === 'variable'
}

function isImageObservation(
  observation: EvidenceObservation | null,
): observation is ImageDefectObservation {
  return observation?.facet === 'image_defect'
}

function isLogObservation(observation: EvidenceObservation | null): observation is LogEventObservation {
  return observation?.facet === 'log_event'
}

watch(
  activeCase,
  (value) => {
    if (!value) {
      selectedObservationId.value = ''
      return
    }

    syncSelectedObservationFromFocus()
  },
  {
    immediate: true,
  },
)

watch(filteredObservations, (value) => {
  if (!value.length) {
    selectedObservationId.value = observations.value[0]?.obs_id ?? ''
    return
  }

  if (!value.some((item) => item.obs_id === selectedObservationId.value)) {
    selectedObservationId.value = value[0]?.obs_id ?? ''
  }
})

onMounted(() => {
  refreshSessionMeta()
  refreshFocusState()
  void loadRuntimeData()
  window.addEventListener(getLocalSessionEventName(), handleSessionChange)
  window.addEventListener(getAnalysisWorkspaceEventName(), handleWorkspaceChange)
  window.addEventListener(getAnalysisFocusEventName(), handleFocusChange)
})

onBeforeUnmount(() => {
  window.removeEventListener(getLocalSessionEventName(), handleSessionChange)
  window.removeEventListener(getAnalysisWorkspaceEventName(), handleWorkspaceChange)
  window.removeEventListener(getAnalysisFocusEventName(), handleFocusChange)
})
</script>

<template>
  <div class="page-stack evidence-workbench">
    <section class="hero-panel">
      <div class="hero-panel__content">
        <div>
          <a-space wrap>
            <a-tag color="arcoblue">Unified Evidence</a-tag>
            <a-tag color="green">Contract Driven</a-tag>
            <a-tag color="gold">Traceable Runtime</a-tag>
          </a-space>
          <h2 class="hero-panel__title">Evidence 审查</h2>
          <p class="hero-panel__body">
            当前页面直接消费浏览器会话里的统一 Evidence contract。每个 case 都带 observation、
            linked hints 和 raw refs，本地导入后无需后端即可做证据审查，并与 RCA 页的 draft case 保持同步。
          </p>
        </div>

        <div class="hero-panel__brief">
          <div class="brief-item">
            <div class="brief-item__label">当前 Bundle</div>
            <div class="brief-item__value">
              {{ schemaVersion || '加载中' }}
            </div>
          </div>
          <div class="brief-item">
            <div class="brief-item__label">Case Count</div>
            <div class="brief-item__value">{{ cases.length }}</div>
          </div>
          <div class="brief-item">
            <div class="brief-item__label">当前会话</div>
            <div class="brief-item__value">{{ sessionLabel }}</div>
          </div>
          <div class="brief-item">
            <div class="brief-item__label">活跃图快照</div>
            <div class="brief-item__value">
              {{ activeCase?.graph_snapshot.label ?? '未选择 case' }}
            </div>
          </div>
          <div class="brief-item">
            <div class="brief-item__label">会话摘要</div>
            <div class="brief-item__value">{{ sessionSummary }}</div>
          </div>
        </div>
      </div>
    </section>

    <a-card v-if="loading" class="glass-card" :bordered="false">
      <a-spin dot tip="正在加载 evidence runtime..." />
    </a-card>

    <SessionBlockerCard
      v-else-if="pageBlocker"
      badge="Evidence Unavailable"
      :session-label="sessionLabel"
      :title="pageBlocker.title"
      :description="pageBlocker.description"
      :reason="errorMessage"
      :hints="pageBlocker.hints"
      :actions="pageBlocker.actions"
      @action="handleBlockerAction"
    />

    <a-alert
      v-else-if="errorMessage"
      type="error"
      show-icon
      :content="errorMessage"
    />

    <template v-else-if="activeCase">
      <a-card class="glass-card" :bordered="false">
        <div class="workbench-toolbar">
          <div class="toolbar-block">
            <div class="toolbar-block__label">Case</div>
            <a-radio-group
              type="button"
              :model-value="activeCaseId"
              @change="handleCaseChange"
            >
              <a-radio
                v-for="caseItem in cases"
                :key="caseItem.case_id"
                :value="caseItem.case_id"
              >
                {{ caseItem.case_label }}
              </a-radio>
            </a-radio-group>
          </div>

          <div class="toolbar-block">
            <div class="toolbar-block__label">Facet Filter</div>
            <a-radio-group v-model="facetFilter" type="button">
              <a-radio value="all">全部</a-radio>
              <a-radio value="variable">变量</a-radio>
              <a-radio value="image_defect">图像缺陷</a-radio>
              <a-radio value="log_event">日志事件</a-radio>
            </a-radio-group>
          </div>
        </div>
      </a-card>

      <div class="evidence-metrics">
        <div class="metric-card">
          <div class="metric-card__label">Dataset</div>
          <div class="metric-card__value">{{ activeCase.dataset }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-card__label">Source</div>
          <div class="metric-card__value">{{ activeCase.source }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-card__label">Observations</div>
          <div class="metric-card__value">{{ observationCounts.all }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-card__label">Route Availability</div>
          <div class="metric-card__value">
            {{ activeCase.analysis.route1 ? 'R1' : '-' }} / {{ activeCase.analysis.route2 ? 'R2' : '-' }}
          </div>
        </div>
        <div class="metric-card">
          <div class="metric-card__label">Case Mode</div>
          <div class="metric-card__value">{{ isDraftCase ? 'draft' : 'base' }}</div>
        </div>
        <div class="metric-card">
          <div class="metric-card__label">Feedback Items</div>
          <div class="metric-card__value">{{ feedbackCount }}</div>
        </div>
      </div>

      <div class="evidence-layout">
        <a-card class="glass-card" :bordered="false">
          <template #title>Observation List</template>
          <template #extra>
            <a-space wrap>
                  <a-tag
                v-for="facet in facetOptions"
                    :key="facet"
                    color="grayblue"
                  >
                {{ facetLabel(facet) }}:
                {{
                  facet === 'all'
                    ? observationCounts.all
                    : observationCounts[facet]
                }}
              </a-tag>
            </a-space>
          </template>

          <div class="observation-list">
            <button
              v-for="observation in filteredObservations"
              :key="observation.obs_id"
              class="observation-item"
              :class="{
                'observation-item--active': observation.obs_id === selectedObservation?.obs_id,
                'observation-item--linked': highlightedObservationIds.has(observation.obs_id),
              }"
              type="button"
              @click="selectObservation(observation.obs_id)"
            >
              <div class="observation-item__top">
                <strong>{{ observationTitle(observation) }}</strong>
                <a-tag :color="facetColor(observation.facet)">
                  {{ facetLabel(observation.facet) }}
                </a-tag>
              </div>
              <div class="observation-item__meta">
                <span>{{ observationSummary(observation) }}</span>
                <span>confidence {{ observation.confidence.toFixed(2) }}</span>
              </div>
            </button>

            <a-empty
              v-if="!filteredObservations.length"
              description="当前筛选条件下没有 observation"
            />
          </div>
        </a-card>

        <a-card class="glass-card" :bordered="false">
          <template #title>Observation Detail</template>

          <template v-if="selectedObservation">
            <div class="detail-stack">
              <div class="detail-head">
                <div>
                  <h3>{{ observationTitle(selectedObservation) }}</h3>
                  <p>{{ observationSummary(selectedObservation) }}</p>
                </div>
                <a-space wrap>
                  <a-tag :color="facetColor(selectedObservation.facet)">
                    {{ facetLabel(selectedObservation.facet) }}
                  </a-tag>
                  <a-tag color="green">
                    confidence {{ selectedObservation.confidence.toFixed(2) }}
                  </a-tag>
                  <a-tag
                    v-if="highlightedObservationIds.has(selectedObservation.obs_id)"
                    color="orangered"
                  >
                    linked focus
                  </a-tag>
                  <a-button :disabled="!canOpenGraphs" size="mini" @click="locateSelectedObservation">
                    在图中定位
                  </a-button>
                  <a-button size="mini" @click="openSelectedObservationInReasoning">
                    带入 RCA
                  </a-button>
                </a-space>
              </div>

              <div class="detail-grid">
                <div class="detail-panel">
                  <div class="detail-panel__label">Case Summary</div>
                  <div class="detail-panel__value">{{ activeCase.summary }}</div>
                </div>
                <div class="detail-panel">
                  <div class="detail-panel__label">Graph Snapshot</div>
                  <div class="detail-panel__value">
                    {{ activeCase.graph_snapshot.label }} / {{ activeCase.graph_snapshot.graph_kind }}
                  </div>
                </div>
              </div>

              <div v-if="isVariableObservation(selectedObservation)" class="field-grid">
                <div class="field-row">
                  <span>Variable</span>
                  <strong>{{ selectedObservation.variable_name }}</strong>
                </div>
                <div class="field-row">
                  <span>Contribution</span>
                  <strong>{{ selectedObservation.contribution.toFixed(2) }}</strong>
                </div>
                <div class="field-row">
                  <span>Direction</span>
                  <strong>{{ selectedObservation.direction }}</strong>
                </div>
                <div class="field-row" v-if="selectedObservation.time_window">
                  <span>Time Window</span>
                  <strong>
                    {{ selectedObservation.time_window.start }} -> {{ selectedObservation.time_window.end }}
                  </strong>
                </div>
              </div>

              <div v-else-if="isImageObservation(selectedObservation)" class="field-grid">
                <div class="field-row">
                  <span>Object</span>
                  <strong>{{ selectedObservation.object }}</strong>
                </div>
                <div class="field-row">
                  <span>Anomaly</span>
                  <strong>{{ selectedObservation.anomaly_type }}</strong>
                </div>
                <div class="field-row">
                  <span>Location</span>
                  <strong>{{ selectedObservation.location }}</strong>
                </div>
                <div class="field-row">
                  <span>Severity</span>
                  <strong>{{ selectedObservation.severity.toFixed(2) }}</strong>
                </div>
                <div class="field-row" v-if="selectedObservation.image_region">
                  <span>Region</span>
                  <strong>
                    x={{ selectedObservation.image_region.x }},
                    y={{ selectedObservation.image_region.y }},
                    w={{ selectedObservation.image_region.w }},
                    h={{ selectedObservation.image_region.h }}
                  </strong>
                </div>
                <pre class="json-block">{{
                  JSON.stringify(selectedObservation.morphology, null, 2)
                }}</pre>
              </div>

              <div v-else-if="isLogObservation(selectedObservation)" class="field-grid">
                <div class="field-row">
                  <span>Event Type</span>
                  <strong>{{ selectedObservation.event_type }}</strong>
                </div>
                <div class="field-row">
                  <span>Event Code</span>
                  <strong>{{ selectedObservation.event_code }}</strong>
                </div>
                <div class="field-row">
                  <span>Equipment</span>
                  <strong>{{ selectedObservation.equipment }}</strong>
                </div>
                <div class="field-row field-row--multiline">
                  <span>Message</span>
                  <strong>{{ selectedObservation.message }}</strong>
                </div>
              </div>

              <div class="detail-panel">
                <div class="detail-panel__label">Linked Entity Hints</div>
                <div class="tag-wall">
                  <a-tag
                    v-for="entityId in selectedObservation.linked_entity_hints"
                    :key="entityId"
                    color="arcoblue"
                  >
                    {{ entityId }}
                  </a-tag>
                </div>
              </div>

              <div class="detail-panel">
                <div class="detail-panel__label">Raw Evidence Refs</div>
                <div class="ref-list">
                  <div
                    v-for="refItem in selectedObservation.raw_evidence_refs"
                    :key="refItem.ref_id"
                    class="ref-item"
                  >
                    <strong>{{ refItem.label }}</strong>
                    <span>{{ refItem.role }}</span>
                    <code>{{ refItem.file_path }}</code>
                  </div>
                </div>
              </div>

              <div v-if="selectedObservation.attributes" class="detail-panel">
                <div class="detail-panel__label">Observation Attributes</div>
                <pre class="json-block">{{
                  JSON.stringify(selectedObservation.attributes, null, 2)
                }}</pre>
              </div>
            </div>
          </template>

          <a-empty v-else description="没有可展示的 observation" />
        </a-card>
      </div>
    </template>
  </div>
</template>

<style scoped>
.evidence-workbench {
  gap: 18px;
}

.workbench-toolbar {
  display: grid;
  gap: 18px;
}

.toolbar-block {
  display: grid;
  gap: 10px;
}

.toolbar-block__label {
  color: var(--kg-muted);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.evidence-metrics {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.metric-card {
  padding: 16px 18px;
  border: 1px solid var(--kg-line);
  border-radius: 20px;
  background: rgba(255, 255, 255, 0.72);
  box-shadow: 0 10px 32px rgba(12, 31, 43, 0.06);
}

.metric-card__label {
  color: var(--kg-muted);
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
}

.metric-card__value {
  margin-top: 8px;
  font-size: 20px;
  font-weight: 700;
}

.evidence-layout {
  display: grid;
  gap: 18px;
  grid-template-columns: minmax(320px, 0.92fr) minmax(0, 1.3fr);
}

.observation-list {
  display: grid;
  gap: 12px;
}

.observation-item {
  width: 100%;
  padding: 14px 16px;
  border: 1px solid rgba(15, 139, 141, 0.14);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.58);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    transform 0.2s ease,
    border-color 0.2s ease,
    box-shadow 0.2s ease;
}

.observation-item:hover,
.observation-item--active {
  transform: translateY(-1px);
  border-color: rgba(15, 139, 141, 0.4);
  box-shadow: 0 14px 30px rgba(15, 139, 141, 0.12);
}

.observation-item--linked {
  border-color: rgba(217, 119, 6, 0.36);
  box-shadow: inset 0 0 0 1px rgba(217, 119, 6, 0.12);
}

.observation-item__top,
.observation-item__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.observation-item__meta {
  margin-top: 10px;
  color: var(--kg-muted);
  font-size: 13px;
}

.detail-stack {
  display: grid;
  gap: 18px;
}

.detail-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
}

.detail-head h3 {
  margin: 0;
  font-size: 24px;
}

.detail-head p {
  margin: 8px 0 0;
  color: var(--kg-muted);
  line-height: 1.7;
}

.detail-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.detail-panel {
  display: grid;
  gap: 10px;
  padding: 14px 16px;
  border: 1px solid rgba(18, 35, 47, 0.08);
  border-radius: 18px;
  background: rgba(255, 255, 255, 0.54);
}

.detail-panel__label {
  color: var(--kg-muted);
  font-size: 12px;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.detail-panel__value {
  line-height: 1.7;
}

.field-grid {
  display: grid;
  gap: 12px;
}

.field-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(18, 35, 47, 0.08);
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.52);
}

.field-row span {
  color: var(--kg-muted);
}

.field-row strong {
  text-align: right;
}

.field-row--multiline {
  align-items: flex-start;
}

.field-row--multiline strong {
  max-width: 72%;
  text-align: left;
}

.tag-wall {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ref-list {
  display: grid;
  gap: 10px;
}

.ref-item {
  display: grid;
  gap: 4px;
  padding: 12px 14px;
  border-radius: 16px;
  background: rgba(12, 31, 43, 0.04);
}

.ref-item span,
.ref-item code {
  color: var(--kg-muted);
}

.json-block {
  overflow: auto;
  margin: 0;
  padding: 14px;
  border-radius: 16px;
  background: rgba(12, 31, 43, 0.92);
  color: #eff8f8;
  font-size: 12px;
  line-height: 1.6;
}

@media (max-width: 1280px) {
  .evidence-layout {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 960px) {
  .evidence-metrics,
  .detail-grid {
    grid-template-columns: 1fr 1fr;
  }

  .detail-head,
  .observation-item__top,
  .observation-item__meta,
  .field-row {
    flex-direction: column;
    align-items: flex-start;
  }

  .field-row strong,
  .field-row--multiline strong {
    max-width: none;
    text-align: left;
  }
}

@media (max-width: 720px) {
  .evidence-metrics,
  .detail-grid {
    grid-template-columns: 1fr;
  }
}
</style>
