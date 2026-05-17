import { describe, expect, it } from "vitest";

import type { ReviewLedgerRecord, RunCaseDetail } from "@/api/contracts";
import {
  buildReviewLedgerDisplayItems,
  filterReviewLedgerRecords,
  formatReviewLedgerAction,
  formatReviewLedgerTargetType,
  isBoundedReviewTargetType,
} from "@/services/review-ledger";

const records: ReviewLedgerRecord[] = [
  {
    feedback_id: "feedback-edge-1",
    created_at: "2026-05-16T10:05:00.000Z",
    run_id: "run-1",
    case_id: "case-1",
    target_type: "edge",
    target_id: "edge-1",
    target_key: "edge:edge-1",
    action: "reject",
    note: "edge is too weak",
    reviewer: "analyst-a",
    source: "rootlens-graphs",
    metadata: null,
  },
  {
    feedback_id: "feedback-path-1",
    created_at: "2026-05-16T10:10:00.000Z",
    run_id: "run-1",
    case_id: "case-1",
    target_type: "path",
    target_id: "path-1",
    target_key: "path:path-1",
    action: "accept",
    note: "path is plausible",
    reviewer: "analyst-b",
    source: "rootlens-graphs",
    metadata: null,
  },
  {
    feedback_id: "feedback-link-1",
    created_at: "2026-05-16T10:08:00.000Z",
    run_id: "run-1",
    case_id: "case-1",
    target_type: "entity_link",
    target_id: "link-1",
    target_key: "entity:link-1",
    action: "reject",
    note: null,
    reviewer: "analyst-c",
    source: "rootlens-graphs",
    metadata: null,
  },
  {
    feedback_id: "feedback-correction-1",
    created_at: "2026-05-16T10:12:00.000Z",
    run_id: "run-1",
    case_id: "case-1",
    target_type: "correction",
    target_id: "correction-1",
    target_key: "correction:1",
    action: "accept",
    note: "apply the correction",
    reviewer: "analyst-d",
    source: "rootlens-graphs",
    metadata: null,
  },
  {
    feedback_id: "feedback-candidate-1",
    created_at: "2026-05-16T10:20:00.000Z",
    run_id: "run-1",
    case_id: "case-1",
    target_type: "root_cause_candidate",
    target_id: "candidate-1",
    target_key: null,
    action: "accept",
    note: "lightweight candidate review",
    reviewer: "analyst-e",
    source: "rootlens-graphs",
    metadata: null,
  },
];

const caseDetail: RunCaseDetail = {
  case_id: "case-1",
  case_label: "Case 1",
  dataset: "mvtec",
  source: "image",
  top_k_paths: [
    {
      path_id: "path-1",
      target_entity_name: "Mechanical contact",
      relations: ["HAS_PLAUSIBLE_CAUSE"],
    },
  ],
  source_edge_provenance: [
    {
      edge_id: "edge-1",
      source: "ScratchDefect",
      target: "MechanicalContact",
      relation: "HAS_PLAUSIBLE_CAUSE",
      evidence: "edge evidence",
    },
  ],
  linked_entities: [
    {
      link_id: "link-1",
      field: "anomaly_type",
      mention: "scratch",
      selected_entity_id: "ScratchDefect",
      selected_entity_name: "Scratch defect",
    },
  ],
  correction_candidates: [
    {
      candidate_id: "correction-1",
      suggested_value: "Linear morphology",
      reason: "ScratchDefect HAS_MORPHOLOGY LinearMorphology",
    },
  ],
  ranked_root_causes: [
    {
      ranking_id: "candidate-1",
      rank: 1,
      candidate_id: "MechanicalContact",
      candidate_name: "Mechanical contact",
      scoring_method: "relation_weighted_path",
    },
  ],
  path_graph: {
    paths: [
      {
        path_id: "path-1",
        target_key: "path:path-1",
        nodes: [
          {
            node_id: "ScratchDefect",
            label: "Scratch defect",
            role: "source",
          },
          {
            node_id: "MechanicalContact",
            label: "Mechanical contact",
            role: "target",
          },
        ],
        edges: [
          {
            edge_id: "edge-1",
            target_key: "edge:edge-1",
            source_node_id: "ScratchDefect",
            target_node_id: "MechanicalContact",
            relation: "HAS_PLAUSIBLE_CAUSE",
          },
        ],
        supporting_evidence: [],
      },
    ],
    path_count: 1,
    node_count: 2,
    edge_count: 1,
  },
};

describe("review ledger helpers", () => {
  it("recognizes bounded review target types and formats labels", () => {
    expect(isBoundedReviewTargetType("path")).toBe(true);
    expect(isBoundedReviewTargetType("entity_link")).toBe(true);
    expect(isBoundedReviewTargetType("root_cause_candidate")).toBe(true);
    expect(formatReviewLedgerTargetType("correction")).toBe("Correction");
    expect(formatReviewLedgerTargetType("root_cause_candidate")).toBe("Candidate");
    expect(formatReviewLedgerAction("accept")).toBe("接受");
  });

  it("filters to bounded targets and sorts by created_at descending", () => {
    const filtered = filterReviewLedgerRecords(records, "all");
    expect(filtered.map((item) => item.feedback_id)).toEqual([
      "feedback-candidate-1",
      "feedback-correction-1",
      "feedback-path-1",
      "feedback-link-1",
      "feedback-edge-1",
    ]);
  });

  it("filters by target type within bounded ledger targets", () => {
    const filtered = filterReviewLedgerRecords(records, "edge");
    expect(filtered).toHaveLength(1);
    expect(filtered[0].target_type).toBe("edge");
  });

  it("builds display items with resolved path, edge, entity link, and correction summaries", () => {
    const displayItems = buildReviewLedgerDisplayItems(
      filterReviewLedgerRecords(records, "all"),
      caseDetail,
    );

    expect(displayItems[0]).toMatchObject({
      target_type: "root_cause_candidate",
      title: "Mechanical contact",
      subtitle: "relation_weighted_path",
      targetAvailable: true,
    });
    expect(displayItems[1]).toMatchObject({
      target_type: "correction",
      title: "Linear morphology",
      subtitle: "ScratchDefect HAS_MORPHOLOGY LinearMorphology",
      targetAvailable: true,
    });
    expect(displayItems[2]).toMatchObject({
      target_type: "path",
      title: "Mechanical contact",
      subtitle: "HAS_PLAUSIBLE_CAUSE",
      targetAvailable: true,
    });
    expect(displayItems[3]).toMatchObject({
      target_type: "entity_link",
      title: "Scratch defect",
      subtitle: "anomaly_type · scratch",
      targetAvailable: true,
    });
    expect(displayItems[4]).toMatchObject({
      target_type: "edge",
      title: "ScratchDefect —HAS_PLAUSIBLE_CAUSE→ MechanicalContact",
      targetAvailable: true,
    });
  });

  it("marks missing targets as unavailable", () => {
    const missing = buildReviewLedgerDisplayItems(
      [
        {
          ...records[0],
          feedback_id: "missing-edge",
          target_id: "edge-missing",
        },
      ],
      caseDetail,
    );

    expect(missing[0]).toMatchObject({
      title: "edge-missing",
      targetAvailable: false,
    });
  });
});
