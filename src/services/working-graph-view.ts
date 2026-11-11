import type { KGStudioGraphEdge, KGStudioGraphNode, KGStudioPayload, WorkingGraphPackage } from '@/api/contracts'
import type { UnifiedGraphDataset, UnifiedGraphEdge, UnifiedGraphNode } from '@/types/graph'
import { traceRecord, traceRows, traceValue, type TraceRecord } from './unified-reasoning-display'

export type WorkingGraphSelection = { type: 'node' | 'edge'; id: string } | null
export type GraphNodeShape = 'diamond' | 'circle' | 'square' | 'ellipse'
export interface GraphNodeAppearance { color: string; shape: GraphNodeShape; radius: number; labelPriority: number; label: string }

/** Stable across datasets and preview order. Scene membership is not a semantic kind. */
export const workingGraphGroups = {
  cause: { label: '候选原因', color: '#7650b6', shape: 'diamond', radius: 7, labelPriority: 25 },
  mechanism: { label: '机理', color: '#ad621d', shape: 'circle', radius: 6, labelPriority: 0 },
  phenomenon: { label: '现象', color: '#306cbe', shape: 'circle', radius: 8, labelPriority: 42 },
  rule: { label: '规则 / 条件', color: '#0c7d83', shape: 'square', radius: 5.4, labelPriority: 0 },
  subject: { label: '对象 / 通道', color: '#278259', shape: 'ellipse', radius: 6, labelPriority: 16 },
  source: { label: '来源断言', color: '#748195', shape: 'square', radius: 5.5, labelPriority: 0 },
  other: { label: '未分类', color: '#98a3b1', shape: 'circle', radius: 5.7, labelPriority: 0 },
} as const satisfies Record<string, GraphNodeAppearance>
export type WorkingGraphGroup = keyof typeof workingGraphGroups
const kinds: Record<string, { group: WorkingGraphGroup; label: string }> = {
  Hypothesis: { group: 'cause', label: '候选原因' }, Mechanism: { group: 'mechanism', label: '机理' }, Phenomenon: { group: 'phenomenon', label: '现象' },
  ObservablePredicate: { group: 'rule', label: '观测条件' }, LogicGate: { group: 'rule', label: '逻辑组合' },
  DefinitionRule: { group: 'rule', label: '定义规则' }, EffectRule: { group: 'rule', label: '作用规则' },
  ExpectationRule: { group: 'rule', label: '诊断规则' }, ValueBinding: { group: 'rule', label: '词汇绑定' },
  Object: { group: 'subject', label: '对象' }, Variable: { group: 'subject', label: '通道变量' }, SourceAssertion: { group: 'source', label: '来源断言' },
}
export const graphPreviewEdgeLimit = 80 // KGStudio GRAPH_PREVIEW_EDGE_LIMIT, not full canonical knowledge.
export const graphText = (value: unknown) => typeof value === 'string' ? value : ''
export const graphIds = (value: unknown) => Array.isArray(value) ? value.filter((entry): entry is string => typeof entry === 'string' && !!entry) : []
export function workingGraphKind(kind: string, scenario?: string) {
  const value = Object.hasOwn(kinds, kind) ? kinds[kind]! : { group: 'other' as const, label: '未分类节点' }
  return kind === 'Hypothesis' && scenario === 'wafer' ? { ...value, label: '图案候选' } : value
}
export const workingGraphScene = (value: string) => ({ mvtec: 'MVTec', tep: 'TEP', wafer: 'Wafer', shared: '共享' } as Record<string, string>)[value] ?? value
const relationshipNames: Record<string, string> = {
  DERIVES_STATE: '导出状态', EXPECTS: '预期现象', ACTIVATES_RULE: '触发规则', APPLIES_TO: '适用于',
  HAS_EXPECTATION: '关联诊断规则', INPUT_OF: '输入至', DEFINES: '定义现象', SUPPORTS: '支持', OBSERVES: '观测',
  NORMALIZES_VALUE_FOR: '规范化观测值', SUBCLASS_OF: '属于子类',
}
export function workingRelationshipName(relation: string) { return relationshipNames[relation] ?? (relation || '未保存关系类型') }
export function workingGraphMode(value: unknown) { return ({ necessary: '必要', expected: '预期', possible: '可能' } as Record<string, string>)[graphText(value)] ?? (graphText(value) || '未保存') }

