import { describe, expect, it } from "vitest";
import type {
  KGStudioPayload,
  PathGraph,
  PathGraphPath,
  RankedRootCause,
  RunCaseDetail,
} from "@/api/contracts";
import type { UnifiedGraphDataset } from "@/types/graph";
import {
  buildKGStudioDataset,
  candidateExplanationPaths,
  matchKnowledgeEdges,
  uniqueRootCauseCandidates,
} from "./graph-workspace";
import { buildWorkspaceProvenance } from "./workspace-provenance";

const path: PathGraphPath = {
  path_id: "path-contact",
  target_key: "path:contact",
  source_entity_id: "Scratch",
  target_entity_id: "Contact",
  nodes: [
    { node_id: "Scratch", label: "Scratch", role: "source" },
    { node_id: "Contact", label: "Contact", role: "target" },
  ],
  edges: [
    {
      edge_id: "runtime-edge",
      target_key: "edge:runtime",
      source_node_id: "Scratch",
      target_node_id: "Contact",
      relation: "HAS_PLAUSIBLE_CAUSE",
      source: "Scratch",
      evidence: "generated summary",
      confidence: 0.75,
    },
  ],
  supporting_evidence: [],
};
const payload = {
  graph_nodes: [
    {
      node_id: "Scratch",
      label: "Scratch",
      node_type: "Defect",
      scenario: "mvtec",
      description: "",
    },
    {
      node_id: "Contact",
      label: "Contact",
      node_type: "Cause",
      scenario: "mvtec",
      description: "",
    },
    {
      node_id: "Pump",
      label: "Pump",
      node_type: "Equipment",
      scenario: "tep",
      description: "",
    },
  ],
  graph_edges: [
    {
      edge_id: "canonical-edge",
      head: "Scratch",
      tail: "Contact",
      relation: "HAS_PLAUSIBLE_CAUSE",
      scenario: "mvtec",
      confidence: 0.75,
      weight: 0.25,
      source: "manual_curation",
      evidence: "Linear surface defect consistent with contact damage",
      review_status: "unreviewed",
    },
  ],
} as KGStudioPayload;
const graph: PathGraph = {
  paths: [
    path,
    { ...path, path_id: "other-path", target_entity_id: "Wear", nodes: [] },
  ],
  path_count: 2,
  node_count: 2,
  edge_count: 1,
};
const candidate = {
  ranking_id: "rank-contact",
  rank: 1,
  candidate_id: "Contact",
  candidate_name: "Contact",
} as RankedRootCause;

describe("reasoning workspace contracts", () => {
  it("never falls back to another hypothesis explanation", () => {
    expect(
      candidateExplanationPaths(candidate, graph).map((p) => p.path_id),
    ).toEqual(["path-contact"]);
    expect(
      candidateExplanationPaths(
        { ...candidate, candidate_id: "Absent" },
        graph,
      ),
    ).toEqual([]);
    expect(
      candidateExplanationPaths(
        {
          ...candidate,
          candidate_id: "Absent",
          explanation_paths: [{ path_id: "other-path" }],
        },
        graph,
      ).map((p) => p.path_id),
    ).toEqual(["other-path"]);
    expect(candidateExplanationPaths(null, graph)).toEqual([]);
  });
  it("scopes canonical nodes and edges by scenario without altering the source", () => {
    const result = buildKGStudioDataset(payload, "mvtec")!;
    expect(result.nodes.map((n) => n.id)).toEqual(["Scratch", "Contact"]);
    expect(result.metadata.scenario).toBe("mvtec");
    expect(result.edges[0]!.attributes.source).toBe("manual_curation");
    expect(payload.graph_nodes).toHaveLength(3);
    expect(buildKGStudioDataset(null)).toBeNull();
  });
  it("matches exact directed relation triples, never just an endpoint or reverse", () => {
    const dataset = buildKGStudioDataset(payload, "mvtec")!;
    expect(
      matchKnowledgeEdges(path.edges[0]!, dataset).map((e) => e.id),
    ).toEqual(["canonical-edge"]);
    expect(
      matchKnowledgeEdges(
        {
          ...path.edges[0]!,
          source_node_id: "Contact",
          target_node_id: "Scratch",
        },
        dataset,
      ),
    ).toEqual([]);
    expect(
      matchKnowledgeEdges({ ...path.edges[0]!, relation: "CAUSES" }, dataset),
    ).toEqual([]);
  });
  it("resolves a knowledge source rather than displaying the path source node as provenance", () => {
    const c = {
      case_id: "case",
      dataset: "mvtec",
      case_label: "Bottle",
      path_graph: graph,
      top_k_paths: [],
      review_targets: [],
      source_edge_provenance: [],
    } as unknown as RunCaseDetail;
    const result = buildWorkspaceProvenance(
      c,
      path,
      buildKGStudioDataset(payload, "mvtec"),
    )!;
    const knowledge = result.records.filter(
      (r) => r.sourceType === "edge_provenance",
    );
    expect(knowledge).toHaveLength(1);
    expect(knowledge[0]).toMatchObject({
      sourcePathOrId: "manual_curation",
      snippetOrPreview: "Linear surface defect consistent with contact damage",
    });
    expect(knowledge[0]!.sourcePathOrId).not.toBe("Scratch");
    const missing = buildWorkspaceProvenance(c, path, {
      nodes: [],
      edges: [],
    } as unknown as UnifiedGraphDataset)!;
    expect(missing.records.some((r) => r.tags.includes("missing-source"))).toBe(
      true,
    );
    expect(buildWorkspaceProvenance(null, path, null)).toBeNull();
  });
});

describe("candidate presentation", () => {
  it("groups repeated path rankings without recomputing scores or losing explanation paths", () => {
    const entries = [
      { candidate_id: "root", ranking_id: "path-low", rank: 3, score: 0.4 },
      { candidate_id: "other", ranking_id: "other-path", rank: 2, score: 0.5 },
      { candidate_id: "root", ranking_id: "path-high", rank: 1, score: 0.6 },
    ] as RankedRootCause[];
    const result = uniqueRootCauseCandidates(entries);
    expect(result.map((c) => c.candidate_id)).toEqual(["root", "other"]);
    expect(result[0]).toBe(entries[2]);
    expect(entries[0]!.rank).toBe(3);
    const paths = {
      paths: [
        { path_id: "path-low", target_entity_id: "root", nodes: [] },
        { path_id: "path-high", target_entity_id: "root", nodes: [] },
      ],
    } as unknown as PathGraph;
    expect(candidateExplanationPaths(result[0]!, paths)).toHaveLength(2);
  });
});
