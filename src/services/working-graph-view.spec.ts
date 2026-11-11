import { describe, expect, it } from 'vitest'
import type { KGStudioGraphEdge, KGStudioGraphNode, KGStudioPayload, WorkingGraphPackage } from '@/api/contracts'
import {
  buildWorkingGraphView, findWorkingGraphNodes, graphConditionName, graphExpressionName, graphSourceLocation, graphPreviewEdgeLimit,
  previewNodeName, readWorkingGraphKnowledge, workingGraphEdgeSources, workingGraphFocus, workingGraphGroups, workingGraphKind, workingGraphMode,
} from './working-graph-view'

const node = (node_id: string, node_type: string, label = node_id, aliases: string[] = []): KGStudioGraphNode => ({
  node_id, node_type, label, aliases, scenario: 'tep', description: '',
})
const edge = (edge_id: string, head: string, relation: string, tail: string): KGStudioGraphEdge => ({
  edge_id, head, tail, relation, scenario: 'tep', target_key: `edge:${edge_id}`, source: 'unified-v2', evidence: '',
  confidence: null, weight: null, review_status: 'unreviewed',
})
function studio(graph_nodes: KGStudioGraphNode[], graph_edges: KGStudioGraphEdge[]): KGStudioPayload {
  return {
    graph_id: 'current', status: 'ok', claim_boundary: '', candidate_dir: null, nodes_path: null, edges_path: null,
    source_registry_path: '', node_count: 142, edge_count: 130, scenario_counts: {}, review_status_counts: {},
    source_counts: {}, confidence_summary: {}, validation_summary: null, sources: [], source_documents: [],
    graph_nodes, graph_edges, review_targets: [], note: '',
  }
}
const network = studio([
  node('candidate', 'Hypothesis', '冷却支路'),
  node('mechanism', 'Mechanism', '温度上升'),
  node('signature', 'Phenomenon', '反应器温度升高'),
  node('expectation', 'ExpectationRule'),
  node('channel:raw', 'Variable', '反应器温度', ['XMEAS(9)']),
  node('reference', 'SourceAssertion'),
  node('unsupported', 'RuntimeSpecific'),
], [edge('declaration', 'candidate', 'HAS_EXPECTATION', 'expectation'),
  edge('rule', 'expectation', 'EXPECTS', 'signature'), edge('reference-edge', 'reference', 'SUPPORTS', 'expectation'),
  edge('not-in-preview', 'channel:raw', 'OBSERVES', 'absent')])

describe('working graph preview', () => {
  it('uses node_type, not the same scenario, and gives unknown nodes a neutral group', () => {
    const view = buildWorkingGraphView(network)
    expect(view.dataset.nodes.map(row => row.category)).toEqual(['cause', 'mechanism', 'phenomenon', 'rule', 'subject', 'source', 'other'])
    expect(new Set(view.dataset.nodes.map(row => workingGraphGroups[row.category as keyof typeof workingGraphGroups].color)).size).toBe(7)
    expect(workingGraphKind('Hypothesis', 'wafer').label).toBe('图案候选')
    expect(workingGraphKind('Hypothesis', 'tep').label).toBe('候选原因')
  })

  it('keeps full counts distinct, caps preview at 80 and never invents edge endpoints', () => {
    const view = buildWorkingGraphView(network)
    expect(view.nodeTotal).toBe(142)
    expect(view.edgeTotal).toBe(130)
    expect(view.dataset.edges).toHaveLength(3)
    expect(view.dataset.edges[0]).toMatchObject({ id: 'declaration', source: 'candidate', target: 'expectation', directed: true })
    expect(view.skippedEdges).toBe(1)
    const many = buildWorkingGraphView({ ...network, graph_edges: Array.from({ length: 85 }, (_, i) => edge(String(i), 'candidate', 'REL', 'signature')) })
    expect(many.dataset.edges).toHaveLength(graphPreviewEdgeLimit)
  })

  it('matches real names, aliases and stable channel tokens and keeps the saved name after rename', () => {
    const view = buildWorkingGraphView(network)
    expect(findWorkingGraphNodes(view, 'ｘｍｅａｓ＿9').map(row => row.id)).toEqual(['channel:raw'])
    expect(findWorkingGraphNodes(view, '温度升高').map(row => row.id)).toEqual(['signature'])
    expect(findWorkingGraphNodes(view, '不存在')).toEqual([])
    const bottle = node('entity:industrial.object:bottle', 'Object', 'bottle', ['玻璃瓶'])
    expect(previewNodeName(bottle)).toBe('玻璃瓶')
    expect(previewNodeName({ ...bottle, label: 'Demo specimen' })).toBe('Demo specimen')
  })

  it('focuses only the selected preview edge or the exact one-hop neighborhood', () => {
    const view = buildWorkingGraphView(network)
    expect(workingGraphFocus(view, { type: 'edge', id: 'rule' }, 'source')).toEqual({ nodes: ['expectation', 'signature'], edges: ['rule'] })
    expect(workingGraphFocus(view, { type: 'node', id: 'signature' }, null)).toEqual({ nodes: ['signature', 'expectation'], edges: ['rule'] })
    expect(workingGraphFocus(view, null, 'source')).toEqual({ nodes: ['reference'], edges: [] })
    expect(workingGraphFocus(view, { type: 'edge', id: 'not-in-preview' }, null)).toEqual({ nodes: [], edges: [] })
  })
})

