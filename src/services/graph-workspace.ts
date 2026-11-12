import type {
  KGStudioGraphNode,
  KGStudioPayload,
  RankedRootCause,
} from "@/api/contracts";
import type {
  UnifiedGraphDataset,
  UnifiedGraphEdge,
  UnifiedGraphNode,
} from "@/types/graph";

export function buildKGStudioDataset(
  payload: KGStudioPayload | null,
  scenario?: string,
): UnifiedGraphDataset | null {
  if (!payload) {
    return null;
  }

  if (scenario) {
    const nodes = payload.graph_nodes.filter(
      (n) => n.scenario === scenario || n.scenario === "shared",
    );
    const ids = new Set(nodes.map((n) => n.node_id));
    payload = {
      ...payload,
      graph_nodes: nodes,
      graph_edges: payload.graph_edges.filter(
        (e) =>
          (e.scenario === scenario || e.scenario === "shared") &&
          ids.has(e.head) &&
          ids.has(e.tail),
      ),
    };
  }
  const nodeSeed = new Map<string, KGStudioGraphNode>();
  for (const node of payload.graph_nodes) {
    nodeSeed.set(node.node_id, node);
  }

  for (const edge of payload.graph_edges) {
    if (!nodeSeed.has(edge.head)) {
      nodeSeed.set(edge.head, {
        node_id: edge.head,
        label: edge.head,
        node_type: "Unknown",
        scenario: edge.scenario,
        description: edge.source,
      });
    }
    if (!nodeSeed.has(edge.tail)) {
      nodeSeed.set(edge.tail, {
        node_id: edge.tail,
        label: edge.tail,
        node_type: "Unknown",
        scenario: edge.scenario,
        description: edge.source,
      });
    }
  }

  const inDegree = new Map<string, number>();
  const outDegree = new Map<string, number>();

  for (const edge of payload.graph_edges) {
    outDegree.set(edge.head, (outDegree.get(edge.head) ?? 0) + 1);
    inDegree.set(edge.tail, (inDegree.get(edge.tail) ?? 0) + 1);
  }

  const nodes: UnifiedGraphNode[] = [...nodeSeed.values()].map((node) => ({
    id: node.node_id,
    name: node.label,
    category: node.scenario,
    kind: node.node_type,
    description: node.description,
    aliases: [],
    degree:
      (inDegree.get(node.node_id) ?? 0) + (outDegree.get(node.node_id) ?? 0),
    inDegree: inDegree.get(node.node_id) ?? 0,
    outDegree: outDegree.get(node.node_id) ?? 0,
    attributes: {
      scenario: node.scenario,
      node_type: node.node_type,
    },
    origin: {
      projectId: "kg-studio",
      projectLabel: "KG Studio",
      filePath: payload.nodes_path ?? "kg-studio",
      layer: "candidate-graph",
      rowNumber: 0,
    },
  }));

  const edges: UnifiedGraphEdge[] = payload.graph_edges.map((edge) => ({
    id: edge.edge_id,
    source: edge.head,
    target: edge.tail,
    relation: edge.relation,
    category: edge.scenario,
    label: edge.relation,
    confidence: edge.confidence,
    weight: edge.weight,
    directed: true,
    attributes: {
      source: edge.source,
      evidence: edge.evidence,
      review_status: edge.review_status,
      target_key: edge.edge_id,
    },
    origin: {
      projectId: "kg-studio",
      projectLabel: "KG Studio",
      filePath: payload.edges_path ?? "kg-studio",
      layer: "candidate-graph",
      rowNumber: 0,
    },
  }));

  return {
    id: `runtime-${scenario ?? "all"}`,
    label: "总图谱",
    description: payload.note,
    graphKind: "candidate-graph",
    projectRoot: payload.candidate_dir ?? "kg-studio",
    sourceFiles: [],
    nodes,
    edges,
    metadata: {
      scenario: scenario ?? "shared",
      full_edge_count: scenario
        ? (payload.scenario_counts?.[scenario] ?? payload.graph_edges.length) +
          (payload.scenario_counts?.shared ?? 0)
        : payload.edge_count,
      preview_edge_count: payload.graph_edges.length,
      status: payload.status,
      claim_boundary: payload.claim_boundary,
    },
  };
}

/** A missing explanation is preferable to displaying another hypothesis's path. */
export function candidateExplanationPaths(
  candidate: import("@/api/contracts").RankedRootCause | null,
  graph: import("@/api/contracts").PathGraph | null | undefined,
) {
  if (!candidate || !graph) return [];
  const referenced = (candidate.explanation_paths ?? [])
    .map((p) =>
      typeof p === "string"
        ? p
        : p && typeof p === "object"
          ? String((p as Record<string, unknown>).path_id ?? "")
          : "",
    )
    .filter(Boolean);
  return graph.paths.filter(
    (p) =>
      p.target_entity_id === candidate.candidate_id ||
      p.path_id === candidate.ranking_id.replace(/^ranking:/, "") ||
      referenced.includes(p.path_id) ||
      p.nodes.at(-1)?.node_id === candidate.candidate_id,
  );
}

export function matchKnowledgeEdges(
  edge: import("@/api/contracts").PathGraphEdge,
  dataset: UnifiedGraphDataset | null,
) {
  if (!dataset) return [];
  return dataset.edges.filter(
    (e) =>
      e.id === edge.edge_id ||
      (e.source === edge.source_node_id &&
        e.target === edge.target_node_id &&
        e.relation === edge.relation),
  );
}

/** One candidate may have several ranked paths; keep its best existing rank, not a new score. */
export function uniqueRootCauseCandidates(
  items: RankedRootCause[],
): RankedRootCause[] {
  const ranked = [...items].sort((a, b) => a.rank - b.rank);
  const unique = new Map<string, RankedRootCause>();
  for (const item of ranked) {
    if (!unique.has(item.candidate_id)) unique.set(item.candidate_id, item);
  }
  return [...unique.values()];
}
