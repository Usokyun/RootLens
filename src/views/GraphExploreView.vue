<script setup lang="ts">
import { IconBulb, IconCheckCircle, IconInfoCircle, IconRefresh, IconRelation, IconSave, IconSend, IconStorage } from '@arco-design/web-vue/es/icon'
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'

import type { KGStudioGraphNode, KGStudioPayload, RunDetail, RunSummary } from '@/api/contracts'
import KnowledgeForceGraph from '@/components/graphs/KnowledgeForceGraph.vue'
import RunPathGraph from '@/components/graphs/RunPathGraph.vue'
import WorkbenchHero from '@/components/layout/WorkbenchHero.vue'
import { type GraphCurationDecision, applyGraphCurationToDataset, areGraphCurationDraftsEqual, buildEmptyGraphCurationCaseDraft, buildNeighborhoodSubgraphDataset, buildPathSubgraphDataset, loadGraphCurationCaseDraft, replaceGraphEdgeDraft, replaceGraphNodeDraft, resetGraphCurationCaseDraft, saveGraphCurationCaseDraft, type MockGraphCurationCaseDraft, type MockGraphEdgeDraft, type MockGraphNodeDraft } from '@/services/graph-curation'
import { useAppPreferences } from '@/services/app-preferences'
import {
  buildCandidateSelectionPatch,
  buildLocalGraphSelectionPatch,
  buildTotalGraphSelectionPatch,
  findBestPathForCandidateInGraph,
  findReviewTargetInList,
  resolveSelectedRootCause,
} from '@/services/graph-explore-selection'
import { loadBundledUnifiedGraphs } from '@/services/rootlens-data'
import { canSubmitReviewTargetType, getRootLensService } from '@/services/rootlens-service'
import { formatScoringMethodLabel } from '@/services/ui-copy'
import { useWorkbenchState } from '@/services/workbench-state'
import type { UnifiedGraphDataset, UnifiedGraphEdge, UnifiedGraphNode } from '@/types/graph'

type GraphSelectPayload =
  | { type: 'node'; item: UnifiedGraphNode }
  | { type: 'edge'; item: UnifiedGraphEdge }
  | null

type LocalGraphSelectPayload =
  | { type: 'node'; id: string }
  | { type: 'edge'; id: string }
  | null

interface CurationSuggestion {
  id: string
  kind: 'node' | 'edge'
  label: string
  subtitle: string
}

const route = useRoute()
const router = useRouter()
const { preferences } = useAppPreferences()
const { state: workbenchState, updateState } = useWorkbenchState()

const loading = ref(false)
const runs = ref<RunSummary[]>([])
const runDetail = ref<RunDetail | null>(null)
const kgStudio = ref<KGStudioPayload | null>(null)
const bundledGraphDatasets = ref<UnifiedGraphDataset[]>([])
const errorMessage = ref('')
const reviewMessage = ref('')
const totalGraphRenderMessage = ref('正在准备总图谱...')
const localGraphRenderMessage = ref('正在准备局部子图...')
const actionMessage = ref('')
const feedbackCardTab = ref<'rca' | 'curation'>('rca')
const savedCaseDrafts = ref<Record<string, MockGraphCurationCaseDraft>>({})
const workingCaseDrafts = ref<Record<string, MockGraphCurationCaseDraft>>({})

const feedbackForm = reactive({
  reviewer: 'rootlens-frontend',
  action: 'accept' as 'accept' | 'reject',
  note: '',
  source: 'rootlens-graphs',
})

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function normalizeText(value: unknown, fallback = '--') {
  return typeof value === 'string' && value.trim().length ? value.trim() : fallback
}

function normalizeNullableText(value: unknown) {
  return typeof value === 'string' && value.trim().length ? value.trim() : null
}

function parseAliasInput(value: string) {
  const aliases = value
    .split(',')
    .map((item) => item.trim())
    .filter((item) => item.length)

  return aliases.length ? [...new Set(aliases)] : null
}

function formatAliasInput(value: string[] | null | undefined) {
  return value?.length ? value.join(', ') : ''
}

function formatScore(value: unknown) {
  return typeof value === 'number' ? value.toFixed(3) : '--'
}

function readStringAttribute(attributes: Record<string, unknown> | undefined, key: string) {
  if (!attributes) {
    return null
  }

  const value = attributes[key]
  return typeof value === 'string' && value.trim().length ? value.trim() : null
}

function edgeDecisionFromReviewStatus(edge: UnifiedGraphEdge | null) {
  const reviewStatus = readStringAttribute(edge?.attributes, 'review_status')
  if (reviewStatus === 'reviewed') {
    return 'accept' as const
  }
  if (reviewStatus === 'rejected') {
    return 'reject' as const
  }
  if (reviewStatus === 'needs_completion') {
    return 'needs_completion' as const
  }
  return 'revise' as const
}

function resolveBundledDatasetId(dataset: string | null | undefined) {
  const normalized = typeof dataset === 'string' ? dataset.toLowerCase() : ''
  if (normalized.includes('tep')) {
    return 'tep-kg'
  }
  return 'mvtec-project'
}


function buildKGStudioDataset(payload: KGStudioPayload | null): UnifiedGraphDataset | null {
  if (!payload) {
    return null
  }

  const nodeSeed = new Map<string, KGStudioGraphNode>()
  for (const node of payload.graph_nodes) {
    nodeSeed.set(node.node_id, node)
  }

  for (const edge of payload.graph_edges) {
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

  for (const edge of payload.graph_edges) {
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
      filePath: payload.nodes_path ?? 'kg-studio',
      layer: 'candidate-graph',
      rowNumber: 0,
    },
  }))

  const edges: UnifiedGraphEdge[] = payload.graph_edges.map((edge) => ({
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
      target_key: edge.edge_id,
    },
    origin: {
      projectId: 'kg-studio',
      projectLabel: 'KG Studio',
      filePath: payload.edges_path ?? 'kg-studio',
      layer: 'candidate-graph',
      rowNumber: 0,
    },
  }))

  return {
    id: payload.candidate_dir ?? 'kg-studio',
    label: '总图谱',
    description: payload.note,
    graphKind: 'candidate-graph',
    projectRoot: payload.candidate_dir ?? 'kg-studio',
    sourceFiles: [],
    nodes,
    edges,
    metadata: {
      status: payload.status,
      claim_boundary: payload.claim_boundary,
    },
  }
}

