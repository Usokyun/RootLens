<script setup lang="ts">
import { IconCheckCircle, IconRefresh, IconSend } from '@arco-design/web-vue/es/icon'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type { KGStudioGraphNode, KGStudioPayload, PathGraph, RankedRootCause, ReviewTarget, RunDetail, RunSummary } from '@/api/contracts'
import KnowledgeForceGraph from '@/components/graphs/KnowledgeForceGraph.vue'
import RunPathGraph from '@/components/graphs/RunPathGraph.vue'
import HoverInfoDock from '@/components/layout/HoverInfoDock.vue'
import WorkbenchHero from '@/components/layout/WorkbenchHero.vue'
import { useAppPreferences } from '@/services/app-preferences'
import { canSubmitReviewTargetType, getRootLensService } from '@/services/rootlens-service'
import { formatScoringMethodLabel } from '@/services/ui-copy'
import { useWorkbenchState } from '@/services/workbench-state'
import type { UnifiedGraphDataset, UnifiedGraphEdge, UnifiedGraphNode } from '@/types/graph'

const route = useRoute()
const router = useRouter()
const { preferences } = useAppPreferences()
const { state: workbenchState, updateState } = useWorkbenchState()

const loading = ref(false)
const runs = ref<RunSummary[]>([])
const runDetail = ref<RunDetail | null>(null)
const kgStudio = ref<KGStudioPayload | null>(null)
const errorMessage = ref('')
const reviewMessage = ref('')
const graphRenderMessage = ref('正在准备总图谱...')

const feedbackForm = reactive({
  reviewer: 'rootlens-frontend',
  action: 'accept' as 'accept' | 'reject',
  note: '',
  source: 'rootlens-graphs',
})

const activeCase = computed(() => {
  if (!runDetail.value) {
    return null
  }

  return runDetail.value.cases.find((item) => item.case_id === workbenchState.value.selectedCaseId) ?? runDetail.value.cases[0] ?? null
})

const activePathGraph = computed(() => activeCase.value?.path_graph ?? runDetail.value?.path_graph ?? null)

const activePath = computed(() => {
  const graph = activePathGraph.value
  if (!graph) {
    return null
  }

  return graph.paths.find((item) => item.path_id === workbenchState.value.selectedPathId) ?? graph.paths[0] ?? null
})

const activeCandidate = computed(() => {
  const list = activeCase.value?.ranked_root_causes ?? runDetail.value?.ranked_root_causes ?? []
  return list.find((item) => item.ranking_id === workbenchState.value.selectedCandidateId) ?? list[0] ?? null
})

const totalGraphDataset = computed<UnifiedGraphDataset | null>(() => {
  if (!kgStudio.value) {
    return null
  }

  const nodeSeed = new Map<string, KGStudioGraphNode>()
  for (const node of kgStudio.value.graph_nodes) {
    nodeSeed.set(node.node_id, node)
  }

  for (const edge of kgStudio.value.graph_edges) {
    if (!nodeSeed.has(edge.head)) {
      nodeSeed.set(edge.head, {
        node_id: edge.head,
        label: edge.head,
        node_type: 'Unknown',
        scenario: edge.scenario,
        description: edge.source,
      })
    }
    if (!nodeSeed.has(edge.tail)) {
      nodeSeed.set(edge.tail, {
        node_id: edge.tail,
        label: edge.tail,
        node_type: 'Unknown',
        scenario: edge.scenario,
        description: edge.source,
      })
    }
  }

  const inDegree = new Map<string, number>()
  const outDegree = new Map<string, number>()

  for (const edge of kgStudio.value.graph_edges) {
    outDegree.set(edge.head, (outDegree.get(edge.head) ?? 0) + 1)
    inDegree.set(edge.tail, (inDegree.get(edge.tail) ?? 0) + 1)
  }

  const nodes: UnifiedGraphNode[] = [...nodeSeed.values()].map((node) => ({
    id: node.node_id,
    name: node.label,
    category: node.scenario,
    kind: node.node_type,
    description: node.description,
    aliases: [],
    degree: (inDegree.get(node.node_id) ?? 0) + (outDegree.get(node.node_id) ?? 0),
    inDegree: inDegree.get(node.node_id) ?? 0,
    outDegree: outDegree.get(node.node_id) ?? 0,
    attributes: {
      scenario: node.scenario,
      node_type: node.node_type,
    },
    origin: {
      projectId: 'kg-studio',
      projectLabel: 'KG Studio',
      filePath: kgStudio.value?.nodes_path ?? 'kg-studio',
      layer: 'candidate-graph',
      rowNumber: 0,
    },
  }))

  const edges: UnifiedGraphEdge[] = kgStudio.value.graph_edges.map((edge) => ({
    id: edge.edge_id,
    source: edge.head,
    target: edge.tail,
    relation: edge.relation,
    category: edge.scenario,
    label: edge.relation,
    confidence: edge.confidence,
    weight: edge.weight,
    directed: true,
    attributes: {
      source: edge.source,
      evidence: edge.evidence,
      review_status: edge.review_status,
    },
    origin: {
      projectId: 'kg-studio',
      projectLabel: 'KG Studio',
      filePath: kgStudio.value?.edges_path ?? 'kg-studio',
      layer: 'candidate-graph',
      rowNumber: 0,
    },
  }))

  return {
    id: kgStudio.value.candidate_dir ?? 'kg-studio',
    label: '总图谱',
    description: kgStudio.value.note,
    graphKind: 'candidate-graph',
    projectRoot: kgStudio.value.candidate_dir ?? 'kg-studio',
    sourceFiles: [],
    nodes,
    edges,
    metadata: {
      status: kgStudio.value.status,
      claim_boundary: kgStudio.value.claim_boundary,
    },
  }
})

