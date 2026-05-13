<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'

import KnowledgeForceGraph from '@/components/graphs/KnowledgeForceGraph.vue'
import { buildAnalysisWorkspaceScope } from '@/services/analysis-workspace'
import {
  clearAnalysisHighlight,
  getAnalysisFocusEventName,
  loadAnalysisFocus,
  saveAnalysisFocus,
  type AnalysisFocusState,
} from '@/services/analysis-focus'
import { buildLocalAnalysisResult } from '@/services/local-reasoning'
import {
  getLocalSessionEventName,
  getLocalSessionMeta,
  loadRootLensRuntime,
  loadUnifiedGraphs,
} from '@/services/rootlens-data'
import type { UnifiedGraphDataset, UnifiedGraphEdge, UnifiedGraphsFile } from '@/types/graph'
import type { RootKGDCandidate, UnifiedEvidence } from '@/types/rootlens'

type EvidenceDataset = 'tep' | 'mvtec' | 'wafer' | 'wm811k'

interface GraphCaseView {
  case_id: string
  case_label: string
  dataset: EvidenceDataset
  graph_snapshot: {
    dataset_id: string
    label: string
  }
  evidence: UnifiedEvidence
}

const loading = ref(true)
const errorMessage = ref('')
const graphBundle = ref<UnifiedGraphsFile | null>(null)
const runtimeCases = ref<GraphCaseView[]>([])

const selectedDatasetId = ref('')
const selectedCaseId = ref('')
const selectedCandidateId = ref('')
const selectedPathIndex = ref(0)

const searchTerm = ref('')
const showLabels = ref(false)

const sessionMeta = ref(getLocalSessionMeta())
const focusState = ref<AnalysisFocusState | null>(null)

const analysisScope = computed(() => buildAnalysisWorkspaceScope(sessionMeta.value))
const datasets = computed(() => graphBundle.value?.datasets ?? [])

const preferredTepDataset = computed(() => {
  return (
    datasets.value.find((dataset) => dataset.id === 'tep-kg') ??
    datasets.value.find(
      (dataset) => dataset.graphKind === 'rca-graph' && dataset.id.toLowerCase().includes('tep'),
    ) ??
    datasets.value.find((dataset) => dataset.graphKind === 'rca-graph') ??
    datasets.value[0] ??
    null
  )
})

const activeDataset = computed<UnifiedGraphDataset | null>(() => {
  if (!datasets.value.length) {
    return null
  }

  return (
    datasets.value.find((dataset) => dataset.id === selectedDatasetId.value) ??
    preferredTepDataset.value
  )
})

const casesForActiveDataset = computed(() => {
  if (!activeDataset.value) {
    return [] as GraphCaseView[]
  }

  return runtimeCases.value.filter((caseItem) => caseItem.graph_snapshot.dataset_id === activeDataset.value?.id)
})

const activeCase = computed(() => {
  return (
    casesForActiveDataset.value.find((caseItem) => caseItem.case_id === selectedCaseId.value) ??
    casesForActiveDataset.value[0] ??
    null
  )
})

const localAnalysis = computed(() => {
  if (!activeDataset.value || !activeCase.value) {
    return null
  }

  return buildLocalAnalysisResult(activeDataset.value, activeCase.value.evidence)
})

const scoreRanking = computed(() => {
  const ranked = localAnalysis.value?.route2?.ranked_candidates ?? []

  return [...ranked].sort((left, right) => {
    if (right.ranking_score === left.ranking_score) {
      return right.root_score - left.root_score
    }

    return right.ranking_score - left.ranking_score
  })
})

const selectedCandidate = computed<RootKGDCandidate | null>(() => {
  return (
    scoreRanking.value.find((candidate) => candidate.candidate_id === selectedCandidateId.value) ??
    scoreRanking.value[0] ??
    null
  )
})

const selectedPropagationPath = computed(() => {
  if (!selectedCandidate.value) {
    return [] as string[]
  }

  const paths = selectedCandidate.value.top_support_paths
  if (!paths.length) {
    return [] as string[]
  }

  return paths[selectedPathIndex.value] ?? paths[0] ?? []
})

