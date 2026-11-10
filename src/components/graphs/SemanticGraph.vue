<script setup lang="ts">
import { computed, ref } from 'vue'
import type { RecordValue } from '@/api/workbench'
import { semanticGraph, expressionRefs } from '@/services/knowledge'
import { rows } from '@/services/presentation'
const props = defineProps<{ knowledge: RecordValue; selectedId?: string; highlightedIds?: string[]; compact?: boolean }>()
defineEmits<{ select: [id: string] }>()
const hovered = ref('')
const graph = computed(() => semanticGraph(props.knowledge))
const nodes = computed(() => graph.value.nodes.filter((n) => n.column < 3))
const height = computed(() => Math.max(props.compact ? 330 : 400, Math.min(690, Math.max(...[0, 1, 2].map((c) => nodes.value.filter((n) => n.column === c).length), 1) * 74 + 64)))
const positioned = computed(() => nodes.value.map((node) => {
  const count = nodes.value.filter((n) => n.column === node.column).length
  const step = (height.value - 58) / count
  return { ...node, x: 142 + node.column * 300, y: 49 + step * (node.index + .5) }
}))
const edges = computed(() => graph.value.edges.flatMap((edge) => {
  const from = positioned.value.find((n) => n.id === edge.from), to = positioned.value.find((n) => n.id === edge.to)
  if (!from || !to) return []
  return [{ ...edge, path: `M ${from.x + 114} ${from.y} C ${from.x + 160} ${from.y}, ${to.x - 160} ${to.y}, ${to.x - 114} ${to.y}` }]
}))
const focus = computed(() => hovered.value || props.selectedId || '')
function activeNode(id: string) { return id === focus.value || (props.highlightedIds?.includes(id) ?? false) || edges.value.some((e) => (e.from === focus.value && e.to === id) || (e.to === focus.value && e.from === id)) }
function activeEdge(from: string, to: string) { return from === focus.value || to === focus.value || (!!props.highlightedIds?.includes(from) && !!props.highlightedIds?.includes(to)) }
function conditionCount(id: string) { return expressionRefs(rows(props.knowledge.pattern_definitions).find((r) => r.pattern_id === id)?.body).length }
</script>
<template>
  <div class="semantic-graph-scroll"><div class="semantic-graph" :style="{ height: height + 'px' }">
    <div v-for="(group, index) in graph.groups.slice(0, 3)" :key="group.key" class="semantic-column-title" :style="{ left: (index * 33.333) + '%' }"><span>{{ String(index + 1).padStart(2, '0') }}</span>{{ group.title }}</div>
    <svg class="semantic-connectors" :style="{ height: height + 'px' }" :viewBox="`0 0 900 ${height}`" preserveAspectRatio="none" aria-hidden="true"><defs><marker id="semantic-arrow" markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto"><path d="M0 0L5 2.5L0 5" fill="#c5cfdf" /></marker><marker id="semantic-arrow-active" markerWidth="5" markerHeight="5" refX="4" refY="2.5" orient="auto"><path d="M0 0L5 2.5L0 5" fill="#7799df" /></marker></defs><path v-for="edge in edges" :key="edge.id" :d="edge.path" fill="none" :stroke="activeEdge(edge.from, edge.to) ? '#7799df' : '#dbe1eb'" :stroke-width="activeEdge(edge.from, edge.to) ? 1.8 : 1" :marker-end="activeEdge(edge.from, edge.to) ? 'url(#semantic-arrow-active)' : 'url(#semantic-arrow)'" :opacity="focus && !activeEdge(edge.from, edge.to) ? .4 : 1" /></svg>
    <button v-for="node in positioned" :key="node.id" class="semantic-node" :class="[node.role, { active: activeNode(node.id), selected: selectedId === node.id }]" :style="{ left: (node.x / 900 * 100) + '%', top: node.y + 'px' }" @click="$emit('select', node.id)" @mouseenter="hovered = node.id" @mouseleave="hovered = ''"><span class="semantic-node__dot" /><span>{{ node.label.replace(/[（(].*$/, '') }}<small v-if="node.role === 'pattern'">{{ conditionCount(node.id) }} 项联合条件</small></span></button>
    <div v-if="!nodes.length" class="empty-state"><p>该图没有可显示的语义内容。</p></div>
  </div></div>
</template>
<style scoped>
.semantic-graph-scroll{width:100%;overflow:auto;}.semantic-graph{position:relative;min-width:680px;background:radial-gradient(#e8edf5 .7px,transparent .7px);background-size:14px 14px;border-radius:6px;}.semantic-column-title{position:absolute;top:12px;width:33.333%;text-align:center;font-size:13px;color:#8390a4;z-index:1;font-weight:500;}.semantic-column-title span{font:9px 'SFMono-Regular',monospace;margin-right:9px;color:#7f8ca1;}.semantic-connectors{position:absolute;inset:0;width:100%;}.semantic-node{position:absolute;transform:translate(-50%,-50%);display:flex;align-items:center;gap:8px;width:25.5%;min-height:48px;padding:10px 12px;text-align:left;border:1px solid #e3e8f0;border-radius:7px;background:#fff;box-shadow:0 2px 3px #21345003;color:#5c6980;font-size:12px;line-height:1.6;transition:border-color .15s,box-shadow .15s;z-index:1;}.semantic-node__dot{width:6px;height:6px;border-radius:50%;background:#7193d4;flex-shrink:0;}.semantic-node.mechanism .semantic-node__dot{background:#aa8bcc;}.semantic-node.pattern .semantic-node__dot{background:#dfad6f;}.semantic-node:hover,.semantic-node.active{border-color:#7f8ca1;color:#355a9e;box-shadow:0 2px 8px #3166df08;}.semantic-node.selected{border-color:var(--blue);background:#f5f8ff;box-shadow:0 0 0 2px #3166df0d;}.semantic-node small{display:block;color:#7f8ca1;font-size:11px;margin-top:3px;}.semantic-node.pattern.active{border-color:#dbbe97;color:#7f8ca1;}.semantic-node.mechanism.active{border-color:#7f8ca1;color:#8664ae;}
</style>
