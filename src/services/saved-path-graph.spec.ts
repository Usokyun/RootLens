import { describe, expect, it } from 'vitest'
import type { PathGraph } from '@/api/contracts'
import { buildPathSubgraphDataset } from './saved-path-graph'

describe('saved path graph', () => {
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
