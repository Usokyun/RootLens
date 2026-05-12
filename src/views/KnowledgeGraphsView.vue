<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'

import KnowledgeForceGraph from '@/components/graphs/KnowledgeForceGraph.vue'
import SessionBlockerCard from '@/components/workflow/SessionBlockerCard.vue'
import { buildAnalysisWorkspaceScope } from '@/services/analysis-workspace'
import {
  clearAnalysisHighlight,
  getAnalysisFocusEventName,
  loadAnalysisFocus,
  type AnalysisFocusState,
} from '@/services/analysis-focus'
import {
  getImportedSessionSummary,
  getLocalSessionEventName,
  getLocalSessionMeta,
  loadUnifiedGraphs,
} from '@/services/rootlens-data'
import { buildWorkflowSnapshot } from '@/services/workflow'
import type {
  UnifiedGraphsFile,
  UnifiedGraphDataset,
  UnifiedGraphEdge,
  UnifiedGraphNode,
} from '@/types/graph'

type SelectionState =
  | { type: 'node'; item: UnifiedGraphNode }
  | { type: 'edge'; item: UnifiedGraphEdge }
  | null

const graphData = ref<UnifiedGraphsFile | null>(null)
const loading = ref(true)
const errorMessage = ref('')
const activeDatasetId = ref('')
const showLabels = ref(false)
const searchTerm = ref('')
const selection = ref<SelectionState>(null)
const sessionMeta = ref(getLocalSessionMeta())
const importSummary = ref(getImportedSessionSummary())
const focusState = ref<AnalysisFocusState | null>(null)
const router = useRouter()

const datasets = computed(() => graphData.value?.datasets ?? [])
const analysisFocusScope = computed(() => buildAnalysisWorkspaceScope(sessionMeta.value))
const workflow = computed(() => buildWorkflowSnapshot(sessionMeta.value, importSummary.value))

const generatedAt = computed(() => graphData.value?.generatedAt ?? '-')
const schemaVersion = computed(() => graphData.value?.schemaVersion ?? '-')
const sessionLabel = computed(() =>
  sessionMeta.value?.source === 'import' ? '本地导入' : '内置示例',
)
const sessionSummary = computed(() => sessionMeta.value?.summary ?? '使用内置示例数据')
const pageBlocker = computed(() => {
  if (workflow.value.hasGraphs) {
    return null
  }

  if (workflow.value.hasCases) {
    return {
      title: '当前会话缺少统一图谱',
      description:
        '你恢复或导入的是 runtime case，但当前 session 不包含 unified-graphs.json，所以图谱工作台无法渲染力导向图。',
      hints: [
        '返回系统入口后补导 unified-graphs.json，或直接恢复包含 graphs 的 session bundle。',
        '当前 runtime 仍可继续在 Evidence 或 RCA 页面使用。',
      ],
      actions: [
        { key: 'import', label: '返回系统入口', type: 'primary' as const },
        { key: 'evidence', label: '继续 Evidence', type: 'outline' as const },
        { key: 'reasoning', label: '继续 RCA', type: 'outline' as const },
      ],
    }
  }

  return {
    title: '当前会话还没有图谱',
    description:
      '图谱工作台依赖 unified-graphs.json 或 nodes/edges 导入结果。当前 session 没有可用图谱，因此只能先回到系统入口补齐导入。',
    hints: [
      'TEP 支持 nodes.jsonl + edges.jsonl，MVTec 支持 nodes.csv + edges.csv。',
      '如果只是想快速体验完整链路，也可以直接切回内置示例。',
    ],
    actions: [
      { key: 'import', label: '去导入图谱', type: 'primary' as const },
    ],
  }
})

const activeDataset = computed<UnifiedGraphDataset | null>(() => {
  const currentDatasets = datasets.value

  return (
    currentDatasets.find((dataset) => dataset.id === activeDatasetId.value) ??
    currentDatasets[0] ??
    null
  )
})

const focusForActiveDataset = computed(() => {
  if (!activeDataset.value || !focusState.value) {
    return null
  }

  return focusState.value.active_dataset_id === activeDataset.value.id ? focusState.value : null
})

const focusedNodeIds = computed(() => focusForActiveDataset.value?.highlighted_node_ids ?? [])
const focusedEdgeIds = computed(() => focusForActiveDataset.value?.highlighted_edge_ids ?? [])

