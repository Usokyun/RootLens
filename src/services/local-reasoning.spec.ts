import { buildLocalAnalysisResult } from '@/services/local-reasoning'
import type { JsonValue, UnifiedGraphDataset } from '@/types/graph'
import type { UnifiedEvidence } from '@/types/rootlens'
import { describe, expect, it } from 'vitest'

function createNode(input: {
  id: string
  name: string
  category: string
  kind: string
  aliases?: string[]
  attributes?: Record<string, JsonValue>
}) {
  return {
    id: input.id,
    name: input.name,
    category: input.category,
    kind: input.kind,
    description: '',
    aliases: input.aliases ?? [],
    degree: 0,
    inDegree: 0,
    outDegree: 0,
    attributes: input.attributes ?? {},
    origin: {
      projectId: 'unit-test',
      projectLabel: 'Unit Test',
      filePath: 'fixture.json',
      layer: 'test',
      rowNumber: 1,
    },
  }
}

function createEdge(input: {
  id: string
  source: string
  target: string
  relation: string
  confidence?: number
  weight?: number
}) {
  return {
    id: input.id,
    source: input.source,
    target: input.target,
    relation: input.relation,
    category: input.relation,
    label: input.relation,
    confidence: input.confidence ?? 0.8,
    weight: input.weight ?? input.confidence ?? 0.8,
    directed: true,
    attributes: {},
    origin: {
      projectId: 'unit-test',
      projectLabel: 'Unit Test',
      filePath: 'fixture.json',
      layer: 'test',
      rowNumber: 1,
    },
  }
}

const dataset: UnifiedGraphDataset = {
  id: 'unit-graph',
  label: 'Unit Graph',
  description: 'Synthetic graph for local reasoning tests.',
  graphKind: 'runtime-kg',
  projectRoot: 'unit',
  sourceFiles: [],
  nodes: [
    createNode({
      id: 'variable:x1',
      name: 'reactor_temp_sensor',
      category: 'Variable',
      kind: 'observation',
      aliases: ['x1', 'reactor temp'],
    }),
    createNode({
      id: 'equipment:reactor',
      name: 'reactor',
      category: 'Equipment',
      kind: 'equipment_anchor',
      aliases: ['reactor vessel'],
    }),
    createNode({
      id: 'stream:feed',
      name: 'feed stream',
      category: 'Stream',
      kind: 'stream_anchor',
    }),
    createNode({
      id: 'faultanchor:feed_loss',
      name: 'feed loss',
      category: 'FaultAnchor',
      kind: 'root_cause_anchor',
      attributes: {
        fault_numbers: [6],
      },
    }),
    createNode({
      id: 'object:bottle',
      name: 'bottle body',
      category: 'Object',
      kind: 'Object',
    }),
    createNode({
      id: 'anomaly:scratch',
      name: 'scratch',
      category: 'AnomalyType',
      kind: 'AnomalyType',
    }),
    createNode({
      id: 'morphology:linear',
      name: 'linear scratch',
      category: 'Morphology',
      kind: 'Morphology',
    }),
    createNode({
      id: 'location:body',
      name: 'body',
      category: 'Location',
      kind: 'Location',
    }),
    createNode({
      id: 'rootcause:seal_wear',
      name: 'seal wear',
      category: 'RootCause',
      kind: 'RootCause',
    }),
  ],
  edges: [
    createEdge({
      id: 'edge-variable-equipment',
      source: 'variable:x1',
      target: 'equipment:reactor',
      relation: 'MEASURED_IN',
      confidence: 0.92,
    }),
    createEdge({
      id: 'edge-variable-stream',
      source: 'variable:x1',
      target: 'stream:feed',
      relation: 'PART_OF',
      confidence: 0.76,
    }),
    createEdge({
      id: 'edge-equipment-fault',
      source: 'equipment:reactor',
      target: 'faultanchor:feed_loss',
      relation: 'CAUSES',
      confidence: 0.95,
    }),
    createEdge({
      id: 'edge-stream-fault',
      source: 'stream:feed',
      target: 'faultanchor:feed_loss',
      relation: 'CAUSES',
      confidence: 0.88,
    }),
    createEdge({
      id: 'edge-object-anomaly',
      source: 'object:bottle',
      target: 'anomaly:scratch',
      relation: 'HAS_ANOMALY',
      confidence: 0.93,
    }),
    createEdge({
      id: 'edge-anomaly-morphology',
      source: 'anomaly:scratch',
      target: 'morphology:linear',
      relation: 'HAS_MORPHOLOGY',
      confidence: 0.89,
    }),
    createEdge({
      id: 'edge-anomaly-location',
      source: 'anomaly:scratch',
      target: 'location:body',
      relation: 'OCCURS_ON',
      confidence: 0.91,
    }),
    createEdge({
      id: 'edge-rootcause-anomaly',
      source: 'rootcause:seal_wear',
      target: 'anomaly:scratch',
      relation: 'HAS_PLAUSIBLE_CAUSE',
      confidence: 0.94,
    }),
  ],
  metadata: {},
}

