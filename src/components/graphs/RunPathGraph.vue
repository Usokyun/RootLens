<script setup lang="ts">
import { computed, ref } from 'vue'

import type { PathGraph, PathGraphPath } from '@/api/contracts'
import KnowledgeForceGraph from '@/components/graphs/KnowledgeForceGraph.vue'
import type { UnifiedGraphDataset, UnifiedGraphEdge, UnifiedGraphNode } from '@/types/graph'

const props = withDefaults(
  defineProps<{
    pathGraph: PathGraph
    selectedPathId?: string | null
  }>(),
  {
    selectedPathId: null,
  },
)

const emit = defineEmits<{
  selectPath: [pathId: string]
}>()

const graphRenderMessage = ref('子图布局准备中...')

const selectedPath = computed(() => {
  return props.pathGraph.paths.find((path) => path.path_id === props.selectedPathId) ?? props.pathGraph.paths[0] ?? null
})

const focusedNodeIds = computed(() => selectedPath.value?.nodes.map((node) => node.node_id) ?? [])
const focusedEdgeIds = computed(() => selectedPath.value?.edges.map((edge) => edge.edge_id) ?? [])

const graphDataset = computed<UnifiedGraphDataset>(() => {
  const nodeSeed = new Map<
    string,
    {
      node_id: string
      label: string
      role: string
      pathIds: Set<string>
    }
  >()
  const edgeSeed = new Map<
    string,
    {
      edge_id: string
      source_node_id: string
      target_node_id: string
      relation: string
      confidence: number | null
      review_status: string | null
      evidence: string | null
      source: string | null
      target_key: string
      pathIds: Set<string>
    }
  >()

  for (const path of props.pathGraph.paths) {
    for (const node of path.nodes) {
      const current = nodeSeed.get(node.node_id)
      if (current) {
        current.pathIds.add(path.path_id)
        continue
      }

      nodeSeed.set(node.node_id, {
        node_id: node.node_id,
        label: node.label,
        role: node.role,
        pathIds: new Set([path.path_id]),
      })
    }

    for (const edge of path.edges) {
      const current = edgeSeed.get(edge.edge_id)
      if (current) {
        current.pathIds.add(path.path_id)
        continue
      }

      edgeSeed.set(edge.edge_id, {
        edge_id: edge.edge_id,
        source_node_id: edge.source_node_id,
        target_node_id: edge.target_node_id,
        relation: edge.relation,
        confidence: edge.confidence ?? null,
        review_status: edge.review_status ?? null,
        evidence: edge.evidence ?? null,
        source: edge.source ?? null,
        target_key: edge.target_key,
        pathIds: new Set([path.path_id]),
      })
    }
  }

  const inDegree = new Map<string, number>()
  const outDegree = new Map<string, number>()
  for (const edge of edgeSeed.values()) {
    outDegree.set(edge.source_node_id, (outDegree.get(edge.source_node_id) ?? 0) + 1)
    inDegree.set(edge.target_node_id, (inDegree.get(edge.target_node_id) ?? 0) + 1)
  }

  const nodes: UnifiedGraphNode[] = [...nodeSeed.values()].map((node) => ({
    id: node.node_id,
    name: node.label,
    category: node.role,
    kind: 'path-node',
    description: `${node.role} · ${node.pathIds.size} 条路径`,
    aliases: [],
    degree: (inDegree.get(node.node_id) ?? 0) + (outDegree.get(node.node_id) ?? 0),
    inDegree: inDegree.get(node.node_id) ?? 0,
    outDegree: outDegree.get(node.node_id) ?? 0,
    attributes: {
      role: node.role,
      path_ids: [...node.pathIds],
    },
    origin: {
      projectId: 'run-path-graph',
      projectLabel: 'Run Path Graph',
      filePath: 'path_graph',
      layer: 'path-subgraph',
      rowNumber: 0,
    },
  }))

  const edges: UnifiedGraphEdge[] = [...edgeSeed.values()].map((edge) => ({
    id: edge.edge_id,
    source: edge.source_node_id,
    target: edge.target_node_id,
    relation: edge.relation,
    category: 'path',
    label: edge.relation,
    confidence: edge.confidence,
    weight: edge.confidence,
    directed: true,
    attributes: {
      target_key: edge.target_key,
      review_status: edge.review_status,
      evidence: edge.evidence,
      source: edge.source,
      path_ids: [...edge.pathIds],
    },
    origin: {
      projectId: 'run-path-graph',
      projectLabel: 'Run Path Graph',
      filePath: 'path_graph',
      layer: 'path-subgraph',
      rowNumber: 0,
    },
  }))

  return {
    id: 'run-path-subgraph',
    label: 'Path Graph 子图',
    description: '当前 case 的 path_graph union subgraph',
    graphKind: 'path-subgraph',
    projectRoot: 'path_graph',
    sourceFiles: [],
    nodes,
    edges,
    metadata: {
      path_count: props.pathGraph.path_count,
      node_count: props.pathGraph.node_count,
      edge_count: props.pathGraph.edge_count,
    },
  }
})

