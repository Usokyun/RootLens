import { describe, expect, it } from "vitest";

import type { RunCaseDetail, RunDetail } from "@/api/contracts";
import {
  buildGraphReasoningInspection,
  buildPathSignature,
} from "@/services/graph-reasoning-inspection";

function createImageCase(input: {
  caseId: string;
  caseLabel: string;
  anomalyType: string;
  targetEntityId: string;
  targetEntityName: string;
  relationSequence: string[];
}) {
  const actualObservationId = `obs_${input.caseId}_image_defect_01`;
  const anomalyObservationId = `obs_${input.caseId}_anomaly_type_${input.anomalyType}`;
  const locationObservationId = `obs_${input.caseId}_location_surface`;
  const defectEntityId = `${input.anomalyType[0].toUpperCase()}${input.anomalyType.slice(1)}Defect`;
  const defectEntityName = `${input.anomalyType} defect`;

  const caseDetail: RunCaseDetail = {
    case_id: input.caseId,
    case_label: input.caseLabel,
    dataset: "mvtec",
    source: "image",
    generated_evidence: {
      case_id: input.caseId,
      case_label: input.caseLabel,
      dataset: "mvtec",
      source: "image",
      timestamp: "2026-05-16T09:00:00Z",
      summary: `${input.caseLabel} summary`,
      graph_dataset_id: "mvtec-project",
      observations: [
        {
          obs_id: actualObservationId,
          facet: "image_defect",
          confidence: 0.91,
          linked_entity_hints: ["bottle", input.anomalyType, "surface"],
          raw_evidence_refs: [],
          object: "bottle",
          anomaly_type: input.anomalyType,
          location: "surface",
          morphology: {
            canonical: "linear",
          },
          severity: 0.3,
        },
      ],
    },
    linked_entities: [
      {
        link_id: `link_${input.caseId}_anomaly`,
        field: "anomaly_type",
        mention: input.anomalyType,
        selected_entity_id: defectEntityId,
        selected_entity_name: defectEntityName,
        score: 0.96,
        obs_id: anomalyObservationId,
      },
      {
        link_id: `link_${input.caseId}_location`,
        field: "location",
        mention: "surface",
        selected_entity_id: "SurfaceLocation",
        selected_entity_name: "Surface location",
        score: 0.88,
        obs_id: locationObservationId,
      },
    ],
    top_k_paths: [
      {
        path_id: `path-${input.caseId}-1`,
        target_entity_id: input.targetEntityId,
        target_entity_name: input.targetEntityName,
        score: 0.82,
        confidence: 0.77,
        nodes: [defectEntityId, input.targetEntityId],
        node_names: [defectEntityName, input.targetEntityName],
        relations: input.relationSequence,
        source_edges: [
          {
            edge_id: `edge-${input.caseId}-1`,
            source: defectEntityId,
            target: input.targetEntityId,
            relation: input.relationSequence[0],
            confidence: 0.77,
          },
        ],
        support_obs_ids: [anomalyObservationId, locationObservationId],
      },
    ],
    ranked_root_causes: [
      {
        ranking_id: `ranking:path-${input.caseId}-1`,
        rank: 1,
        candidate_id: input.targetEntityId,
        candidate_name: input.targetEntityName,
        candidate_role: "plausible_mechanism",
        score: 0.82,
        scoring_method: "artifact_bridge",
      },
    ],
    path_graph: {
      paths: [
        {
          path_id: `path-${input.caseId}-1`,
          target_key: `path:${input.caseId}:1`,
          target_entity_id: input.targetEntityId,
          confidence: 0.77,
          score: 0.82,
          supporting_evidence: [anomalyObservationId, locationObservationId],
          nodes: [
            {
              node_id: defectEntityId,
              label: defectEntityName,
              role: "source",
            },
            {
              node_id: input.targetEntityId,
              label: input.targetEntityName,
              role: "target",
            },
          ],
          edges: [
            {
              edge_id: `edge-${input.caseId}-1`,
              target_key: `edge:${input.caseId}:1`,
              source_node_id: defectEntityId,
              target_node_id: input.targetEntityId,
              relation: input.relationSequence[0],
              confidence: 0.77,
            },
          ],
        },
      ],
      path_count: 1,
      node_count: 2,
      edge_count: 1,
    },
  };

  return {
    actualObservationId,
    anomalyObservationId,
    locationObservationId,
    caseDetail,
  };
}

const caseA = createImageCase({
  caseId: "case_a",
  caseLabel: "Case A",
  anomalyType: "scratch",
  targetEntityId: "MechanicalContact",
  targetEntityName: "Mechanical contact",
  relationSequence: ["HAS_PLAUSIBLE_CAUSE"],
});