function ensureCaseDraftLoaded(caseId: string) {
  if (!savedCaseDrafts.value[caseId]) {
    const loaded = loadGraphCurationCaseDraft(caseId)
    savedCaseDrafts.value = {
      ...savedCaseDrafts.value,
      [caseId]: deepClone(loaded),
    }
    workingCaseDrafts.value = {
      ...workingCaseDrafts.value,
      [caseId]: deepClone(loaded),
    }
  }
}

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
  return resolveSelectedRootCause(list, workbenchState.value.selectedCandidateId)
})

const activeSavedCaseDraft = computed(() => {
  const caseId = activeCase.value?.case_id
  return caseId ? savedCaseDrafts.value[caseId] ?? null : null
})

const activeWorkingCaseDraft = computed(() => {
  const caseId = activeCase.value?.case_id
  return caseId ? workingCaseDrafts.value[caseId] ?? null : null
})

const baseTotalGraphDataset = computed<UnifiedGraphDataset | null>(() => {
  if (preferences.value.dataSourceMode === 'backend') {
    return buildKGStudioDataset(kgStudio.value)
  }

  const datasetId = resolveBundledDatasetId(activeCase.value?.dataset ?? runDetail.value?.run.dataset ?? null)
  return bundledGraphDatasets.value.find((dataset) => dataset.id === datasetId) ?? bundledGraphDatasets.value[0] ?? null
})

const totalGraphDataset = computed<UnifiedGraphDataset | null>(() => {
  const dataset = baseTotalGraphDataset.value
  if (!dataset) {
    return null
  }

  return applyGraphCurationToDataset(dataset, activeWorkingCaseDraft.value)
})

const pathSubgraphDataset = computed<UnifiedGraphDataset | null>(() => {
  if (!activePathGraph.value) {
    return null
  }

  const dataset = buildPathSubgraphDataset(activePathGraph.value)
  return applyGraphCurationToDataset(dataset, activeWorkingCaseDraft.value)
})

const neighborhoodGraphDataset = computed<UnifiedGraphDataset | null>(() => {
  if (!totalGraphDataset.value || !workbenchState.value.selectedGraphNodeId) {
    return null
  }

  return buildNeighborhoodSubgraphDataset(totalGraphDataset.value, workbenchState.value.selectedGraphNodeId)
})

const activeSubgraphMode = computed(() => {
  if (workbenchState.value.subgraphMode === 'neighborhood' && neighborhoodGraphDataset.value) {
    return 'neighborhood' as const
  }
  return 'path' as const
})

const activeLocalGraphDataset = computed(() => {
  if (activeSubgraphMode.value === 'neighborhood') {
    return neighborhoodGraphDataset.value
  }
  return pathSubgraphDataset.value
})

const selectedGraphNode = computed(() => {
  if (!totalGraphDataset.value || !workbenchState.value.selectedGraphNodeId) {
    return null
  }

  return totalGraphDataset.value.nodes.find((node) => node.id === workbenchState.value.selectedGraphNodeId) ?? null
})

const activeCurationNode = computed(() => {
  if (!activeLocalGraphDataset.value || !workbenchState.value.selectedSubgraphNodeId) {
    return null
  }

  return activeLocalGraphDataset.value.nodes.find((node) => node.id === workbenchState.value.selectedSubgraphNodeId) ?? null
})

const activeCurationEdge = computed(() => {
  if (!activeLocalGraphDataset.value || !workbenchState.value.selectedSubgraphEdgeId) {
    return null
  }

  return activeLocalGraphDataset.value.edges.find((edge) => edge.id === workbenchState.value.selectedSubgraphEdgeId) ?? null
})

const selectedEdgeDraft = computed(() => {
  if (!activeWorkingCaseDraft.value || !workbenchState.value.selectedSubgraphEdgeId) {
    return null
  }

  return activeWorkingCaseDraft.value.edge_drafts.find((draft) => draft.edge_id === workbenchState.value.selectedSubgraphEdgeId) ?? null
})

const selectedNodeDraft = computed(() => {
  if (!activeWorkingCaseDraft.value || !workbenchState.value.selectedSubgraphNodeId) {
    return null
  }

  return activeWorkingCaseDraft.value.node_drafts.find((draft) => draft.node_id === workbenchState.value.selectedSubgraphNodeId) ?? null
})

const activeCurationSuggestions = computed<CurationSuggestion[]>(() => {
  const draft = activeWorkingCaseDraft.value
  if (!draft) {
    return []
  }

  const edgeSuggestions = draft.edge_drafts.map((item) => ({
    id: item.edge_id,
    kind: 'edge' as const,
    label: item.relation ?? item.edge_id,
    subtitle: `${item.review_decision} · ${normalizeText(item.note, '点击进入边策展')}`,
  }))

  const nodeSuggestions = draft.node_drafts.map((item) => ({
    id: item.node_id,
    kind: 'node' as const,
    label: item.display_name ?? item.node_id,
    subtitle: normalizeText(item.note, '点击进入节点策展'),
  }))

  return [...edgeSuggestions, ...nodeSuggestions]
})