const propagationPathOptions = computed(() => {
  return (selectedCandidate.value?.top_support_paths ?? []).map((path, index) => ({
    label: `路径 ${index + 1}: ${path.join(' -> ')}`,
    value: index,
  }))
})

const edgeLookup = computed(() => {
  const byDirectedPair = new Map<string, UnifiedGraphEdge[]>()

  for (const edge of activeDataset.value?.edges ?? []) {
    const key = `${edge.source}=>${edge.target}`
    const current = byDirectedPair.get(key) ?? []
    current.push(edge)
    byDirectedPair.set(key, current)
  }

  return byDirectedPair
})

function pickEdgeIdForSegment(sourceId: string, targetId: string): string | null {
  const direct = edgeLookup.value.get(`${sourceId}=>${targetId}`)
  if (direct?.length) {
    const preferred = direct.find((edge) => edge.directed) ?? direct[0]
    return preferred.id
  }

  const reverse = edgeLookup.value.get(`${targetId}=>${sourceId}`)
  if (reverse?.length) {
    const preferred = reverse.find((edge) => edge.directed) ?? reverse[0]
    return preferred.id
  }

  return null
}

const highlightedEdgeIds = computed(() => {
  const path = selectedPropagationPath.value

  if (path.length < 2) {
    return [] as string[]
  }

  const edgeIds: string[] = []
  for (let index = 0; index < path.length - 1; index += 1) {
    const edgeId = pickEdgeIdForSegment(path[index], path[index + 1])
    if (edgeId) {
      edgeIds.push(edgeId)
    }
  }

  return edgeIds
})

const highlightedNodeIds = computed(() => {
  if (!selectedCandidate.value) {
    return [] as string[]
  }

  return [
    ...new Set([
      selectedCandidate.value.candidate_id,
      ...selectedPropagationPath.value,
      ...selectedCandidate.value.top_affected_variables.map((item) => item.entity_id),
    ]),
  ]
})

function getDatasetCaseId(datasetId: string, preferredCaseId: string | null): string {
  const availableCases = runtimeCases.value.filter(
    (caseItem) => caseItem.graph_snapshot.dataset_id === datasetId,
  )

  if (!availableCases.length) {
    return ''
  }

  if (preferredCaseId && availableCases.some((caseItem) => caseItem.case_id === preferredCaseId)) {
    return preferredCaseId
  }

  const preferredTepCase = availableCases.find((caseItem) => caseItem.dataset === 'tep')
  return preferredTepCase?.case_id ?? availableCases[0].case_id
}

function syncSelectionFromFocus() {
  if (!focusState.value) {
    return
  }

  if (
    focusState.value.active_dataset_id &&
    datasets.value.some((dataset) => dataset.id === focusState.value?.active_dataset_id)
  ) {
    selectedDatasetId.value = focusState.value.active_dataset_id
  }

  if (
    focusState.value.active_case_id &&
    casesForActiveDataset.value.some((caseItem) => caseItem.case_id === focusState.value?.active_case_id)
  ) {
    selectedCaseId.value = focusState.value.active_case_id
  }

  const focusedCandidateId = focusState.value.selected_route2_candidate_ids[0]
  if (focusedCandidateId && scoreRanking.value.some((item) => item.candidate_id === focusedCandidateId)) {
    selectedCandidateId.value = focusedCandidateId
  }
}

