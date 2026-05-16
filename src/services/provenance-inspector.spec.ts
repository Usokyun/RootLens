import { describe, expect, it } from "vitest";

import type {
  KGConstructionBuildDetail,
  KGConstructionBuildValidationResponse,
  KGConstructionReviewQueueEdge,
  RunCaseDetail,
} from "@/api/contracts";
import {
  buildGraphCorrectionProvenance,
  buildGraphEdgeProvenance,
  buildGraphEntityLinkProvenance,
  buildGraphPathProvenance,
  buildMaterialsBuildEdgeProvenance,
  buildMaterialsBuildProvenance,
  type ProvenanceSourceMaterial,
} from "@/services/provenance-inspector";
import type { UnifiedGraphEdge } from "@/types/graph";

const claimBoundary = "candidate/plausible explanation only";

const graphCase: RunCaseDetail = {
  case_id: "tep_0001",
  case_label: "TEP 0001",
  dataset: "tep",
  source: "image",
  generated_evidence: {
    case_id: "tep_0001",
    case_label: "TEP 0001",
    dataset: "tep",
    source: "image",
    timestamp: "2026-05-16T09:00:00Z",
    summary: "demo",
    graph_dataset_id: "tep-kg",
    observations: [
      {
        obs_id: "obs_tep_0001_image_defect_01",
        facet: "image_defect",
        confidence: 0.75,
        linked_entity_hints: ["process", "process_fault", "reactor"],
        raw_evidence_refs: [
          {
            ref_id: "None",
            label: "None",
            role: "evidence",
            file_path: "",
            line: null,
          },
        ],
        object: "process",
        anomaly_type: "process_fault",
        location: "reactor",
        morphology: {},
        severity: 0.6,
      },
    ],
  },
  linked_entities: [
    {
      link_id: "link-entity-1",
      field: "anomaly_type",
      mention: "process_fault",
      selected_entity_id: "component:component_a",
      selected_entity_name: "Component_A (组分 A)",
      score: 0.82,
      match_type: "partial",
      ambiguous: true,
      obs_id: "obs_tep_0001_anomaly_type_process_fault",
    },
  ],
  correction_candidates: [
    {
      candidate_id: "correction-1",
      target_obs_id: "obs_tep_0001_anomaly_type_process_fault",
      original_value: "process_fault",
      suggested_entity_id: "component:component_a",
      suggested_value: "Component_A (组分 A)",
      score: 0.64,
      reason: "process_fault maps weakly to component A",
      supporting_edge_ids: ["edge-1"],
    },
  ],
  top_k_paths: [
    {
      path_id: "path-1",
      target_entity_id: "faultanchor:stream_1_a_feed_loss",
      target_entity_name: "Stream 1 A-feed loss disturbance",
      relations: ["CAUSES"],
      source_edges: [
        {
          edge_id: "edge-1",
          source: "component:component_a",
          target: "faultanchor:stream_1_a_feed_loss",
          relation: "CAUSES",
          confidence: 0.95,
          evidence: "CAUSES supports Stream 1 A-feed loss disturbance",
        },
      ],
      support_obs_ids: ["obs_tep_0001_anomaly_type_process_fault"],
    },
  ],
  source_edge_provenance: [
    {
      edge_id: "edge-1",
      source: "component:component_a",
      target: "faultanchor:stream_1_a_feed_loss",
      relation: "CAUSES",
      confidence: 0.95,
      evidence: "CAUSES supports Stream 1 A-feed loss disturbance",
    },
  ],
  path_graph: {
    paths: [
      {
        path_id: "path-1",
        target_key: "path:path-1",
        target_entity_id: "faultanchor:stream_1_a_feed_loss",
        confidence: 0.95,
        supporting_evidence: ["obs_tep_0001_anomaly_type_process_fault"],
        nodes: [
          {
            node_id: "component:component_a",
            label: "Component_A (组分 A)",
            role: "source",
          },
          {
            node_id: "faultanchor:stream_1_a_feed_loss",
            label: "Stream 1 A-feed loss disturbance",
            role: "target",
          },
        ],
        edges: [
          {
            edge_id: "edge-1",
            target_key: "edge:edge-1",
            source_node_id: "component:component_a",
            target_node_id: "faultanchor:stream_1_a_feed_loss",
            relation: "CAUSES",
            confidence: 0.95,
            evidence: "CAUSES supports Stream 1 A-feed loss disturbance",
          },
        ],
      },
    ],
    path_count: 1,
    node_count: 2,
    edge_count: 1,
  },
  review_targets: [
    {
      target_type: "path",
      target_id: "path-1",
      target_key: "path:path-1",
      label: "Path 1",
    },
    {
      target_type: "entity_link",
      target_id: "link-entity-1",
      target_key: "entity:link-entity-1",
      label: "Entity link",
    },
    {
      target_type: "edge",
      target_id: "edge-1",
      target_key: "edge:edge-1",
      label: "Edge 1",
    },
    {
      target_type: "correction",
      target_id: "correction-1",
      target_key: "correction:1",
      label: "Correction 1",
    },
  ],
  visual_evidence: [
    {
      artifact_id: "visual-1",
      case_id: "tep_0001",
      dataset: "tep",
      kind: "image",
      title: "Observation Preview",
      source_key: "obs:tep_0001:image",
      source_path: "/tmp/observation.png",
      url: "/tmp/observation.png",
      preview_path: "/tmp/observation.png",
      available: true,
      note: "visual evidence preview",
      metadata: {},
    },
  ],
};