/** Render only the nodes and actual directed edges provided by this studio response. */
export function buildWorkingGraphView(studio: KGStudioPayload) {
  const nodesById = new Map<string, KGStudioGraphNode>()
  for (const node of studio.graph_nodes) if (node.node_id && !nodesById.has(node.node_id)) nodesById.set(node.node_id, node)
  const edgesById = new Map<string, KGStudioGraphEdge>()
  for (const edge of studio.graph_edges.slice(0, graphPreviewEdgeLimit)) {
    if (edge.edge_id && nodesById.has(edge.head) && nodesById.has(edge.tail) && !edgesById.has(edge.edge_id)) edgesById.set(edge.edge_id, edge)
  }
  const adjacency = new Map<string, KGStudioGraphEdge[]>(), incoming = new Map<string, number>(), outgoing = new Map<string, number>()
  for (const edge of edgesById.values()) {
    incoming.set(edge.tail, (incoming.get(edge.tail) ?? 0) + 1)
    outgoing.set(edge.head, (outgoing.get(edge.head) ?? 0) + 1)
    for (const id of new Set([edge.head, edge.tail])) {
      const bucket = adjacency.get(id) ?? []
      bucket.push(edge); adjacency.set(id, bucket)
    }
  }
  const scene = [...new Set([...nodesById.values()].map(node => node.scenario).filter(Boolean))]
  const names = new Map([...nodesById.values()].map(node => [node.node_id, readablePreviewName(node, adjacency.get(node.node_id) ?? [], nodesById)]))
  const groupCounts = new Map<WorkingGraphGroup, number>()
  const origin = (filePath: string | null) => ({ projectId: 'working-graph', projectLabel: '工作图', filePath: filePath ?? '', layer: 'studio-preview', rowNumber: 0 })
  const nodes: UnifiedGraphNode[] = [...nodesById.values()].map((node) => {
    const group = workingGraphKind(node.node_type).group
    groupCounts.set(group, (groupCounts.get(group) ?? 0) + 1)
    const inDegree = incoming.get(node.node_id) ?? 0, outDegree = outgoing.get(node.node_id) ?? 0
    return { id: node.node_id, name: names.get(node.node_id) ?? previewNodeName(node), category: group, kind: node.node_type, description: node.description, aliases: node.aliases ?? [],
      degree: inDegree + outDegree, inDegree, outDegree, attributes: { scenario: node.scenario, node_type: node.node_type, kind_label: workingGraphKind(node.node_type, node.scenario).label }, origin: origin(studio.nodes_path) }
  })
  const edges: UnifiedGraphEdge[] = [...edgesById.values()].map(edge => ({
    id: edge.edge_id, source: edge.head, target: edge.tail, relation: edge.relation, category: edge.scenario,
    label: workingRelationshipName(edge.relation), directed: true, confidence: edge.confidence, weight: edge.weight,
    attributes: { source: edge.source, evidence: edge.evidence, target_key: edge.target_key, review_status: edge.review_status }, origin: origin(studio.edges_path),
  }))
  const dataset: UnifiedGraphDataset = {
    id: `working-graph-preview:${studio.graph_id ?? studio.candidate_dir ?? 'studio'}`, label: '工作图网络预览', description: studio.note,
    graphKind: 'working-graph-preview', projectRoot: '', sourceFiles: [], nodes, edges,
    metadata: { preview: true, full_node_count: studio.node_count, full_edge_count: studio.edge_count },
  }
  return { dataset, nodesById, edgesById, adjacency, names, groupCounts, scenarios: scene, nodeTotal: studio.node_count,
    edgeTotal: studio.edge_count, skippedEdges: studio.graph_edges.length - edges.length }
}

export function previewNodeName(node: KGStudioGraphNode) {
  const savedName = node.label || node.node_id
  const localizedAlias = node.node_type === 'Object' && node.node_id.endsWith(`:${savedName}`)
    ? node.aliases?.find(alias => /[\u3400-\u9fff]/.test(alias)) : undefined
  return localizedAlias ?? savedName
}
function readablePreviewName(node: KGStudioGraphNode, neighbors: KGStudioGraphEdge[], nodes: ReadonlyMap<string, KGStudioGraphNode>) {
  if (node.label && node.label !== node.node_id) return previewNodeName(node)
  const kind = workingGraphKind(node.node_type, node.scenario)
  if (kind.group !== 'rule' && kind.group !== 'source') return previewNodeName(node)
  const related = node.node_type === 'ExpectationRule' ? neighbors.filter(edge => edge.tail === node.node_id && edge.relation === 'HAS_EXPECTATION').map(edge => edge.head)
    : node.node_type === 'EffectRule' ? neighbors.filter(edge => edge.tail === node.node_id && edge.relation === 'ACTIVATES_RULE').map(edge => edge.head)
    : node.node_type === 'DefinitionRule' ? neighbors.filter(edge => edge.head === node.node_id && edge.relation === 'DEFINES').map(edge => edge.tail)
    : []
  const anchor = related.length === 1 ? nodes.get(related[0]!) : undefined
  return anchor ? `${previewNodeName(anchor)} · ${kind.label}` : kind.label
}
function normalizeKeyword(value: string) { return value.normalize('NFKC').toLowerCase().replace(/[\s()（）_\-]+/g, '') }
export function findWorkingGraphNodes(view: ReturnType<typeof buildWorkingGraphView>, term: string) {
  const keyword = normalizeKeyword(term.trim())
  return keyword ? view.dataset.nodes.filter(node => [node.name, node.id, view.nodesById.get(node.id)?.label ?? '', ...node.aliases]
    .some(value => normalizeKeyword(value).includes(keyword))) : []
}
export function workingGraphFocus(view: ReturnType<typeof buildWorkingGraphView>, selection: WorkingGraphSelection, group: WorkingGraphGroup | null) {
  if (selection?.type === 'edge') {
    const edge = view.edgesById.get(selection.id)
    if (edge) return { nodes: [edge.head, edge.tail], edges: [edge.edge_id] }
  } else if (selection?.type === 'node' && view.nodesById.has(selection.id)) {
    const edges = view.adjacency.get(selection.id) ?? []
    return { nodes: [...new Set([selection.id, ...edges.flatMap(edge => [edge.head, edge.tail])])], edges: edges.map(edge => edge.edge_id) }
  }
  if (!group) return { nodes: [], edges: [] }
  // A legend focus means this kind, not an implicit expansion of all its neighbors.
  return { nodes: view.dataset.nodes.filter(node => node.category === group).map(node => node.id), edges: [] }
}