const activeSubmitTarget = computed(() => {
  const reviewTargets = activeCase.value?.review_targets ?? runDetail.value?.review_targets ?? []
  const candidateTarget =
    findReviewTargetInList(
      reviewTargets,
      'root_cause_candidate',
      activeCandidate.value?.ranking_id ?? activeCandidate.value?.candidate_id,
    ) ?? null
  const pathTarget = findReviewTargetInList(reviewTargets, 'path', activePath.value?.path_id) ?? null

  if (candidateTarget && canSubmitReviewTargetType(candidateTarget.target_type)) {
    return candidateTarget
  }

  if (pathTarget && canSubmitReviewTargetType(pathTarget.target_type)) {
    return pathTarget
  }

  return reviewTargets.find((item) => canSubmitReviewTargetType(item.target_type)) ?? null
})

const totalGraphFocusedNodeIds = computed(() => {
  const ids = new Set<string>()

  if (workbenchState.value.selectedGraphNodeId) {
    ids.add(workbenchState.value.selectedGraphNodeId)
  }
  if (workbenchState.value.selectedSubgraphNodeId) {
    ids.add(workbenchState.value.selectedSubgraphNodeId)
  }

  return [...ids]
})

const totalGraphFocusedEdgeIds = computed(() => {
  const ids = new Set<string>()

  if (workbenchState.value.selectedSubgraphEdgeId) {
    ids.add(workbenchState.value.selectedSubgraphEdgeId)
  }

  return [...ids]
})

const localGraphFocusedNodeIds = computed(() => {
  const ids = new Set<string>()

  if (workbenchState.value.selectedGraphNodeId) {
    ids.add(workbenchState.value.selectedGraphNodeId)
  }
  if (workbenchState.value.selectedSubgraphNodeId) {
    ids.add(workbenchState.value.selectedSubgraphNodeId)
  }

  return [...ids]
})

const localGraphFocusedEdgeIds = computed(() => {
  const ids = new Set<string>()

  if (workbenchState.value.selectedSubgraphEdgeId) {
    ids.add(workbenchState.value.selectedSubgraphEdgeId)
  }

  return [...ids]
})

const heroMetrics = computed(() => [
  {
    label: '总图谱节点',
    value: totalGraphDataset.value?.nodes.length ?? 0,
    hint: preferences.value.dataSourceMode === 'backend' ? 'KG Studio 返回的总图节点数' : '论文演示静态 RCA graph 节点数',
    tone: 'blue' as const,
  },
  {
    label: '局部子图边',
    value: activeLocalGraphDataset.value?.edges.length ?? 0,
    hint: activeSubgraphMode.value === 'neighborhood' ? '当前选中节点的一阶邻域边数' : '当前 case path_graph union 边数',
    tone: 'teal' as const,
  },
  {
    label: '根因候选',
    value: activeCase.value?.ranked_root_causes?.length ?? 0,
    hint: '右侧候选会同步驱动图谱联动',
    tone: 'amber' as const,
  },
])

const workspaceTags = computed(() => [
  {
    label: preferences.value.dataSourceMode === 'backend' ? '后端模式' : '论文 Mock 模式',
    color: 'arcoblue' as const,
  },
  {
    label: activeCase.value?.dataset ?? runDetail.value?.run.dataset ?? '暂无案例',
    color: 'green' as const,
  },
  {
    label: activeSubgraphMode.value === 'neighborhood' ? '邻域子图' : '路径子图',
    color: 'gold' as const,
  },
])

const hasUnsavedCurationChanges = computed(() => {
  if (!activeCase.value) {
    return false
  }

  return !areGraphCurationDraftsEqual(activeWorkingCaseDraft.value, activeSavedCaseDraft.value)
})

const canRevertCurrentSelection = computed(() => {
  if (activeCurationEdge.value) {
    const savedDraft = activeSavedCaseDraft.value?.edge_drafts.find((draft) => draft.edge_id === activeCurationEdge.value?.id) ?? null
    return !areGraphCurationDraftsEqual(
      {
        case_id: activeCase.value?.case_id ?? 'current',
        edge_drafts: selectedEdgeDraft.value ? [selectedEdgeDraft.value] : [],
        node_drafts: [],
      },
      {
        case_id: activeCase.value?.case_id ?? 'current',
        edge_drafts: savedDraft ? [savedDraft] : [],
        node_drafts: [],
      },
    )
  }

  if (activeCurationNode.value) {
    const savedDraft = activeSavedCaseDraft.value?.node_drafts.find((draft) => draft.node_id === activeCurationNode.value?.id) ?? null
    return !areGraphCurationDraftsEqual(
      {
        case_id: activeCase.value?.case_id ?? 'current',
        edge_drafts: [],
        node_drafts: selectedNodeDraft.value ? [selectedNodeDraft.value] : [],
      },
      {
        case_id: activeCase.value?.case_id ?? 'current',
        edge_drafts: [],
        node_drafts: savedDraft ? [savedDraft] : [],
      },
    )
  }

  return false
})

const localGraphDescription = computed(() => {
  if (activeSubgraphMode.value === 'neighborhood') {
    return selectedGraphNode.value
      ? `当前展示 ${selectedGraphNode.value.name} 的一阶父子邻域；局部子图中的节点和边可单独选中，点击空白或再次点击当前项可取消局部选择。`
      : '当前展示总图节点的一阶邻域。'
  }

  return '默认展示当前 case 的 path_graph union 子图；点击总图节点可切换为邻域子图。'
})

const edgeDecisionModel = computed<GraphCurationDecision>({
  get() {
    return selectedEdgeDraft.value?.review_decision ?? edgeDecisionFromReviewStatus(activeCurationEdge.value)
  },
  set(value) {
    updateSelectedEdgeDraft({
      review_decision: value,
    })
  },
})

const edgeRelationModel = computed({
  get() {
    return selectedEdgeDraft.value?.relation ?? activeCurationEdge.value?.relation ?? ''
  },
  set(value: string) {
    updateSelectedEdgeDraft({
      relation: normalizeNullableText(value),
    })
  },
})

const edgeConfidenceModel = computed<number | undefined>({
  get() {
    const currentValue = selectedEdgeDraft.value?.confidence ?? activeCurationEdge.value?.confidence ?? null
    return typeof currentValue === 'number' ? currentValue : undefined
  },
  set(value) {
    updateSelectedEdgeDraft({
      confidence: typeof value === 'number' ? value : null,
    })
  },
})