function formatScore(value: number | null | undefined) {
  return typeof value === 'number' ? value.toFixed(3) : '--'
}

function formatPathLabel(path: PathGraphPath) {
  return path.target_entity_id || path.target_key || path.path_id
}
</script>

<template>
  <div v-if="!pathGraph.paths.length" class="run-path-graph run-path-graph--empty">
    <p>当前没有路径图数据。</p>
  </div>
  <div v-else class="run-path-graph">
    <div class="run-path-graph__toolbar">
      <button
        v-for="path in pathGraph.paths"
        :key="path.path_id"
        type="button"
        class="run-path-graph__chip"
        :class="{ 'run-path-graph__chip--active': path.path_id === selectedPath?.path_id }"
        @click="emit('selectPath', path.path_id)"
      >
        <span class="run-path-graph__chip-rank">{{ path.path_id }}</span>
        <strong class="run-path-graph__chip-target">{{ formatPathLabel(path) }}</strong>
        <small class="run-path-graph__chip-score">{{ formatScore(path.score) }}</small>
      </button>
    </div>

    <div class="run-path-graph__scene">
      <KnowledgeForceGraph
        :dataset="graphDataset"
        :show-labels="true"
        :search-term="selectedPath?.target_entity_id ?? ''"
        :focused-node-ids="focusedNodeIds"
        :focused-edge-ids="focusedEdgeIds"
        @render-state="(payload) => (graphRenderMessage = payload.message)"
      />
    </div>

    <div class="run-path-graph__footer">
      <span>{{ graphRenderMessage }}</span>
      <span>{{ graphDataset.nodes.length }} 节点 / {{ graphDataset.edges.length }} 边</span>
    </div>
  </div>
</template>

<style scoped>
.run-path-graph {
  display: grid;
  gap: 12px;
}

.run-path-graph--empty {
  min-height: 240px;
  place-items: center;
  display: grid;
  color: #52606d;
}

.run-path-graph__toolbar {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.run-path-graph__chip {
  border: 1px solid rgba(148, 163, 184, 0.24);
  border-radius: 14px;
  padding: 10px 12px;
  display: grid;
  gap: 4px;
  background: rgba(255, 255, 255, 0.94);
  color: inherit;
  text-align: left;
  cursor: pointer;
  transition:
    transform 0.18s ease,
    border-color 0.18s ease,
    box-shadow 0.18s ease,
    background-color 0.18s ease;
}

.run-path-graph__chip:hover {
  transform: translateY(-1px);
  border-color: rgba(37, 99, 235, 0.28);
  box-shadow: 0 12px 24px rgba(37, 99, 235, 0.08);
}

.run-path-graph__chip--active {
  border-color: rgba(37, 99, 235, 0.36);
  background: linear-gradient(180deg, rgba(239, 246, 255, 0.96), rgba(230, 240, 255, 0.94));
  box-shadow: 0 14px 26px rgba(37, 99, 235, 0.1);
}

.run-path-graph__chip-rank,
.run-path-graph__chip-score {
  color: #61758a;
  font-size: 11px;
  line-height: 1.4;
}

.run-path-graph__chip-target {
  color: #102a43;
  font-size: 13px;
  line-height: 1.35;
}

.run-path-graph__scene {
  min-height: 360px;
  border: 1px solid rgba(226, 232, 240, 0.88);
  border-radius: 14px;
  overflow: hidden;
  background:
    radial-gradient(circle at top left, rgba(125, 211, 252, 0.1), transparent 34%),
    linear-gradient(180deg, rgba(249, 252, 255, 0.98), rgba(242, 247, 255, 0.96));
}

.run-path-graph__footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  color: #61758a;
  font-size: 12px;
  line-height: 1.5;
}

@media (max-width: 720px) {
  .run-path-graph__footer {
    align-items: flex-start;
    flex-direction: column;
  }
}
</style>