const selectedEdge: UnifiedGraphEdge = {
  id: "edge-1",
  source: "faultanchor:stream_1_a_feed_loss",
  target: "component:component_a",
  relation: "CAUSES",
  category: "tep",
  label: "CAUSES",
  confidence: 0.95,
  weight: 0.95,
  directed: true,
  attributes: {
    source: "mock://edge-source",
    evidence: "fault anchor causes component A",
  },
  origin: {
    projectId: "tep-kg",
    projectLabel: "TEP_KG",
    filePath: "/generated/unified-graphs.json",
    layer: "rca-graph",
    rowNumber: 1,
  },
};

const buildDetail: KGConstructionBuildDetail = {
  build: {
    run_id: "build-1",
    status: "completed",
    created_at: "2026-05-16T09:00:00Z",
    output_dir: "mock://build-1",
    nodes_path: "mock://build-1/nodes.json",
    edges_path: "mock://build-1/edges.json",
    summary_path: "mock://build-1/summary.json",
    manifest_path: "mock://build-1/manifest.json",
    source_ids: ["source-a", "source-b"],
    source_count: 2,
    node_count: 12,
    edge_count: 18,
    scenarios: { shared: 18 },
    review_status_counts: { auto: 18 },
    claim_boundary: claimBoundary,
  },
  summary: {
    accepted_edges: 18,
  },
  manifest: {
    sources: ["source-a", "source-b"],
  },
};

const buildValidation: KGConstructionBuildValidationResponse = {
  build: buildDetail.build,
  qa_report: {
    warnings: ["edge confidence below threshold"],
  },
  claim_boundary: claimBoundary,
};

const buildEdge: KGConstructionReviewQueueEdge = {
  target_key: "head|REL|tail|shared",
  head: "head",
  relation: "REL",
  tail: "tail",
  scenario: "shared",
  source: "source-a",
  evidence: "edge extracted from source-a",
  confidence: 0.82,
  weight: 0.82,
  review_status: "auto",
  feedback_count: 0,
  accepted_count: 0,
  rejected_count: 0,
};

const materials: ProvenanceSourceMaterial[] = [
  {
    sourceId: "source-a",
    title: "Source A",
    path: "/tmp/source-a.csv",
    sourceType: "manual_table",
    note: "seeded source material",
  },
  {
    sourceId: "source-b",
    title: "Source B",
    path: "/tmp/source-b.json",
    sourceType: "structured_records",
  },
];

describe("provenance inspector builders", () => {
  it("builds path provenance from support observations, visual evidence, and edge provenance with a TEP projection note", () => {
    const result = buildGraphPathProvenance({
      caseDetail: graphCase,
      pathId: "path-1",
      claimBoundary,
    });

    expect(result?.semanticNotes).toContain(
      "Explanatory projection / FaultAnchor 视图，不等于原始工艺层级或已验证因果方向。",
    );
    expect(result?.records.map((item) => item.sourceType)).toEqual(
      expect.arrayContaining([
        "raw_evidence_ref",
        "visual_evidence",
        "edge_provenance",
      ]),
    );
    expect(result?.linkedReviewTarget).toBe("path:path-1");
  });

  it("builds entity-link provenance and marks ambiguous linking with a semantic note", () => {
    const result = buildGraphEntityLinkProvenance({
      caseDetail: graphCase,
      linkId: "link-entity-1",
      claimBoundary,
    });

    expect(result?.summary).toBe("Component_A (组分 A)");
    expect(result?.semanticNotes).toContain(
      "当前 entity link 仍属弱匹配/歧义匹配，只能作为候选 grounding 线索。",
    );
    expect(result?.records.map((item) => item.sourceType)).toEqual(
      expect.arrayContaining([
        "entity_link",
        "raw_evidence_ref",
        "visual_evidence",
      ]),
    );
  });

  it("builds edge provenance from edge metadata and source-edge provenance with a projected tag", () => {
    const result = buildGraphEdgeProvenance({
      caseDetail: graphCase,
      edge: selectedEdge,
      claimBoundary,
    });

    expect(result?.semanticNotes).toContain(
      "Explanatory projection / FaultAnchor 视图，不等于原始工艺层级或已验证因果方向。",
    );
    expect(result?.records.map((item) => item.sourceType)).toEqual(
      expect.arrayContaining(["edge_metadata", "edge_provenance"]),
    );
    expect(result?.records[0].tags).toContain("projected");
  });

  it("builds correction provenance from correction metadata, supporting edges, and target observation refs", () => {
    const result = buildGraphCorrectionProvenance({
      caseDetail: graphCase,
      correctionId: "correction-1",
      claimBoundary,
    });

    expect(result?.targetKind).toBe("correction");
    expect(result?.records.map((item) => item.sourceType)).toEqual(
      expect.arrayContaining([
        "correction",
        "raw_evidence_ref",
        "visual_evidence",
        "edge_provenance",
      ]),
    );
    expect(result?.linkedReviewTarget).toBe("correction:1");
  });

  it("builds build-level provenance from manifest, summary, qa report, and linked source materials", () => {
    const result = buildMaterialsBuildProvenance({
      buildDetail,
      buildValidation,
      materials,
      claimBoundary,
    });

    expect(result?.semanticNotes).toContain(
      "当前 provenance 主要来自生成产物（manifest / summary / QA / review queue）及其关联 source metadata。",
    );
    expect(result?.records.map((item) => item.sourceType)).toEqual(
      expect.arrayContaining([
        "manifest",
        "summary",
        "qa_report",
        "source_material",
      ]),
    );
  });

  it("builds build-edge provenance from review queue metadata and mapped source materials", () => {
    const result = buildMaterialsBuildEdgeProvenance({
      buildDetail,
      edge: buildEdge,
      materials,
      claimBoundary,
    });

    expect(result?.linkedReviewTarget).toBe("head|REL|tail|shared");
    expect(result?.records.map((item) => item.sourceType)).toEqual([
      "review_queue",
      "source_material",
    ]);
  });
});