const edgeNoteModel = computed({
  get() {
    return selectedEdgeDraft.value?.note ?? ''
  },
  set(value: string) {
    updateSelectedEdgeDraft({
      note: normalizeNullableText(value),
    })
  },
})

const nodeDisplayNameModel = computed({
  get() {
    return selectedNodeDraft.value?.display_name ?? activeCurationNode.value?.name ?? ''
  },
  set(value: string) {
    updateSelectedNodeDraft({
      display_name: normalizeNullableText(value),
    })
  },
})

const nodeAliasesModel = computed({
  get() {
    return formatAliasInput(selectedNodeDraft.value?.aliases ?? activeCurationNode.value?.aliases ?? null)
  },
  set(value: string) {
    updateSelectedNodeDraft({
      aliases: parseAliasInput(value),
    })
  },
})

const nodeDescriptionModel = computed({
  get() {
    return selectedNodeDraft.value?.description ?? activeCurationNode.value?.description ?? ''
  },
  set(value: string) {
    updateSelectedNodeDraft({
      description: normalizeNullableText(value),
    })
  },
})

const nodeNoteModel = computed({
  get() {
    return selectedNodeDraft.value?.note ?? ''
  },
  set(value: string) {
    updateSelectedNodeDraft({
      note: normalizeNullableText(value),
    })
  },
})