const focusedNodeIds = computed(() => {
  if (activePath.value?.nodes.length) {
    return activePath.value.nodes.map((item) => item.node_id)
  }

  if (activeCandidate.value?.candidate_id) {
    return [activeCandidate.value.candidate_id]
  }

  return []
})

const heroMetrics = computed(() => [
  {
    label: '总图谱节点',
    value: totalGraphDataset.value?.nodes.length ?? 0,
    hint: 'KG Studio 提供的全局候选图谱',
    tone: 'blue' as const,
  },
  {
    label: '路径数',
    value: activePathGraph.value?.path_count ?? 0,
    hint: '当前 case 的 path_graph 路径数',
    tone: 'teal' as const,
  },
  {
    label: '根因候选',
    value: activeCase.value?.ranked_root_causes?.length ?? 0,
    hint: '右侧常驻辅区中的候选根因数',
    tone: 'amber' as const,
  },
])

const workspaceTags = computed(() => [
  {
    label: preferences.value.dataSourceMode === 'backend' ? '后端模式' : '模拟模式',
    color: 'arcoblue' as const,
  },
  {
    label: activeCase.value?.dataset ?? runDetail.value?.run.dataset ?? '暂无案例',
    color: 'green' as const,
  },
  {
    label: activeCase.value?.case_label ?? activeCase.value?.case_id ?? '未选择案例',
    color: 'gold' as const,
  },
])

function normalizeText(value: unknown, fallback = '--') {
  return typeof value === 'string' && value.trim().length ? value.trim() : fallback
}

function formatScore(value: unknown) {
  return typeof value === 'number' ? value.toFixed(3) : '--'
}

function formatDateTime(value: string | undefined | null) {
  if (!value) {
    return '--'
  }

  const date = new Date(value)
  if (Number.isNaN(date.getTime())) {
    return value
  }

  return date.toLocaleString('zh-CN', { hour12: false })
}

function findBestPathForCandidateInGraph(candidate: RankedRootCause | null, graph: PathGraph | null | undefined) {
  if (!candidate || !graph) {
    return null
  }

  return (
    graph.paths.find((path) => path.target_entity_id === candidate.candidate_id) ??
    graph.paths.find((path) => path.path_id === candidate.ranking_id.replace(/^ranking:/, '')) ??
    graph.paths.find((path) =>
      path.nodes.some(
        (node) =>
          node.node_id === candidate.candidate_id ||
          node.label === candidate.candidate_name,
      ),
    ) ??
    graph.paths[0] ??
    null
  )
}

function findBestPathForCandidate(candidate: RankedRootCause | null) {
  return findBestPathForCandidateInGraph(candidate, activePathGraph.value)
}

function findReviewTargetInList(
  list: ReviewTarget[] | null | undefined,
  type: ReviewTarget['target_type'],
  targetId: string | null | undefined,
) {
  if (!list || !targetId) {
    return null
  }

  return list.find((item) => item.target_type === type && item.target_id === targetId) ?? null
}

