import type { PathGraphPath } from '@/api/contracts'
import type { SavedAnalysisFrame } from '@/services/saved-analysis-reader'
import { traceRecord, traceRows, traceValue, type TraceRecord } from '@/services/unified-reasoning-display'
import { savedWaferZone } from './wafer-zone'

export const detailTabs = [
  { id: 'overview', label: '总览' }, { id: 'input', label: '输入' }, { id: 'backbone', label: 'Backbone' },
  { id: 'evidence', label: 'Evidence' }, { id: 'reasoning', label: '推理' }, { id: 'graph', label: '图谱' },
] as const
export type DetailTab = typeof detailTabs[number]['id']
export function detailTab(value: unknown): DetailTab {
  return detailTabs.find(tab => tab.id === value)?.id ?? 'overview'
}
export function stageForTab(tab: DetailTab) { return tab === 'graph' ? 'reasoning' : tab }
export const text = (value: unknown) => typeof value === 'string' && value.length ? value : ''
export const strings = (value: unknown) => Array.isArray(value) ? value.filter((v): v is string => typeof v === 'string' && v.length > 0) : []
export const number = (value: unknown) => typeof value === 'number' && Number.isFinite(value) ? value : null
export function datasetLabel(value: unknown) { return ({ mvtec: 'MVTec', tep: 'TEP', wafer: 'WM-811K' } as Record<string, string>)[text(value)] ?? (text(value) || '未保存场景') }
export function reasonerLabel(value: unknown) { return ({ unified_abduction: '统一条件溯因', tep_rootkgd: 'RootKGD', graded_abduction: '分级解释溯因' } as Record<string, string>)[text(value)] ?? (text(value) || '未保存解释器') }
export function inputLabel(mode: unknown) { return mode === 'evidence' ? '中间 Evidence' : mode === 'records' ? '中间测量记录' : ['image', 'process', 'wafer'].includes(text(mode)) ? '原始样本' : (text(mode) || '未保存输入类型') }
export function scopeLabel(scope: unknown, fallback = '未保存范围') {
  const row = traceRecord(scope)
  if (row.kind === 'time_window' && number(row.sample_start) !== null && number(row.sample_end) !== null) return `样本 ${row.sample_start}–${row.sample_end}`
  if (row.kind === 'spatial_grid') return '晶圆网格'
  const waferZone = savedWaferZone(row)
  if (waferZone) return waferZone.label
  return text(row.scope_id) || fallback
}