function buildCaseSelection(detail: RunDetail, caseId: string | null) {
  const nextCase = detail.cases.find((item) => item.case_id === caseId) ?? detail.cases[0] ?? null
  const nextCandidate = nextCase?.ranked_root_causes?.[0] ?? detail.ranked_root_causes[0] ?? null
  const nextPathGraph = nextCase?.path_graph ?? detail.path_graph ?? null
  const nextPath = findBestPathForCandidateInGraph(nextCandidate, nextPathGraph) ?? nextPathGraph?.paths[0] ?? null
  const reviewTargets = nextCase?.review_targets ?? detail.review_targets ?? []
  const nextReviewTarget =
    findReviewTargetInList(
      reviewTargets,
      'root_cause_candidate',
      nextCandidate?.ranking_id ?? nextCandidate?.candidate_id,
    ) ?? findReviewTargetInList(reviewTargets, 'path', nextPath?.path_id)

  return {
    selectedCaseId: nextCase?.case_id ?? null,
    selectedCandidateId: nextCandidate?.ranking_id ?? null,
    selectedPathId: nextPath?.path_id ?? null,
    selectedReviewTargetKey: nextReviewTarget?.target_key ?? null,
    selectedGraphNodeId: null,
    subgraphMode: 'path' as const,
    selectedSubgraphNodeId: null,
    selectedSubgraphEdgeId: null,
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

function updateWorkingCaseDraft(caseId: string, updater: (draft: MockGraphCurationCaseDraft) => MockGraphCurationCaseDraft) {
  ensureCaseDraftLoaded(caseId)
  const current = workingCaseDrafts.value[caseId] ?? buildEmptyGraphCurationCaseDraft(caseId)
  const nextDraft = updater(deepClone(current))
  workingCaseDrafts.value = {
    ...workingCaseDrafts.value,
    [caseId]: nextDraft,
  }
}

function updateSelectedEdgeDraft(patch: Partial<MockGraphEdgeDraft>) {
  const caseId = activeCase.value?.case_id
  const edge = activeCurationEdge.value
  if (!caseId || !edge) {
    return
  }

  updateWorkingCaseDraft(caseId, (caseDraft) => {
    const previous = caseDraft.edge_drafts.find((draft) => draft.edge_id === edge.id)
    const nextDraft: MockGraphEdgeDraft = {
      edge_id: edge.id,
      target_key: patch.target_key ?? previous?.target_key ?? readStringAttribute(edge.attributes, 'target_key') ?? edge.id,
      review_decision: patch.review_decision ?? previous?.review_decision ?? edgeDecisionFromReviewStatus(edge),
      relation: patch.relation ?? previous?.relation ?? edge.relation,
      confidence: Object.prototype.hasOwnProperty.call(patch, 'confidence')
        ? patch.confidence ?? null
        : previous?.confidence ?? edge.confidence ?? null,
      note: Object.prototype.hasOwnProperty.call(patch, 'note')
        ? patch.note ?? null
        : previous?.note ?? null,
      updated_at: new Date().toISOString(),
    }

    return replaceGraphEdgeDraft(caseDraft, nextDraft)
  })
}

function updateSelectedNodeDraft(patch: Partial<MockGraphNodeDraft>) {
  const caseId = activeCase.value?.case_id
  const node = activeCurationNode.value
  if (!caseId || !node) {
    return
  }

  updateWorkingCaseDraft(caseId, (caseDraft) => {
    const previous = caseDraft.node_drafts.find((draft) => draft.node_id === node.id)
    const nextDraft: MockGraphNodeDraft = {
      node_id: node.id,
      display_name: Object.prototype.hasOwnProperty.call(patch, 'display_name')
        ? patch.display_name ?? null
        : previous?.display_name ?? node.name,
      aliases: Object.prototype.hasOwnProperty.call(patch, 'aliases')
        ? patch.aliases ?? null
        : previous?.aliases ?? node.aliases ?? null,
      description: Object.prototype.hasOwnProperty.call(patch, 'description')
        ? patch.description ?? null
        : previous?.description ?? node.description ?? null,
      note: Object.prototype.hasOwnProperty.call(patch, 'note')
        ? patch.note ?? null
        : previous?.note ?? null,
      updated_at: new Date().toISOString(),
    }

    return replaceGraphNodeDraft(caseDraft, nextDraft)
  })
}

function saveCurrentCaseDraft() {
  const caseId = activeCase.value?.case_id
  const currentDraft = activeWorkingCaseDraft.value
  if (!caseId || !currentDraft) {
    return
  }

  saveGraphCurationCaseDraft(currentDraft)
  const savedCopy = deepClone(currentDraft)
  savedCaseDrafts.value = {
    ...savedCaseDrafts.value,
    [caseId]: savedCopy,
  }
  workingCaseDrafts.value = {
    ...workingCaseDrafts.value,
    [caseId]: deepClone(savedCopy),
  }
  actionMessage.value = `已保存 ${caseId} 的本地策展草稿。`
}

function revertCurrentSelectionDraft() {
  const caseId = activeCase.value?.case_id
  if (!caseId) {
    return
  }

  updateWorkingCaseDraft(caseId, (caseDraft) => {
    if (activeCurationEdge.value) {
      const savedDraft =
        activeSavedCaseDraft.value?.edge_drafts.find((draft) => draft.edge_id === activeCurationEdge.value?.id) ?? null
      return replaceGraphEdgeDraft(caseDraft, savedDraft ? deepClone(savedDraft) : null)
    }

    if (activeCurationNode.value) {
      const savedDraft =
        activeSavedCaseDraft.value?.node_drafts.find((draft) => draft.node_id === activeCurationNode.value?.id) ?? null
      return replaceGraphNodeDraft(caseDraft, savedDraft ? deepClone(savedDraft) : null)
    }

    return caseDraft
  })

  actionMessage.value = '已撤销当前选中项的未保存修改。'
}

function resetCurrentCaseDraft() {
  const caseId = activeCase.value?.case_id
  if (!caseId) {
    return
  }

  resetGraphCurationCaseDraft(caseId)
  const reloaded = loadGraphCurationCaseDraft(caseId)
  savedCaseDrafts.value = {
    ...savedCaseDrafts.value,
    [caseId]: deepClone(reloaded),
  }
  workingCaseDrafts.value = {
    ...workingCaseDrafts.value,
    [caseId]: deepClone(reloaded),
  }
  actionMessage.value = `已重置 ${caseId} 的本地策展草稿。`
}

function focusCurationSuggestion(item: CurationSuggestion) {
  if (!totalGraphDataset.value) {
    return
  }

  if (item.kind === 'node') {
    updateState({
      selectedGraphNodeId: item.id,
      subgraphMode: 'neighborhood',
      selectedSubgraphNodeId: item.id,
      selectedSubgraphEdgeId: null,
    })
    feedbackCardTab.value = 'curation'
    return
  }

  const edge = totalGraphDataset.value.edges.find((edgeItem) => edgeItem.id === item.id)
  if (!edge) {
    return
  }

  const centerNodeId =
    workbenchState.value.selectedGraphNodeId === edge.source || workbenchState.value.selectedGraphNodeId === edge.target
      ? workbenchState.value.selectedGraphNodeId
      : edge.source

  updateState({
    selectedGraphNodeId: centerNodeId,
    subgraphMode: 'neighborhood',
    selectedSubgraphNodeId: null,
    selectedSubgraphEdgeId: edge.id,
  })
  feedbackCardTab.value = 'curation'
}

function selectCandidate(candidateId: string) {
  updateState(
    buildCandidateSelectionPatch({
      state: workbenchState.value,
      candidateId,
      candidates: activeCase.value?.ranked_root_causes ?? runDetail.value?.ranked_root_causes ?? [],
      pathGraph: activePathGraph.value,
      reviewTargets: activeCase.value?.review_targets ?? runDetail.value?.review_targets ?? [],
      totalGraphDataset: totalGraphDataset.value,
    }),
  )
}

function handleTotalGraphSelect(payload: GraphSelectPayload) {
  if (payload?.type === 'edge') {
    return
  }

  updateState(
    buildTotalGraphSelectionPatch({
      state: workbenchState.value,
      payload: payload
        ? {
            type: 'node',
            nodeId: payload.item.id,
          }
        : null,
      candidates: activeCase.value?.ranked_root_causes ?? runDetail.value?.ranked_root_causes ?? [],
      pathGraph: activePathGraph.value,
      reviewTargets: activeCase.value?.review_targets ?? runDetail.value?.review_targets ?? [],
      totalGraphDataset: totalGraphDataset.value,
    }),
  )
}

function handleLocalGraphSelect(payload: LocalGraphSelectPayload) {
  updateState(buildLocalGraphSelectionPatch(workbenchState.value, payload))

  if (payload) {
    feedbackCardTab.value = 'curation'
  }
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
  reviewMessage.value = ''

  try {
    const graphTask =
      preferences.value.dataSourceMode === 'backend'
        ? getRootLensService().kgStudio()
        : loadBundledUnifiedGraphs()

    const [runsResult, graphResult] = await Promise.allSettled([
      getRootLensService().listRuns(),
      graphTask,
    ])

    if (runsResult.status === 'fulfilled') {
      runs.value = runsResult.value
    } else {
      throw runsResult.reason
    }

    if (graphResult.status === 'fulfilled') {
      if (preferences.value.dataSourceMode === 'backend') {
        kgStudio.value = graphResult.value as KGStudioPayload
        bundledGraphDatasets.value = []
      } else {
        bundledGraphDatasets.value = (graphResult.value as { datasets: UnifiedGraphDataset[] }).datasets
        kgStudio.value = null
      }
    } else {
      if (preferences.value.dataSourceMode === 'backend') {
        kgStudio.value = null
        totalGraphRenderMessage.value = '后端总图谱暂不可用。'
      } else {
        bundledGraphDatasets.value = []
        totalGraphRenderMessage.value = '论文演示图谱加载失败。'
      }
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
    if (!caseId) {
      return
    }

    ensureCaseDraftLoaded(caseId)
    actionMessage.value = ''

    if (caseId !== previousCaseId) {
      feedbackCardTab.value = 'rca'
    }

    if (!runDetail.value || caseId === previousCaseId) {
      return
    }

    const nextSelection = buildCaseSelection(runDetail.value, caseId)

    if (
      nextSelection.selectedCandidateId !== workbenchState.value.selectedCandidateId ||
      nextSelection.selectedPathId !== workbenchState.value.selectedPathId ||
      nextSelection.selectedReviewTargetKey !== workbenchState.value.selectedReviewTargetKey ||
      nextSelection.selectedGraphNodeId !== workbenchState.value.selectedGraphNodeId ||
      nextSelection.subgraphMode !== workbenchState.value.subgraphMode
    ) {
      updateState(nextSelection)
    }

    syncRouteQuery(runDetail.value.run.run_id, caseId)
  },
)

watch(
  [totalGraphDataset, () => workbenchState.value.selectedGraphNodeId],
  ([dataset, selectedGraphNodeId]) => {
    if (!selectedGraphNodeId) {
      return
    }

    const hasNode = dataset?.nodes.some((node) => node.id === selectedGraphNodeId) ?? false
    if (!hasNode) {
      updateState({
        selectedGraphNodeId: null,
        subgraphMode: 'path',
        selectedSubgraphNodeId: null,
        selectedSubgraphEdgeId: null,
      })
    }
  },
)

watch(
  [activeLocalGraphDataset, () => workbenchState.value.selectedSubgraphNodeId, () => workbenchState.value.selectedSubgraphEdgeId],
  ([dataset, selectedNodeId, selectedEdgeId]) => {
    const patch: Record<string, string | null> = {}

    if (selectedNodeId && !(dataset?.nodes.some((node) => node.id === selectedNodeId) ?? false)) {
      patch.selectedSubgraphNodeId = null
    }

    if (selectedEdgeId && !(dataset?.edges.some((edge) => edge.id === selectedEdgeId) ?? false)) {
      patch.selectedSubgraphEdgeId = null
    }

    if (Object.keys(patch).length) {
      updateState(patch)
    }
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
      title="总图谱、局部子图与审阅策展"
      :metrics="heroMetrics"
    >
      <template #badges>
        <a-tag v-for="tag in workspaceTags" :key="tag.label" size="small" :color="tag.color">
          {{ tag.label }}
        </a-tag>
      </template>
      <template #actions>
        <a-button size="small" :loading="loading" @click="refreshWorkspace">
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
              <h3 class="rl-section-card__title workspace-title-with-icon">
                <icon-relation />
                <span>总图谱</span>
              </h3>
              <p class="rl-section-card__desc">
                点击总图节点可切到对应的一阶邻域子图；右侧根因候选若能映射到图谱节点，也会复用同一套联动逻辑。
              </p>
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
              search-term=""
              :focused-node-ids="totalGraphFocusedNodeIds"
              :focused-edge-ids="totalGraphFocusedEdgeIds"
              :selected-node-id="workbenchState.selectedGraphNodeId"
              @select="handleTotalGraphSelect"
              @render-state="(payload) => (totalGraphRenderMessage = payload.message)"
            />
            <a-empty v-else>暂无总图谱数据</a-empty>
          </div>
          <div class="rl-section-card__footer">
            <span class="workspace-subtle">{{ totalGraphRenderMessage }}</span>
          </div>
        </article>

        <section class="workspace-bottom-grid workspace-bottom-grid--graphs-main">
          <article class="rl-section-card">
            <header class="rl-section-card__header">
              <div>
                <h3 class="rl-section-card__title workspace-title-with-icon">
                  <icon-relation />
                  <span>局部子图</span>
                </h3>
                <p class="rl-section-card__desc">{{ localGraphDescription }}</p>
              </div>
            </header>
            <div class="rl-section-card__body workspace-graph-stage workspace-graph-stage--local">
              <RunPathGraph
                v-if="activeLocalGraphDataset"
                :dataset="activeLocalGraphDataset"
                :mode="activeSubgraphMode"
                :focused-node-ids="localGraphFocusedNodeIds"
                :focused-edge-ids="localGraphFocusedEdgeIds"
                :selected-node-id="workbenchState.selectedSubgraphNodeId"
                :selected-edge-id="workbenchState.selectedSubgraphEdgeId"
                @select="handleLocalGraphSelect"
                @render-state="(payload) => (localGraphRenderMessage = payload.message)"
              />
              <div v-else class="workspace-graph-stage__empty">
                <a-empty>暂无局部子图</a-empty>
              </div>
            </div>
            <div class="rl-section-card__footer">
              <span class="workspace-subtle">{{ localGraphRenderMessage }}</span>
            </div>
          </article>

          <article class="rl-section-card workspace-feedback-card">
            <header class="rl-section-card__header workspace-feedback-card__header">
              <div>
                <h3 class="rl-section-card__title workspace-title-with-icon">
                  <icon-info-circle />
                  <span>审阅与策展卡</span>
                </h3>
                <p class="rl-section-card__desc">更紧凑地承载 RCA 反馈与图谱策展，减少冗余状态块。</p>
              </div>
              <span class="workspace-feedback-card__badge">{{ feedbackCardTab === 'rca' ? activeSubmitTarget?.label ?? '暂无反馈目标' : '本地 Draft Overlay' }}</span>
            </header>
            <div class="rl-section-card__body workspace-feedback-card__body">
              <div class="workspace-feedback-tabs" role="tablist" aria-label="切换审阅与策展卡内容">
                <button
                  type="button"
                  class="workspace-feedback-tabs__item"
                  :class="{ 'workspace-feedback-tabs__item--active': feedbackCardTab === 'rca' }"
                  @click="feedbackCardTab = 'rca'"
                >
                  RCA 反馈
                </button>
                <button
                  type="button"
                  class="workspace-feedback-tabs__item"
                  :class="{ 'workspace-feedback-tabs__item--active': feedbackCardTab === 'curation' }"
                  @click="feedbackCardTab = 'curation'"
                >
                  图谱策展
                </button>
              </div>

              <template v-if="feedbackCardTab === 'rca'">
                <section class="workspace-feedback-compact">
                  <div class="workspace-summary-list workspace-summary-list--two-col">
                    <div class="workspace-summary-list__item">
                      <span class="workspace-summary-label">
                        <icon-bulb />
                        <span>当前候选</span>
                      </span>
                      <strong>{{ activeCandidate?.candidate_name ?? '--' }}</strong>
                    </div>
                    <div class="workspace-summary-list__item">
                      <span class="workspace-summary-label">
                        <icon-relation />
                        <span>当前路径</span>
                      </span>
                      <strong>{{ activePath?.path_id ?? '--' }}</strong>
                    </div>
                    <div class="workspace-summary-list__item">
                      <span class="workspace-summary-label">
                        <icon-info-circle />
                        <span>反馈目标</span>
                      </span>
                      <strong>{{ activeSubmitTarget?.target_type ?? '--' }}</strong>
                    </div>
                    <div class="workspace-summary-list__item">
                      <span class="workspace-summary-label">
                        <icon-storage />
                        <span>得分</span>
                      </span>
                      <strong>{{ formatScore(activeCandidate?.score) }}</strong>
                    </div>
                  </div>

                  <div class="workspace-feedback-compact__decision-bar">
                    <a-button
                      size="small"
                      :type="feedbackForm.action === 'accept' ? 'primary' : 'outline'"
                      class="workspace-feedback-compact__decision-button workspace-feedback-compact__decision-button--accept"
                      @click="feedbackForm.action = 'accept'"
                    >
                      接受
                    </a-button>
                    <a-button
                      size="small"
                      status="danger"
                      :type="feedbackForm.action === 'reject' ? 'primary' : 'outline'"
                      class="workspace-feedback-compact__decision-button workspace-feedback-compact__decision-button--reject"
                      @click="feedbackForm.action = 'reject'"
                    >
                      拒绝
                    </a-button>
                  </div>

                  <div class="rl-form-field workspace-feedback-compact__field">
                    <span class="workspace-field-label">
                      <icon-info-circle />
                      <span>备注</span>
                    </span>
                    <a-textarea v-model="feedbackForm.note" :auto-size="{ minRows: 4, maxRows: 6 }" placeholder="记录你的审阅判断和上下文。" />
                  </div>

                  <div class="workspace-feedback-compact__footer">
                    <a-button type="primary" @click="handleFeedbackSubmit">
                      <template #icon>
                        <icon-send />
                      </template>
                      提交反馈
                    </a-button>
                  </div>

                  <a-alert
                    v-if="reviewMessage"
                    class="workspace-feedback-inline-alert"
                    :type="reviewMessage.startsWith('反馈已记录') ? 'success' : 'warning'"
                    :show-icon="false"
                    :title="reviewMessage"
                  />
                </section>
              </template>

              <template v-else>
                <section class="workspace-feedback-pane workspace-feedback-pane--curation">
                  <div class="workspace-feedback-pane__section">
                    <div class="workspace-feedback-pane__section-head">
                      <strong>{{ activeCurationEdge ? '边策展' : activeCurationNode ? '节点策展' : '图谱策展' }}</strong>
                      <span>{{ activeCurationEdge ? '已选中边' : activeCurationNode ? '已选中节点' : '等待在左侧子图中选择节点或边' }}</span>
                    </div>

                    <div v-if="activeCurationEdge" class="workspace-curation-panel">
                      <div class="workspace-curation-meta">
                        <div class="workspace-claim-note">
                          <span class="workspace-summary-label">
                            <icon-info-circle />
                            <span>Evidence</span>
                          </span>
                          <strong>{{ normalizeText(readStringAttribute(activeCurationEdge.attributes, 'evidence'), '当前边没有附带 evidence snippet。') }}</strong>
                        </div>
                      </div>

                      <div class="rl-form-field">
                        <span class="workspace-field-label">
                          <icon-bulb />
                          <span>审阅决策</span>
                        </span>
                        <a-select v-model="edgeDecisionModel">
                          <a-option value="accept">accept</a-option>
                          <a-option value="reject">reject</a-option>
                          <a-option value="revise">revise</a-option>
                          <a-option value="needs_completion">needs_completion</a-option>
                        </a-select>
                      </div>

                      <div class="workspace-form-row workspace-form-row--two">
                        <div class="rl-form-field">
                          <span class="workspace-field-label">
                            <icon-relation />
                            <span>Relation</span>
                          </span>
                          <a-input v-model="edgeRelationModel" placeholder="修改 relation 文本" />
                        </div>
                        <div class="rl-form-field">
                          <span class="workspace-field-label">
                            <icon-storage />
                            <span>Confidence</span>
                          </span>
                          <a-input-number v-model="edgeConfidenceModel" :min="0" :max="1" :step="0.01" :precision="2" />
                        </div>
                      </div>

                      <div class="rl-form-field">
                        <span class="workspace-field-label">
                          <icon-info-circle />
                          <span>Note</span>
                        </span>
                        <a-textarea v-model="edgeNoteModel" :auto-size="{ minRows: 4, maxRows: 6 }" placeholder="记录为什么接受、拒绝或修订这条边。" />
                      </div>
                    </div>

                    <div v-else-if="activeCurationNode" class="workspace-curation-panel">
                      <div class="workspace-summary-list workspace-summary-list--two-col">
                        <div class="workspace-summary-list__item">
                          <span class="workspace-summary-label">
                            <icon-relation />
                            <span>节点 ID</span>
                          </span>
                          <strong>{{ activeCurationNode.id }}</strong>
                        </div>
                        <div class="workspace-summary-list__item">
                          <span class="workspace-summary-label">
                            <icon-info-circle />
                            <span>场景</span>
                          </span>
                          <strong>{{ normalizeText(readStringAttribute(activeCurationNode.attributes, 'scenario'), activeCurationNode.category) }}</strong>
                        </div>
                        <div class="workspace-summary-list__item">
                          <span class="workspace-summary-label">
                            <icon-storage />
                            <span>Kind</span>
                          </span>
                          <strong>{{ normalizeText(activeCurationNode.kind) }}</strong>
                        </div>
                        <div class="workspace-summary-list__item">
                          <span class="workspace-summary-label">
                            <icon-bulb />
                            <span>说明</span>
                          </span>
                          <strong>{{ normalizeText(activeCurationNode.description) }}</strong>
                        </div>
                      </div>

                      <div class="workspace-form-row workspace-form-row--two">
                        <div class="rl-form-field">
                          <span class="workspace-field-label">
                            <icon-info-circle />
                            <span>Display name</span>
                          </span>
                          <a-input v-model="nodeDisplayNameModel" placeholder="节点展示名" />
                        </div>
                        <div class="rl-form-field">
                          <span class="workspace-field-label">
                            <icon-relation />
                            <span>Aliases</span>
                          </span>
                          <a-input v-model="nodeAliasesModel" placeholder="alias1, alias2" />
                        </div>
                      </div>

                      <div class="rl-form-field">
                        <span class="workspace-field-label">
                          <icon-bulb />
                          <span>Description</span>
                        </span>
                        <a-textarea v-model="nodeDescriptionModel" :auto-size="{ minRows: 4, maxRows: 6 }" placeholder="补充节点说明或更保守的解释文案。" />
                      </div>

                      <div class="rl-form-field">
                        <span class="workspace-field-label">
                          <icon-info-circle />
                          <span>Note</span>
                        </span>
                        <a-textarea v-model="nodeNoteModel" :auto-size="{ minRows: 3, maxRows: 5 }" placeholder="记录节点策展备注。" />
                      </div>
                    </div>

                    <div v-else class="workspace-curation-empty">
                      <p>先在左侧局部子图中点击节点或边，再进入对应的本地策展表单。</p>
                      <div v-if="activeCurationSuggestions.length" class="workspace-curation-suggestions">
                        <button
                          v-for="item in activeCurationSuggestions"
                          :key="`${item.kind}:${item.id}`"
                          type="button"
                          class="workspace-curation-suggestion"
                          @click="focusCurationSuggestion(item)"
                        >
                          <strong>{{ item.kind === 'edge' ? '边' : '节点' }} · {{ item.label }}</strong>
                          <span>{{ item.subtitle }}</span>
                        </button>
                      </div>
                    </div>
                  </div>

                  <div class="workspace-curation-actions">
                    <a-button type="primary" @click="saveCurrentCaseDraft">
                      <template #icon>
                        <icon-save />
                      </template>
                      保存本地草稿
                    </a-button>
                    <a-button :disabled="!canRevertCurrentSelection" @click="revertCurrentSelectionDraft">撤销当前修改</a-button>
                    <a-button status="warning" @click="resetCurrentCaseDraft">重置当前 case 草稿</a-button>
                  </div>

                  <div class="workspace-feedback-status" :class="{ 'workspace-feedback-status--success': hasUnsavedCurationChanges === false && !!actionMessage }">
                    <div class="workspace-feedback-status__header">
                      <icon-check-circle v-if="actionMessage" />
                      <strong>{{ actionMessage || (hasUnsavedCurationChanges ? '当前有未保存的本地策展修改。' : '当前 case 没有未保存改动。') }}</strong>
                    </div>
                    <div class="workspace-feedback-status__meta">
                      <span>未保存修改：{{ hasUnsavedCurationChanges ? '有' : '无' }}</span>
                      <span>节点草稿：{{ activeWorkingCaseDraft?.node_drafts.length ?? 0 }}</span>
                      <span>边草稿：{{ activeWorkingCaseDraft?.edge_drafts.length ?? 0 }}</span>
                    </div>
                  </div>
                </section>
              </template>
            </div>
          </article>
        </section>
      </div>

      <aside class="workspace-shell__aside workspace-shell__aside--graphs">
        <article class="rl-section-card workspace-root-cause-aside-card">
          <header class="rl-section-card__header">
            <div>
              <h3 class="rl-section-card__title workspace-title-with-icon">
                <icon-bulb />
                <span>根因列表</span>
              </h3>
              <p class="rl-section-card__desc">顶部保留 Run / Case 切换；点击候选会联动总图与局部子图，再次点击同一项可取消选择。</p>
            </div>
            <a-tag color="green">{{ activeCase?.ranked_root_causes?.length ?? 0 }}</a-tag>
          </header>
          <div class="rl-section-card__body workspace-root-cause-aside-card__body">
            <section class="workspace-root-cause-aside-card__context workspace-stack workspace-stack--tight">
              <div class="rl-form-field">
                <span class="workspace-field-label">
                  <icon-storage />
                  <span>Run</span>
                </span>
                <a-select :model-value="runDetail?.run.run_id" @change="handleRunChange">
                  <a-option v-for="run in runs" :key="run.run_id" :value="run.run_id">
                    {{ run.label }}
                  </a-option>
                </a-select>
              </div>
              <div class="rl-form-field">
                <span class="workspace-field-label">
                  <icon-relation />
                  <span>Case</span>
                </span>
                <a-select :model-value="activeCase?.case_id" @change="handleCaseChange">
                  <a-option v-for="caseItem in runDetail?.cases ?? []" :key="caseItem.case_id" :value="caseItem.case_id">
                    {{ caseItem.case_label ?? caseItem.case_id }}
                  </a-option>
                </a-select>
              </div>
            </section>

            <section class="workspace-root-cause-aside-card__list">
              <div class="workspace-root-cause-aside-card__section-header">
                <strong>候选根因</strong>
                <span>{{ activeCandidate ? '已选中 1 项' : '当前未选中' }}</span>
              </div>
              <div class="workspace-scroll-list workspace-scroll-list--fill">
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
            </section>
          </div>
        </article>
      </aside>
    </section>
  </div>
</template>
