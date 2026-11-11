<script setup lang="ts">
import { IconMinus, IconPlus, IconSearch } from '@arco-design/web-vue/es/icon'
import { computed, ref, watch } from 'vue'
import type { KGStudioPayload } from '@/api/contracts'
import {
  buildWorkingGraphView, findWorkingGraphNodes, graphPreviewEdgeLimit, workingGraphFocus, workingGraphGroups,
  workingGraphKind, type WorkingGraphGroup, type WorkingGraphSelection,
} from '@/services/working-graph-view'
import KnowledgeForceGraph from './KnowledgeForceGraph.vue'

const props = defineProps<{ studio: KGStudioPayload; selection: WorkingGraphSelection }>()
const emit = defineEmits<{ select: [selection: WorkingGraphSelection] }>()
const canvas = ref<InstanceType<typeof KnowledgeForceGraph> | null>(null)
const term = ref('')
const searching = ref(false)
const group = ref<WorkingGraphGroup | null>(null)
const view = computed(() => buildWorkingGraphView(props.studio))
const matches = computed(() => findWorkingGraphNodes(view.value, term.value))
const matchingIds = computed(() => matches.value.map(node => node.id))
const focus = computed(() => workingGraphFocus(view.value, props.selection, group.value))
const legend = computed(() => (Object.keys(workingGraphGroups) as WorkingGraphGroup[]).flatMap(key => {
  const count = view.value.groupCounts.get(key) ?? 0
  return count ? [{ key, count, ...workingGraphGroups[key], label: key === 'cause' && view.value.scenarios.includes('wafer') ? '图案候选' : workingGraphGroups[key].label }] : []
}))
const partial = computed(() => view.value.dataset.nodes.length < view.value.nodeTotal || view.value.dataset.edges.length < view.value.edgeTotal)
const searchResults = computed(() => matches.value.slice(0, 6))
watch(() => props.selection, selection => { if (selection) group.value = null })

function choose(selection: WorkingGraphSelection) {
  group.value = null
  searching.value = false
  emit('select', selection)
}
function focusGroup(key: WorkingGraphGroup) {
  group.value = group.value === key ? null : key
  term.value = ''
  searching.value = false
  if (props.selection) emit('select', null)
}
function pickFirst() {
  const first = matches.value[0]
  if (first) choose({ type: 'node', id: first.id })
}
</script>

<template>
  <section class="working-network" aria-label="知识网络">
    <header class="network-head">
      <div class="network-title">
        <h2>知识网络</h2>
        <p data-testid="working-graph-preview-count"
          :title="partial ? `画布最多预览 ${graphPreviewEdgeLimit} 条关系` : undefined">
          {{ partial ? '预览 ' : '' }}{{ view.dataset.nodes.length }}{{ partial ? ` / ${view.nodeTotal}` : '' }} 节点
          · {{ view.dataset.edges.length }}{{ partial ? ` / ${view.edgeTotal}` : '' }} 关系
        </p>
      </div>
      <div class="network-search" @focusout="event => { if (!(event.currentTarget as HTMLElement).contains(event.relatedTarget as Node | null)) searching = false }">
        <a-input v-model="term" allow-clear placeholder="节点、别名或通道"
          :input-attrs="{ 'aria-label': '搜索节点、别名或通道' }" @focus="searching = true" @input="searching = true"
          @keydown.enter.prevent="pickFirst" @keydown.escape.stop="searching = false">
          <template #prefix><IconSearch /></template>
        </a-input>
        <div v-if="searching && term.trim()" class="network-results" aria-label="预览节点搜索结果">
          <p role="status">{{ matches.length ? `预览中找到 ${matches.length} 个节点` : '当前预览中没有匹配节点' }}</p>
          <button v-for="node in searchResults" :key="node.id" type="button" @click="choose({ type: 'node', id: node.id })">
            <span>{{ node.name }}</span><small>{{ workingGraphKind(node.kind, String(node.attributes.scenario)).label }}</small>
          </button>
          <p v-if="matches.length > searchResults.length">继续输入可缩小范围</p>
        </div>
      </div>
    </header>

    <div v-if="view.dataset.nodes.length" class="network-stage">
      <KnowledgeForceGraph ref="canvas" :dataset="view.dataset" show-labels search-term=""
        :semantic-appearance="workingGraphGroups" :search-matches="matchingIds"
        :selected-node-id="selection?.type === 'node' ? selection.id : null"
        :selected-edge-id="selection?.type === 'edge' ? selection.id : null"
        :focused-node-ids="focus.nodes" :focused-edge-ids="focus.edges" aria-label="工作图有向知识网络"
        @select="choose($event ? { type: $event.type, id: $event.item.id } : null)" />
      <div class="network-tools">
        <small>点击节点或边 · 拖动画布</small>
        <div class="network-zoom" aria-label="画布缩放">
          <a-button size="mini" aria-label="缩小画布" @click="canvas?.zoomBy(.8)"><IconMinus /></a-button>
          <a-button size="mini" aria-label="放大画布" @click="canvas?.zoomBy(1.25)"><IconPlus /></a-button>
          <a-button size="mini" aria-label="适配画布" @click="canvas?.fitViewport()">适配</a-button>
        </div>
      </div>
    </div>
    <div v-else class="network-empty">这张工作图没有可预览的节点。</div>

    <footer v-if="legend.length" class="network-legend" aria-label="节点类型图例">
      <button v-for="entry in legend" :key="entry.key" type="button" :aria-pressed="group === entry.key"
        :class="{ 'is-focused': group === entry.key }" @click="focusGroup(entry.key)">
        <span class="network-symbol" :class="`is-${entry.shape}`" :style="{ backgroundColor: entry.color }" aria-hidden="true" />
        {{ entry.label }} <span class="network-count">{{ entry.count }}</span>
      </button>
      <small v-if="partial" class="network-limit">最多预览 {{ graphPreviewEdgeLimit }} 条关系</small>
    </footer>
  </section>
