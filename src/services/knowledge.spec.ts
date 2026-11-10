import { describe, expect, it } from 'vitest'
import { catalog, expressionRefs, expressionText, labelMap, semanticGraph, sourcesFor } from '@/services/knowledge'
const knowledge = {
  entities: [{ entity_id: 'object', label: 'bottle', kind: 'Object', aliases: ['玻璃容器'] }],
  hypotheses: [{ hypothesis_id: 'candidate', label: '候选原因', target_role: 'mechanism' }],
  mechanisms: [{ mechanism_id: 'mechanism', label: '机械作用' }],
  observable_definitions: [{ predicate_id: 'a', label: '检测到异常', feature_id: 'detection.anomaly_present', op: 'bool_eq', operand: { kind: 'boolean', boolean: true } }, { predicate_id: 'b', label: '玻璃缺失' }],
  pattern_definitions: [{ pattern_id: 'pattern', label: '破损现象', body: { all: ['a', { any: ['a','b'] }] } }],
  effect_rules: [{ rule_id: 'effect', from_id: 'candidate', to_id: 'mechanism', source_assertion_ids: ['source'] }],
  expectation_rules: [{ rule_id: 'expect', from_id: 'mechanism', pattern_id: 'pattern', mode: 'expected' }],
  source_assertions: [{ assertion_id: 'source', origin: 'llm_proposed', text: '可追溯来源' }],
}
describe('semantic graph view model', () => {
  it('shows real semantic nodes and relationships without default source/reified rule nodes', () => {
    const graph = semanticGraph(knowledge)
    expect(graph.nodes.map((n) => n.id)).toEqual(['candidate','mechanism','pattern','a','b'])
    expect(graph.edges).toEqual(expect.arrayContaining([expect.objectContaining({ from: 'candidate', to: 'mechanism' }), expect.objectContaining({ from: 'mechanism', to: 'pattern' })]))
    expect(graph.nodes.some((n) => n.id === 'source' || n.id === 'effect')).toBe(false)
  })
  it('keeps AND/OR/at-least nesting declarative and does not evaluate it in the browser', () => {
    const body = { all: ['a', { any: ['a','b'] }, { at_least: { count: 1, of: ['b'] } }] }
    expect(expressionRefs(body)).toEqual(['a','b'])
    expect(expressionText(body,labelMap(knowledge))).toBe('（检测到异常 且 （检测到异常 或 玻璃缺失） 且 至少 1 项：玻璃缺失）')
  })
  it('renders bindings, rules and sources by meaning while retaining stable references', () => {
    expect(catalog(knowledge,'entities')[0]).toEqual(expect.objectContaining({ id:'object', label:'玻璃瓶', subtitle:'产品 / 过程' }))
    expect(catalog(knowledge,'rules')[0]?.label).toBe('候选原因 → 机械作用')
    expect(sourcesFor(knowledge,knowledge.effect_rules[0]!)[0]?.text).toBe('可追溯来源')
  })
})