const caseB = createImageCase({
  caseId: "case_b",
  caseLabel: "Case B",
  anomalyType: "scratch",
  targetEntityId: "MechanicalContact",
  targetEntityName: "Mechanical contact",
  relationSequence: ["HAS_PLAUSIBLE_CAUSE"],
});

const caseC = createImageCase({
  caseId: "case_c",
  caseLabel: "Case C",
  anomalyType: "dent",
  targetEntityId: "HandlingDamage",
  targetEntityName: "Handling damage",
  relationSequence: ["PART_OF"],
});

const runDetail: RunDetail = {
  run: {
    run_id: "run-1",
    created_at: "2026-05-16T09:00:00Z",
    mode: "evidence",
    source_filename: "demo.json",
    top_k: 5,
    run_dir: "mock://run-1",
    status: "completed",
    dataset: "mvtec",
    case_count: 3,
    evidence_count: 3,
    label: "Run 1",
    model_preset: null,
    model_backend: null,
  },
  workflow_steps: [],
  claim_boundary: "candidate only",
  evidence: null,
  evidence_summary: null,
  evidence_with_analysis: null,
  analysis: null,
  summary: null,
  cases: [caseA.caseDetail, caseB.caseDetail, caseC.caseDetail],
  linked_entities: [],
  correction_candidates: [],
  top_k_paths: [],
  ranked_root_causes: [],
  path_graph: {
    paths: [],
    path_count: 0,
    node_count: 0,
    edge_count: 0,
  },
  source_edge_provenance: [],
  review_targets: [],
  artifacts: {},
  visual_evidence: [],
};

describe("graph reasoning inspection helpers", () => {
  it("chooses the primary observation from candidate support observations before the shared selected observation", () => {
    const inspection = buildGraphReasoningInspection({
      runDetail,
      caseDetail: caseA.caseDetail,
      selectedCandidateId: "ranking:path-case_a-1",
      selectedObservationId: caseA.actualObservationId,
      selectedPathId: "path-case_a-1",
    });

    expect(inspection.primaryObservation?.obsId).toBe(
      caseA.anomalyObservationId,
    );
    expect(inspection.primaryObservation?.sharedObservationId).toBe(
      caseA.actualObservationId,
    );
  });

  it("keeps supporting observation order stable when a path references multiple observations", () => {
    const inspection = buildGraphReasoningInspection({
      runDetail,
      caseDetail: caseA.caseDetail,
      selectedCandidateId: "ranking:path-case_a-1",
      selectedObservationId: null,
      selectedPathId: "path-case_a-1",
    });

    expect(inspection.supportingObservations.map((item) => item.obsId)).toEqual(
      [caseA.anomalyObservationId, caseA.locationObservationId],
    );
  });

  it("groups linked entities by support observation and keeps derived observation titles", () => {
    const inspection = buildGraphReasoningInspection({
      runDetail,
      caseDetail: caseA.caseDetail,
      selectedCandidateId: "ranking:path-case_a-1",
      selectedObservationId: null,
      selectedPathId: "path-case_a-1",
    });

    expect(inspection.supportingObservations[0]).toMatchObject({
      obsId: caseA.anomalyObservationId,
      linkedEntityCount: 1,
      title: "anomaly type / scratch",
    });
    expect(inspection.supportingObservations[1]).toMatchObject({
      obsId: caseA.locationObservationId,
      linkedEntityCount: 1,
      title: "location / surface",
    });
    expect(inspection.linkedEntities.map((item) => item.entityName)).toEqual([
      "scratch defect",
      "Surface location",
    ]);
  });

  it("derives recurring entities and paths across cases in the same run", () => {
    const inspection = buildGraphReasoningInspection({
      runDetail,
      caseDetail: caseA.caseDetail,
      selectedCandidateId: "ranking:path-case_a-1",
      selectedObservationId: null,
      selectedPathId: "path-case_a-1",
    });

    expect(inspection.crossCaseRecurrence?.recurringEntities).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          entityId: "ScratchDefect",
          occurrenceCount: 1,
          caseHits: [
            expect.objectContaining({
              caseId: "case_b",
            }),
          ],
        }),
      ]),
    );
    expect(inspection.crossCaseRecurrence?.recurringPaths).toEqual([
      expect.objectContaining({
        signature: "MechanicalContact::HAS_PLAUSIBLE_CAUSE",
        occurrenceCount: 1,
        caseHits: [
          expect.objectContaining({
            caseId: "case_b",
            matchedPathIds: ["path-case_b-1"],
          }),
        ],
      }),
    ]);
  });

  it("builds a stable path signature from target entity and relation sequence", () => {
    expect(
      buildPathSignature({
        targetEntityId: "MechanicalContact",
        relationSequence: ["HAS_PLAUSIBLE_CAUSE", "PART_OF"],
      }),
    ).toBe("MechanicalContact::HAS_PLAUSIBLE_CAUSE>PART_OF");
  });
});