const featureNames: Record<string, string> = {
  'detection.anomaly_present': '异常检测', 'appearance.defect_present': '外观缺陷判定', 'appearance.semantic_candidates': '外观候选',
  'geometry.area_ratio': '区域面积占比', 'geometry.aspect_ratio': '区域长宽比', 'geometry.eccentricity': '离心率',
  'geometry.component_count': '连通区域数', 'geometry.morphology': '区域形态', 'geometry.location': '区域位置',
  'statistics.mean_z': '标准化均值偏移', 'statistics.std_z': '标准化波动', 'statistics.slope_z': '标准化趋势斜率',
  'residual.contribution': '残差贡献', 'residual.energy': '残差能量', 'residual.normal_limit': '正常参考限值',
  'series.raw_values': '保存的通道曲线',
  'spatial.failure_density': '失效 die 密度', 'spatial.valid_die_count': '有效 die 数', 'spatial.failed_die_count': '失效 die 数',
  'spatial.component_count': '失效连通分量数', 'spatial.largest_component_ratio': '最大失效连通占比', 'spatial.linearity': '失效分布线性度',
  'spatial.edge_sector_participation': '边缘扇区参与度',
  'classifier.pattern': 'ResNet 图案类别', 'spatial.grid': '保存的晶圆网格',
}
const categoryNames: Record<string, string> = {
  cracked_or_missing_glass: '开裂或玻璃缺失', broken_finish: '瓶口破损', chipped_finish: '瓶口崩缺',
  chipped: '崩缺', chipped_edge: '边缘崩缺', small_chipped_section: '小块崩缺', spot: '斑点', linear: '线状', surface: '表面', edge: '边缘',
  nearfull: '近全片失效', edge_ring: '边缘环状失效', edge_loc: '边缘局部失效', center: '中心失效',
  donut: '环形失效', loc: '局部失效', random: '随机失效', scratch: '划痕',
}
const ops: Record<string, string> = { bool_eq: '=', eq: '=', neq: '≠', gt: '>', gte: '≥', lt: '<', lte: '≤', abs_gte: '绝对值 ≥', between: '介于', in: '属于', candidate_contains: '包含' }
export function featureLabel(value: unknown) { return featureNames[text(value)] ?? (text(value) || '未命名观测') }
export function valueLabel(value: unknown): string {
  if (value === null || value === undefined) return '未记录'
  const row = traceRecord(value)
  if (row.kind === 'boolean') return row.boolean === true ? '是' : row.boolean === false ? '否' : '未记录'
  if (row.kind === 'category') return categoryNames[text(row.category)] ?? (text(row.category) || '未记录')
  if (row.kind === 'candidate_set') return `${strings(row.items).map(item => categoryNames[item] ?? item).join('、') || '∅'}${row.exhaustive === false ? '（开放集合）' : ''}`
  if (row.kind === 'array_ref') return '引用保存数组'
  if (row.kind === 'number' && row.unit === '1') return traceValue(row.number)
  return traceValue(value)
}
export function valueKind(value: unknown) {
  const kind = text(traceRecord(value).kind)
  return ({ number: '数值', boolean: '布尔', category: '类别', candidate_set: '候选集合', array_ref: '数组引用' } as Record<string, string>)[kind] ?? (kind || '未记录')
}
export function observationStatus(value: unknown) {
  return ({ observed: '已观测', missing: '缺测', unknown: '未知', invalid: '无效', unavailable: '不可用', not_applicable: '不适用' } as Record<string, string>)[text(value)] ?? (text(value) || '状态未保存')
}
export function predicateLabel(predicate: unknown, fallback: string) {
  const row = traceRecord(predicate)
  return text(row.feature_id) && text(row.op) ? `${featureLabel(row.feature_id)} ${ops[text(row.op)] ?? row.op} ${valueLabel(row.operand)}` : fallback
}
export function truthLabel(value: unknown) { return value === true ? '成立' : value === false ? '不成立' : '未知' }
export function truthColor(value: unknown) { return value === true ? 'green' : value === false ? 'red' : 'orange' }
export function factReason(value: unknown) {
  return ({
    open_candidate_set_does_not_refute: '候选集合非穷尽，未列出不能判假。', missing_or_invalid_observations: '缺少适用观测。',
    scope_join_not_satisfied: '已保存观测不满足该范围联接。', no_bound_observation: '没有绑定的保存观测。',
  } as Record<string, string>)[text(value)] ?? text(value)
}
export function procedureLabel(procedure: unknown) {
  const row = traceRecord(procedure), id = text(row.procedure_id)
  return ({ detector: '检测记录', geometry: '几何测量', semantics: 'ROI 外观语义', 'normal-statistics': '正常参考窗口统计', 'spatial-statistics': '原网格空间统计', 'edge-sector-statistics': '边缘角向统计', classifier: 'ResNet 图案分类' } as Record<string, string>)[id] ?? (id || '未保存')
}
export function channelLabel(value: unknown) {
  const id = text(value), match = /^(xmeas|xmv)_(\d+)$/.exec(id)
  return match ? `${match[1]!.toUpperCase()}(${match[2]})` : id
}
export function sourceLocator(value: unknown) {
  const raw = text(value)
  try {
    const row = traceRecord(JSON.parse(raw))
    if (number(row.page) !== null) return `PDF 第 ${row.page} 页`
    if (number(row.start_line) !== null) return `第 ${row.start_line}–${row.end_line ?? row.start_line} 行`
  } catch { /* A saved source can already carry a prose locator. */ }
  return raw
}