const featureNames: Record<string, string> = {
  'detection.anomaly_present': '异常检测', 'appearance.defect_present': '外观缺陷判定', 'appearance.semantic_candidates': '外观候选',
  'geometry.area_ratio': '区域面积占比', 'geometry.aspect_ratio': '区域长宽比', 'geometry.eccentricity': '离心率',
  'geometry.component_count': '连通区域数', 'geometry.morphology': '区域形态', 'geometry.location': '区域位置',
  'statistics.mean_z': '标准化均值偏移', 'statistics.std_z': '标准化波动', 'statistics.slope_z': '标准化趋势斜率', 'residual.contribution': '残差贡献',
}
const operators: Record<string, string> = { gte: '≥', lte: '≤', abs_gte: '绝对值 ≥', eq: '=', in: '属于', intersects: '相交', candidate_contains: '包含', bool_eq: '=' }
const categories: Record<string, string> = { cracked_or_missing_glass: '开裂或玻璃缺失', chipped_edge: '边缘崩缺', broken_finish: '瓶口破损', chipped_finish: '瓶口崩缺', spot: '斑点', linear: '线状', edge: '边缘', surface: '表面' }
export function graphFeatureName(id: unknown) { return featureNames[graphText(id)] ?? (graphText(id) || '未保存特征') }
export function graphOperandText(input: unknown) {
  const row = traceRecord(input)
  if (row.kind === 'number' && typeof row.number === 'number') return `${row.number} ${graphText(row.unit)}`.trim()
  if (row.kind === 'boolean') return row.boolean === true ? '是' : row.boolean === false ? '否' : '未保存'
  if (row.kind === 'category') return categories[graphText(row.category)] ?? graphText(row.category)
  if (row.kind === 'candidate_set') return graphIds(row.items).map(value => categories[value] ?? value).join('、') || '空集合'
  return traceValue(input)
}
export function graphConditionName(row: TraceRecord) {
  const lhs = graphText(row.feature_id), operator = graphText(row.op)
  if (lhs && operator) return `${graphFeatureName(lhs)} ${operators[operator] ?? operator} ${graphOperandText(row.operand)}`
  return graphText(row.label) || graphText(row.predicate_id) || '观测条件'
}
export const graphScopeName = (scope: unknown) => {
  const row = traceRecord(scope)
  if (row.kind === 'task_scope') return '任务范围'
  if (row.kind === 'wafer_zone' || row.kind === 'spatial_zone') return `空间分区 · ${graphText(row.zone)}`
  return graphText(row.kind) || '未保存范围'
}
export const graphScopeJoinName = (join: unknown) => ({ same_subject_same_scope: '同一主体和范围', same_event_same_window: '同一事件和窗口', same_wafer_parent_scope: '同一晶圆父范围', same_subject_parent_scope: '同一主体的父子范围' } as Record<string, string>)[graphText(join)] ?? (graphText(join) || '未保存')
export function graphSourceOrigin(value: unknown) {
  return ({ source_explicit: '资料明示', llm_proposed: '模型提议', normal_reference_estimate: '正常参考估计', declared_demo_heuristic: '演示启发式', synthetic_design_assertion: '设计断言' } as Record<string, string>)[graphText(value)] ?? (graphText(value) || '未标注来源类别')
}
export function graphSourceLocation(value: unknown) {
  const raw = graphText(value)
  if (!raw) return ''
  try {
    const row = traceRecord(JSON.parse(raw))
    if (typeof row.page === 'number') return `第 ${row.page} 页`
    if (typeof row.start_line === 'number') return `第 ${row.start_line}${typeof row.end_line === 'number' && row.end_line !== row.start_line ? `–${row.end_line}` : ''} 行`
    if (typeof row.section === 'string') return row.section
    if (typeof row.char_start === 'number' && typeof row.char_end === 'number') return `字符偏移 ${row.char_start}–${row.char_end}`
  } catch { /* A source can already carry a prose locator. */ }
  return raw
}

