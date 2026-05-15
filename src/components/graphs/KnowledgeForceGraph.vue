<script setup lang="ts">
import { IconSync } from '@arco-design/web-vue/es/icon'
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'

import { loadD3 } from '@/services/d3-loader'
import type {
  UnifiedGraphDataset,
  UnifiedGraphEdge,
  UnifiedGraphNode,
} from '@/types/graph'

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

interface LayoutSnapshot {
  x: number
  y: number
  vx: number
  vy: number
}

interface RenderNode extends UnifiedGraphNode {
  x: number
  y: number
  vx: number
  vy: number
  fx?: number | null
  fy?: number | null
  radius: number
  categoryIndex: number
}

interface RenderEdge extends Omit<UnifiedGraphEdge, 'source' | 'target'> {
  source: string | RenderNode
  target: string | RenderNode
}

interface GraphScene {
  d3: any
  svg: any
  viewport: any
  links: any
  nodes: any
  circles: any
  labels: any
  simulation: any
  nodeItems: RenderNode[]
  edgeItems: RenderEdge[]
  width: number
  height: number
}

type GraphRenderPhase = 'bootstrapping' | 'layout' | 'stable' | 'error'

const layoutCache = new Map<string, Map<string, LayoutSnapshot>>()

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
      | { type: 'edge'; item: UnifiedGraphEdge }
      | null,
  ]
  hover: [
    payload:
      | { type: 'node'; item: UnifiedGraphNode }
      | { type: 'edge'; item: UnifiedGraphEdge }
      | null,
  ]
  renderState: [
    payload: {
      phase: GraphRenderPhase
      message: string
    },
  ]
}>()

const chartRef = ref<HTMLDivElement | null>(null)
const surfaceRef = ref<HTMLDivElement | null>(null)
const scene = shallowRef<GraphScene | null>(null)

const bootstrapping = ref(true)
const layoutRunning = ref(false)
const renderError = ref('')
const statusMessage = ref('加载 D3 渲染器...')

function emitRenderState(phase: GraphRenderPhase, message: string) {
  emit('renderState', {
    phase,
    message,
  })
}

const nodeById = computed(() => new Map(props.dataset.nodes.map((node) => [node.id, node])))
const edgeById = computed(() => new Map(props.dataset.edges.map((edge) => [edge.id, edge])))
const focusedEdgeIds = computed(() => new Set(props.focusedEdgeIds ?? []))
const focusedNodeIds = computed(() => new Set(props.focusedNodeIds ?? []))

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
  () => new Map(nodeCategoryNames.value.map((name, index) => [name, index])),
)

const highlightedNodeIds = computed(() => {
  const keyword = props.searchTerm.trim().toLowerCase()
  if (!keyword) {
    return new Set<string>()
  }

  return new Set(
    props.dataset.nodes
      .filter((node) => {
        const haystack = [node.id, node.name, node.category, node.kind, node.description, ...node.aliases]
          .join(' ')
          .toLowerCase()

        return haystack.includes(keyword)
      })
      .map((node) => node.id),
  )
})

let renderVersion = 0
let resizeObserver: ResizeObserver | null = null
let tickFrame = 0
let renderStartId: number | null = null
let motionPulseId: number | null = null

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}

function waitForRenderTurn() {
  return new Promise<void>((resolve) => {
    window.requestAnimationFrame(() => {
      window.setTimeout(resolve, 0)
    })
  })
}

function resolveEndpointId(endpoint: string | RenderNode) {
  return typeof endpoint === 'string' ? endpoint : endpoint.id
}

function cacheLayout() {
  if (!scene.value) {
    return
  }

  layoutCache.set(
    props.dataset.id,
    new Map(
      scene.value.nodeItems.map((node) => [
        node.id,
        {
          x: node.x,
          y: node.y,
          vx: node.vx ?? 0,
          vy: node.vy ?? 0,
        },
      ]),
    ),
  )
}

function clearRenderSchedule() {
  if (renderStartId !== null) {
    window.clearTimeout(renderStartId)
    renderStartId = null
  }
}

function clearMotionPulse() {
  if (motionPulseId !== null) {
    window.clearTimeout(motionPulseId)
    motionPulseId = null
  }
}

