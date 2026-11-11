<script setup lang="ts">
import { IconSync } from '@arco-design/web-vue/es/icon'
import { computed, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'

import { loadD3 } from '@/services/d3-loader'
import type { GraphNodeAppearance } from '@/services/working-graph-view'
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
  zoom: any
  viewport: any
  links: any
  linkHitAreas: any
  nodes: any
  circles: any
  labels: any
  simulation: any
  nodeItems: RenderNode[]
  edgeItems: RenderEdge[]
  width: number
  height: number
  labelWidths?: ReadonlyMap<string, number>
}

type GraphRenderPhase = 'bootstrapping' | 'layout' | 'stable' | 'error'

const layoutCache = new Map<string, Map<string, LayoutSnapshot>>()

const props = defineProps<{
  dataset: UnifiedGraphDataset
  renderKey?: string | null
  showLabels: boolean
  searchTerm: string
  focusedNodeIds?: string[]
  focusedEdgeIds?: string[]
  selectedNodeId?: string | null
  selectedEdgeId?: string | null
  semanticAppearance?: Readonly<Record<string, GraphNodeAppearance>>
  searchMatches?: readonly string[]
  ariaLabel?: string
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
const selectedNodeIds = computed(() => new Set(props.selectedNodeId ? [props.selectedNodeId] : []))
const selectedEdgeIds = computed(() => new Set(props.selectedEdgeId ? [props.selectedEdgeId] : []))

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
  if (props.searchMatches) return new Set(props.searchMatches)
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

function resolveLineEndpoint(edge: RenderEdge) {
  const sourceNode = edge.source as RenderNode
  const targetNode = edge.target as RenderNode
  const dx = targetNode.x - sourceNode.x
  const dy = targetNode.y - sourceNode.y
  const distance = Math.max(Math.hypot(dx, dy), 0.001)
  const unitX = dx / distance
  const unitY = dy / distance
  const sourceOffset = sourceNode.radius + 2
  const targetOffset = targetNode.radius + (props.semanticAppearance ? 4 : 12)

  return {
    x1: sourceNode.x + unitX * sourceOffset,
    y1: sourceNode.y + unitY * sourceOffset,
    x2: targetNode.x - unitX * targetOffset,
    y2: targetNode.y - unitY * targetOffset,
  }
}

function readStringAttribute(attributes: Record<string, unknown>, key: string) {
  const value = attributes[key]
  return typeof value === 'string' ? value : null
}

function readNodeCurationStatus(node: RenderNode) {
  return readStringAttribute(node.attributes, 'curation_status')
}

function readEdgeCurationDecision(edge: RenderEdge) {
  return readStringAttribute(edge.attributes, 'curation_decision')
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
  const semantic = !!props.semanticAppearance
  const defaultCharge = semantic ? -70 : props.dataset.nodes.length > 300 ? -58 : -146

  simulation
    .force('cluster-x', null)
    .force('cluster-y', null)
    .force('charge', scene.value.d3.forceManyBody().strength(defaultCharge))
    .force(
      'collide',
      scene.value.d3.forceCollide().radius((node: RenderNode) => node.radius + (semantic ? 7 : 10)).strength(0.82),
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
  const selectedNodes = selectedNodeIds.value
  const selectedEdgesSet = selectedEdgeIds.value
  const hasSearch = keywordMatches.size > 0
  const hasFocus = focusedNodes.size > 0 || focusedEdgesSet.size > 0 || selectedNodes.size > 0 || selectedEdgesSet.size > 0

  if (props.semanticAppearance) {
    applySemanticDecorations(scene.value, props.semanticAppearance, keywordMatches, focusedNodes, focusedEdgesSet, selectedNodes, selectedEdgesSet)
    return
  }

  scene.value.circles
    .attr('r', (node: RenderNode) => {
      const isSelected = selectedNodes.has(node.id)
      const isSearchMatched = keywordMatches.has(node.id)
      const isFocusMatched = focusedNodes.has(node.id)
      return node.radius + (isSelected ? 7 : isFocusMatched ? 1.8 : isSearchMatched ? 2 : 0)
    })
    .attr('opacity', (node: RenderNode) => {
      const isSelected = selectedNodes.has(node.id)
      const isSearchMatched = keywordMatches.has(node.id)
      const isFocusMatched = focusedNodes.has(node.id)
      const isMatched = isSelected || isSearchMatched || isFocusMatched

      if (!hasSearch && !hasFocus) {
        return 0.96
      }

      if (isSelected) {
        return 1
      }

      if (isMatched) {
        return 0.92
      }

      return hasFocus && !hasSearch ? 0.36 : 0.5
    })
    .attr('fill', (node: RenderNode) => palette[node.categoryIndex % palette.length])
    .attr('stroke', (node: RenderNode) => {
      const curationStatus = readNodeCurationStatus(node)
      if (selectedNodes.has(node.id)) {
        return '#1e3a8a'
      }

      if (focusedNodes.has(node.id)) {
        return 'rgba(37, 99, 235, 0.78)'
      }

      if (curationStatus === 'revised') {
        return '#d97706'
      }

      if (keywordMatches.has(node.id)) {
        return '#1d4ed8'
      }

      return 'rgba(255, 255, 255, 0.72)'
    })
    .attr('stroke-width', (node: RenderNode) => {
      const curationStatus = readNodeCurationStatus(node)
      if (selectedNodes.has(node.id)) {
        return 4.8
      }

      if (focusedNodes.has(node.id)) {
        return 1.4
      }

      if (curationStatus === 'revised') {
        return 2.2
      }

      if (keywordMatches.has(node.id)) {
        return 1.8
      }

      return 0.9
    })
    .attr('filter', (node: RenderNode) => {
      if (selectedNodes.has(node.id)) {
        return 'drop-shadow(0 0 22px rgba(30, 58, 138, 0.34))'
      }

      if (focusedNodes.has(node.id)) {
        return 'drop-shadow(0 0 10px rgba(37, 99, 235, 0.14))'
      }

      return readNodeCurationStatus(node) === 'revised'
        ? 'drop-shadow(0 0 10px rgba(217, 119, 6, 0.22))'
        : null
    })

  scene.value.labels
    .attr('display', (node: RenderNode) =>
      props.showLabels || keywordMatches.has(node.id) || focusedNodes.has(node.id) || selectedNodes.has(node.id)
        ? null
        : 'none',
    )
    .attr('opacity', (node: RenderNode) => {
      if (selectedNodes.has(node.id)) {
        return 1
      }
      if (focusedNodes.has(node.id)) {
        return 0.9
      }
      return keywordMatches.has(node.id) ? 0.88 : 0.78
    })

  scene.value.links
    .attr('opacity', (edge: RenderEdge) => {
      const decision = readEdgeCurationDecision(edge)
      const sourceId = resolveEndpointId(edge.source)
      const targetId = resolveEndpointId(edge.target)
      const isSearchRelated = keywordMatches.has(sourceId) || keywordMatches.has(targetId)
      const isSelected = selectedEdgesSet.has(edge.id)
      const isFocusMatched = focusedEdgesSet.has(edge.id)
      const isSelectedRelated = selectedNodes.has(sourceId) || selectedNodes.has(targetId)
      const isFocusRelated = focusedNodes.has(sourceId) || focusedNodes.has(targetId)
      const isRelated = isSearchRelated || isSelected || isFocusMatched || isSelectedRelated || isFocusRelated

      if (!hasSearch && !hasFocus) {
        return 0.24
      }

      if (isSelected) {
        return 1
      }

      if (isFocusMatched) {
        return 0.52
      }

      if (decision === 'reject') {
        return 0.18
      }

      if (isSelectedRelated) {
        return 0.38
      }

      if (isFocusRelated) {
        return 0.28
      }

      if (isRelated) {
        return 0.24
      }

      return 0.16
    })
    .attr('stroke', (edge: RenderEdge) => {
      const decision = readEdgeCurationDecision(edge)
      if (selectedEdgesSet.has(edge.id)) {
        return '#1e3a8a'
      }
      if (focusedEdgesSet.has(edge.id)) {
        return 'rgba(37, 99, 235, 0.74)'
      }
      if (decision === 'accept') {
        return '#059669'
      }
      if (decision === 'reject') {
        return '#94a3b8'
      }
      if (decision === 'needs_completion') {
        return '#d97706'
      }
      if (decision === 'revise') {
        return '#2563eb'
      }
      return '#7b8ea8'
    })
    .attr('stroke-width', (edge: RenderEdge) => {
      const widthBase = edge.weight ?? edge.confidence ?? 0.3
      const decision = readEdgeCurationDecision(edge)
      const emphasis = decision === 'accept' ? 0.8 : decision === 'revise' ? 0.5 : 0
      const selectedBoost = selectedEdgesSet.has(edge.id) ? 3 : focusedEdgesSet.has(edge.id) ? 0.8 : 0
      return Math.max(0.8, Math.min(4.2, widthBase * 3.4)) + emphasis + selectedBoost
    })
    .attr('stroke-dasharray', (edge: RenderEdge) => {
      const decision = readEdgeCurationDecision(edge)
      if (selectedEdgesSet.has(edge.id) || focusedEdgesSet.has(edge.id)) {
        return null
      }
      if (decision === 'reject') {
        return '2 7'
      }
      if (decision === 'needs_completion') {
        return '7 5'
      }
      if (decision === 'accept' || decision === 'revise') {
        return null
      }
      return '3 4'
    })
}

function nodeGlyph(shape: GraphNodeAppearance['shape'], r: number) {
  switch (shape) {
    case 'diamond': return `M0,${-r} L${r},0 0,${r} ${-r},0 Z`
    case 'square': return `M${-r},${-r} H${r} V${r} H${-r} Z`
    case 'ellipse': return `M${-r * 1.2},0 a${r * 1.2},${r * .76} 0 1,0 ${r * 2.4},0 a${r * 1.2},${r * .76} 0 1,0 ${-r * 2.4},0`
    case 'circle': return `M${-r},0 a${r},${r} 0 1,0 ${r * 2},0 a${r},${r} 0 1,0 ${-r * 2},0`
  }
}

function applySemanticDecorations(
  current: GraphScene,
  appearance: Readonly<Record<string, GraphNodeAppearance>>,
  search: Set<string>, focus: Set<string>, edges: Set<string>, selectedNodes: Set<string>, selectedEdges: Set<string>,
) {
  const hasFocus = focus.size > 0 || edges.size > 0 || selectedNodes.size > 0 || selectedEdges.size > 0
  const active = hasFocus || search.size > 0
  current.circles
    .attr('d', (node: RenderNode) => nodeGlyph(appearance[node.category]?.shape ?? 'circle', node.radius + (selectedNodes.has(node.id) ? 2 : 0)))
    .attr('fill', (node: RenderNode) => appearance[node.category]?.color ?? '#98a3b1')
    .attr('opacity', (node: RenderNode) => !active || selectedNodes.has(node.id) || search.has(node.id) || focus.has(node.id) ? 1 : .27)
    .attr('stroke', (node: RenderNode) => selectedNodes.has(node.id) ? '#193d86' : search.has(node.id) ? '#2361c9' : '#fff')
    .attr('stroke-width', (node: RenderNode) => selectedNodes.has(node.id) ? 2.5 : search.has(node.id) ? 2 : .8)

  const isRelated = (edge: RenderEdge) => search.has(resolveEndpointId(edge.source)) || search.has(resolveEndpointId(edge.target))
    || (focus.has(resolveEndpointId(edge.source)) && focus.has(resolveEndpointId(edge.target)))
  current.links
    .attr('opacity', (edge: RenderEdge) => selectedEdges.has(edge.id) ? 1 : edges.has(edge.id) ? .85
      : !active ? .62 : isRelated(edge) ? .48 : .15)
    .attr('stroke', (edge: RenderEdge) => selectedEdges.has(edge.id) ? '#1d4ed8' : edges.has(edge.id) ? '#4780ee' : '#91a4bc')
    .attr('stroke-width', (edge: RenderEdge) => selectedEdges.has(edge.id) ? 2.2 : edges.has(edge.id) ? 1.5 : 1)
  current.linkHitAreas.attr('tabindex', (edge: RenderEdge) => selectedEdges.has(edge.id) ? 0 : -1)
  revealSemanticSelection(current)
  placeSemanticLabels(current)
}

function revealSemanticSelection(current: GraphScene) {
  const node = current.nodeItems.find(item => item.id === props.selectedNodeId)
  const edge = current.edgeItems.find(item => item.id === props.selectedEdgeId)
  const source = edge?.source as RenderNode | undefined, target = edge?.target as RenderNode | undefined
  const point = node ?? (source && target ? { x: (source.x + target.x) / 2, y: (source.y + target.y) / 2 } : null)
  if (!point) return
  const transform = current.d3.zoomTransform(current.svg.node())
  const [x, y] = transform.apply([point.x, point.y])
  if (x >= 14 && x <= current.width - 14 && y >= 14 && y <= current.height - 30) return
  current.svg.call(current.zoom.transform, current.d3.zoomIdentity
    .translate(current.width / 2 - point.x * transform.k, current.height / 2 - point.y * transform.k).scale(transform.k))
}

type LabelBox = { left: number; right: number; top: number; bottom: number }
type LabelPlacement = { dx: number; dy: number; anchor: 'start' | 'end' | 'middle' }
const labelFontSize = 10.5

function semanticCaption(node: RenderNode) {
  // The full saved name remains available in the inspector and native tooltip.
  const stem = /[\u3400-\u9fff]/.test(node.name) ? node.name.split(/[（(]/, 1)[0]?.trim() || node.name : node.name
  return stem.length > 19 ? `${stem.slice(0, 18)}…` : stem
}

function placeSemanticLabels(current: GraphScene) {
  const appearance = props.semanticAppearance
  if (!appearance || !current.labelWidths) return
  const transform = current.d3.zoomTransform(current.svg.node())
  const scale = transform.k
  const fontSize = clamp(labelFontSize * scale, 11, 13)
  const selected = props.selectedNodeId, focus = focusRelatedNodeIds.value, search = highlightedNodeIds.value
  const active = !!selected || !!props.selectedEdgeId || focus.size > 0 || search.size > 0
  const score = (node: RenderNode) => (node.id === selected ? 1000 : search.has(node.id) ? 800 : focus.has(node.id) ? 500 : 0)
    + (appearance[node.category]?.labelPriority ?? 0)
  const ordered = current.nodeItems.filter(node => score(node) > (active ? 100 : 0))
    .sort((a, b) => score(b) - score(a) || b.degree - a.degree)
  const boxes: LabelBox[] = []
  const placements = new Map<string, LabelPlacement>()
  const budget = current.width >= 620 ? 10 : current.width >= 430 ? 8 : 5
  const positions = current.nodeItems.map(node => ({ node, x: transform.applyX(node.x), y: transform.applyY(node.y) }))
  const intersects = (a: LabelBox, b: LabelBox) => a.left < b.right && a.right > b.left && a.top < b.bottom && a.bottom > b.top

  for (const node of ordered) {
    if (placements.size >= budget) break
    const x = transform.applyX(node.x), y = transform.applyY(node.y)
    const offset = (node.radius + (node.id === selected ? 6 : 4)) * scale
    const width = (current.labelWidths.get(node.id) ?? 0) * fontSize / labelFontSize * (node.id === selected ? 1.1 : 1)
    const placementsNearNode: LabelPlacement[] = [
      { dx: offset, dy: 4, anchor: 'start' }, { dx: -offset, dy: 4, anchor: 'end' },
      { dx: 0, dy: -offset, anchor: 'middle' }, { dx: 0, dy: offset + fontSize, anchor: 'middle' },
    ]
    if ((appearance[node.category]?.labelPriority ?? 0) >= 40) placementsNearNode.push(
      { dx: 0, dy: -offset - 10, anchor: 'middle' }, { dx: 0, dy: offset + fontSize + 10, anchor: 'middle' },
    )
    for (const placement of placementsNearNode) {
      const left = x + placement.dx - (placement.anchor === 'start' ? 0 : placement.anchor === 'middle' ? width / 2 : width)
      const box = { left: left - 2, right: left + width + 2, top: y + placement.dy - fontSize, bottom: y + placement.dy + 4 }
      if (box.left < 6 || box.right > current.width - 6 || box.top < 5 || box.bottom > current.height - 28 || boxes.some(other => intersects(box, other))) continue
      if (node.id !== selected && positions.some(other => {
        if (other.node.id === node.id) return false
        const r = (other.node.radius + 1.5) * scale
        return intersects(box, { left: other.x - r, right: other.x + r, top: other.y - r, bottom: other.y + r })
      })) continue
      placements.set(node.id, placement)
      boxes.push(box)
      break
    }
  }
  current.nodes.attr('tabindex', (node: RenderNode) => placements.has(node.id) || node.id === selected ? 0 : -1)
  current.labels
    .attr('display', (node: RenderNode) => props.showLabels && placements.has(node.id) ? null : 'none')
    .attr('dx', (node: RenderNode) => (placements.get(node.id)?.dx ?? 0) / scale)
    .attr('dy', (node: RenderNode) => (placements.get(node.id)?.dy ?? 0) / scale)
    .attr('text-anchor', (node: RenderNode) => placements.get(node.id)?.anchor ?? 'start')
    .attr('font-size', fontSize / scale)
    .attr('font-weight', (node: RenderNode) => node.id === selected ? 650 : 450)
}

function sceneSize(host: HTMLDivElement) {
  return {
    width: Math.max(host.clientWidth, props.semanticAppearance ? 220 : 680),
    height: Math.max(host.clientHeight, props.semanticAppearance ? 330 : 520),
  }
}

function orientation(width: number, height: number) {
  return width / height > 1.2 ? 'wide' : width / height < .84 ? 'tall' : 'natural'
}

/** Orient the force layout to the viewport without moving nodes relative to one another. */
function orientSemanticLayout(current: GraphScene) {
  const target = orientation(current.width, current.height)
  if (target === 'natural' || current.nodeItems.length < 3) return
  const items = current.nodeItems
  const cx = items.reduce((sum, node) => sum + node.x, 0) / items.length
  const cy = items.reduce((sum, node) => sum + node.y, 0) / items.length
  let xx = 0, yy = 0, xy = 0
  for (const node of items) {
    const x = node.x - cx, y = node.y - cy
    xx += x * x; yy += y * y; xy += x * y
  }
  if (Math.hypot(xx - yy, 2 * xy) < .1 * (xx + yy)) return
  const principal = Math.atan2(2 * xy, xx - yy) / 2
  const angle = (target === 'wide' ? 0 : Math.sign(principal || 1) * Math.PI / 2) - principal
  if (Math.abs(angle) < .12) return
  const cos = Math.cos(angle), sin = Math.sin(angle)
  for (const node of items) {
    const x = node.x - cx, y = node.y - cy
    node.x = cx + x * cos - y * sin
    node.y = cy + x * sin + y * cos
  }
}

function zoomBy(factor: number) {
  const current = scene.value
  if (current) current.svg.call(current.zoom.scaleBy, factor)
}

function fitViewport() {
  const current = scene.value
  if (!current?.nodeItems.length) return
  const { d3, svg, zoom, width, height, nodeItems } = current
  const left = Math.min(...nodeItems.map(node => node.x - node.radius))
  const right = Math.max(...nodeItems.map(node => node.x + node.radius))
  const top = Math.min(...nodeItems.map(node => node.y - node.radius))
  const bottom = Math.max(...nodeItems.map(node => node.y + node.radius))
  // Leave room beside the outer nodes for the labels, not only for the glyphs.
  const labelRoom = Math.min(74, width * .16)
  const scale = clamp(Math.min((width - labelRoom - 36) / Math.max(right - left, 1), (height - 62) / Math.max(bottom - top, 1)), .36, width > 620 ? 1.38 : 1.2)
  svg.call(zoom.transform, d3.zoomIdentity.translate((width - labelRoom + 18) / 2 - (left + right) * scale / 2,
    (height - 14) / 2 - (top + bottom) * scale / 2).scale(scale))
}

defineExpose({ zoomBy, fitViewport })

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
      .attr('x1', (edge: RenderEdge) => resolveLineEndpoint(edge).x1)
      .attr('y1', (edge: RenderEdge) => resolveLineEndpoint(edge).y1)
      .attr('x2', (edge: RenderEdge) => resolveLineEndpoint(edge).x2)
      .attr('y2', (edge: RenderEdge) => resolveLineEndpoint(edge).y2)

    scene.value.linkHitAreas
      .attr('x1', (edge: RenderEdge) => resolveLineEndpoint(edge).x1)
      .attr('y1', (edge: RenderEdge) => resolveLineEndpoint(edge).y1)
      .attr('x2', (edge: RenderEdge) => resolveLineEndpoint(edge).x2)
      .attr('y2', (edge: RenderEdge) => resolveLineEndpoint(edge).y2)

    scene.value.nodes.attr('transform', (node: RenderNode) => `translate(${node.x}, ${node.y})`)
    if (props.semanticAppearance) placeSemanticLabels(scene.value)

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

    const { width: nextWidth, height: nextHeight } = sceneSize(chartRef.value)
    if (props.semanticAppearance && scene.value.width === nextWidth && scene.value.height === nextHeight) return
    const orientationChanged = orientation(scene.value.width, scene.value.height) !== orientation(nextWidth, nextHeight)

    scene.value.width = nextWidth
    scene.value.height = nextHeight
    scene.value.svg.attr('viewBox', `0 0 ${nextWidth} ${nextHeight}`)
    if (props.semanticAppearance) {
      if (orientationChanged) orientSemanticLayout(scene.value)
      fitViewport()
      applyDecorations()
      scheduleTickRender()
      return
    }
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
      radius: props.semanticAppearance?.[node.category]?.radius ?? Math.max(9, Math.min(30, 10 + Math.sqrt(node.degree || 1) * 2.6)),
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
  const semantic = !!props.semanticAppearance
  const previousTransform = semantic && scene.value ? scene.value.d3.zoomTransform(scene.value.svg.node()) : null
  stopScene()

  try {
    const d3 = await loadD3()

    if (version !== renderVersion || !chartRef.value || !surfaceRef.value) {
      return
    }

    const { width, height } = sceneSize(chartRef.value)
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
    if (semantic) svg.attr('role', 'group').attr('aria-label', props.ariaLabel || '有向知识网络')
    const arrowId = `graph-arrow-${props.dataset.id}`

    svg
      .append('defs')
      .append('marker')
      .attr('id', arrowId)
      .attr('viewBox', '0 0 10 10')
      .attr('refX', semantic ? 10 : 11)
      .attr('refY', 5)
      .attr('markerWidth', semantic ? 5.5 : 8)
      .attr('markerHeight', semantic ? 5.5 : 8)
      .attr('markerUnits', semantic ? 'userSpaceOnUse' : null)
      .attr('orient', 'auto-start-reverse')
      .append('path')
      .attr('d', 'M 0 0 L 10 5 L 0 10 z')
      .attr('fill', semantic ? 'context-stroke' : '#8aa1bc')

    const viewport = svg.append('g').attr('class', 'knowledge-graph-chart__viewport')

    const zoom = d3.zoom().scaleExtent([0.36, 3.2]).on('zoom', (event: any) => {
      viewport.attr('transform', event.transform)
      if (semantic && scene.value) placeSemanticLabels(scene.value)
    })
    svg
      .call(zoom)
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
        edge.directed ? `url(#${arrowId})` : null,
      )
      .style('pointer-events', 'none')

    const linkHitAreas = viewport
      .append('g')
      .attr('class', 'knowledge-graph-chart__link-hit-areas')
      .selectAll('line')
      .data(edgeItems, (edge: RenderEdge) => edge.id)
      .join('line')
      .attr('stroke', 'rgba(0, 0, 0, 0)')
      .attr('stroke-width', 16)
      .attr('stroke-linecap', 'round')
      .style('cursor', 'pointer')
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

    if (semantic) {
      const nodeLabel = (node: RenderNode) => `${readStringAttribute(node.attributes, 'kind_label') || node.kind}：${node.name}`
      const edgeLabel = (edge: RenderEdge) => `${nodeById.value.get(resolveEndpointId(edge.source))?.name ?? resolveEndpointId(edge.source)} → ${nodeById.value.get(resolveEndpointId(edge.target))?.name ?? resolveEndpointId(edge.target)}：${edge.label || edge.relation}`
      const keyboardClick = (event: KeyboardEvent) => {
        if (event.key !== 'Enter' && event.key !== ' ') return
        event.preventDefault()
        event.currentTarget?.dispatchEvent(new MouseEvent('click', { bubbles: true }))
      }
      nodes.attr('data-node-id', (node: RenderNode) => node.id).attr('role', 'button').attr('aria-label', nodeLabel)
        .on('keydown', keyboardClick).append('title').text(nodeLabel)
      linkHitAreas.attr('data-edge-id', (edge: RenderEdge) => edge.id).attr('role', 'button').attr('aria-label', edgeLabel)
        .on('keydown', keyboardClick).append('title').text(edgeLabel)
      links.attr('data-edge-id', (edge: RenderEdge) => edge.id)
    }

    const circles = nodes
      .append(semantic ? 'path' : 'circle')
      .attr('class', semantic ? 'knowledge-graph-chart__semantic-node' : null)
      .attr('stroke-linejoin', 'round')

    const labels = nodes
      .append('text')
      .attr('dx', semantic ? 11 : 10)
      .attr('dy', 3)
      .attr('font-size', labelFontSize)
      .attr('fill', semantic ? 'var(--color-text-1, #10253b)' : '#10253b')
      .style('paint-order', 'stroke')
      .style('stroke', semantic ? 'var(--color-fill-1, #f4f7fb)' : 'rgba(255, 255, 255, 0.88)')
      .style('stroke-width', 3)
      .style('pointer-events', 'none')
      .text((node: RenderNode) => semantic ? semanticCaption(node) : node.name)

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
            semantic ? 54 : props.dataset.nodes.length > 300
              ? 34
              : clamp(((edge.weight ?? edge.confidence ?? 0.42) + 0.18) * 112, 56, 136),
          )
          .strength((edge: RenderEdge) => clamp((edge.weight ?? edge.confidence ?? 0.32) + 0.08, 0.12, 0.72)),
      )
      .force('charge', d3.forceManyBody().strength(props.dataset.nodes.length > 300 ? -58 : -146))
      .force('collide', d3.forceCollide().radius((node: RenderNode) => node.radius + 10).strength(0.82))
      .force('center', d3.forceCenter(width / 2, height / 2))
      .alpha(cachedLayout ? 0.42 : 0.95)
      .alphaDecay(props.dataset.nodes.length > 250 ? 0.08 : 0.055)
      .velocityDecay(0.34)
    if (semantic) simulation.force('keep-near-x', d3.forceX(width / 2).strength(.035))
      .force('keep-near-y', d3.forceY(height / 2).strength(.035))

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
      zoom,
      viewport,
      links,
      linkHitAreas,
      nodes,
      circles,
      labels,
      simulation,
      nodeItems,
      edgeItems,
      width,
      height,
      labelWidths: semantic ? new Map((labels.nodes() as SVGTextElement[]).map(label => [
        (label as SVGTextElement & { __data__: RenderNode }).__data__.id, label.getComputedTextLength(),
      ])) : undefined,
    }

    applySceneForces()
    applyDecorations()
    if (!semantic) {
      window.requestAnimationFrame(() => {
        if (version === renderVersion && scene.value) pulseGraphMotion()
      })
    }

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

    if (semantic) {
      simulation.stop().tick(86)
      orientSemanticLayout(scene.value)
      if (previousTransform) svg.call(zoom.transform, previousTransform)
      else fitViewport()
      scheduleTickRender()
      cacheLayout()
      bootstrapping.value = false
      layoutRunning.value = false
      statusMessage.value = '布局已稳定'
      emitRenderState('stable', statusMessage.value)
    }

    bindResizeObserver()
  } catch (error) {
    renderError.value = error instanceof Error ? error.message : 'D3 graph render failed'
    bootstrapping.value = false
    layoutRunning.value = false
    emitRenderState('error', renderError.value)
  }
}

