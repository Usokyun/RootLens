<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'

import { buildAnalysisWorkspaceScope } from '@/services/analysis-workspace'
import {
  getAnalysisFocusEventName,
  loadAnalysisFocus,
  saveAnalysisFocus,
  type AnalysisFocusState,
} from '@/services/analysis-focus'
import { buildLocalImportResult } from '@/services/browser-runtime'
import {
  getLocalSessionEventName,
  getLocalSessionMeta,
  loadRootLensRuntime,
  saveImportedSession,
} from '@/services/rootlens-data'
import type {
  EvidenceObservation,
  ImageDefectObservation,
  LogEventObservation,
  ObservationFacet,
  VariableObservation,
} from '@/types/rootlens'

type EvidenceDataset = 'tep' | 'mvtec' | 'wafer' | 'wm811k'

interface CaseViewItem {
  case_id: string
  case_label: string
  dataset: EvidenceDataset
  graph_snapshot: {
    dataset_id: string
    label: string
  }
  evidence: {
    observations: EvidenceObservation[]
  }
}

const router = useRouter()

const loading = ref(true)
const importing = ref(false)
const errorMessage = ref('')
const noticeMessage = ref('')

const allCases = ref<CaseViewItem[]>([])
const selectedCaseId = ref('')
const selectedObservationId = ref('')

const caseSearch = ref('')
const facetFilter = ref<'all' | ObservationFacet>('all')
const tepOnly = ref(true)

const importInput = ref<HTMLInputElement | null>(null)

const sessionMeta = ref(getLocalSessionMeta())
const focusState = ref<AnalysisFocusState | null>(null)
const analysisScope = computed(() => buildAnalysisWorkspaceScope(sessionMeta.value))

const filteredCases = computed(() => {
  const search = caseSearch.value.trim().toLowerCase()

  return allCases.value.filter((caseItem) => {
    if (tepOnly.value) {
      const isTepCase = caseItem.dataset === 'tep' || caseItem.graph_snapshot.dataset_id === 'tep-kg'
      if (!isTepCase) {
        return false
      }
    }

    if (!search) {
      return true
    }

    return [caseItem.case_id, caseItem.case_label, caseItem.graph_snapshot.label]
      .join(' ')
      .toLowerCase()
      .includes(search)
  })
})

const activeCase = computed(() => {
  return (
    filteredCases.value.find((caseItem) => caseItem.case_id === selectedCaseId.value) ??
    filteredCases.value[0] ??
    null
  )
})

const observations = computed(() => {
  const list = activeCase.value?.evidence.observations ?? []

  if (facetFilter.value === 'all') {
    return list
  }

  return list.filter((observation) => observation.facet === facetFilter.value)
})

const activeObservation = computed(() => {
  return (
    observations.value.find((observation) => observation.obs_id === selectedObservationId.value) ??
    observations.value[0] ??
    null
  )
})

function observationTitle(observation: EvidenceObservation): string {
  switch (observation.facet) {
    case 'variable':
      return (observation as VariableObservation).variable_name
    case 'image_defect':
      return `${(observation as ImageDefectObservation).object} / ${(observation as ImageDefectObservation).anomaly_type}`
    case 'log_event':
      return `${(observation as LogEventObservation).event_code} / ${(observation as LogEventObservation).equipment}`
  }
}

function observationSummary(observation: EvidenceObservation): string {
  switch (observation.facet) {
    case 'variable': {
      const item = observation as VariableObservation
      return `contrib ${item.contribution.toFixed(3)} · direction ${item.direction}`
    }
    case 'image_defect': {
      const item = observation as ImageDefectObservation
      return `severity ${item.severity.toFixed(3)} · location ${item.location}`
    }
    case 'log_event': {
      const item = observation as LogEventObservation
      return `${item.event_type} · ${item.message.slice(0, 64)}`
    }
  }
}

function resolveFacetColor(facet: ObservationFacet) {
  switch (facet) {
    case 'variable':
      return 'arcoblue'
    case 'image_defect':
      return 'orangered'
    case 'log_event':
      return 'green'
    default:
      return 'gray'
  }
}