function applySceneForces() {
  if (!scene.value) {
    return
  }

  const simulation = scene.value.simulation
  const defaultCharge = props.dataset.nodes.length > 300 ? -48 : -118

  simulation
    .force('cluster-x', null)
    .force('cluster-y', null)
    .force('charge', scene.value.d3.forceManyBody().strength(defaultCharge))
    .force(
      'collide',
      scene.value.d3.forceCollide().radius((node: RenderNode) => node.radius + 6).strength(0.72),
    )
}

function pulseGraphMotion() {
  if (!scene.value) {
    return
  }

  const intensity = props.dataset.nodes.length > 380 ? 0.12 : 0.2
  for (const node of scene.value.nodeItems) {
    node.vx = (node.vx ?? 0) + (Math.random() - 0.5) * intensity
    node.vy = (node.vy ?? 0) + (Math.random() - 0.5) * intensity
  }

  scene.value.simulation.alphaTarget(0.06).alpha(0.16).restart()
  clearMotionPulse()
  motionPulseId = window.setTimeout(() => {
    if (scene.value) {
      scene.value.simulation.alphaTarget(0)
    }
    motionPulseId = null
  }, 760)
}

function stopScene() {
  clearRenderSchedule()

  if (tickFrame) {
    window.cancelAnimationFrame(tickFrame)
    tickFrame = 0
  }

  if (scene.value?.simulation) {
    scene.value.simulation.stop()
  }

  if (surfaceRef.value) {
    surfaceRef.value.innerHTML = ''
  }

  emit('hover', null)
  scene.value = null
}

function scheduleRenderGraph() {
  clearRenderSchedule()
  const delay = props.dataset.nodes.length > 420 ? 180 : 90

  renderStartId = window.setTimeout(() => {
    renderStartId = null
    void renderGraph()
  }, delay)
}

function applyDecorations() {
  if (!scene.value) {
    return
  }

  const keywordMatches = highlightedNodeIds.value
  const focusedNodes = focusRelatedNodeIds.value
  const focusedEdgesSet = focusedEdgeIds.value
  const hasSearch = keywordMatches.size > 0
  const hasFocus = focusedNodes.size > 0 || focusedEdgesSet.size > 0

  scene.value.circles
    .attr('r', (node: RenderNode) => {
      const isSearchMatched = keywordMatches.has(node.id)
      const isFocusMatched = focusedNodes.has(node.id)
      return node.radius + (isFocusMatched ? 4 : isSearchMatched ? 2 : 0)
    })
    .attr('opacity', (node: RenderNode) => {
      const isSearchMatched = keywordMatches.has(node.id)
      const isFocusMatched = focusedNodes.has(node.id)
      const isMatched = isSearchMatched || isFocusMatched

      if (!hasSearch && !hasFocus) {
        return 0.94
      }

      if (isMatched) {
        return 1
      }

      return hasFocus && !hasSearch ? 0.16 : 0.22
    })
    .attr('fill', (node: RenderNode) => palette[node.categoryIndex % palette.length])
    .attr('stroke', (node: RenderNode) => {
      if (focusedNodes.has(node.id)) {
        return '#0f172a'
      }

      if (keywordMatches.has(node.id)) {
        return '#1d4ed8'
      }

      return 'rgba(255, 255, 255, 0.72)'
    })
    .attr('stroke-width', (node: RenderNode) => {
      if (focusedNodes.has(node.id)) {
        return 2.8
      }

      if (keywordMatches.has(node.id)) {
        return 1.8
      }

      return 0.9
    })
    .attr('filter', (node: RenderNode) =>
      focusedNodes.has(node.id) ? 'drop-shadow(0 0 18px rgba(29, 78, 216, 0.28))' : null,
    )

  scene.value.labels
    .attr('display', (node: RenderNode) =>
      props.showLabels || keywordMatches.has(node.id) || focusedNodes.has(node.id) ? null : 'none',
    )
    .attr('opacity', (node: RenderNode) => (focusedNodes.has(node.id) ? 1 : keywordMatches.has(node.id) ? 0.92 : 0.82))

  scene.value.links
    .attr('opacity', (edge: RenderEdge) => {
      const sourceId = resolveEndpointId(edge.source)
      const targetId = resolveEndpointId(edge.target)
      const isSearchRelated = keywordMatches.has(sourceId) || keywordMatches.has(targetId)
      const isFocusMatched = focusedEdgesSet.has(edge.id)
      const isFocusRelated = focusedNodes.has(sourceId) || focusedNodes.has(targetId)
      const isRelated = isSearchRelated || isFocusMatched || isFocusRelated

      if (!hasSearch && !hasFocus) {
        return 0.18
      }

      if (isFocusMatched) {
        return 0.96
      }

      if (isFocusRelated) {
        return 0.68
      }

      if (isRelated) {
        return 0.42
      }

      return 0.05
    })
    .attr('stroke', (edge: RenderEdge) => (focusedEdgesSet.has(edge.id) ? '#1d4ed8' : '#7b8ea8'))
    .attr('stroke-width', (edge: RenderEdge) => {
      const widthBase = edge.weight ?? edge.confidence ?? 0.3
      return Math.max(0.8, Math.min(4.2, widthBase * 3.4)) + (focusedEdgesSet.has(edge.id) ? 1.8 : 0)
    })
    .attr('stroke-dasharray', (edge: RenderEdge) => (focusedEdgesSet.has(edge.id) ? null : '3 4'))
}