const evidence: UnifiedEvidence = {
  case_id: 'case-1',
  case_label: 'Case 1',
  dataset: 'tep',
  source: 'multimodal',
  timestamp: '2026-05-12T12:00:00Z',
  summary: 'Synthetic multimodal case.',
  graph_dataset_id: 'unit-graph',
  observations: [
    {
      obs_id: 'obs-variable',
      facet: 'variable',
      variable_name: 'sensor that needs hint resolution',
      contribution: 0.91,
      direction: 'increase',
      confidence: 0.97,
      linked_entity_hints: ['variable:x1', 'reactor temp'],
      raw_evidence_refs: [],
    },
    {
      obs_id: 'obs-image',
      facet: 'image_defect',
      object: 'panel that needs hint resolution',
      anomaly_type: 'surface scratch',
      location: 'body',
      morphology: {
        canonical: 'blob cluster',
      },
      severity: 0.84,
      confidence: 0.95,
      linked_entity_hints: ['object:bottle', 'anomaly:scratch'],
      raw_evidence_refs: [],
    },
  ],
}

describe('buildLocalAnalysisResult', () => {
  it('uses linked_entity_hints and generates correction candidates for unmatched fields', () => {
    const result = buildLocalAnalysisResult(dataset, evidence)
    const route1 = result.route1

    expect(route1).not.toBeNull()
    expect(
      route1?.linked_entities.find((item) => item.field === 'variable')?.selected_entity_id,
    ).toBe('variable:x1')
    expect(route1?.linked_entities.find((item) => item.field === 'variable')?.match_type).toBe('exact')
    expect(route1?.inconsistent_fields).toContain('morphology')
    expect(route1?.correction_candidates.some((item) => item.suggested_entity_id === 'morphology:linear')).toBe(true)
  })

  it('returns multiple route1 paths and route2 candidates with cross-route overlap', () => {
    const result = buildLocalAnalysisResult(dataset, evidence)
    const route1 = result.route1
    const route2 = result.route2

    expect(route1).not.toBeNull()
    expect(route2).not.toBeNull()

    const feedLossPaths =
      route1?.ranked_paths.filter(
        (path) =>
          path.source_entity_id === 'variable:x1' &&
          path.target_entity_id === 'faultanchor:feed_loss',
      ) ?? []

    expect(feedLossPaths).toHaveLength(2)
    expect(route2?.ranked_candidates.map((candidate) => candidate.candidate_id)).toEqual(
      expect.arrayContaining(['equipment:reactor', 'faultanchor:feed_loss']),
    )

    const crossSignal = result.cross_route_signals.find(
      (item) => item.candidate_id === 'faultanchor:feed_loss',
    )

    expect(crossSignal).toBeTruthy()
    expect(crossSignal?.route1_path_ids).toHaveLength(2)
    expect(crossSignal?.shared_obs_ids).toContain('obs-variable')
  })
})
