import { beforeEach, describe, expect, it } from 'vitest'

import type { PathGraph } from '@/api/contracts'
import { applyGraphCurationToDataset, buildNeighborhoodSubgraphDataset, buildPathSubgraphDataset, loadGraphCurationCaseDraft, resetGraphCurationCaseDraft, saveGraphCurationCaseDraft, type MockGraphCurationCaseDraft } from '@/services/graph-curation'
import type { UnifiedGraphDataset } from '@/types/graph'

function createDemoDataset(): UnifiedGraphDataset {
  return {
    id: 'demo-graph',
    label: 'Demo Graph',
    description: 'demo dataset',
    graphKind: 'candidate-graph',
    projectRoot: 'demo',
    sourceFiles: [],
    metadata: {},
    nodes: [
      {
        id: 'A',
        name: 'Node A',
        category: 'demo',
        kind: 'entity',
        description: 'original A',
        aliases: [],
        degree: 2,
        inDegree: 1,
        outDegree: 1,
        attributes: {
          scenario: 'demo',
        },
        origin: {
          projectId: 'demo',
          projectLabel: 'Demo',
          filePath: 'demo.json',
          layer: 'candidate-graph',
          rowNumber: 1,
        },
      },
      {
        id: 'B',
        name: 'Node B',
        category: 'demo',
        kind: 'entity',
        description: 'original B',
        aliases: [],
        degree: 1,
        inDegree: 1,
        outDegree: 0,
        attributes: {
          scenario: 'demo',
        },
        origin: {
          projectId: 'demo',
          projectLabel: 'Demo',
          filePath: 'demo.json',
          layer: 'candidate-graph',
          rowNumber: 2,
        },
      },
      {
        id: 'C',
        name: 'Node C',
        category: 'demo',
        kind: 'entity',
        description: 'original C',
        aliases: [],
        degree: 2,
        inDegree: 0,
        outDegree: 2,
        attributes: {
          scenario: 'demo',
        },
        origin: {
          projectId: 'demo',
          projectLabel: 'Demo',
          filePath: 'demo.json',
          layer: 'candidate-graph',
          rowNumber: 3,
        },
      },
      {
        id: 'D',
        name: 'Node D',
        category: 'demo',
        kind: 'entity',
        description: 'original D',
        aliases: [],
        degree: 1,
        inDegree: 1,
        outDegree: 0,
        attributes: {
          scenario: 'demo',
        },
        origin: {
          projectId: 'demo',
          projectLabel: 'Demo',
          filePath: 'demo.json',
          layer: 'candidate-graph',
          rowNumber: 4,
        },
      },
    ],
    edges: [
      {
        id: 'edge-1',
        source: 'A',
        target: 'B',
        relation: 'CAUSES',
        category: 'demo',
        label: 'CAUSES',
        confidence: 0.6,
        weight: 0.6,
        directed: true,
        attributes: {
          source: 'doc-1',
          evidence: 'edge 1 evidence',
          review_status: 'auto',
          target_key: 'edge-1',
        },
        origin: {
          projectId: 'demo',
          projectLabel: 'Demo',
          filePath: 'demo.json',
          layer: 'candidate-graph',
          rowNumber: 5,
        },
      },
      {
        id: 'edge-2',
        source: 'C',
        target: 'A',
        relation: 'IMPACTS',
        category: 'demo',
        label: 'IMPACTS',
        confidence: 0.4,
        weight: 0.4,
        directed: true,
        attributes: {
          source: 'doc-2',
          evidence: 'edge 2 evidence',
          review_status: 'auto',
          target_key: 'edge-2',
        },
        origin: {
          projectId: 'demo',
          projectLabel: 'Demo',
          filePath: 'demo.json',
          layer: 'candidate-graph',
          rowNumber: 6,
        },
      },
      {
        id: 'edge-3',
        source: 'C',
        target: 'D',
        relation: 'RELATED_TO',
        category: 'demo',
        label: 'RELATED_TO',
        confidence: 0.8,
        weight: 0.8,
        directed: true,
        attributes: {
          source: 'doc-3',
          evidence: 'edge 3 evidence',
          review_status: 'auto',
          target_key: 'edge-3',
        },
        origin: {
          projectId: 'demo',
          projectLabel: 'Demo',
          filePath: 'demo.json',
          layer: 'candidate-graph',
          rowNumber: 7,
        },
      },
    ],
  }
}