async function hydrate() {
  loading.value = true
  errorMessage.value = ''

  try {
    const [graphs, runtime] = await Promise.all([
      loadUnifiedGraphs(),
      loadRootLensRuntime().catch(() => null),
    ])

    graphBundle.value = graphs
    runtimeCases.value = (runtime?.cases ?? []).map((caseItem) => ({
      case_id: caseItem.case_id,
      case_label: caseItem.case_label,
      dataset: caseItem.dataset,
      graph_snapshot: {
        dataset_id: caseItem.graph_snapshot.dataset_id,
        label: caseItem.graph_snapshot.label,
      },
      evidence: caseItem.evidence,
    }))

    const preferredDatasetId =
      focusState.value?.active_dataset_id && graphs.datasets.some((item) => item.id === focusState.value?.active_dataset_id)
        ? (focusState.value.active_dataset_id as string)
        : (preferredTepDataset.value?.id ?? graphs.datasets[0]?.id ?? '')

    selectedDatasetId.value = preferredDatasetId
    selectedCaseId.value = getDatasetCaseId(preferredDatasetId, focusState.value?.active_case_id ?? null)
    syncSelectionFromFocus()
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : 'failed to load graph/runtime data'
  } finally {
    loading.value = false
  }
}

function refreshSessionMeta() {
  sessionMeta.value = getLocalSessionMeta()
}

function refreshFocusState() {
  focusState.value = loadAnalysisFocus(analysisScope.value)
}

function handleSessionChange() {
  refreshSessionMeta()
  refreshFocusState()
  void hydrate()
}

function handleFocusChange(event: Event) {
  const customEvent = event as CustomEvent<{ sessionScope?: string }>

  if (customEvent.detail?.sessionScope && customEvent.detail.sessionScope !== analysisScope.value) {
    return
  }

  refreshFocusState()
  syncSelectionFromFocus()
}

function handleCaseChange(caseId: string | number | boolean) {
  selectedCaseId.value = String(caseId)
}

function handleCandidateSelect(candidateId: string) {
  selectedCandidateId.value = candidateId
  selectedPathIndex.value = 0
}

function clearCandidateHighlight() {
  selectedCandidateId.value = ''
  selectedPathIndex.value = 0
  clearAnalysisHighlight(analysisScope.value)
}

watch(
  activeDataset,
  (dataset) => {
    if (!dataset) {
      selectedCaseId.value = ''
      return
    }

    if (!casesForActiveDataset.value.some((item) => item.case_id === selectedCaseId.value)) {
      selectedCaseId.value = getDatasetCaseId(dataset.id, focusState.value?.active_case_id ?? null)
    }
  },
  { immediate: true },
)

watch(
  scoreRanking,
  (ranking) => {
    if (!ranking.length) {
      selectedCandidateId.value = ''
      selectedPathIndex.value = 0
      return
    }

    if (!ranking.some((item) => item.candidate_id === selectedCandidateId.value)) {
      selectedCandidateId.value = ranking[0].candidate_id
      selectedPathIndex.value = 0
    }
  },
  { immediate: true },
)

watch(activeCase, (caseItem) => {
  if (!caseItem) {
    return
  }

  saveAnalysisFocus(analysisScope.value, {
    active_case_id: caseItem.case_id,
    active_dataset_id: caseItem.graph_snapshot.dataset_id,
    selected_observation_id: null,
    selected_route1_path_ids: [],
    selected_route2_candidate_ids: [],
    highlighted_node_ids: [],
    highlighted_edge_ids: [],
    highlighted_obs_ids: [],
    focus_kind: 'case',
    focus_label: caseItem.case_label,
    source_view: 'graphs',
  })
})

watch(
  [selectedCandidate, highlightedNodeIds, highlightedEdgeIds],
  ([candidate, nodeIds, edgeIds]) => {
    if (!candidate || !activeCase.value) {
      return
    }

    saveAnalysisFocus(analysisScope.value, {
      active_case_id: activeCase.value.case_id,
      active_dataset_id: activeCase.value.graph_snapshot.dataset_id,
      selected_observation_id: null,
      selected_route1_path_ids: [],
      selected_route2_candidate_ids: [candidate.candidate_id],
      highlighted_node_ids: nodeIds,
      highlighted_edge_ids: edgeIds,
      highlighted_obs_ids: candidate.support_evidence_ids,
      focus_kind: 'route2-candidate',
      focus_label: candidate.candidate_name,
      source_view: 'graphs',
    })
  },
)