</template>

<style scoped>
.working-network {
  display: flex; flex-direction: column; min-width: 0; min-height: 0; height: 100%;
  border: 1px solid var(--color-border-2); border-radius: 5px; background: var(--color-bg-2);
}
.network-head {
  display: flex; flex: 0 0 auto; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 10px 16px;
  min-height: 60px; padding: 9px 13px; border-bottom: 1px solid var(--color-border-2);
}
.network-title h2 { margin: 0 0 4px; color: var(--color-text-1); font-size: 14px; font-weight: 650; }
.network-title p { margin: 0; color: var(--color-text-2); font-size: 12px; }
.network-search { position: relative; width: 204px; max-width: 100%; }
.network-results {
  position: absolute; z-index: 3; top: calc(100% + 5px); width: max(100%, 220px); max-width: calc(100vw - 82px); right: 0;
  padding: 4px; background: var(--color-bg-popup); border: 1px solid var(--color-border-2); border-radius: 4px;
  box-shadow: 0 4px 14px rgb(28 49 75 / 12%);
}
.network-results p { margin: 0; padding: 5px 7px; font-size: 12px; color: var(--color-text-3); }
.network-results button {
  display: flex; gap: 3px; flex-direction: column; width: 100%; min-width: 0; padding: 6px 7px; text-align: left;
  border: 0; border-radius: 3px; background: transparent; color: var(--color-text-1); cursor: pointer;
  font: inherit; font-size: 12px; overflow-wrap: anywhere;
}
.network-results button:hover, .network-results button:focus-visible { background: var(--color-primary-light-1); }
.network-results small { color: var(--color-text-3); }
.network-stage { position: relative; min-height: 330px; flex: 1 1 420px; }
.network-stage > :deep(.knowledge-graph-chart) { position: absolute; inset: 0; }
.network-tools {
  display: flex; align-items: flex-end; justify-content: space-between; gap: 6px; pointer-events: none;
  position: absolute; inset: auto 9px 8px; color: var(--color-text-3);
}
.network-tools > small { padding: 3px 5px; border-radius: 3px; background: var(--color-bg-2); font-size: 11px; }
.network-zoom { display: flex; gap: 4px; pointer-events: auto; }
.network-zoom :deep(.arco-btn) { color: var(--color-text-1); background: var(--color-bg-2); border: 1px solid var(--color-border-2); }
.network-empty { min-height: 330px; flex: 1; display: grid; place-items: center; padding: 16px; color: var(--color-text-3); }
.network-legend { display: flex; flex: 0 0 auto; align-items: center; gap: 3px 7px; flex-wrap: wrap; min-height: 38px; border-top: 1px solid var(--color-border-2); padding: 5px 10px; }
.network-legend button {
  display: inline-flex; align-items: center; gap: 5px; border-radius: 3px; border: 0; padding: 4px 3px;
  font: inherit; font-size: 12px; white-space: nowrap; background: transparent; color: var(--color-text-1); cursor: pointer;
}
.network-legend button:hover, .network-legend button.is-focused { background: var(--color-primary-light-1); color: rgb(var(--primary-6)); }
.network-symbol { display: inline-block; width: 8px; height: 8px; flex: none; }
.network-symbol.is-diamond { width: 7px; height: 7px; transform: rotate(45deg); }
.network-symbol.is-circle { border-radius: 50%; }
.network-symbol.is-square { border-radius: 1px; }
.network-symbol.is-ellipse { width: 11px; height: 6px; border-radius: 50%; }
.network-count, .network-limit { color: var(--color-text-3); }
.network-limit { margin-left: auto; font-size: 11px; }
@media (max-width: 540px) {
  .network-search { width: 100%; }
  .network-results { width: 100%; max-width: 100%; }
  .network-stage { flex-basis: 330px; }
  .network-tools > small { display: none; }
  .network-zoom { margin-left: auto; }
  .network-limit { margin-left: 3px; }
}
</style>