function buildCaseFocusPatch(caseItem: CaseViewItem) {
  return {
    active_case_id: caseItem.case_id,
    active_dataset_id: caseItem.graph_snapshot.dataset_id,
    selected_observation_id: null,
    selected_route1_path_ids: [],
    selected_route2_candidate_ids: [],
    highlighted_node_ids: [],
    highlighted_edge_ids: [],
    highlighted_obs_ids: [],
    focus_kind: 'case' as const,
    focus_label: caseItem.case_label,
    source_view: 'evidence' as const,
  }
}

function buildObservationFocusPatch(caseItem: CaseViewItem, observation: EvidenceObservation) {
  return {
    active_case_id: caseItem.case_id,
    active_dataset_id: caseItem.graph_snapshot.dataset_id,
    selected_observation_id: observation.obs_id,
    selected_route1_path_ids: [],
    selected_route2_candidate_ids: [],
    highlighted_node_ids: observation.linked_entity_hints,
    highlighted_edge_ids: [],
    highlighted_obs_ids: [observation.obs_id],
    focus_kind: 'observation' as const,
    focus_label: observationTitle(observation),
    source_view: 'evidence' as const,
  }
}

function syncSelectionFromFocus() {
  if (!focusState.value) {
    return
  }

  if (
    focusState.value.active_case_id &&
    filteredCases.value.some((caseItem) => caseItem.case_id === focusState.value?.active_case_id)
  ) {
    selectedCaseId.value = focusState.value.active_case_id
  }

  if (
    focusState.value.selected_observation_id &&
    observations.value.some((observation) => observation.obs_id === focusState.value?.selected_observation_id)
  ) {
    selectedObservationId.value = focusState.value.selected_observation_id
  }
}

function refreshSessionMeta() {
  sessionMeta.value = getLocalSessionMeta()
}

function refreshFocusState() {
  focusState.value = loadAnalysisFocus(analysisScope.value)
}

async function loadCases() {
  loading.value = true
  errorMessage.value = ''

  try {
    const runtime = await loadRootLensRuntime()
    allCases.value = runtime.cases.map((caseItem) => ({
      case_id: caseItem.case_id,
      case_label: caseItem.case_label,
      dataset: caseItem.dataset,
      graph_snapshot: {
        dataset_id: caseItem.graph_snapshot.dataset_id,
        label: caseItem.graph_snapshot.label,
      },
      evidence: {
        observations: caseItem.evidence.observations,
      },
    }))

    if (!filteredCases.value.some((caseItem) => caseItem.case_id === selectedCaseId.value)) {
      selectedCaseId.value =
        focusState.value?.active_case_id &&
        filteredCases.value.some((caseItem) => caseItem.case_id === focusState.value?.active_case_id)
          ? (focusState.value.active_case_id as string)
          : filteredCases.value[0]?.case_id ?? ''
    }

    syncSelectionFromFocus()
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'failed to load rootlens runtime bundle'
  } finally {
    loading.value = false
  }
}

function handleSessionChange() {
  refreshSessionMeta()
  refreshFocusState()
  void loadCases()
}

function handleFocusChange(event: Event) {
  const customEvent = event as CustomEvent<{ sessionScope?: string }>

  if (customEvent.detail?.sessionScope && customEvent.detail.sessionScope !== analysisScope.value) {
    return
  }

  refreshFocusState()
  syncSelectionFromFocus()
}

function switchCase(caseId: string) {
  selectedCaseId.value = caseId

  const caseItem = filteredCases.value.find((item) => item.case_id === caseId)
  if (!caseItem) {
    return
  }

  saveAnalysisFocus(analysisScope.value, buildCaseFocusPatch(caseItem))
}

function switchObservation(observationId: string) {
  selectedObservationId.value = observationId

  if (!activeCase.value) {
    return
  }

  const observation = observations.value.find((item) => item.obs_id === observationId)
  if (!observation) {
    return
  }

  saveAnalysisFocus(analysisScope.value, buildObservationFocusPatch(activeCase.value, observation))
}

function triggerEvidenceImport() {
  importInput.value?.click()
}