export function isRootPropagation(result: TraceRecord | null | undefined) {
  return text(result?.scoring_method).startsWith('tep_rootkgd_propagation') || text(traceRecord(result?.propagation).projection_version).length > 0
}
export function savedCandidateRanks(frame: SavedAnalysisFrame) { return traceRows(frame.result?.ranked_root_causes) }
export function savedFacts(frame: SavedAnalysisFrame) { return traceRows(frame.result?.grounded_facts) }
export function observationChannel(frame: SavedAnalysisFrame, obs: TraceRecord) {
  const location = frame.locationsByObsId.get(text(obs.obs_id))
  const subject = traceRows(frame.frame.subjects).find(item => item.subject_id === obs.subject_id)
  return text(traceRecord(location).subject_external_id ?? subject?.external_id)
}
export function observationScope(frame: SavedAnalysisFrame, obs: TraceRecord) {
  return traceRecord(traceRecord(frame.locationsByObsId.get(text(obs.obs_id))).scope
    ?? traceRows(frame.frame.scopes).find(item => item.scope_id === obs.scope_id))
}
export function nativePath(frame: SavedAnalysisFrame, pathId: string) {
  return traceRows(frame.result?.top_k_paths).find(path => path.path_id === pathId)
}
export function getPathObs(frame: SavedAnalysisFrame, path: PathGraphPath) {
  return strings(path.supporting_evidence).filter(id => frame.observationsById.has(id))
}

export function observationUsage(frame: SavedAnalysisFrame, candidate: TraceRecord | null) {
  return {
    condition: new Set(savedFacts(frame).flatMap(fact => strings(fact.source_obs_ids))),
    structural: new Set(strings(traceRecord(frame.result?.propagation).scoring_input_obs_ids)),
    support: new Set(strings(candidate?.support_obs_ids)),
  }
}

export interface PathFocus { pathId: string; edgeId?: string; obsId?: string; factId?: string; nodeId?: string }
export function pathForFact(frame: SavedAnalysisFrame, candidateId: string, fact: TraceRecord): PathFocus | null {
  const predicateId = text(fact.predicate_id), factId = text(fact.fact_id), obs = strings(fact.source_obs_ids)
  if (!predicateId || !factId) return null
  const matches = (frame.pathsByCandidateId.get(candidateId) ?? []).flatMap(path => {
    const native = nativePath(frame, path.path_id)
    if (!strings(native?.required_joint_fact_ids).includes(factId) || !path.nodes.some(node => node.node_id === predicateId)) return []
    const obsId = getPathObs(frame, path).find(id => obs.includes(id))
    return obsId ? [{ path, obsId, edges: path.edges.filter(edge => edge.source_node_id === predicateId || edge.target_node_id === predicateId) }] : []
  })
  const first = matches[0]
  if (!first) return null
  const edges = new Set(matches.flatMap(item => item.edges.map(edge => edge.edge_id)))
  // A path-level reference is not an annotation on an arbitrary endpoint edge.
  const edgeId = edges.size === 1 && first.edges[0]?.edge_id ? first.edges[0].edge_id : undefined
  return { pathId: first.path.path_id, edgeId, obsId: first.obsId, factId }
}
export function factOnPath(frame: SavedAnalysisFrame, path: PathGraphPath, obsId: string | null, edgeId?: string) {
  const allowed = new Set(strings(nativePath(frame, path.path_id)?.required_joint_fact_ids))
  const edge = edgeId ? path.edges.find(item => item.edge_id === edgeId) : null
  const relevant = savedFacts(frame).filter(f => allowed.has(text(f.fact_id)) && strings(f.source_obs_ids).includes(obsId ?? ''))
  return relevant.find(f => edge && (f.predicate_id === edge.source_node_id || f.predicate_id === edge.target_node_id))
    ?? relevant.find(f => path.nodes.some(node => node.node_id === f.predicate_id)) ?? null
}
export function chooseSavedPath(paths: readonly PathGraphPath[], currentPathId: string | null, candidateId: string | null) {
  return paths.find(path => path.path_id === currentPathId)
    ?? paths.find(path => path.target_entity_id === candidateId) ?? paths[0] ?? null
}