describe('graph curation service', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('loads seeded paper demo drafts when storage is empty', () => {
    const seeded = loadGraphCurationCaseDraft('mvtec_fixture_clean_scratch')

    expect(seeded.case_id).toBe('mvtec_fixture_clean_scratch')
    expect(seeded.edge_drafts).toHaveLength(1)
    expect(seeded.edge_drafts[0].review_decision).toBe('revise')
    expect(seeded.node_drafts[0].node_id).toBe('MechanicalContact')
  })

  it('persists case drafts and falls back to seeded defaults after reset', () => {
    const customDraft: MockGraphCurationCaseDraft = {
      case_id: 'tep_0001',
      edge_drafts: [
        {
          edge_id: 'fault_anchor_edge_c28368046a61642d',
          target_key: 'fault_anchor_edge_c28368046a61642d',
          review_decision: 'accept',
          relation: 'SUPPORTED_BY',
          confidence: 0.91,
          note: 'custom persisted override',
          updated_at: '2026-05-15T12:00:00.000Z',
        },
      ],
      node_drafts: [],
    }

    saveGraphCurationCaseDraft(customDraft)

    const reloaded = loadGraphCurationCaseDraft('tep_0001')
    expect(reloaded.edge_drafts[0].review_decision).toBe('accept')
    expect(reloaded.edge_drafts[0].relation).toBe('SUPPORTED_BY')

    resetGraphCurationCaseDraft('tep_0001')

    const resetDraft = loadGraphCurationCaseDraft('tep_0001')
    expect(resetDraft.edge_drafts[0].review_decision).toBe('reject')
    expect(resetDraft.edge_drafts[0].relation).toBeNull()
  })

  it('projects local curation overlay onto nodes and edges', () => {
    const curated = applyGraphCurationToDataset(createDemoDataset(), {
      case_id: 'demo-case',
      edge_drafts: [
        {
          edge_id: 'edge-1',
          target_key: 'edge-1',
          review_decision: 'reject',
          relation: 'SUGGESTS_CAUSE',
          confidence: 0.22,
          note: 'downgrade to local reject',
          updated_at: '2026-05-15T12:00:00.000Z',
        },
      ],
      node_drafts: [
        {
          node_id: 'A',
          display_name: 'Node Alpha',
          aliases: ['alpha'],
          description: 'revised description',
          note: 'local rename',
          updated_at: '2026-05-15T12:00:00.000Z',
        },
      ],
    })

    const nodeA = curated.nodes.find((node) => node.id === 'A')
    const edge1 = curated.edges.find((edge) => edge.id === 'edge-1')

    expect(nodeA?.name).toBe('Node Alpha')
    expect(nodeA?.aliases).toEqual(['alpha'])
    expect(nodeA?.attributes.curation_status).toBe('revised')
    expect(edge1?.relation).toBe('SUGGESTS_CAUSE')
    expect(edge1?.confidence).toBe(0.22)
    expect(edge1?.attributes.review_status).toBe('rejected')
    expect(edge1?.attributes.curation_decision).toBe('reject')
  })

  it('builds a one-hop neighborhood subgraph around the selected node', () => {
    const neighborhood = buildNeighborhoodSubgraphDataset(createDemoDataset(), 'A')

    expect(neighborhood).not.toBeNull()
    expect(neighborhood?.nodes.map((node) => node.id).sort()).toEqual(['A', 'B', 'C'])
    expect(neighborhood?.edges.map((edge) => edge.id).sort()).toEqual(['edge-1', 'edge-2'])
    expect(neighborhood?.metadata.center_node_id).toBe('A')
  })

  it('builds a path union subgraph with shared path annotations', () => {
    const pathGraph: PathGraph = {
      path_count: 2,
      node_count: 3,
      edge_count: 2,
      paths: [
        {
          path_id: 'path-1',
          target_key: 'path-1',
          target_entity_id: 'B',
          supporting_evidence: [],
          nodes: [
            { node_id: 'A', label: 'Node A', role: 'source' },
            { node_id: 'B', label: 'Node B', role: 'target' },
          ],
          edges: [
            {
              edge_id: 'edge-1',
              target_key: 'edge-1',
              source_node_id: 'A',
              target_node_id: 'B',
              relation: 'CAUSES',
              confidence: 0.6,
              review_status: 'auto',
              evidence: 'path edge 1',
              source: 'doc-1',
            },
          ],
        },
        {
          path_id: 'path-2',
          target_key: 'path-2',
          target_entity_id: 'C',
          supporting_evidence: [],
          nodes: [
            { node_id: 'A', label: 'Node A', role: 'source' },
            { node_id: 'C', label: 'Node C', role: 'target' },
          ],
          edges: [
            {
              edge_id: 'edge-2',
              target_key: 'edge-2',
              source_node_id: 'A',
              target_node_id: 'C',
              relation: 'IMPACTS',
              confidence: 0.4,
              review_status: 'reviewed',
              evidence: 'path edge 2',
              source: 'doc-2',
            },
          ],
        },
      ],
    }

    const dataset = buildPathSubgraphDataset(pathGraph)
    const sourceNode = dataset.nodes.find((node) => node.id === 'A')

    expect(dataset.nodes).toHaveLength(3)
    expect(dataset.edges).toHaveLength(2)
    expect(sourceNode?.attributes.path_ids).toEqual(['path-1', 'path-2'])
  })
})