function findReviewTarget(type: ReviewTarget['target_type'], targetId: string | null | undefined) {
  return findReviewTargetInList(activeCase.value?.review_targets ?? runDetail.value?.review_targets ?? [], type, targetId)
}

const candidateReviewTarget = computed(() => {
  return findReviewTarget('root_cause_candidate', activeCandidate.value?.ranking_id ?? activeCandidate.value?.candidate_id)
})

const pathReviewTarget = computed(() => {
  return findReviewTarget('path', activePath.value?.path_id)
})

const activeSubmitTarget = computed(() => {
  if (candidateReviewTarget.value && canSubmitReviewTargetType(candidateReviewTarget.value.target_type)) {
    return candidateReviewTarget.value
  }

  if (pathReviewTarget.value && canSubmitReviewTargetType(pathReviewTarget.value.target_type)) {
    return pathReviewTarget.value
  }

  return (activeCase.value?.review_targets ?? []).find((item) => canSubmitReviewTargetType(item.target_type)) ?? null
})

function buildCaseSelection(detail: RunDetail, caseId: string | null) {
  const nextCase =
    detail.cases.find((item) => item.case_id === caseId) ??
    detail.cases[0] ??
    null

  const nextCandidate =
    nextCase?.ranked_root_causes?.[0] ??
    detail.ranked_root_causes[0] ??
    null

  const nextPathGraph = nextCase?.path_graph ?? detail.path_graph ?? null
  const nextPath =
    findBestPathForCandidateInGraph(nextCandidate, nextPathGraph) ??
    nextPathGraph?.paths[0] ??
    null

  const reviewTargets = nextCase?.review_targets ?? detail.review_targets ?? []
  const nextReviewTarget =
    findReviewTargetInList(
      reviewTargets,
      'root_cause_candidate',
      nextCandidate?.ranking_id ?? nextCandidate?.candidate_id,
    ) ??
    findReviewTargetInList(reviewTargets, 'path', nextPath?.path_id)

  return {
    selectedCaseId: nextCase?.case_id ?? null,
    selectedCandidateId: nextCandidate?.ranking_id ?? null,
    selectedPathId: nextPath?.path_id ?? null,
    selectedReviewTargetKey: nextReviewTarget?.target_key ?? null,
  }
}

function syncRouteQuery(runId: string | null, caseId: string | null) {
  const nextQuery = {
    ...route.query,
    run_id: runId ?? undefined,
    case_id: caseId ?? undefined,
  }

  const currentRunId = typeof route.query.run_id === 'string' ? route.query.run_id : null
  const currentCaseId = typeof route.query.case_id === 'string' ? route.query.case_id : null

  if (currentRunId === runId && currentCaseId === caseId) {
    return
  }

  void router.replace({
    query: nextQuery,
  })
}

function selectCandidate(candidateId: string) {
  const list = activeCase.value?.ranked_root_causes ?? []
  const candidate = list.find((item) => item.ranking_id === candidateId) ?? null
  const matchedPath = findBestPathForCandidate(candidate)
  const reviewTargets = activeCase.value?.review_targets ?? runDetail.value?.review_targets ?? []
  const matchedCandidateTarget =
    findReviewTargetInList(reviewTargets, 'root_cause_candidate', candidateId) ??
    findReviewTargetInList(reviewTargets, 'root_cause_candidate', candidate?.candidate_id)

  updateState({
    selectedCandidateId: candidateId,
    selectedPathId: matchedPath?.path_id ?? workbenchState.value.selectedPathId,
    selectedReviewTargetKey:
      matchedCandidateTarget?.target_key ??
      findReviewTargetInList(reviewTargets, 'path', matchedPath?.path_id)?.target_key ??
      null,
  })
}

function handlePathSelect(pathId: string) {
  const matchedTarget = findReviewTarget('path', pathId)
  updateState({
    selectedPathId: pathId,
    selectedReviewTargetKey: matchedTarget?.target_key ?? null,
  })
}

function handleRunChange(value: unknown) {
  const runId = typeof value === 'string' && value.trim().length ? value : null
  if (!runId) {
    return
  }

  void loadRun(runId)
}

function handleCaseChange(value: unknown) {
  if (!runDetail.value) {
    return
  }

  const caseId = typeof value === 'string' && value.trim().length ? value : null
  const nextSelection = buildCaseSelection(runDetail.value, caseId)

  updateState(nextSelection)
  syncRouteQuery(runDetail.value.run.run_id, nextSelection.selectedCaseId)
}