function scheduleTickRender() {
  if (!scene.value || tickFrame) {
    return
  }

  tickFrame = window.requestAnimationFrame(() => {
    tickFrame = 0

    if (!scene.value) {
      return
    }

    scene.value.links
      .attr('x1', (edge: RenderEdge) => (edge.source as RenderNode).x)
      .attr('y1', (edge: RenderEdge) => (edge.source as RenderNode).y)
      .attr('x2', (edge: RenderEdge) => (edge.target as RenderNode).x)
      .attr('y2', (edge: RenderEdge) => (edge.target as RenderNode).y)

    scene.value.nodes.attr('transform', (node: RenderNode) => `translate(${node.x}, ${node.y})`)

    if (bootstrapping.value) {
      bootstrapping.value = false
      statusMessage.value = '图谱已切换，力导向布局正在稳定...'
      emitRenderState('layout', statusMessage.value)
    }
  })
}

function bindResizeObserver() {
  if (!chartRef.value) {
    return
  }

  resizeObserver?.disconnect()
  resizeObserver = new ResizeObserver(() => {
    if (!scene.value || !chartRef.value) {
      return
    }

    const nextWidth = Math.max(chartRef.value.clientWidth, 680)
    const nextHeight = Math.max(chartRef.value.clientHeight, 520)

    scene.value.width = nextWidth
    scene.value.height = nextHeight
    scene.value.svg.attr('viewBox', `0 0 ${nextWidth} ${nextHeight}`)
    scene.value.simulation.force('center', scene.value.d3.forceCenter(nextWidth / 2, nextHeight / 2))
    applySceneForces()
    scene.value.simulation.alpha(0.18).restart()
  })
  resizeObserver.observe(chartRef.value)
}

async function buildRenderNodes(
  version: number,
  width: number,
  height: number,
  cachedLayout: Map<string, LayoutSnapshot> | undefined,
  categoryIndex: Map<string, number>,
) {
  const total = props.dataset.nodes.length
  const nodeItems = new Array<RenderNode>(total)

  for (let index = 0; index < total; index += 1) {
    if (index > 0 && index % 120 === 0) {
      await waitForRenderTurn()
      if (version !== renderVersion || !chartRef.value || !surfaceRef.value) {
        return null
      }
    }

    const node = props.dataset.nodes[index]
    const cached = cachedLayout?.get(node.id)
    const fallbackAngle = (index / Math.max(total, 1)) * Math.PI * 2
    const fallbackRadius = Math.min(width, height) * 0.22
    const categoryIdx = categoryIndex.get(node.category) ?? 0

    nodeItems[index] = {
      ...node,
      categoryIndex: categoryIdx,
      radius: Math.max(9, Math.min(30, 10 + Math.sqrt(node.degree || 1) * 2.6)),
      x: cached?.x ?? width / 2 + Math.cos(fallbackAngle) * fallbackRadius,
      y: cached?.y ?? height / 2 + Math.sin(fallbackAngle) * fallbackRadius,
      vx: cached?.vx ?? 0,
      vy: cached?.vy ?? 0,
    }
  }

  return nodeItems
}