async function importEvidenceFiles(event: Event) {
  const target = event.target as HTMLInputElement
  const files = target.files ? Array.from(target.files) : []

  if (!files.length) {
    return
  }

  importing.value = true
  errorMessage.value = ''
  noticeMessage.value = ''

  try {
    const result = await buildLocalImportResult(files)

    saveImportedSession({
      graphs: result.graphs,
      runtime: result.runtime,
      summary: 'Evidence imported from UI',
      importSummary: result.summary,
    })

    noticeMessage.value = result.summary.warnings.length
      ? `导入完成（含警告）：${result.summary.warnings.join('；')}`
      : '导入完成，已生成/更新 runtime cases。'

    refreshSessionMeta()
    refreshFocusState()
    await loadCases()

    const firstTepCase = filteredCases.value.find((caseItem) => caseItem.dataset === 'tep')
    if (firstTepCase) {
      selectedCaseId.value = firstTepCase.case_id
    }
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'evidence import failed'
  } finally {
    importing.value = false
    target.value = ''
  }
}

function sendToGraphs(withObservation: boolean) {
  if (!activeCase.value) {
    return
  }

  if (withObservation && activeObservation.value) {
    saveAnalysisFocus(
      analysisScope.value,
      buildObservationFocusPatch(activeCase.value, activeObservation.value),
    )
  } else {
    saveAnalysisFocus(analysisScope.value, buildCaseFocusPatch(activeCase.value))
  }

  void router.push({
    name: 'graphs',
  })
}

watch(activeCase, (caseItem) => {
  if (!caseItem) {
    selectedObservationId.value = ''
    return
  }

  if (!observations.value.some((item) => item.obs_id === selectedObservationId.value)) {
    selectedObservationId.value = observations.value[0]?.obs_id ?? ''
  }
})

watch(tepOnly, () => {
  if (!filteredCases.value.some((caseItem) => caseItem.case_id === selectedCaseId.value)) {
    selectedCaseId.value = filteredCases.value[0]?.case_id ?? ''
  }
})

onMounted(() => {
  refreshSessionMeta()
  refreshFocusState()
  void loadCases()

  window.addEventListener(getLocalSessionEventName(), handleSessionChange)
  window.addEventListener(getAnalysisFocusEventName(), handleFocusChange)
})

onBeforeUnmount(() => {
  window.removeEventListener(getLocalSessionEventName(), handleSessionChange)
  window.removeEventListener(getAnalysisFocusEventName(), handleFocusChange)
})
</script>

<template>
  <div class="rl-page evidence-page">
    <input
      ref="importInput"
      type="file"
      accept=".json,.jsonl"
      multiple
      class="evidence-import-input"
      @change="importEvidenceFiles"
    />

    <a-alert v-if="errorMessage" type="error" show-icon :content="errorMessage" />
    <a-alert v-else-if="noticeMessage" type="success" show-icon :content="noticeMessage" />

    <div v-if="loading" class="evidence-loading">
      <a-spin tip="加载 runtime cases..." />
    </div>

    <div v-else class="evidence-layout">
      <aside class="rl-section-card case-column">
        <header class="rl-section-card__header">
          <h3 class="rl-section-card__title">Case 列表</h3>
        </header>
        <div class="rl-section-card__body case-column__body">
          <a-input-search v-model="caseSearch" allow-clear placeholder="搜索 case..." />
          <a-space align="center">
            <a-switch v-model="tepOnly" size="small">
              <template #checked>仅 TEP</template>
              <template #unchecked>全部</template>
            </a-switch>
            <a-button type="primary" size="small" :loading="importing" @click="triggerEvidenceImport">
              导入 Evidence
            </a-button>
          </a-space>

          <div class="case-list">
            <article
              v-for="item in filteredCases"
              :key="item.case_id"
              class="case-item"
              :class="{ 'case-item--active': activeCase?.case_id === item.case_id }"
              @click="switchCase(item.case_id)"
            >
              <h4>{{ item.case_label }}</h4>
              <p>{{ item.case_id }}</p>
              <p>{{ item.evidence.observations.length }} obs · {{ item.graph_snapshot.dataset_id }}</p>
            </article>
          </div>
        </div>
      </aside>

      <section class="evidence-main">
        <article class="rl-section-card">
          <header class="rl-section-card__header">
            <h3 class="rl-section-card__title">Observation</h3>
            <a-space>
              <a-select v-model="facetFilter" :style="{ width: '160px' }" size="small">
                <a-option value="all">全部 facet</a-option>
                <a-option value="variable">variable</a-option>
                <a-option value="image_defect">image_defect</a-option>
                <a-option value="log_event">log_event</a-option>
              </a-select>
              <a-tag>{{ activeCase?.case_id ?? '无案例' }}</a-tag>
            </a-space>
          </header>
          <div class="rl-section-card__body observation-list">
            <article
              v-for="observation in observations"
              :key="observation.obs_id"
              class="observation-item"
              :class="{ 'observation-item--active': observation.obs_id === activeObservation?.obs_id }"
              @click="switchObservation(observation.obs_id)"
            >
              <div class="observation-item__header">
                <strong>{{ observation.obs_id }}</strong>
                <a-tag :color="resolveFacetColor(observation.facet)">{{ observation.facet }}</a-tag>
              </div>
              <p>{{ observationTitle(observation) }}</p>
              <p>{{ observationSummary(observation) }}</p>
            </article>
          </div>
        </article>

        <article class="rl-section-card">
          <header class="rl-section-card__header">
            <h3 class="rl-section-card__title">详情</h3>
          </header>
          <div class="rl-section-card__body detail-grid">
            <div class="detail-panel">
              <h4>{{ activeObservation ? observationTitle(activeObservation) : '-' }}</h4>
              <p>Facet: {{ activeObservation?.facet ?? '-' }}</p>
              <p>Confidence: {{ activeObservation?.confidence ?? '-' }}</p>
              <p>
                Hints:
                {{ activeObservation?.linked_entity_hints?.join(', ') || '-' }}
              </p>
            </div>

            <div class="detail-panel detail-panel--refs">
              <h4>Raw Evidence Refs</h4>
              <ul>
                <li v-for="refItem in activeObservation?.raw_evidence_refs ?? []" :key="refItem.ref_id">
                  {{ refItem.label }} · {{ refItem.file_path }}
                  <span v-if="refItem.line !== null">(line {{ refItem.line }})</span>
                </li>
              </ul>
            </div>
          </div>
        </article>

        <div class="evidence-actions">
          <a-space>
            <a-button type="primary" @click="sendToGraphs(false)">将此 Case 用于图谱 RCA</a-button>
            <a-button @click="sendToGraphs(true)">发送当前 Observation 到图谱</a-button>
          </a-space>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.evidence-import-input {
  display: none;
}

