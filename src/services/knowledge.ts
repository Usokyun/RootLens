import { record, rows, text, friendly, texts, conditionText } from '@/services/presentation'
import type { RecordValue } from '@/api/workbench'
export type KnowledgeSection = 'entities' | 'hypotheses' | 'mechanisms' | 'pattern_definitions' | 'observable_definitions' | 'rules' | 'bindings' | 'sources'
export const knowledgeSections: Array<{ key: KnowledgeSection; label: string; hint: string }> = [
  { key: 'entities', label: '对象与变量', hint: '被观测的设备、产品和测量变量' },
  { key: 'hypotheses', label: '候选解释', hint: '资料支持的竞争性原因或图案假设' },
  { key: 'mechanisms', label: '中间机制', hint: '候选如何产生可观测表现' },
  { key: 'pattern_definitions', label: '联合现象', hint: '哪些条件需要同时或择一满足' },
  { key: 'observable_definitions', label: '观测条件', hint: '特征、阈值、主体与作用范围' },
  { key: 'rules', label: '关系与规则', hint: '原因到机制、机制到现象的关系' },
  { key: 'bindings', label: '观测绑定', hint: '外部主体和特征词汇如何进入图谱' },
  { key: 'sources', label: '资料依据', hint: '定位原文、模型提议和阈值来源' },
]
export interface KnowledgeItem { id: string; label: string; subtitle: string; group: string; index: number; raw: RecordValue }
export function knowledgeOf(pkg: unknown): RecordValue { const p = record(pkg); return record(p.knowledge ?? record(p.package).knowledge) }
export function rowId(row: RecordValue): string {
  return text(row.entity_id ?? row.hypothesis_id ?? row.mechanism_id ?? row.pattern_id ?? row.predicate_id ?? row.rule_id ?? row.relation_id ?? row.binding_id ?? row.assertion_id)
}
export function labelMap(knowledge: RecordValue): Map<string, string> {
  const map = new Map<string, string>()
  for (const group of ['entities', 'hypotheses', 'mechanisms', 'pattern_definitions', 'observable_definitions']) {
    rows(knowledge[group]).forEach((row) => map.set(rowId(row), friendly(row.label, '未命名内容')))
  }
  return map
}
export function nameOf(knowledge: RecordValue, id: unknown, fallback = '未命名内容') { return labelMap(knowledge).get(text(id)) ?? friendly(id, fallback) }
export function expressionRefs(value: unknown): string[] {
  if (typeof value === 'string') return [value]
  const obj = record(value)
  return [...new Set((Array.isArray(obj.all) ? obj.all : Array.isArray(obj.any) ? obj.any : record(obj.at_least).of as unknown[] ?? []).flatMap(expressionRefs))]
}
export function expressionText(value: unknown, names: Map<string, string>): string {
  if (typeof value === 'string') return names.get(value) ?? friendly(value)
  const obj = record(value)
  const children = Array.isArray(obj.all) ? obj.all : Array.isArray(obj.any) ? obj.any : record(obj.at_least).of as unknown[] ?? []
  const joiner = obj.all ? ' 且 ' : obj.any ? ' 或 ' : '、'
  const result = children.map((child) => expressionText(child, names)).join(joiner)
  return obj.at_least ? `至少 ${record(obj.at_least).count} 项：${result}` : `（${result}）`
}
export function catalog(knowledge: RecordValue, section: KnowledgeSection): KnowledgeItem[] {
  const groups = section === 'rules' ? ['effect_rules', 'expectation_rules', 'relations'] : section === 'bindings' ? ['subject_bindings', 'value_bindings'] : section === 'sources' ? ['source_assertions'] : [section]
  const names = labelMap(knowledge)
  return groups.flatMap((group) => rows(knowledge[group]).map((row, index) => {
    const id = rowId(row) || `${group}/${index}`
    let label = friendly(row.label, '未命名内容'), subtitle = ''
    if (group === 'observable_definitions') subtitle = conditionText(row)
    if (group === 'pattern_definitions') subtitle = expressionText(row.body, names)
    if (group === 'hypotheses') subtitle = row.target_role === 'pattern_family' ? '图案类别假设' : '原因机制假设'
    if (group === 'entities') subtitle = ({ Object: '产品 / 过程', Variable: '测量变量', Equipment: '设备' } as Record<string, string>)[text(row.kind)] ?? friendly(row.kind, '对象')
    if (group === 'effect_rules') { label = `${names.get(text(row.from_id)) ?? friendly(row.from_id)} → ${names.get(text(row.to_id)) ?? friendly(row.to_id)}`; subtitle = '影响 / 产生机制' }
    if (group === 'expectation_rules') { label = `${names.get(text(row.from_id)) ?? friendly(row.from_id)} → ${names.get(text(row.pattern_id)) ?? friendly(row.pattern_id)}`; subtitle = friendly(row.mode) }
    if (group === 'relations') { label = `${names.get(text(row.head)) ?? friendly(row.head)} → ${names.get(text(row.tail)) ?? friendly(row.tail)}`; subtitle = friendly(row.relation) }
    if (group === 'subject_bindings') { label = `${friendly(row.external_id)} → ${names.get(text(row.target_id)) ?? friendly(row.target_id)}`; subtitle = '外部主体绑定' }
    if (group === 'value_bindings') { label = `${friendly(row.external_value)} → ${friendly(row.canonical_value)}`; subtitle = '特征值映射' }
    if (group === 'source_assertions') { label = friendly(row.origin); subtitle = text(row.text) }
    return { id, label, subtitle, group, index, raw: row }
  }))
}
export function sourcesFor(knowledge: RecordValue, row: RecordValue) {
  const ids = texts(row.source_assertion_ids)
  return rows(knowledge.source_assertions).filter((source) => ids.includes(text(source.assertion_id)))
}
export function semanticGraph(knowledge: RecordValue) {
  const groups = [
    { key: 'hypotheses', title: '候选解释', role: 'candidate' },
    { key: 'mechanisms', title: '中间机制', role: 'mechanism' },
    { key: 'pattern_definitions', title: '联合现象', role: 'pattern' },
    { key: 'observable_definitions', title: '观测条件', role: 'condition' },
  ]
  const nodes = groups.flatMap((g, column) => rows(knowledge[g.key]).map((row, index) => ({ id: rowId(row), label: friendly(row.label), column, index, role: g.role })))
  const edges = [
    ...rows(knowledge.effect_rules).map((r) => ({ id: text(r.rule_id), from: text(r.from_id), to: text(r.to_id), kind: '影响' })),
    ...rows(knowledge.expectation_rules).map((r) => ({ id: text(r.rule_id), from: text(r.from_id), to: text(r.pattern_id), kind: friendly(r.mode) })),
    ...rows(knowledge.pattern_definitions).flatMap((r) => expressionRefs(r.body).map((id) => ({ id: `${rowId(r)}/${id}`, from: rowId(r), to: id, kind: '联合条件' }))),
  ]
  return { groups, nodes, edges }
}