async function buildRenderEdges(version: number) {
  const total = props.dataset.edges.length
  const edgeItems = new Array<RenderEdge>(total)

  for (let index = 0; index < total; index += 1) {
    if (index > 0 && index % 320 === 0) {
      await waitForRenderTurn()
      if (version !== renderVersion || !chartRef.value || !surfaceRef.value) {
        return null
      }
    }

    const edge = props.dataset.edges[index]
    edgeItems[index] = {
      ...edge,
      source: edge.source,
      target: edge.target,
    }
  }

  return edgeItems
}

async function renderGraph() {
  const version = ++renderVersion
  const host = chartRef.value
  const surface = surfaceRef.value

  if (!host || !surface) {
    return
  }

  renderError.value = ''
  bootstrapping.value = true
  layoutRunning.value = false
  statusMessage.value = '加载 D3 渲染器...'
  emitRenderState('bootstrapping', statusMessage.value)
  stopScene()

  try {
    const d3 = await loadD3()

    if (version !== renderVersion || !chartRef.value || !surfaceRef.value) {
      return
    }

    const width = Math.max(chartRef.value.clientWidth, 680)
    const height = Math.max(chartRef.value.clientHeight, 520)
    const cachedLayout = layoutCache.get(props.dataset.id)
    const categoryIndex = categoryIndexByName.value

    statusMessage.value = '组装图谱并启动力导向布局...'
    emitRenderState('bootstrapping', statusMessage.value)
    await waitForRenderTurn()

    if (version !== renderVersion || !chartRef.value || !surfaceRef.value) {
      return
    }

    const nodeItems = await buildRenderNodes(version, width, height, cachedLayout, categoryIndex)
    if (!nodeItems) {
      return
    }

    const edgeItems = await buildRenderEdges(version)
    if (!edgeItems) {
      return
    }

    const svg = d3
      .select(surfaceRef.value)
      .append('svg')
      .attr('class', 'knowledge-graph-chart__svg')
      .attr('width', '100%')
      .attr('height', '100%')
      .attr('viewBox', `0 0 ${width} ${height}`)

    svg
      .append('defs')
      .append('marker')
      .attr('id', `graph-arrow-${props.dataset.id}`)
      .attr('viewBox', '0 0 10 10')
      .attr('refX', 8)
      .attr('refY', 5)
      .attr('markerWidth', 7)
      .attr('markerHeight', 7)
      .attr('orient', 'auto-start-reverse')
      .append('path')
      .attr('d', 'M 0 0 L 10 5 L 0 10 z')
      .attr('fill', '#8aa1bc')

    const viewport = svg.append('g').attr('class', 'knowledge-graph-chart__viewport')

    svg
      .call(
        d3
          .zoom()
          .scaleExtent([0.36, 3.2])
          .on('zoom', (event: any) => {
            viewport.attr('transform', event.transform)
          }),
      )
      .on('dblclick.zoom', null)
      .on('click', () => {
        emit('select', null)
        emit('hover', null)
      })
      .on('mouseleave', () => {
        emit('hover', null)
      })

    const links = viewport
      .append('g')
      .attr('class', 'knowledge-graph-chart__links')
      .selectAll('line')
      .data(edgeItems, (edge: RenderEdge) => edge.id)
      .join('line')
      .attr('stroke-linecap', 'round')
      .attr('marker-end', (edge: RenderEdge) =>
        edge.directed ? `url(#graph-arrow-${props.dataset.id})` : null,
      )
      .style('pointer-events', 'stroke')
      .on('click', (event: MouseEvent, edge: RenderEdge) => {
        event.stopPropagation()
        const original = edgeById.value.get(edge.id)
        if (!original) {
          return
        }

        emit('select', {
          type: 'edge',
          item: original,
        })
      })
      .on('mouseenter', (_event: MouseEvent, edge: RenderEdge) => {
        const original = edgeById.value.get(edge.id)
        if (!original) {
          return
        }

        emit('hover', {
          type: 'edge',
          item: original,
        })
      })
      .on('mouseleave', () => {
        emit('hover', null)
      })

    const nodes = viewport
      .append('g')
      .attr('class', 'knowledge-graph-chart__nodes')
      .selectAll('g')
      .data(nodeItems, (node: RenderNode) => node.id)
      .join('g')
      .style('cursor', 'pointer')
      .on('click', (event: MouseEvent, node: RenderNode) => {
        event.stopPropagation()
        const original = nodeById.value.get(node.id)
        if (!original) {
          return
        }

        emit('select', {
          type: 'node',
          item: original,
        })
      })
      .on('mouseenter', (_event: MouseEvent, node: RenderNode) => {
        const original = nodeById.value.get(node.id)
        if (!original) {
          return
        }

        emit('hover', {
          type: 'node',
          item: original,
        })
      })
      .on('mouseleave', () => {
        emit('hover', null)
      })

    const circles = nodes
      .append('circle')
      .attr('stroke-linejoin', 'round')

    const labels = nodes
      .append('text')
      .attr('dx', 10)
      .attr('dy', 3)
      .attr('font-size', 10.5)
      .attr('fill', '#10253b')
      .style('paint-order', 'stroke')
      .style('stroke', 'rgba(255, 255, 255, 0.88)')
      .style('stroke-width', 3)
      .style('pointer-events', 'none')
      .text((node: RenderNode) => node.name)

    await waitForRenderTurn()

    if (version !== renderVersion || !chartRef.value || !surfaceRef.value) {
      return
    }

    const simulation = d3
      .forceSimulation(nodeItems)
      .force(
        'link',
        d3
          .forceLink(edgeItems)
          .id((node: RenderNode) => node.id)
          .distance((edge: RenderEdge) =>
            props.dataset.nodes.length > 300
              ? 24
              : clamp(((edge.weight ?? edge.confidence ?? 0.42) + 0.15) * 88, 38, 110),
          )
          .strength((edge: RenderEdge) => clamp((edge.weight ?? edge.confidence ?? 0.32) + 0.08, 0.12, 0.72)),
      )
      .force('charge', d3.forceManyBody().strength(props.dataset.nodes.length > 300 ? -48 : -118))
      .force('collide', d3.forceCollide().radius((node: RenderNode) => node.radius + 6).strength(0.72))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .alpha(cachedLayout ? 0.42 : 0.95)
      .alphaDecay(props.dataset.nodes.length > 250 ? 0.08 : 0.055)
      .velocityDecay(0.34)

    nodes.call(
      d3
        .drag()
        .on('start', (event: any, node: RenderNode) => {
          if (!event.active) {
            simulation.alphaTarget(0.16).restart()
          }
          node.fx = node.x
          node.fy = node.y
        })
        .on('drag', (event: any, node: RenderNode) => {
          node.fx = event.x
          node.fy = event.y
        })
        .on('end', (event: any, node: RenderNode) => {
          if (!event.active) {
            simulation.alphaTarget(0)
          }
          node.fx = null
          node.fy = null
          cacheLayout()
        }),
    )

    scene.value = {
      d3,
      svg,
      viewport,
      links,
      nodes,
      circles,
      labels,
      simulation,
      nodeItems,
      edgeItems,
      width,
      height,
    }

    applySceneForces()
    applyDecorations()
    window.requestAnimationFrame(() => {
      if (version === renderVersion && scene.value) {
        pulseGraphMotion()
      }
    })

    layoutRunning.value = true
    simulation.on('tick', scheduleTickRender)
    simulation.on('end', () => {
      scheduleTickRender()
      cacheLayout()
      layoutRunning.value = false
      if (!renderError.value) {
        statusMessage.value = '布局已稳定'
        emitRenderState('stable', statusMessage.value)
      }
    })

    bindResizeObserver()
  } catch (error) {
    renderError.value = error instanceof Error ? error.message : 'D3 graph render failed'
    bootstrapping.value = false
    layoutRunning.value = false
    emitRenderState('error', renderError.value)
  }
}