.evidence-loading {
  min-height: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.evidence-layout {
  display: grid;
  grid-template-columns: 320px minmax(0, 1fr);
  gap: 12px;
  min-height: 680px;
}

.case-column__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 0;
}

.case-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
  overflow-y: auto;
  max-height: 560px;
}

.case-item {
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  background: #fff;
  padding: 10px;
  cursor: pointer;
}

.case-item--active {
  border-color: #3f7cff;
  background: #f7faff;
}

.case-item h4 {
  margin: 0;
  font-size: 14px;
}

.case-item p {
  margin: 4px 0 0;
  color: #4e5969;
  font-size: 12px;
}

.evidence-main {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.observation-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(230px, 1fr));
  gap: 10px;
}

.observation-item {
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  background: #fff;
  padding: 10px;
  cursor: pointer;
}

.observation-item--active {
  border-color: #3f7cff;
  background: #f7faff;
}

.observation-item__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.observation-item p {
  margin: 6px 0 0;
  color: #4e5969;
  font-size: 12px;
  line-height: 1.5;
}

.detail-grid {
  display: grid;
  grid-template-columns: minmax(240px, 0.7fr) minmax(0, 1fr);
  gap: 12px;
}

.detail-panel {
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  background: #fff;
  padding: 12px;
}

.detail-panel h4 {
  margin: 0 0 8px;
  font-size: 14px;
}

.detail-panel p {
  margin: 6px 0;
  color: #4e5969;
  font-size: 12px;
}

.detail-panel--refs ul {
  margin: 0;
  padding-left: 16px;
}

.detail-panel--refs li {
  margin: 6px 0;
  color: #4e5969;
  font-size: 12px;
  line-height: 1.5;
}

.evidence-actions {
  border: 1px solid #dfe3ea;
  border-radius: 10px;
  background: rgba(255, 255, 255, 0.86);
  padding: 10px 12px;
}

@media (max-width: 1180px) {
  .evidence-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .case-list {
    max-height: none;
  }
}

@media (max-width: 860px) {
  .detail-grid {
    grid-template-columns: minmax(0, 1fr);
  }
}
</style>