const hasAnalysisFocus = computed(
  () =>
    Boolean(
      focusState.value?.selected_observation_id ||
        focusState.value?.selected_route1_path_ids.length ||
        focusState.value?.selected_route2_candidate_ids.length ||
        focusState.value?.highlighted_node_ids.length ||
        focusState.value?.highlighted_edge_ids.length ||
        focusState.value?.highlighted_obs_ids.length,
    ),
)

const focusKindLabel = computed(() => {
  switch (focusState.value?.focus_kind) {
    case 'case':
      return 'Case'
    case 'observation':
      return 'Observation'
    case 'route1-path':
      return 'Route 1 Path'
    case 'route2-candidate':
      return 'Route 2 Candidate'
    case 'cross-signal':
      return 'Cross Route'
    default:
      return 'No Focus'
  }
})

const nodeCategoryStats = computed(() => {
  if (!activeDataset.value) {
    return []
  }

  const counter = new Map<string, number>()

  for (const node of activeDataset.value.nodes) {
    counter.set(node.category, (counter.get(node.category) ?? 0) + 1)
  }

  return [...counter.entries()]
    .map(([name, count]) => ({
      name,
      count,
    }))
    .sort((left, right) => right.count - left.count)
})

const relationStats = computed(() => {
  if (!activeDataset.value) {
    return []
  }

  const counter = new Map<string, number>()

  for (const edge of activeDataset.value.edges) {
    counter.set(edge.relation, (counter.get(edge.relation) ?? 0) + 1)
  }

  return [...counter.entries()]
    .map(([name, count]) => ({
      name,
      count,
    }))
    .sort((left, right) => right.count - left.count)
})

const sourceFiles = computed(() => activeDataset.value?.sourceFiles ?? [])

const selectedTitle = computed(() => {
  if (!selection.value) {
    return '未选择元素'
  }

  return selection.value.type === 'node'
    ? selection.value.item.name
    : selection.value.item.relation
})

const selectedPayload = computed(() => {
  if (!selection.value) {
    return ''
  }

  return JSON.stringify(selection.value.item, null, 2)
})

async function loadGraphData() {
  loading.value = true
  errorMessage.value = ''

  try {
    const previousDatasetId = activeDatasetId.value
    const payload: UnifiedGraphsFile = await loadUnifiedGraphs()
    graphData.value = payload
    const preferredDatasetId = focusState.value?.active_dataset_id ?? previousDatasetId
    activeDatasetId.value = payload.datasets.some((dataset) => dataset.id === preferredDatasetId)
      ? preferredDatasetId
      : payload.datasets[0]?.id ?? ''
    selection.value = null
  } catch (error) {
    errorMessage.value =
      error instanceof Error ? error.message : 'failed to load graph datasets'
  } finally {
    loading.value = false
  }
}

function refreshSessionMeta() {
  sessionMeta.value = getLocalSessionMeta()
  importSummary.value = getImportedSessionSummary()
}

function refreshFocusState() {
  focusState.value = loadAnalysisFocus(analysisFocusScope.value)
}

function handleSessionChange() {
  refreshSessionMeta()
  refreshFocusState()
  void loadGraphData()
}

function handleFocusChange(event: Event) {
  const customEvent = event as CustomEvent<{ sessionScope?: string }>

  if (
    customEvent.detail?.sessionScope &&
    customEvent.detail.sessionScope !== analysisFocusScope.value
  ) {
    return
  }

  refreshFocusState()

  const focusedDatasetId = focusState.value?.active_dataset_id
  if (focusedDatasetId && datasets.value.some((dataset) => dataset.id === focusedDatasetId)) {
    activeDatasetId.value = focusedDatasetId
  }
}

function handleDatasetChange(value: string | number | boolean) {
  activeDatasetId.value = String(value)
  selection.value = null
  searchTerm.value = ''
}

function handleSelection(
  payload:
    | { type: 'node'; item: UnifiedGraphNode }
    | { type: 'edge'; item: UnifiedGraphEdge },
) {
  selection.value = payload
}

function clearSelection() {
  selection.value = null
}

function clearGlobalFocus() {
  clearAnalysisHighlight(analysisFocusScope.value)
}

function goToEvidence() {
  void router.push({
    name: 'evidence',
  })
}

function goToReasoning() {
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

  if (actionKey === 'evidence') {
    goToEvidence()
    return
  }

  if (actionKey === 'reasoning') {
    goToReasoning()
  }
}