onMounted(() => {
  refreshSessionMeta()
  refreshFocusState()
  void hydrate()

  window.addEventListener(getLocalSessionEventName(), handleSessionChange)
  window.addEventListener(getAnalysisFocusEventName(), handleFocusChange)
})

onBeforeUnmount(() => {
  window.removeEventListener(getLocalSessionEventName(), handleSessionChange)
  window.removeEventListener(getAnalysisFocusEventName(), handleFocusChange)
})
</script>

<template>
  <div class="rl-page graphs-page">
    <div v-if="loading" class="graphs-loading">
      <a-spin tip="加载 TEP-KG 图谱与 RCA 数据中..." />
    </div>

    <a-alert
      v-else-if="errorMessage"
      type="error"
      show-icon
      :content="errorMessage"
    />

    <div v-else class="graphs-layout">
      <section class="graphs-main">
        <article class="rl-section-card graph-canvas-shell">
          <header class="rl-section-card__header graph-toolbar">
            <div class="graph-toolbar__left">
              <a-space>
                <div class="graph-selector">
                  <span class="graph-selector__label">RCA 图谱</span>
                  <a-select
                    v-model="selectedDatasetId"
                    size="small"
                    :style="{ width: '320px' }"
                  >
                    <a-option v-for="dataset in datasets" :key="dataset.id" :value="dataset.id">
                      {{ dataset.label }} · {{ dataset.nodes.length }}N/{{ dataset.edges.length }}E
                    </a-option>
                  </a-select>
                </div>
              </a-space>
            </div>

            <div class="graph-toolbar__right">
              <a-space>
                <a-input-search
                  v-model="searchTerm"
                  allow-clear
                  size="small"
                  placeholder="搜索节点..."
                />
                <a-switch v-model="showLabels" size="small">
                  <template #checked>标签开</template>
                  <template #unchecked>标签关</template>
                </a-switch>
              </a-space>
            </div>
          </header>

          <div class="rl-section-card__body graph-canvas-shell__body">
            <KnowledgeForceGraph
              v-if="activeDataset"
              :dataset="activeDataset"
              :show-labels="showLabels"
              :search-term="searchTerm"
              :focused-node-ids="highlightedNodeIds"
              :focused-edge-ids="highlightedEdgeIds"
            />
            <a-empty v-else description="当前没有可渲染图谱" />
          </div>
        </article>

        <article class="rl-section-card analysis-overview">
          <header class="rl-section-card__header analysis-overview__header">
            <h3 class="rl-section-card__title">RCA 计算链路状态</h3>
            <a-space>
              <a-select
                v-model="selectedCaseId"
                size="small"
                :style="{ width: '340px' }"
                :disabled="!casesForActiveDataset.length"
                @change="handleCaseChange"
              >
                <a-option v-for="item in casesForActiveDataset" :key="item.case_id" :value="item.case_id">
                  {{ item.case_label }} ({{ item.case_id }})
                </a-option>
              </a-select>
              <a-tag color="arcoblue">obs: {{ activeCase?.evidence.observations.length ?? 0 }}</a-tag>
              <a-tag color="green">Route2 候选: {{ scoreRanking.length }}</a-tag>
            </a-space>
          </header>
          <div class="rl-section-card__body analysis-overview__body">
            <p>
              链路：证据导入图谱 -> 图谱本地 RCA 计算 -> score 排行 -> 选择根因 -> 高亮传播路径。
            </p>
            <p v-if="!localAnalysis?.route2" class="analysis-overview__warn">
              当前 case 未生成 Route2 结果。请导入包含 `variable` observation 的 TEP evidence。
            </p>
          </div>
        </article>
      </section>

      <aside class="rl-section-card score-panel">
        <header class="rl-section-card__header score-panel__header">
          <h3 class="rl-section-card__title">Score 排行</h3>
          <a-button size="mini" @click="clearCandidateHighlight">清除高亮</a-button>
        </header>

        <div class="rl-section-card__body score-panel__body">
          <template v-if="!activeCase">
            <a-empty description="当前图谱暂无可分析 case" />
          </template>

          <template v-else-if="!scoreRanking.length">
            <a-empty description="Route2 暂无候选得分" />
          </template>

          <template v-else>
            <article
              v-for="candidate in scoreRanking"
              :key="candidate.candidate_id"
              class="score-item"
              :class="{ 'score-item--active': selectedCandidate?.candidate_id === candidate.candidate_id }"
              @click="handleCandidateSelect(candidate.candidate_id)"
            >
              <div class="score-item__row">
                <span class="score-item__rank">#{{ candidate.rank }}</span>
                <strong class="score-item__name">{{ candidate.candidate_name }}</strong>
              </div>
              <p class="score-item__meta">{{ candidate.candidate_type }} · {{ candidate.candidate_role }}</p>
              <p class="score-item__meta">
                ranking_score: {{ candidate.ranking_score.toFixed(4) }} · root_score:
                {{ candidate.root_score.toFixed(4) }}
              </p>
            </article>

            <div v-if="selectedCandidate" class="path-detail">
              <h4>传播路径</h4>
              <a-select
                v-model="selectedPathIndex"
                size="small"
                :style="{ width: '100%' }"
                :disabled="!propagationPathOptions.length"
              >
                <a-option
                  v-for="option in propagationPathOptions"
                  :key="option.value"
                  :value="option.value"
                >
                  {{ option.label }}
                </a-option>
              </a-select>

              <p v-if="selectedPropagationPath.length" class="path-detail__text">
                {{ selectedPropagationPath.join(' -> ') }}
              </p>
              <p v-else class="path-detail__text">当前候选没有可用传播路径。</p>
            </div>
          </template>
        </div>
      </aside>
    </div>
  </div>
