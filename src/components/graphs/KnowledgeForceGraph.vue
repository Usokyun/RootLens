<script setup lang="ts">
import { computed } from 'vue'
import { GraphChart } from 'echarts/charts'
import {
  GridComponent,
  LegendComponent,
  TooltipComponent,
} from 'echarts/components'
import { use } from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'
import VChart from 'vue-echarts'

import type {
  UnifiedGraphDataset,
  UnifiedGraphEdge,
  UnifiedGraphNode,
} from '@/types/graph'

use([CanvasRenderer, GraphChart, GridComponent, TooltipComponent, LegendComponent])

const palette = [
  '#0f8b8d',
  '#d97706',
  '#2563eb',
  '#b45309',
  '#0284c7',
  '#7c3aed',
  '#1d4ed8',
  '#0f766e',
  '#be123c',
  '#4f46e5',
  '#059669',
  '#a16207',
]

const props = defineProps<{
  dataset: UnifiedGraphDataset
  showLabels: boolean
  searchTerm: string
  focusedNodeIds?: string[]
  focusedEdgeIds?: string[]
}>()

const emit = defineEmits<{
  select: [
    payload:
      | { type: 'node'; item: UnifiedGraphNode }
      | { type: 'edge'; item: UnifiedGraphEdge },
  ]
}>()

const nodeById = computed(
  () =>
    new Map(props.dataset.nodes.map((node) => [node.id, node])),
)

const edgeById = computed(
  () =>
    new Map(props.dataset.edges.map((edge) => [edge.id, edge])),
)

const focusedEdgeIds = computed(
  () => new Set(props.focusedEdgeIds ?? []),
)

const focusedNodeIds = computed(
  () => new Set(props.focusedNodeIds ?? []),
)

const focusRelatedNodeIds = computed(() => {
  const related = new Set(focusedNodeIds.value)

  for (const edgeId of focusedEdgeIds.value) {
    const edge = edgeById.value.get(edgeId)

    if (!edge) {
      continue
    }

    related.add(edge.source)
    related.add(edge.target)
  }

  return related
})

const nodeCategoryNames = computed(() => {
  const unique = new Set(props.dataset.nodes.map((node) => node.category))
  return [...unique].sort((left, right) => left.localeCompare(right))
})

const categoryIndexByName = computed(
  () =>
    new Map(
      nodeCategoryNames.value.map((name, index) => [name, index]),
    ),
)

const highlightedNodeIds = computed(() => {
  const keyword = props.searchTerm.trim().toLowerCase()
  if (!keyword) {
    return new Set<string>()
  }

  return new Set(
    props.dataset.nodes
      .filter((node) => {
        const haystack = [
          node.id,
          node.name,
          node.category,
          node.kind,
          node.description,
          ...node.aliases,
        ]
          .join(' ')
          .toLowerCase()

        return haystack.includes(keyword)
      })
      .map((node) => node.id),
  )
})

