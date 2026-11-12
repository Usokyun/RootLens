import { describe, expect, it } from "vitest";

import type { RunCaseDetail, VisualEvidenceItem } from "@/api/contracts";
import {
  buildObservationBrowseItems,
  collectObservationModalities,
  collectObservationSources,
  filterObservationBrowseItems,
  findObservationBrowseItem,
  selectVisualEvidenceForObservation,
} from "@/services/evidence-observation";

const caseDetail: RunCaseDetail = {
  case_id: "case-1",
  case_label: "Case 1",
  dataset: "mvtec",
  source: "image",
  generated_evidence: {
    case_id: "case-1",
    case_label: "Case 1",
    dataset: "mvtec",
    source: "image",
    timestamp: "2026-05-16T10:00:00Z",
    summary: "test",
    graph_dataset_id: "demo-graph",
    observations: [
      {
        obs_id: "img-1",
        facet: "image_defect",
        confidence: 0.9,
        linked_entity_hints: ["SurfaceWear"],
        raw_evidence_refs: [
          {
            ref_id: "ref-1",
            label: "mask.png",
            role: "mask",
            file_path: "/tmp/mask.png",
            line: null,
          },
        ],
        object: "bottle",
        anomaly_type: "scratch",
        location: "neck",
        severity: 0.8,
      },
      {
        obs_id: "var-1",
        facet: "variable",
        confidence: 0.55,
        linked_entity_hints: ["stream_1"],
        raw_evidence_refs: [],
        variable_name: "feed_flow",
        direction: "increase",
        contribution: 0.6,
        time_window: {
          start: "2026-05-16T09:00:00Z",
          end: "2026-05-16T09:30:00Z",
        },
      },
      {
        obs_id: "log-1",
        facet: "log_event",
        confidence: 0.2,
        linked_entity_hints: [],
        raw_evidence_refs: [],
        event_type: "alarm",
        event_code: "ALM-1",
        equipment: "pump-3",
        message: "pressure high",
      },
    ],
  },
};

const visualEvidence: VisualEvidenceItem[] = [
  {
    artifact_id: "artifact-1",
    case_id: "case-1",
    dataset: "mvtec",
    kind: "image",
    title: "Original",
    source_key: "obs:img-1",
    source_path: "/tmp/image.png",
    url: "/tmp/image.png",
    preview_path: "/tmp/image.png",
    available: true,
    note: "preview",
    metadata: {},
  },
];

describe("evidence observation helpers", () => {
  it("builds observation browse items from generated evidence", () => {
    const items = buildObservationBrowseItems(caseDetail);
    expect(items).toHaveLength(3);
    expect(items[0].modality).toBe("image");
    expect(items[1].modality).toBe("time_series");
    expect(items[2].modality).toBe("log");
    expect(items[1].timeLabel).toContain("2026-05-16T09:00:00Z");
  });

  it("collects distinct modalities and sources", () => {
    const items = buildObservationBrowseItems(caseDetail);
    expect(collectObservationModalities(items)).toEqual([
      "image",
      "time_series",
      "log",
    ]);
    expect(collectObservationSources(items)).toEqual(["image"]);
  });

  it("filters by graph, modality, confidence band, keyword, and time range", () => {
    const items = buildObservationBrowseItems(caseDetail);
    const filtered = filterObservationBrowseItems(items, {
      graph: "demo-graph",
      modality: "time_series",
      source: "image",
      keyword: "feed_flow",
      confidenceBand: "medium",
      timeFrom: "2026-05-16T08:59:00Z",
      timeTo: "2026-05-16T09:05:00Z",
    });

    expect(filtered).toHaveLength(1);
    expect(filtered[0].id).toBe("var-1");
  });

  it("finds a selected observation item by id", () => {
    const items = buildObservationBrowseItems(caseDetail);
    expect(findObservationBrowseItem(items, "log-1")?.title).toContain("ALM-1");
    expect(findObservationBrowseItem(items, "missing")).toBeNull();
  });

  it("returns image previews only for image observations", () => {
    const items = buildObservationBrowseItems(caseDetail);
    expect(
      selectVisualEvidenceForObservation(items[0], visualEvidence),
    ).toHaveLength(1);
    expect(
      selectVisualEvidenceForObservation(items[1], visualEvidence),
    ).toHaveLength(0);
  });
});

describe("visual evidence binding", () => {
  it("never uses another observation or case image as a placeholder", () => {
    const selected = buildObservationBrowseItems(caseDetail)[0]!;
    const asset = visualEvidence[0]!;
    expect(
      selectVisualEvidenceForObservation(selected, [
        { ...asset, source_key: "obs:other" },
      ]),
    ).toEqual([]);
    expect(
      selectVisualEvidenceForObservation(selected, [
        { ...asset, case_id: "other-case" },
      ]),
    ).toEqual([]);
    expect(
      selectVisualEvidenceForObservation(selected, [
        { ...asset, source_key: "", metadata: { scope: "case" } },
      ]),
    ).toHaveLength(1);
  });
  it("drops null-string hints and invalid raw references", () => {
    const input = JSON.parse(JSON.stringify(caseDetail)) as RunCaseDetail;
    const obs = (
      input.generated_evidence!.observations as Record<string, unknown>[]
    )[0]!;
    obs.raw_evidence_refs = [{ ref_id: "None", label: "None", file_path: "" }];
    obs.linked_entity_hints = ["None", "", null, "SurfaceWear"];
    const result = buildObservationBrowseItems(input)[0]!;
    expect(result.rawEvidenceRefs).toEqual([]);
    expect(result.linkedEntityHints).toEqual(["SurfaceWear"]);
  });
});

describe("persisted backend observation presentation", () => {
  it("presents normalized image fields without exposing observation IDs as names", () => {
    const input = {
      ...caseDetail,
      generated_evidence: {
        ...caseDetail.generated_evidence,
        observations: [
          {
            obs_id: "obs_mvtec_noisy_0001_anomaly_type_scratch",
            facet: "anomaly_type",
            name: "scratch",
            confidence: 0.8,
          },
        ],
      },
    } as RunCaseDetail;
    const item = buildObservationBrowseItems(input)[0]!;
    expect(item.modality).toBe("image");
    expect(item.title).toBe("异常类型 / scratch");
    expect(item.title).not.toContain("obs_");
  });
});

describe("legacy process observation presentation", () => {
  it("does not mistake a legacy image_defect facet for an image in a process source", () => {
    const input = {
      ...caseDetail,
      dataset: "tep",
      source: "time_series",
      generated_evidence: {
        ...caseDetail.generated_evidence,
        source: "time_series",
      },
    } as RunCaseDetail;
    const items = buildObservationBrowseItems(input);
    expect(items[0]!.modality).toBe("document");
    expect(items[1]!.modality).toBe("time_series");
    expect(
      selectVisualEvidenceForObservation(items[0], visualEvidence),
    ).toEqual([]);
    expect(
      (input.generated_evidence!.observations as Record<string, unknown>[])[0]!
        .facet,
    ).toBe("image_defect");
  });
});