onMounted(() => {
  refreshSessionMeta()
  refreshFocusState()
  void loadGraphData()
  window.addEventListener(getLocalSessionEventName(), handleSessionChange)
  window.addEventListener(getAnalysisFocusEventName(), handleFocusChange)
})

onBeforeUnmount(() => {
  window.removeEventListener(getLocalSessionEventName(), handleSessionChange)
  window.removeEventListener(getAnalysisFocusEventName(), handleFocusChange)
})
</script>

<template>
  <div class="page-stack graph-workspace">
    <section class="hero-panel">
      <div class="hero-panel__content">
        <div>
          <a-space wrap>
            <a-tag color="arcoblue">Unified Graph Model</a-tag>
            <a-tag color="green">Force Layout</a-tag>
            <a-tag color="orangered">Toggle Ready</a-tag>
            <a-tag color="grayblue">{{ schemaVersion }}</a-tag>
          </a-space>
          <h2 class="hero-panel__title">图谱可视化</h2>
          <p class="hero-panel__body">
            当前页面聚焦主链路里的统一图谱展示。系统把 TEP_KG 与 MVTec/KGTraceVis 的原始图谱
            解析成同一种节点/边格式，并用同一个力导向图组件完成渲染、切换与检查。
          </p>
        </div>

        <div class="hero-panel__brief">
          <div class="brief-item">
            <div class="brief-item__label">统一目标</div>
            <div class="brief-item__value">
              一个前端模型，同时承接知识图谱展示与后续推理模块输入。
            </div>
          </div>
          <div class="brief-item">
            <div class="brief-item__label">当前数据集</div>
            <div class="brief-item__value">
              {{ activeDataset?.label ?? '加载中' }}
            </div>
          </div>
          <div class="brief-item">
            <div class="brief-item__label">当前会话</div>
            <div class="brief-item__value">{{ sessionLabel }}</div>
          </div>
          <div class="brief-item">
            <div class="brief-item__label">数据生成时间</div>
            <div class="brief-item__value">{{ generatedAt }}</div>
          </div>
          <div class="brief-item">
            <div class="brief-item__label">会话摘要</div>
            <div class="brief-item__value">{{ sessionSummary }}</div>
          </div>
        </div>
      </div>
    </section>

    <a-card v-if="activeDataset" class="glass-card" :bordered="false">
      <div class="graph-toolbar">
        <a-radio-group
          type="button"
          :model-value="activeDatasetId"
          @change="handleDatasetChange"
        >
          <a-radio
            v-for="dataset in datasets"
            :key="dataset.id"
            :value="dataset.id"
          >
            {{ dataset.label }}
          </a-radio>
        </a-radio-group>

        <a-input
          v-model="searchTerm"
          allow-clear
          class="graph-toolbar__search"
          placeholder="按 id / 名称 / 类型 / alias 搜索高亮节点"
        />

        <a-switch v-model="showLabels" type="round">
          <template #checked>显示标签</template>
          <template #unchecked>隐藏标签</template>
        </a-switch>

        <a-button @click="clearSelection">清空本页选择</a-button>
        <a-button :disabled="!hasAnalysisFocus" @click="clearGlobalFocus">
          清空联动焦点
        </a-button>
      </div>
    </a-card>

    <a-card v-if="loading" class="glass-card" :bordered="false">
      <a-spin dot tip="正在加载统一图谱数据..." />
    </a-card>

    <SessionBlockerCard
      v-else-if="pageBlocker"
      badge="Graphs Unavailable"
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

    <div v-else-if="activeDataset" class="graph-layout">
      <a-card class="glass-card graph-canvas-card" :bordered="false">
        <template #title>
          {{ activeDataset.label }} · 力导向图
        </template>
        <template #extra>
          <a-space>
            <a-tag color="arcoblue">{{ activeDataset.graphKind }}</a-tag>
            <a-tag color="green">{{ activeDataset.nodes.length }} nodes</a-tag>
            <a-tag color="gold">{{ activeDataset.edges.length }} edges</a-tag>
          </a-space>
        </template>

        <KnowledgeForceGraph
          :dataset="activeDataset"
          :focused-edge-ids="focusedEdgeIds"
          :focused-node-ids="focusedNodeIds"
          :show-labels="showLabels"
          :search-term="searchTerm"
          @select="handleSelection"
        />
      </a-card>

      <div class="graph-sidebar">
        <a-card class="glass-card" :bordered="false" title="数据集摘要">
          <div class="graph-stat-grid">
            <div class="graph-stat-card">
              <div class="graph-stat-card__label">Project Root</div>
              <div class="graph-stat-card__value graph-stat-card__mono">
                {{ activeDataset.projectRoot }}
              </div>
            </div>
            <div class="graph-stat-card">
              <div class="graph-stat-card__label">Nodes / Edges</div>
              <div class="graph-stat-card__value">
                {{ activeDataset.nodes.length }} / {{ activeDataset.edges.length }}
              </div>
            </div>
            <div class="graph-stat-card">
              <div class="graph-stat-card__label">Source Files</div>
              <div class="graph-stat-card__value">{{ sourceFiles.length }}</div>
            </div>
          </div>
          <p class="timeline-note">{{ activeDataset.description }}</p>
        </a-card>

        <a-card class="glass-card" :bordered="false" title="联动焦点">
          <template v-if="hasAnalysisFocus && focusState">
            <a-space wrap>
              <a-tag color="arcoblue">{{ focusKindLabel }}</a-tag>
              <a-tag color="green">{{ focusState.source_view ?? 'system' }}</a-tag>
              <a-tag color="grayblue">{{ focusState.active_case_id ?? 'no case' }}</a-tag>
            </a-space>

            <p class="timeline-note">
              {{ focusState.focus_label ?? '当前焦点没有标签。' }}
            </p>

            <div class="graph-stat-grid">
              <div class="graph-stat-card">
                <div class="graph-stat-card__label">Highlighted Nodes</div>
                <div class="graph-stat-card__value">
                  {{ focusForActiveDataset?.highlighted_node_ids.length ?? 0 }}
                </div>
              </div>
              <div class="graph-stat-card">
                <div class="graph-stat-card__label">Highlighted Edges</div>
                <div class="graph-stat-card__value">
                  {{ focusForActiveDataset?.highlighted_edge_ids.length ?? 0 }}
                </div>
              </div>
              <div class="graph-stat-card">
                <div class="graph-stat-card__label">Support Obs</div>
                <div class="graph-stat-card__value">
                  {{ focusState.highlighted_obs_ids.length }}
                </div>
              </div>
            </div>

            <a-space wrap>
              <a-button size="mini" @click="goToEvidence">查看 Evidence</a-button>
              <a-button size="mini" @click="goToReasoning">查看 RCA</a-button>
            </a-space>
          </template>

          <a-empty
            v-else
            description="从 Evidence 或 RCA 页选择 observation、path 或 candidate 后，这里会自动高亮相关节点和边。"
          />
        </a-card>

        <a-card class="glass-card" :bordered="false" title="原始来源文件">
          <div class="directory-list">
            <article
              v-for="file in sourceFiles"
              :key="`${file.path}:${file.layer}`"
              class="directory-card"
            >
              <div class="directory-card__path">{{ file.path }}</div>
              <p class="directory-card__purpose">
                {{ file.role }} · layer={{ file.layer }} · rows={{ file.rowCount }}
              </p>
            </article>
          </div>
        </a-card>

        <a-card class="glass-card" :bordered="false" title="节点类型分布">
          <div class="graph-chip-list">
            <span
              v-for="item in nodeCategoryStats.slice(0, 12)"
              :key="item.name"
              class="graph-chip"
            >
              {{ item.name }} · {{ item.count }}
            </span>
          </div>
        </a-card>

        <a-card class="glass-card" :bordered="false" title="关系分布">
          <div class="graph-chip-list">
            <span
              v-for="item in relationStats.slice(0, 12)"
              :key="item.name"
              class="graph-chip"
            >
              {{ item.name }} · {{ item.count }}
            </span>
          </div>
        </a-card>

        <a-card class="glass-card" :bordered="false" :title="`元素检查器 · ${selectedTitle}`">
          <template v-if="selection">
            <a-space wrap>
              <a-tag color="arcoblue">{{ selection.type }}</a-tag>
              <a-tag color="green">{{ selection.item.origin.layer }}</a-tag>
            </a-space>
            <pre class="json-panel">{{ selectedPayload }}</pre>
          </template>
          <a-empty v-else description="点击图中的节点或边查看无损保留的原始属性。" />
        </a-card>
      </div>
    </div>
  </div>
</template>