const option = computed(() => {
  const keyword = props.searchTerm.trim().toLowerCase()
  const highlighted = highlightedNodeIds.value
  const focusedNodes = focusRelatedNodeIds.value
  const focusedEdges = focusedEdgeIds.value
  const hasSearch = Boolean(keyword)
  const hasFocus = Boolean(focusedNodes.size || focusedEdges.size)
  const categories = nodeCategoryNames.value.map((name) => ({
    name,
  }))

  const nodes = props.dataset.nodes.map((node) => {
    const categoryIndex = categoryIndexByName.value.get(node.category) ?? 0
    const isSearchMatched = highlighted.has(node.id)
    const isFocusMatched = focusedNodes.has(node.id)
    const isMatched = isSearchMatched || isFocusMatched
    const opacity =
      !hasSearch && !hasFocus
        ? 0.9
        : isMatched
          ? 1
          : hasFocus && !hasSearch
            ? 0.14
            : 0.22

    return {
      id: node.id,
      name: node.name,
      category: categoryIndex,
      value: node.degree,
      symbolSize:
        Math.max(10, Math.min(34, 10 + Math.sqrt(node.degree || 1) * 2.8)) +
        (isFocusMatched ? 4 : 0),
      draggable: true,
      label: {
        show: props.showLabels || isMatched,
        position: 'right',
        color: '#12232f',
        fontSize: 10,
      },
      itemStyle: {
        color: palette[categoryIndex % palette.length],
        opacity,
        borderColor: isFocusMatched ? '#0f172a' : 'rgba(255, 255, 255, 0.56)',
        borderWidth: isFocusMatched ? 2.6 : 0.8,
        shadowBlur: isFocusMatched ? 18 : 0,
        shadowColor: isFocusMatched ? 'rgba(15, 23, 42, 0.25)' : 'transparent',
      },
      emphasis: {
        scale: true,
        label: {
          show: true,
        },
      },
    }
  })

  const links = props.dataset.edges.map((edge) => {
    const isSearchRelated = highlighted.has(edge.source) || highlighted.has(edge.target)
    const isFocusMatched = focusedEdges.has(edge.id)
    const isFocusRelated = focusedNodes.has(edge.source) || focusedNodes.has(edge.target)
    const isRelated = isSearchRelated || isFocusMatched || isFocusRelated
    const opacity =
      !hasSearch && !hasFocus
        ? 0.18
        : isFocusMatched
          ? 0.94
          : isFocusRelated
            ? 0.64
            : isRelated
              ? 0.42
              : 0.04
    const widthBase = edge.weight ?? edge.confidence ?? 0.3

    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      value: edge.relation,
      lineStyle: {
        width: Math.max(0.8, Math.min(3.5, widthBase * 3)) + (isFocusMatched ? 1.8 : 0),
        opacity,
        curveness: 0.08,
        type: isFocusMatched ? 'solid' : 'dashed',
      },
      emphasis: {
        lineStyle: {
          opacity: 0.88,
          width: Math.max(1.6, Math.min(5, widthBase * 4)),
        },
      },
    }
  })

  return {
    backgroundColor: 'transparent',
    animation: false,
    legend: [
      {
        type: 'scroll',
        bottom: 6,
        icon: 'circle',
        pageIconColor: '#0f8b8d',
        pageTextStyle: {
          color: '#5a6a77',
        },
        textStyle: {
          color: '#5a6a77',
          fontSize: 11,
        },
        data: categories.map((item) => item.name),
      },
    ],
    tooltip: {
      trigger: 'item',
      backgroundColor: 'rgba(13, 31, 38, 0.92)',
      borderWidth: 0,
      textStyle: {
        color: '#eff8f8',
      },
      formatter: (params: { dataType?: string; data?: { id?: string } }) => {
        if (params.dataType === 'edge' && params.data?.id) {
          const edge = edgeById.value.get(params.data.id)
          if (!edge) {
            return ''
          }

          return [
            `<strong>${edge.relation}</strong>`,
            `${edge.source} → ${edge.target}`,
            `layer: ${edge.origin.layer}`,
          ].join('<br>')
        }

        if (params.dataType === 'node' && params.data?.id) {
          const node = nodeById.value.get(params.data.id)
          if (!node) {
            return ''
          }

          return [
            `<strong>${node.name}</strong>`,
            `id: ${node.id}`,
            `category: ${node.category}`,
            `degree: ${node.degree}`,
          ].join('<br>')
        }

        return ''
      },
    },
    series: [
      {
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        focusNodeAdjacency: true,
        data: nodes,
        links,
        categories,
        edgeSymbol: ['none', 'arrow'],
        edgeSymbolSize: props.dataset.nodes.length > 500 ? 4 : 6,
        force: {
          repulsion: props.dataset.nodes.length > 500 ? 26 : 90,
          gravity: props.dataset.nodes.length > 500 ? 0.18 : 0.08,
          edgeLength: props.dataset.nodes.length > 500 ? [8, 20] : [35, 110],
          friction: 0.45,
        },
        lineStyle: {
          color: 'source',
        },
        emphasis: {
          focus: 'adjacency',
          label: {
            show: true,
          },
        },
      },
    ],
  }
})

function handleChartClick(params: unknown) {
  const payload = params as {
    dataType?: string
    data?: {
      id?: string
    } | null
  }

  if (payload.dataType === 'node' && payload.data?.id) {
    const node = nodeById.value.get(payload.data.id)
    if (node) {
      emit('select', {
        type: 'node',
        item: node,
      })
    }
  }

  if (payload.dataType === 'edge' && payload.data?.id) {
    const edge = edgeById.value.get(payload.data.id)
    if (edge) {
      emit('select', {
        type: 'edge',
        item: edge,
      })
    }
  }
}
</script>

<template>
  <VChart
    :key="dataset.id"
    :option="option"
    autoresize
    class="knowledge-graph-chart"
    @click="handleChartClick"
  />
</template>
