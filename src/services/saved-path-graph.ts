import type { PathGraph } from '@/api/contracts'
import type { UnifiedGraphDataset, UnifiedGraphEdge, UnifiedGraphNode } from '@/types/graph'

export function buildPathSubgraphDataset(pathGraph: PathGraph): UnifiedGraphDataset {
  const nodeSeed = new Map<
    string,
    {
      node_id: string
      label: string
      role: string
      pathIds: Set<string>
    }
  >()
  const edgeSeed = new Map<
    string,
    {
      edge_id: string
      source_node_id: string
      target_node_id: string
      relation: string
      confidence: number | null
      review_status: string | null
      evidence: string | null
      source: string | null
      target_key: string
      pathIds: Set<string>
    }
  >()

  for (const path of pathGraph.paths) {
    for (const node of path.nodes) {
      const current = nodeSeed.get(node.node_id)
      if (current) {
        current.pathIds.add(path.path_id)
        continue
      }

      nodeSeed.set(node.node_id, {
        node_id: node.node_id,
        label: node.label,
        role: node.role,
        pathIds: new Set([path.path_id]),
      })
    }

    for (const edge of path.edges) {
      const current = edgeSeed.get(edge.edge_id)
      if (current) {
        current.pathIds.add(path.path_id)
        continue
      }

      edgeSeed.set(edge.edge_id, {
        edge_id: edge.edge_id,
        source_node_id: edge.source_node_id,
        target_node_id: edge.target_node_id,
        relation: edge.relation,
        confidence: edge.confidence ?? null,
        review_status: edge.review_status ?? null,
        evidence: edge.evidence ?? null,
        source: edge.source ?? null,
        target_key: edge.target_key,
        pathIds: new Set([path.path_id]),
      })
    }
  }

  const inDegree = new Map<string, number>()
  const outDegree = new Map<string, number>()
  for (const edge of edgeSeed.values()) {
    outDegree.set(edge.source_node_id, (outDegree.get(edge.source_node_id) ?? 0) + 1)
    inDegree.set(edge.target_node_id, (inDegree.get(edge.target_node_id) ?? 0) + 1)
  }

  const nodes: UnifiedGraphNode[] = [...nodeSeed.values()].map((node) => ({
    id: node.node_id,
    name: node.label,
    category: node.role,
    kind: 'path-node',
    description: `${node.role} · ${node.pathIds.size} 条路径`,
    aliases: [],
    degree: (inDegree.get(node.node_id) ?? 0) + (outDegree.get(node.node_id) ?? 0),
    inDegree: inDegree.get(node.node_id) ?? 0,
    outDegree: outDegree.get(node.node_id) ?? 0,
    attributes: {
      role: node.role,
      path_ids: [...node.pathIds],
    },
    origin: {
      projectId: 'run-path-graph',
      projectLabel: 'Run Path Graph',
      filePath: 'path_graph',
      layer: 'path-subgraph',
      rowNumber: 0,
    },
  }))

  const edges: UnifiedGraphEdge[] = [...edgeSeed.values()].map((edge) => ({
    id: edge.edge_id,
    source: edge.source_node_id,
    target: edge.target_node_id,
    relation: edge.relation,
    category: 'path',
    label: edge.relation,
    confidence: edge.confidence,
    weight: edge.confidence,
    directed: true,
    attributes: {
      target_key: edge.target_key,
      review_status: edge.review_status,
      evidence: edge.evidence,
      source: edge.source,
      path_ids: [...edge.pathIds],
    },
    origin: {
      projectId: 'run-path-graph',
      projectLabel: 'Run Path Graph',
      filePath: 'path_graph',
      layer: 'path-subgraph',
      rowNumber: 0,
    },
  }))

  return {
    id: 'run-path-subgraph',
    label: 'Path Graph 子图',
    description: '当前 case 的 path_graph union subgraph',
    graphKind: 'path-subgraph',
    projectRoot: 'path_graph',
    sourceFiles: [],
    nodes,
    edges,
    metadata: {
      path_count: pathGraph.path_count,
      node_count: pathGraph.node_count,
      edge_count: pathGraph.edge_count,
      subgraph_mode: 'path',
    },
  }
}