watch(
  () => props.renderKey ?? props.dataset,
  () => {
    emit('hover', null)
    scheduleRenderGraph()
  },
)

watch(
  [
    () => props.showLabels,
    () => props.searchTerm,
    () => props.searchMatches,
    () => (props.focusedNodeIds ?? []).join('|'),
    () => (props.focusedEdgeIds ?? []).join('|'),
    () => props.selectedNodeId ?? '',
    () => props.selectedEdgeId ?? '',
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
  <div ref="chartRef" class="knowledge-graph-chart" :class="{ 'knowledge-graph-chart--semantic': semanticAppearance }">
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
  background: #f8fbff;
}

.knowledge-graph-chart__surface {
  position: absolute;
  inset: 0;
}

.knowledge-graph-chart--semantic {
  min-height: 330px;
  border-radius: 0;
  background: radial-gradient(circle, var(--color-border-2, #dbe2eb) .65px, transparent .8px) 0 0 / 15px 15px,
    var(--color-fill-1, #f5f7fa);
}

.knowledge-graph-chart--semantic :deep(g[role='button']:focus-visible) { outline: none; }
.knowledge-graph-chart--semantic :deep(g[role='button']:focus-visible path) {
  stroke: var(--color-primary-6, #165dff);
  stroke-width: 2.5px;
}

.knowledge-graph-chart__overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  background: rgba(248, 251, 255, 0.9);
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
