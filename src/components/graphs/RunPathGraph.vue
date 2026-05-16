<script setup lang="ts">
import KnowledgeForceGraph from '@/components/graphs/KnowledgeForceGraph.vue'
import type { GraphSubgraphMode } from '@/services/graph-curation'
import type { UnifiedGraphDataset } from '@/types/graph'

withDefaults(
  defineProps<{
    dataset: UnifiedGraphDataset | null
    mode?: GraphSubgraphMode
    focusedNodeIds?: string[]
    focusedEdgeIds?: string[]
    selectedNodeId?: string | null
    selectedEdgeId?: string | null
  }>(),
  {
    mode: 'path',
    focusedNodeIds: () => [],
    focusedEdgeIds: () => [],
    selectedNodeId: null,
    selectedEdgeId: null,
  },
)

const emit = defineEmits<{
  select: [
    payload:
      | { type: 'node'; id: string }
      | { type: 'edge'; id: string }
      | null,
  ]
  renderState: [
    payload: {
      phase: 'bootstrapping' | 'layout' | 'stable' | 'error'
      message: string
    },
  ]
}>()

function handleSelect(
  payload:
    | {
        type: 'node' | 'edge'
        item: { id: string }
      }
    | null,
) {
  if (!payload) {
    emit('select', null)
    return
  }

  emit('select', {
    type: payload.type,
    id: payload.item.id,
  })
}
</script>

<template>
  <div v-if="!dataset" class="run-path-graph run-path-graph--empty">
    <p>当前没有局部子图数据。</p>
  </div>
  <div v-else class="run-path-graph">
    <KnowledgeForceGraph
      :dataset="dataset"
      :show-labels="true"
      :search-term="''"
      :focused-node-ids="focusedNodeIds"
      :focused-edge-ids="focusedEdgeIds"
      :selected-node-id="selectedNodeId"
      :selected-edge-id="selectedEdgeId"
      @select="handleSelect"
      @render-state="(payload) => emit('renderState', payload)"
    />
  </div>
</template>

<style scoped>
.run-path-graph {
  min-height: 0;
  height: 100%;
}

.run-path-graph :deep(.knowledge-graph-chart) {
  min-height: 0;
  height: 100%;
}

.run-path-graph--empty {
  min-height: 0;
  height: 100%;
  place-items: center;
  display: grid;
  color: #52606d;
}
</style>