export interface SavedCondition {
  id: string; label: string; truth: unknown; reason: string; join: string; expression: unknown
  predicates: readonly string[]; factsByPredicate: ReadonlyMap<string, readonly TraceRecord[]>; edgeFocus: PathFocus | null
}
export interface SavedProofGroup { id: string; label: string; mechanism: boolean; edgeFocus: PathFocus | null; conditions: SavedCondition[] }

/** Organize the candidate's stored checks; the saved expression is shown, never evaluated. */
export function savedProofGroups(snapshot: unknown, frame: SavedAnalysisFrame, candidate: TraceRecord): SavedProofGroup[] {
  if (isRootPropagation(frame.result)) return []
  const knowledge = traceRecord(traceRecord(snapshot).knowledge)
  const rules = traceRows(knowledge.expectation_rules), definitions = traceRows(knowledge.pattern_definitions)
  const labels = traceRecord(frame.result?.display_labels), candidateId = text(candidate.candidate_id)
  const paths = frame.pathsByCandidateId.get(candidateId) ?? []
  const effectIds = new Set(strings(candidate.activated_effect_rule_ids))
  const mechanisms = new Set(strings(candidate.active_hypothesis_world_entities).filter(id => id !== candidateId))
  const facts = savedFacts(frame), effects = traceRows(knowledge.effect_rules)
  const groups = new Map<string, SavedProofGroup>()
  for (const check of traceRows(candidate.expectation_checks)) {
    const patternId = text(check.pattern_id), ruleId = text(check.rule_id)
    if (!patternId || !ruleId) continue
    const definition = definitions.find(row => row.pattern_id === patternId)
    const observed = traceRows(frame.result?.observed_patterns).find(row => row.pattern_id === patternId)
    const hostId = text(rules.find(row => row.rule_id === ruleId)?.from_id)
    const host = hostId && (hostId === candidateId || mechanisms.has(hostId)) ? hostId : candidateId
    const group = groups.get(host) ?? {
      id: host, label: text(labels[host]) || text(candidate.candidate_name) || host,
      mechanism: host !== candidateId, edgeFocus: null, conditions: [],
    }
    if (group.mechanism && !group.edgeFocus) {
      const effect = effects.find(row => effectIds.has(text(row.rule_id)) && row.to_id === host)
      for (const path of paths) {
        const rule = text(effect?.rule_id)
        const edge = rule && path.edges.find(edge => (edge.source_node_id === rule && edge.target_node_id === host)
          || (edge.target_node_id === rule && edge.source_node_id === host))
        if (edge) { group.edgeFocus = { pathId: path.path_id, edgeId: edge.edge_id }; break }
      }
    }
    const predicates = strings(check.predicate_ids)
    const assessedIds = new Set([...strings(check.covered_fact_ids), ...strings(check.conflicting_fact_ids), ...strings(check.partial_matching_fact_ids)])
    const factsByPredicate = new Map(predicates.map(id => {
      const all = facts.filter(fact => fact.predicate_id === id)
      const named = all.filter(fact => assessedIds.has(text(fact.fact_id)))
      return [id, named.length ? named : all]
    }))
    const related = paths.find(path => path.nodes.some(node => node.node_id === ruleId) && path.nodes.some(node => node.node_id === patternId))
    const relation = related?.edges.find(edge => (edge.source_node_id === ruleId && edge.target_node_id === patternId)
      || (edge.target_node_id === ruleId && edge.source_node_id === patternId))
    group.conditions.push({
      id: ruleId, label: text(definition?.label) || text(labels[patternId]) || patternId, truth: check.observed_value,
      reason: factReason(check.reason), join: text(observed?.scope_join ?? definition?.scope_join), expression: definition?.body,
      predicates, factsByPredicate,
      edgeFocus: related && relation ? { pathId: related.path_id, edgeId: relation.edge_id } : null,
    })
    groups.set(host, group)
  }
  return [...groups.values()]
}
