import { describe, expect, it } from 'vitest'
import type { UnifiedWorkingGraphPackage, WorkingGraphPackage } from '@/api/contracts'
import { editableWorkingGraphNode, parseWorkingGraphDraft, updateWorkingGraphNode } from './working-graph-edit'

function workingPackage() {
  return {
    schema_version: 'rootlens-working-graph.v2',
    graph_id: 'saved-graph',
    title: '瓶口工作图',
    dataset: 'mvtec',
    build_id: 'saved-build',
    future_package_field: { provenance: ['unchanged'] },
    knowledge: {
      schema_version: 'rootlens-knowledge-package.v2',
      graph_id: 'saved-graph',
      entities: [{ entity_id: 'bottle', label: '瓶', kind: 'Object', aliases: ['bottle'], future_field: 10 }],
      hypotheses: [{ hypothesis_id: 'h', label: '候选', applies_to_class_id: 'bottle', assumption_cost: 1 }],
      mechanisms: [{ mechanism_id: 'm', label: '机理' }],
      pattern_definitions: [{
        pattern_id: 'appearance', definition_id: 'definition', label: '现象',
        body: { all: ['p'] }, source_assertion_ids: ['s'],
      }],
      feature_registry: [{ feature_id: 'appearance.semantic_candidates', semantic_role: 'diagnostic' }],
      observable_definitions: [{ predicate_id: 'p', label: '条件' }],
      relations: [{ relation_id: 'edge', head: 'bottle', tail: 'bottle', relation: 'IS_A' }],
      value_bindings: [{ binding_id: 'v', canonical_value: 'chipped', source_assertion_ids: ['s'] }],
      expectation_rules: [{ rule_id: 'r', from_id: 'm', pattern_id: 'appearance' }],
      effect_rules: [{ rule_id: 'e', from_id: 'h', to_id: 'm' }],
      source_assertions: [{ assertion_id: 's', locator: { page: 13 } }],
    },
  } satisfies UnifiedWorkingGraphPackage & { future_package_field: unknown }
}

describe('working graph edits', () => {
  it('updates only the canonical entity label and aliases; retains IDs and unrelated data', () => {
    const base = workingPackage()
    const original = JSON.stringify(base)
    const next = updateWorkingGraphNode(base, 'bottle', { name: '  玻璃瓶  ', aliases: [' bottle ', '玻璃容器', '', 'bottle'] })
    expect(next).toEqual({
      ...base,
      knowledge: {
        ...base.knowledge,
        entities: [{ ...base.knowledge.entities[0], label: '玻璃瓶', aliases: ['bottle', '玻璃容器'] }],
      },
    })
    expect(next.knowledge.relations).toBe(base.knowledge.relations)
    expect(next.knowledge.expectation_rules).toBe(base.knowledge.expectation_rules)
    expect(JSON.stringify(base)).toBe(original)
  })

  it.each([
    ['h', 'hypothesis', 'hypotheses'],
    ['m', 'mechanism', 'mechanisms'],
    ['appearance', 'pattern', 'pattern_definitions'],
  ] as const)('edits %s only via its canonical label', (id, kind, list) => {
    const base = workingPackage()
    expect(editableWorkingGraphNode(base, id)).toMatchObject({ id, kind, aliases: null })
    expect(updateWorkingGraphNode(base, id, { name: '新名称' }).knowledge[list]).toEqual([
      { ...base.knowledge[list][0], label: '新名称' },
    ])
    expect(() => updateWorkingGraphNode(base, id, { name: '新名称', aliases: [] })).toThrow('只有实体')
  })

  it('does not edit compiled definitions, predicates, rules, missing IDs, or old graphs', () => {
    const base = workingPackage()
    for (const id of ['definition', 'p', 'e', 'r', 's', 'unknown']) {
      expect(editableWorkingGraphNode(base, id)).toBeNull()
      expect(() => updateWorkingGraphNode(base, id, { name: '错误编辑' })).toThrow('没有可编辑')
    }
    const legacy: WorkingGraphPackage = {
      schema_version: 'rootlens-working-graph.v1', title: '旧版', dataset: 'mvtec',
      build_id: 'old', nodes: [], edges: [], profiles: {},
    }
    expect(editableWorkingGraphNode(legacy, 'bottle')).toBeNull()
    expect(() => updateWorkingGraphNode(legacy, 'bottle', { name: '错误编辑' })).toThrow('只读')
    expect(() => updateWorkingGraphNode(base, 'bottle', { name: '   ' })).toThrow('请输入')
  })

  it('requires a full editable envelope and leaves valid import JSON intact', () => {
    const base = workingPackage()
    expect(parseWorkingGraphDraft(JSON.stringify(base))).toEqual(base)
    expect(() => parseWorkingGraphDraft('{')).toThrow('格式')
    expect(() => parseWorkingGraphDraft(JSON.stringify({ ...base, schema_version: 'rootlens-working-graph.v1' }))).toThrow('v2')
    expect(() => parseWorkingGraphDraft(JSON.stringify({ ...base, knowledge: { graph_id: 'saved-graph' } }))).toThrow('规范知识')
  })

  it('saves an edited full package only under the same existing graph identity', () => {
    const base = workingPackage()
    const revised = { ...base, title: '新标题' }
    expect(parseWorkingGraphDraft(JSON.stringify(revised), base)).toEqual(revised)
    for (const alternate of [
      { ...base, graph_id: null },
      { ...base, graph_id: 'another-graph' },
      { ...base, dataset: 'tep' },
      { ...base, build_id: 'another-source' },
      { ...base, knowledge: { ...base.knowledge, graph_id: 'another-graph' } },
    ]) expect(() => parseWorkingGraphDraft(JSON.stringify(alternate), base)).toThrow('导入为新图')
  })
})