watch(
  () => props.dataset,
  () => {
    emit('hover', null)
    scheduleRenderGraph()
  },
)

watch(
  [
    () => props.showLabels,
    () => props.searchTerm,
    () => (props.focusedNodeIds ?? []).join('|'),
    () => (props.focusedEdgeIds ?? []).join('|'),
  ],
  () => {
    applyDecorations()
  },
)

onMounted(() => {
  scheduleRenderGraph()
})

onBeforeUnmount(() => {
  clearRenderSchedule()
  clearMotionPulse()
  emit('hover', null)
  resizeObserver?.disconnect()
  stopScene()
})
</script>

<template>
  <div ref="chartRef" class="knowledge-graph-chart">
    <div ref="surfaceRef" class="knowledge-graph-chart__surface" />

    <transition name="graph-fade">
      <div v-if="bootstrapping && !renderError" class="knowledge-graph-chart__overlay">
        <span class="knowledge-graph-chart__overlay-spinner">
          <icon-sync />
        </span>
        <p>{{ statusMessage }}</p>
      </div>
    </transition>

    <transition name="graph-fade">
      <div v-if="layoutRunning && !bootstrapping && !renderError" class="knowledge-graph-chart__status">
        <span class="knowledge-graph-chart__status-dot" />
        <span>{{ statusMessage }}</span>
      </div>
    </transition>

    <div v-if="renderError" class="knowledge-graph-chart__error">
      <strong>D3 render failed</strong>
      <span>{{ renderError }}</span>
    </div>
  </div>
