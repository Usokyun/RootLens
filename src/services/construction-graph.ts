import type { KGConstructionGraphPayload } from '@/api/contracts'
import type { UnifiedGraphDataset } from '@/types/graph'

export function constructionGraphLocation(buildId: string) {
  return { name: 'graphs', query: { build_id: buildId } }
}

/** Adapt a backend snapshot for display only; never assemble evidence or RCA results. */
export function buildConstructionGraphDataset(payload: KGConstructionGraphPayload): UnifiedGraphDataset {
  const inDegree = new Map<string, number>()
  const outDegree = new Map<string, number>()
  for (const edge of payload.graph_edges) {
    inDegree.set(edge.tail, (inDegree.get(edge.tail) ?? 0) + 1)
    outDegree.set(edge.head, (outDegree.get(edge.head) ?? 0) + 1)
  }
  const origin = (filePath: string) => ({
    projectId: payload.build_id, projectLabel: payload.title,
    filePath, layer: 'candidate-graph', rowNumber: 0,
  })
  return {
    id: `construction:${payload.build_id}`, label: payload.title,
    description: payload.note, graphKind: 'candidate-graph',
    projectRoot: payload.candidate_dir ?? '',
    sourceFiles: [
      { path: payload.nodes_path ?? '', role: 'nodes', layer: 'candidate-graph', rowCount: payload.node_count, fields: [] },
      { path: payload.edges_path ?? '', role: 'edges', layer: 'candidate-graph', rowCount: payload.edge_count, fields: [] },
    ],
    nodes: payload.graph_nodes.map((node) => ({
      id: node.node_id, name: node.label, category: node.scenario,
      kind: node.node_type, description: node.description, aliases: [],
      degree: (inDegree.get(node.node_id) ?? 0) + (outDegree.get(node.node_id) ?? 0),
      inDegree: inDegree.get(node.node_id) ?? 0, outDegree: outDegree.get(node.node_id) ?? 0,
      attributes: { scenario: node.scenario, node_type: node.node_type },
      origin: origin(payload.nodes_path ?? ''),
    })),
    edges: payload.graph_edges.map((edge) => ({
      id: edge.edge_id, source: edge.head, target: edge.tail, relation: edge.relation,
      category: edge.scenario, label: edge.relation, confidence: edge.confidence,
      weight: edge.weight, directed: true,
      attributes: {
        source: edge.source, evidence: edge.evidence, review_status: edge.review_status,
        target_key: edge.target_key, build_id: payload.build_id,
      },
      origin: origin(payload.edges_path ?? ''),
    })),
    metadata: { build_id: payload.build_id, read_only: true, claim_boundary: payload.claim_boundary },
  }
}