export function readWorkingGraphKnowledge(graphPackage: WorkingGraphPackage | null, studioGraphId?: string | null) {
  if (graphPackage?.schema_version !== 'rootlens-working-graph.v2' || (studioGraphId && graphPackage.graph_id && graphPackage.graph_id !== studioGraphId)) return null
  const knowledge = graphPackage.knowledge
  const entities = traceRows(knowledge.entities), hypotheses = traceRows(knowledge.hypotheses), mechanisms = traceRows(knowledge.mechanisms)
  const conditions = traceRows(knowledge.observable_definitions), patterns = traceRows(knowledge.pattern_definitions)
  const expectations = traceRows(knowledge.expectation_rules), effects = traceRows(knowledge.effect_rules)
  const subjectBindings = traceRows(knowledge.subject_bindings), valueBindings = traceRows(knowledge.value_bindings)
  const sources = traceRows(knowledge.source_assertions), features = traceRows(knowledge.feature_registry), relations = traceRows(knowledge.relations)
  const indexed = new Map<string, TraceRecord>()
  for (const [list, key] of [[entities, 'entity_id'], [hypotheses, 'hypothesis_id'], [mechanisms, 'mechanism_id'], [conditions, 'predicate_id'], [patterns, 'pattern_id'], [patterns, 'definition_id'], [expectations, 'rule_id'], [effects, 'rule_id'], [valueBindings, 'binding_id'], [sources, 'assertion_id']] as const) {
    for (const item of list) { const id = graphText(item[key]); if (id) indexed.set(id, item) }
  }
  return { indexed, conditions, patterns, expectations, effects, subjectBindings, valueBindings, sources, features, relations }
}
export type WorkingGraphKnowledge = NonNullable<ReturnType<typeof readWorkingGraphKnowledge>>
export function knownGraphSources(knowledge: WorkingGraphKnowledge | null, ids: unknown) {
  if (!knowledge) return []
  const wanted = new Set(graphIds(ids))
  return knowledge.sources.filter(source => wanted.has(graphText(source.assertion_id)))
}

/** A preview edge can display only the provenance attached to its exact declaration. */
export function workingGraphEdgeSources(knowledge: WorkingGraphKnowledge | null, edge: KGStudioGraphEdge) {
  if (!knowledge) return []
  if (edge.relation === 'SUPPORTS') return knownGraphSources(knowledge, [edge.head])
  const from = knowledge.indexed.get(edge.head), to = knowledge.indexed.get(edge.tail)
  const declaration = edge.relation === 'EXPECTS' && from?.pattern_id === edge.tail ? from
    : edge.relation === 'HAS_EXPECTATION' && to?.from_id === edge.head && to.pattern_id ? to
    : edge.relation === 'DEFINES' && from?.definition_id === edge.head && from.pattern_id === edge.tail ? from
    : edge.relation === 'ACTIVATES_RULE' && to?.from_id === edge.head && to.to_id ? to
    : edge.relation === 'DERIVES_STATE' && from?.to_id === edge.tail ? from
    : undefined
  if (declaration) return knownGraphSources(knowledge, declaration.source_assertion_ids)
  const exact = knowledge.relations.filter(row => row.head === edge.head && row.tail === edge.tail && row.relation === edge.relation)
  return exact.length === 1 ? knownGraphSources(knowledge, exact[0]?.source_assertion_ids) : []
}

/** Describe the persisted expression, without evaluating it or expanding a runtime proof. */
export function graphExpressionName(expression: unknown, label: (id: string) => string): string {
  if (typeof expression === 'string') return label(expression)
  const row = traceRecord(expression), threshold = traceRecord(row.at_least)
  if (Array.isArray(row.all)) return `全部（${row.all.map(value => graphExpressionName(value, label)).join('；')}）`
  if (Array.isArray(row.any)) return `任一（${row.any.map(value => graphExpressionName(value, label)).join('；')}）`
  if (typeof threshold.count === 'number' && Array.isArray(threshold.of)) return `至少 ${threshold.count} 项（${threshold.of.map(value => graphExpressionName(value, label)).join('；')}）`
  return '未保存可读的联合条件'
}