</template>

<style scoped>
.graphs-loading {
  min-height: 420px;
  display: flex;
  align-items: center;
  justify-content: center;
}

.graphs-layout {
  display: grid;
  grid-template-columns: minmax(0, 1fr) 360px;
  gap: 12px;
  min-height: 720px;
}

.graphs-main {
  display: flex;
  flex-direction: column;
  gap: 12px;
  min-width: 0;
}

.graph-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.graph-selector {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.graph-selector__label {
  color: #4e5969;
  font-size: 12px;
}

.graph-canvas-shell__body {
  padding: 10px;
}

.graph-canvas-shell :deep(.knowledge-graph-chart) {
  height: 560px;
  border-radius: 10px;
  border: 1px solid #e5e6eb;
  background: #f8fbff;
}

.analysis-overview__header {
  align-items: flex-start;
}

.analysis-overview__body p {
  margin: 0;
  color: #4e5969;
  font-size: 13px;
  line-height: 1.6;
}

.analysis-overview__warn {
  margin-top: 8px !important;
  color: #c24f05 !important;
}

.score-panel__body {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 690px;
  overflow-y: auto;
}

.score-item {
  border: 1px solid #e5e6eb;
  border-radius: 10px;
  background: #fff;
  padding: 10px;
  cursor: pointer;
  transition: all 0.16s ease;
}

.score-item:hover {
  border-color: #3f7cff;
}

.score-item--active {
  border-color: #3f7cff;
  background: #f7faff;
  box-shadow: 0 0 0 1px rgba(63, 124, 255, 0.16);
}

.score-item__row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.score-item__rank {
  color: #1f58df;
  font-weight: 600;
}

.score-item__name {
  font-size: 14px;
}

.score-item__meta {
  margin: 5px 0 0;
  color: #4e5969;
  font-size: 12px;
  line-height: 1.5;
}

.path-detail {
  border: 1px solid #dfe3ea;
  border-radius: 10px;
  background: #fbfcff;
  padding: 10px;
}

.path-detail h4 {
  margin: 0 0 8px;
  font-size: 13px;
}

.path-detail__text {
  margin: 8px 0 0;
  color: #4e5969;
  font-size: 12px;
  line-height: 1.6;
}

@media (max-width: 1280px) {
  .graphs-layout {
    grid-template-columns: minmax(0, 1fr);
  }

  .score-panel__body {
    max-height: none;
  }
}
</style>