describe('read-only canonical knowledge', () => {
  const valueBinding = {
    binding_id: 'binding', feature_id: 'appearance.semantic_candidates', external_value: 'alias', canonical_value: 'chipped_edge',
    procedure_model_id: 'detector', source_assertion_ids: ['reference'],
  }
  const packageV2: WorkingGraphPackage = {
    schema_version: 'rootlens-working-graph.v2', graph_id: 'current', title: 'Current', dataset: 'tep', build_id: 'b',
    knowledge: {
      expectation_rules: [{ rule_id: 'expectation', from_id: 'candidate', pattern_id: 'signature', mode: 'necessary', source_assertion_ids: ['reference'] }],
      observable_definitions: [{ predicate_id: 'predicate', feature_id: 'statistics.mean_z', op: 'gte', operand: { kind: 'number', number: 0.000001231234, unit: 'z' } }],
      subject_bindings: [{ namespace: 'tep_braatz.channel', external_id: 'xmeas_9', target_id: 'channel:raw' }],
      value_bindings: [valueBinding],
      source_assertions: [{ assertion_id: 'reference', origin: 'source_explicit', locator: '{"page":13}', text: '原文' }],
    },
  }

  it('reads bindings and saved logic without rewriting, and refuses a different package', () => {
    const knowledge = readWorkingGraphKnowledge(packageV2, 'current')!
    expect(knowledge.valueBindings[0]).toBe(valueBinding)
    expect(knowledge.subjectBindings[0]?.target_id).toBe('channel:raw')
    expect(graphConditionName(knowledge.conditions[0]!)).toBe('标准化均值偏移 ≥ 0.000001231234 z')
    expect(workingGraphMode(knowledge.expectations[0]?.mode)).toBe('必要')
    expect(graphExpressionName({ all: ['P', { at_least: { count: 1, of: ['Q', { any: ['R', 'S'] }] } }] }, id => id))
      .toBe('全部（P；至少 1 项（Q；任一（R；S）））')
    expect(graphSourceLocation(knowledge.sources[0]?.locator)).toBe('第 13 页')
    expect(readWorkingGraphKnowledge(packageV2, 'another')).toBeNull()
  })

  it('shows only provenance on the exact support or declared endpoints, never the reversed edge', () => {
    const knowledge = readWorkingGraphKnowledge(packageV2, 'current')!
    const sources = network.graph_edges.slice(0, 3).map(item => workingGraphEdgeSources(knowledge, item).map(row => row.assertion_id))
    expect(sources).toEqual([['reference'], ['reference'], ['reference']])
    expect(workingGraphEdgeSources(knowledge, edge('false', 'signature', 'EXPECTS', 'expectation'))).toEqual([])
    expect(workingGraphEdgeSources(knowledge, edge('no-citation', 'candidate', 'OBSERVES', 'signature'))).toEqual([])
  })
})