function syncQueryContext() {
  const runId = typeof route.query.run_id === 'string' ? route.query.run_id : null
  const caseId = typeof route.query.case_id === 'string' ? route.query.case_id : null

  if (runId || caseId) {
    updateState({
      selectedRunId: runId ?? workbenchState.value.selectedRunId,
      selectedCaseId: caseId ?? workbenchState.value.selectedCaseId,
    })
  }
}

async function loadRun(runId: string) {
  loading.value = true
  errorMessage.value = ''

  try {
    const detail = await getRootLensService().getRun(runId)
    runDetail.value = detail

    const routeCaseId = typeof route.query.case_id === 'string' ? route.query.case_id : workbenchState.value.selectedCaseId
    const nextSelection = buildCaseSelection(detail, routeCaseId)
    updateState({
      selectedRunId: runId,
      ...nextSelection,
    })
    syncRouteQuery(runId, nextSelection.selectedCaseId)
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
    const [runsResult, graphResult] = await Promise.allSettled([
      getRootLensService().listRuns(),
      getRootLensService().kgStudio(),
    ])

    if (runsResult.status === 'fulfilled') {
      runs.value = runsResult.value
    } else {
      throw runsResult.reason
    }

    if (graphResult.status === 'fulfilled') {
      kgStudio.value = graphResult.value
    } else {
      kgStudio.value = null
    }

    const routeRunId = typeof route.query.run_id === 'string' ? route.query.run_id : null
    const nextRunId =
      runs.value.find((item) => item.run_id === routeRunId)?.run_id ??
      runs.value.find((item) => item.run_id === workbenchState.value.selectedRunId)?.run_id ??
      runs.value[0]?.run_id ??
      null

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

async function handleFeedbackSubmit() {
  if (!activeCase.value || !activeSubmitTarget.value) {
    reviewMessage.value = '当前没有可提交的反馈目标。'
    return
  }

  errorMessage.value = ''
  reviewMessage.value = ''

  try {
    const response = await getRootLensService().submitReview({
      run_id: runDetail.value?.run.run_id,
      case_id: activeCase.value.case_id,
      target_type: activeSubmitTarget.value.target_type,
      target_id: activeSubmitTarget.value.target_id,
      action: feedbackForm.action,
      note: feedbackForm.note,
      reviewer: feedbackForm.reviewer,
      source: feedbackForm.source,
    })

    reviewMessage.value = `反馈已记录：${String(response.record.feedback_id ?? response.status)}`
  } catch (error) {
    errorMessage.value = error instanceof Error ? error.message : String(error)
  }
}

watch(
  () => [preferences.value.dataSourceMode, preferences.value.apiBaseUrl],
  () => {
    void refreshWorkspace()
  },
)

watch(
  () => route.query,
  () => {
    syncQueryContext()
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
  () => activeCase.value?.case_id,
  (caseId, previousCaseId) => {
    if (!runDetail.value || !caseId || caseId === previousCaseId) {
      return
    }

    const nextSelection = buildCaseSelection(runDetail.value, caseId)

    if (
      nextSelection.selectedCandidateId !== workbenchState.value.selectedCandidateId ||
      nextSelection.selectedPathId !== workbenchState.value.selectedPathId ||
      nextSelection.selectedReviewTargetKey !== workbenchState.value.selectedReviewTargetKey
    ) {
      updateState({
        ...nextSelection,
      })
    }

    syncRouteQuery(runDetail.value.run.run_id, caseId)
  },
)

onMounted(() => {
  syncQueryContext()
  void refreshWorkspace()
})
</script>

<template>
  <div class="rl-page rl-screen" :class="{ 'rl-page--motion': preferences.enablePageEntranceMotion }">
    <WorkbenchHero
      eyebrow="图谱探索"
      title="总图谱、子图与反馈卡"
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
        <a-button size="small" @click="router.push({ name: 'evidence' })">返回证据与审阅</a-button>
      </template>
    </WorkbenchHero>

    <a-alert v-if="errorMessage" class="rl-alert" type="error" :title="errorMessage" />

    <section class="workspace-shell">
      <div class="workspace-shell__main workspace-stack">
        <article class="rl-section-card">
          <header class="rl-section-card__header">
            <div>
              <h3 class="rl-section-card__title">总图谱</h3>
              <p class="rl-section-card__desc">基于 KG Studio 数据渲染总图谱，并跟随当前候选和 path_graph 做高亮。</p>
            </div>
            <div class="rl-inline-tags">
              <a-tag color="green">{{ totalGraphDataset?.nodes.length ?? 0 }} 节点</a-tag>
              <a-tag color="gold">{{ totalGraphDataset?.edges.length ?? 0 }} 边</a-tag>
            </div>
          </header>
          <div class="rl-section-card__body workspace-graph-stage">
            <KnowledgeForceGraph
              v-if="totalGraphDataset"
              :dataset="totalGraphDataset"
              :show-labels="false"
              :search-term="activeCandidate?.candidate_name ?? ''"
              :focused-node-ids="focusedNodeIds"
              @render-state="(payload) => (graphRenderMessage = payload.message)"
            />
            <a-empty v-else>暂无总图谱数据</a-empty>
          </div>
          <div class="rl-section-card__footer">
            <span class="workspace-subtle">{{ graphRenderMessage }}</span>
          </div>
        </article>

        <section class="workspace-bottom-grid">
          <article class="rl-section-card">
            <header class="rl-section-card__header">
              <div>
                <h3 class="rl-section-card__title">path_graph 子图</h3>
                <p class="rl-section-card__desc">仅显示当前 case 的解释子图，并与右侧根因列表联动。</p>
              </div>
              <a-tag color="arcoblue">{{ activePathGraph?.path_count ?? 0 }} 条路径</a-tag>
            </header>
            <div class="rl-section-card__body workspace-path-stage">
              <RunPathGraph
                v-if="activePathGraph"
                :path-graph="activePathGraph"
                :selected-path-id="activePath?.path_id ?? null"
                @select-path="handlePathSelect"
              />
              <a-empty v-else>暂无子图</a-empty>
            </div>
          </article>

          <article class="rl-section-card">
            <header class="rl-section-card__header">
              <div>
                <h3 class="rl-section-card__title">反馈卡</h3>
                <p class="rl-section-card__desc">反馈结果直接集成在这张卡里，不再拆分到独立结果区。</p>
              </div>
              <a-tag color="gold">{{ activeSubmitTarget?.label ?? '暂无目标' }}</a-tag>
            </header>
            <div class="rl-section-card__body workspace-stack">
              <div class="workspace-summary-list">
                <div class="workspace-summary-list__item">
                  <span>当前候选</span>
                  <strong>{{ activeCandidate?.candidate_name ?? '--' }}</strong>
                </div>
                <div class="workspace-summary-list__item">
                  <span>当前路径</span>
                  <strong>{{ activePath?.path_id ?? '--' }}</strong>
                </div>
                <div class="workspace-summary-list__item">
                  <span>反馈目标</span>
                  <strong>{{ activeSubmitTarget?.target_type ?? '--' }}</strong>
                </div>
                <div class="workspace-summary-list__item">
                  <span>得分</span>
                  <strong>{{ formatScore(activeCandidate?.score) }}</strong>
                </div>
              </div>

              <div class="workspace-segmented-actions">
                <button
                  type="button"
                  class="workspace-segmented-actions__item"
                  :class="{ 'workspace-segmented-actions__item--active': feedbackForm.action === 'accept' }"
                  @click="feedbackForm.action = 'accept'"
                >
                  接受
                </button>
                <button
                  type="button"
                  class="workspace-segmented-actions__item"
                  :class="{ 'workspace-segmented-actions__item--active workspace-segmented-actions__item--danger': feedbackForm.action === 'reject' }"
                  @click="feedbackForm.action = 'reject'"
                >
                  拒绝
                </button>
              </div>

              <div class="rl-form-field">
                <span>备注</span>
                <a-textarea v-model="feedbackForm.note" :auto-size="{ minRows: 6, maxRows: 8 }" placeholder="记录你的审阅判断和上下文。" />
              </div>

              <div class="workspace-feedback-footer">
                <a-button type="primary" @click="handleFeedbackSubmit">
                  <template #icon>
                    <icon-send />
                  </template>
                  提交反馈
                </a-button>
              </div>

              <div class="workspace-feedback-result" :class="{ 'workspace-feedback-result--success': !!reviewMessage }">
                <div class="workspace-feedback-result__header">
                  <icon-check-circle v-if="reviewMessage" />
                  <strong>{{ reviewMessage || '等待提交反馈' }}</strong>
                </div>
                <div class="workspace-feedback-result__meta">
                  <span>最近动作：{{ feedbackForm.action === 'accept' ? '接受' : '拒绝' }}</span>
                  <span>提交人：{{ feedbackForm.reviewer }}</span>
                  <span>时间：{{ reviewMessage ? formatDateTime(new Date().toISOString()) : '--' }}</span>
                </div>
              </div>
            </div>
          </article>
        </section>
      </div>

      <aside class="workspace-shell__aside">
        <article class="rl-section-card workspace-aside-card--compact">
          <header class="rl-section-card__header">
            <div>
              <h3 class="rl-section-card__title">紧凑上下文</h3>
              <p class="rl-section-card__desc">上下文条被收进右侧常驻辅区顶部。</p>
            </div>
          </header>
          <div class="rl-section-card__body workspace-stack workspace-stack--tight">
            <div class="rl-form-field">
              <span>Run</span>
              <a-select :model-value="runDetail?.run.run_id" @change="handleRunChange">
                <a-option v-for="run in runs" :key="run.run_id" :value="run.run_id">
                  {{ run.label }}
                </a-option>
              </a-select>
            </div>
            <div class="rl-form-field">
              <span>Case</span>
              <a-select :model-value="activeCase?.case_id" @change="handleCaseChange">
                <a-option v-for="caseItem in runDetail?.cases ?? []" :key="caseItem.case_id" :value="caseItem.case_id">
                  {{ caseItem.case_label ?? caseItem.case_id }}
                </a-option>
              </a-select>
            </div>
            <div class="workspace-summary-list">
              <div class="workspace-summary-list__item">
                <span>Dataset</span>
                <strong>{{ activeCase?.dataset ?? '--' }}</strong>
              </div>
              <div class="workspace-summary-list__item">
                <span>反馈状态</span>
                <strong>{{ reviewMessage ? '已记录' : '待审阅' }}</strong>
              </div>
            </div>
          </div>
        </article>

        <article class="rl-section-card">
          <header class="rl-section-card__header">
            <div>
              <h3 class="rl-section-card__title">根因列表</h3>
              <p class="rl-section-card__desc">点击候选后同步高亮总图谱和 path_graph。</p>
            </div>
            <a-tag color="green">{{ activeCase?.ranked_root_causes?.length ?? 0 }}</a-tag>
          </header>
          <div class="rl-section-card__body workspace-stack workspace-stack--tight">
            <button
              v-for="candidate in activeCase?.ranked_root_causes ?? []"
              :key="candidate.ranking_id"
              type="button"
              class="workspace-list-item"
              :class="{ 'workspace-list-item--active': candidate.ranking_id === activeCandidate?.ranking_id }"
              @click="selectCandidate(candidate.ranking_id)"
            >
              <div class="workspace-list-item__head">
                <strong>#{{ candidate.rank }} {{ candidate.candidate_name }}</strong>
                <span>{{ formatScore(candidate.score) }}</span>
              </div>
              <div class="workspace-list-item__meta">
                <span>{{ formatScoringMethodLabel(candidate.scoring_method) }}</span>
                <span>{{ normalizeText(candidate.candidate_role, 'candidate') }}</span>
              </div>
            </button>
            <a-empty v-if="!(activeCase?.ranked_root_causes?.length)">暂无候选根因</a-empty>
          </div>
        </article>
      </aside>

      <HoverInfoDock title="图谱提示" label="GRAPH" subtitle="额外信息挂件，用于放统计、provenance 和风险提示。" tone="teal">
        <div class="workspace-summary-list">
          <div class="workspace-summary-list__item">
            <span>图谱节点</span>
            <strong>{{ totalGraphDataset?.nodes.length ?? 0 }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span>图谱边数</span>
            <strong>{{ totalGraphDataset?.edges.length ?? 0 }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span>Path 边数</span>
            <strong>{{ activePath?.edges.length ?? 0 }}</strong>
          </div>
          <div class="workspace-summary-list__item">
            <span>可视证据</span>
            <strong>{{ activeCase?.visual_evidence?.length ?? 0 }}</strong>
          </div>
        </div>
      </HoverInfoDock>
    </section>
  </div>
</template>