</template>

<style scoped>
.knowledge-graph-chart {
  position: relative;
  height: 100%;
  min-height: 520px;
  overflow: hidden;
  border-radius: 18px;
  background:
    radial-gradient(circle at top left, rgba(63, 124, 255, 0.14), transparent 24%),
    radial-gradient(circle at bottom right, rgba(15, 139, 141, 0.12), transparent 22%),
    linear-gradient(180deg, rgba(248, 251, 255, 0.98), rgba(242, 247, 252, 0.98));
}

.knowledge-graph-chart__surface {
  position: absolute;
  inset: 0;
}

.knowledge-graph-chart__overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: rgba(248, 251, 255, 0.86);
  backdrop-filter: blur(4px);
  color: #39526c;
}

.knowledge-graph-chart__overlay p {
  margin: 0;
  font-size: 13px;
}

.knowledge-graph-chart__overlay-spinner {
  display: inline-flex;
  font-size: 30px;
  color: #2f62d9;
  animation: graph-rotate-wheel 0.95s linear infinite;
}

.knowledge-graph-chart__status {
  position: absolute;
  top: 14px;
  right: 14px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border: 1px solid rgba(63, 124, 255, 0.18);
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.88);
  box-shadow: 0 10px 24px rgba(22, 50, 91, 0.12);
  color: #21456a;
  font-size: 12px;
  backdrop-filter: blur(6px);
}

.knowledge-graph-chart__status-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  background: linear-gradient(135deg, #3f7cff, #0f8b8d);
  box-shadow: 0 0 0 4px rgba(63, 124, 255, 0.12);
  animation: graph-status-pulse 1.4s ease-in-out infinite;
}

.knowledge-graph-chart__error {
  position: absolute;
  inset: 18px 18px auto;
  display: grid;
  gap: 6px;
  padding: 14px 16px;
  border: 1px solid rgba(190, 18, 60, 0.18);
  border-radius: 14px;
  background: rgba(255, 245, 247, 0.96);
  color: #8a1c35;
  box-shadow: 0 12px 26px rgba(138, 28, 53, 0.08);
}

.graph-fade-enter-active,
.graph-fade-leave-active {
  transition: opacity 0.18s ease, transform 0.18s ease;
}

.graph-fade-enter-from,
.graph-fade-leave-to {
  opacity: 0;
  transform: translateY(6px);
}

@keyframes graph-status-pulse {
  0%,
  100% {
    transform: scale(1);
    opacity: 1;
  }

  50% {
    transform: scale(1.16);
    opacity: 0.72;
  }
}

@keyframes graph-rotate-wheel {
  from {
    transform: rotate(0deg);
  }

  to {
    transform: rotate(360deg);
  }
}
</style>
