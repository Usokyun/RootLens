import type {
  KGConstructionBuildDetail,
  KGConstructionBuildValidationResponse,
  KGConstructionReviewQueueEdge,
  RunCaseDetail,
  VisualEvidenceItem,
} from "@/api/contracts";
import {
  buildObservationBrowseItems,
  findObservationBrowseItem,
  type ObservationBrowseItem,
} from "@/services/evidence-observation";
import type { JsonValue, UnifiedGraphEdge } from "@/types/graph";

export type ProvenanceTargetKind =
  | "path"
  | "edge"
  | "entity_link"
  | "correction"
  | "build"
  | "build_edge";
export type ProvenanceSourceType =
  | "raw_evidence_ref"
  | "visual_evidence"
  | "edge_provenance"
  | "entity_link"
  | "correction"
  | "edge_metadata"
  | "manifest"
  | "summary"
  | "qa_report"
  | "review_queue"
  | "source_material";

export interface ProvenanceRecord {
  recordId: string;
  sourceType: ProvenanceSourceType;
  sourceLabel: string;
  sourcePathOrId: string;
  snippetOrPreview: string | null;
  previewUrl: string | null;
  confidence: number | null;
  claimBoundary: string;
  reviewTargetKey: string | null;
  tags: string[];
  multiline: boolean;
}

export interface ProvenanceInspectorState {
  targetKind: ProvenanceTargetKind;
  targetId: string;
  summary: string;
  contextLabel: string;
  linkedReviewTarget: string | null;
  claimBoundary: string;
  records: ProvenanceRecord[];
  semanticNotes: string[];
}

export interface GraphProvenanceEdgeRef {
  id: string;
  source: string;
  target: string;
  relation: string;
  confidence: number | null;
  origin?: UnifiedGraphEdge["origin"];
  attributes?: Record<string, JsonValue>;
}

export interface ProvenanceSourceMaterial {
  sourceId: string;
  title: string;
  path: string | null;
  sourceType: string | null;
  note?: string | null;
}

const OBSERVATION_FIELD_ORDER = [
  "anomaly_type",
  "morphology",
  "location",
  "object",
  "variable",
  "log_event",
];
const TEP_PROJECTION_NOTE =
  "Explanatory projection / FaultAnchor 视图，不等于原始工艺层级或已验证因果方向。";
const AMBIGUOUS_LINK_NOTE =
  "当前 entity link 仍属弱匹配/歧义匹配，只能作为候选 grounding 线索。";
const GENERATED_BUILD_NOTE =
  "当前 provenance 主要来自生成产物（manifest / summary / QA / review queue）及其关联 source metadata。";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeText(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.trim().length
    ? value.trim()
    : fallback;
}

function normalizeNullableText(value: unknown): string | null {
  return typeof value === "string" && value.trim().length ? value.trim() : null;
}

function normalizeNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function normalizeComparable(value: unknown): string {
  return normalizeText(value)
    .toLowerCase()
    .replace(/[_-]+/g, " ")
    .replace(/[^a-z0-9\s]+/gi, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function uniqueStable<T>(items: T[], getKey: (item: T) => string): T[] {
  const seen = new Set<string>();
  const result: T[] = [];

  for (const item of items) {
    const key = getKey(item);
    if (!key || seen.has(key)) {
      continue;
    }

    seen.add(key);
    result.push(item);
  }

  return result;
}

function truncateMultiline(text: string, maxLength = 1200) {
  if (text.length <= maxLength) {
    return text;
  }

  return `${text.slice(0, maxLength)}\n…`;
}

function formatJsonSnippet(value: unknown) {
  return truncateMultiline(JSON.stringify(value ?? {}, null, 2));
}

function readStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.map((item) => normalizeText(item)).filter(Boolean);
}

function readStringValue(
  attributes: Record<string, unknown> | undefined,
  key: string,
) {
  if (!attributes) {
    return null;
  }

  return normalizeNullableText(attributes[key]);
}

function collectMorphologyValues(rawObservation: Record<string, unknown>) {
  const morphology = rawObservation.morphology;
  if (typeof morphology === "string" && morphology.trim().length) {
    return [morphology];
  }

  if (!isRecord(morphology)) {
    return [];
  }

  return Object.values(morphology).filter(
    (value): value is string =>
      typeof value === "string" && value.trim().length > 0,
  );
}

function doesObservationMatchFieldMention(
  observation: ObservationBrowseItem,
  field: string | null,
  mention: string | null,
) {
  if (!field || !mention) {
    return false;
  }

  const normalizedMention = normalizeComparable(mention);
  if (!normalizedMention) {
    return false;
  }

  const raw = observation.rawObservation;
  switch (field) {
    case "object":
      return normalizeComparable(raw.object) === normalizedMention;
    case "anomaly_type":
      return normalizeComparable(raw.anomaly_type) === normalizedMention;
    case "location":
      return normalizeComparable(raw.location) === normalizedMention;
    case "morphology":
      return collectMorphologyValues(raw).some(
        (value) => normalizeComparable(value) === normalizedMention,
      );
    case "variable":
      return normalizeComparable(raw.variable_name) === normalizedMention;
    case "log_event":
      return [raw.event_code, raw.event_type, raw.message, raw.equipment].some(
        (value) => normalizeComparable(value) === normalizedMention,
      );
    default:
      return observation.linkedEntityHints.some(
        (item) => normalizeComparable(item) === normalizedMention,
      );
  }
}

function parseObservationIdTail(obsId: string) {
  for (const field of OBSERVATION_FIELD_ORDER) {
    const marker = `_${field}_`;
    const index = obsId.lastIndexOf(marker);
    if (index < 0) {
      continue;
    }

    const mention = obsId.slice(index + marker.length);
    if (!mention) {
      continue;
    }

    return {
      field,
      mention,
    };
  }

  return null;
}

function findParentObservationForField(
  observations: ObservationBrowseItem[],
  field: string | null,
  mention: string | null,
) {
  if (!field || !mention) {
    return null;
  }

  return (
    observations.find((item) =>
      doesObservationMatchFieldMention(item, field, mention),
    ) ?? null
  );
}

export function resolveObservationForSelection(
  caseDetail: RunCaseDetail,
  selectionId: string | null | undefined,
) {
  if (!selectionId) {
    return null;
  }

  const observations = buildObservationBrowseItems(caseDetail);
  const direct = findObservationBrowseItem(observations, selectionId);
  if (direct) {
    return direct;
  }

  const parsedTail = parseObservationIdTail(selectionId);
  if (!parsedTail) {
    return null;
  }

  return findParentObservationForField(
    observations,
    parsedTail.field,
    parsedTail.mention,
  );
}

function buildRawRefRecord(input: {
  recordId: string;
  claimBoundary: string;
  reviewTargetKey: string | null;
  observationId: string;
  rawRef: ObservationBrowseItem["rawEvidenceRefs"][number];
}): ProvenanceRecord {
  const label = normalizeText(input.rawRef.label);
  const path = normalizeText(input.rawRef.filePath);
  const isPlaceholder =
    (!path && (label === "None" || !label)) || input.rawRef.refId === "None";

  return {
    recordId: input.recordId,
    sourceType: "raw_evidence_ref",
    sourceLabel: isPlaceholder
      ? "Runtime evidence placeholder"
      : label || "Raw evidence ref",
    sourcePathOrId: path || input.rawRef.refId || input.observationId,
    snippetOrPreview: isPlaceholder
      ? `Observation ${input.observationId} 当前没有可回跳的外部文件，只保留 runtime 占位 evidence ref。`
      : `role=${input.rawRef.role}${input.rawRef.line !== null ? ` · line ${input.rawRef.line}` : ""}`,
    previewUrl: null,
    confidence: null,
    claimBoundary: input.claimBoundary,
    reviewTargetKey: input.reviewTargetKey,
    tags: ["source-grounded"],
    multiline: false,
  };
}

function buildVisualEvidenceRecords(input: {
  visualEvidence: VisualEvidenceItem[] | null | undefined;
  observation: ObservationBrowseItem | null;
  claimBoundary: string;
  reviewTargetKey: string | null;
}): ProvenanceRecord[] {
  const observation = input.observation;
  if (!observation || observation.modality !== "image") {
    return [];
  }

  return (input.visualEvidence ?? [])
    .filter((item) => item.available !== false)
    .slice(0, 3)
    .map((item) => ({
      recordId: `visual:${item.artifact_id}`,
      sourceType: "visual_evidence",
      sourceLabel: item.title,
      sourcePathOrId: item.source_path ?? item.source_key,
      snippetOrPreview: item.note,
      previewUrl: item.preview_path ?? item.url,
      confidence: null,
      claimBoundary: input.claimBoundary,
      reviewTargetKey: input.reviewTargetKey,
      tags: ["source-grounded"],
      multiline: false,
    }));
}

function findPathReviewTargetKey(caseDetail: RunCaseDetail, pathId: string) {
  return (
    caseDetail.review_targets?.find(
      (item) => item.target_type === "path" && item.target_id === pathId,
    )?.target_key ?? null
  );
}

function findEntityLinkReviewTargetKey(
  caseDetail: RunCaseDetail,
  linkId: string,
) {
  return (
    caseDetail.review_targets?.find(
      (item) => item.target_type === "entity_link" && item.target_id === linkId,
    )?.target_key ?? null
  );
}

function findEdgeReviewTargetKey(
  caseDetail: RunCaseDetail,
  edgeId: string | null | undefined,
) {
  if (!edgeId) {
    return null;
  }

  return (
    caseDetail.review_targets?.find(
      (item) => item.target_type === "edge" && item.target_id === edgeId,
    )?.target_key ?? null
  );
}

function findCorrectionReviewTargetKey(
  caseDetail: RunCaseDetail,
  correctionId: string | null | undefined,
) {
  if (!correctionId) {
    return null;
  }

  return (
    caseDetail.review_targets?.find(
      (item) =>
        item.target_type === "correction" && item.target_id === correctionId,
    )?.target_key ?? null
  );
}

function findGraphPathRecord(caseDetail: RunCaseDetail, pathId: string) {
  const topKPath =
    (Array.isArray(caseDetail.top_k_paths)
      ? caseDetail.top_k_paths.find(
          (item) => isRecord(item) && item.path_id === pathId,
        )
      : null) ?? null;
  const pathGraphRecord =
    caseDetail.path_graph?.paths.find((item) => item.path_id === pathId) ??
    null;

  if (!topKPath && !pathGraphRecord) {
    return null;
  }

  const sourceEdges = Array.isArray(topKPath?.source_edges)
    ? topKPath?.source_edges.filter(isRecord)
    : [];
  const supportObservationIds = uniqueStable(
    [
      ...readStringArray(topKPath?.support_obs_ids),
      ...readStringArray(topKPath?.supporting_evidence),
      ...readStringArray(pathGraphRecord?.supporting_evidence),
    ],
    (item) => item,
  );
  const relationSequence = readStringArray(topKPath?.relations).length
    ? readStringArray(topKPath?.relations)
    : (pathGraphRecord?.edges
        .map((edge) => normalizeText(edge.relation))
        .filter(Boolean) ?? []);

  const lastGraphNode =
    pathGraphRecord && pathGraphRecord.nodes.length
      ? pathGraphRecord.nodes[pathGraphRecord.nodes.length - 1]
      : null;

  return {
    pathId,
    targetEntityId:
      normalizeNullableText(topKPath?.target_entity_id) ??
      normalizeNullableText(pathGraphRecord?.target_entity_id),
    targetEntityName:
      normalizeText(topKPath?.target_entity_name) ||
      normalizeText(lastGraphNode?.label) ||
      pathId,
    sourceEdges,
    pathGraphRecord,
    supportObservationIds,
    relationSequence,
  };
}

function buildPathSemanticNotes(
  pathRecord: ReturnType<typeof findGraphPathRecord>,
  caseDetail: RunCaseDetail,
) {
  const notes: string[] = [];
  if (!pathRecord) {
    return notes;
  }

  const involvesFaultAnchor =
    (pathRecord.targetEntityId?.startsWith("faultanchor:") ?? false) ||
    pathRecord.pathGraphRecord?.nodes.some((node) =>
      node.node_id.startsWith("faultanchor:"),
    ) ||
    false;

  if (caseDetail.dataset === "tep" && involvesFaultAnchor) {
    notes.push(TEP_PROJECTION_NOTE);
  }

  return notes;
}

function buildPathEdgeRecords(input: {
  caseDetail: RunCaseDetail;
  pathRecord: NonNullable<ReturnType<typeof findGraphPathRecord>>;
  claimBoundary: string;
  reviewTargetKey: string | null;
}): ProvenanceRecord[] {
  const records: ProvenanceRecord[] = [];

  for (const edge of input.pathRecord.sourceEdges) {
    const edgeId = normalizeText(
      edge.edge_id,
      `${normalizeText(edge.source)}|${normalizeText(edge.relation)}|${normalizeText(edge.target)}`,
    );
    const sourcePathOrId = normalizeText(edge.source, edgeId);
    const snippet = normalizeText(
      edge.evidence,
      `${normalizeText(edge.source)} —${normalizeText(edge.relation)}→ ${normalizeText(edge.target)}`,
    );

    records.push({
      recordId: `path-edge:${edgeId}`,
      sourceType: "edge_provenance",
      sourceLabel: normalizeText(edge.relation, "Path edge"),
      sourcePathOrId,
      snippetOrPreview: snippet,
      previewUrl: null,
      confidence: normalizeNumber(edge.confidence),
      claimBoundary: input.claimBoundary,
      reviewTargetKey: input.reviewTargetKey,
      tags:
        input.caseDetail.dataset === "tep" &&
        input.pathRecord.targetEntityId?.startsWith("faultanchor:")
          ? ["projected"]
          : ["source-grounded"],
      multiline: false,
    });
  }

  return records;
}

export function buildGraphPathProvenance(input: {
  caseDetail: RunCaseDetail | null | undefined;
  pathId: string | null | undefined;
  claimBoundary: string;
}): ProvenanceInspectorState | null {
  if (!input.caseDetail || !input.pathId) {
    return null;
  }

  const pathRecord = findGraphPathRecord(input.caseDetail, input.pathId);
  if (!pathRecord) {
    return null;
  }

  const reviewTargetKey = findPathReviewTargetKey(
    input.caseDetail,
    input.pathId,
  );
  const records: ProvenanceRecord[] = [];

  for (const observationId of pathRecord.supportObservationIds) {
    const observation = resolveObservationForSelection(
      input.caseDetail,
      observationId,
    );
    if (!observation) {
      continue;
    }

    records.push(
      ...observation.rawEvidenceRefs.map((rawRef, index) =>
        buildRawRefRecord({
          recordId: `path-raw-ref:${observation.id}:${index}`,
          claimBoundary: input.claimBoundary,
          reviewTargetKey,
          observationId,
          rawRef,
        }),
      ),
    );
    records.push(
      ...buildVisualEvidenceRecords({
        visualEvidence: input.caseDetail.visual_evidence,
        observation,
        claimBoundary: input.claimBoundary,
        reviewTargetKey,
      }),
    );
  }

  records.push(
    ...buildPathEdgeRecords({
      caseDetail: input.caseDetail,
      pathRecord,
      claimBoundary: input.claimBoundary,
      reviewTargetKey,
    }),
  );

  return {
    targetKind: "path",
    targetId: input.pathId,
    summary: pathRecord.targetEntityName,
    contextLabel: input.caseDetail.case_label ?? input.caseDetail.case_id,
    linkedReviewTarget: reviewTargetKey,
    claimBoundary: input.claimBoundary,
    records: uniqueStable(records, (item) => item.recordId),
    semanticNotes: buildPathSemanticNotes(pathRecord, input.caseDetail),
  };
}

export function buildGraphEntityLinkProvenance(input: {
  caseDetail: RunCaseDetail | null | undefined;
  linkId: string | null | undefined;
  claimBoundary: string;
}): ProvenanceInspectorState | null {
  if (!input.caseDetail || !input.linkId) {
    return null;
  }

  const link = Array.isArray(input.caseDetail.linked_entities)
    ? input.caseDetail.linked_entities.find(
        (item) => isRecord(item) && item.link_id === input.linkId,
      )
    : null;
  if (!link || !isRecord(link)) {
    return null;
  }

  const observation =
    resolveObservationForSelection(
      input.caseDetail,
      normalizeNullableText(link.obs_id),
    ) ??
    findParentObservationForField(
      buildObservationBrowseItems(input.caseDetail),
      normalizeNullableText(link.field),
      normalizeNullableText(link.mention),
    );
  const reviewTargetKey = findEntityLinkReviewTargetKey(
    input.caseDetail,
    input.linkId,
  );
  const records: ProvenanceRecord[] = [
    {
      recordId: `entity-link:${input.linkId}`,
      sourceType: "entity_link",
      sourceLabel: normalizeText(
        link.selected_entity_name,
        normalizeText(link.selected_entity_id, input.linkId),
      ),
      sourcePathOrId: normalizeText(link.selected_entity_id, input.linkId),
      snippetOrPreview: `${normalizeText(link.field, "field")} · ${normalizeText(link.mention, "--")} · ${normalizeText(link.match_type, "match")} · score ${normalizeNumber(link.score)?.toFixed(2) ?? "--"}`,
      previewUrl: null,
      confidence: normalizeNumber(link.score),
      claimBoundary: input.claimBoundary,
      reviewTargetKey,
      tags: ["source-grounded"],
      multiline: false,
    },
  ];

  if (observation) {
    records.push(
      ...observation.rawEvidenceRefs.map((rawRef, index) =>
        buildRawRefRecord({
          recordId: `entity-raw-ref:${input.linkId}:${index}`,
          claimBoundary: input.claimBoundary,
          reviewTargetKey,
          observationId: observation.id,
          rawRef,
        }),
      ),
    );
    records.push(
      ...buildVisualEvidenceRecords({
        visualEvidence: input.caseDetail.visual_evidence,
        observation,
        claimBoundary: input.claimBoundary,
        reviewTargetKey,
      }),
    );
  }

  return {
    targetKind: "entity_link",
    targetId: input.linkId,
    summary: normalizeText(
      link.selected_entity_name,
      normalizeText(link.selected_entity_id, input.linkId),
    ),
    contextLabel: input.caseDetail.case_label ?? input.caseDetail.case_id,
    linkedReviewTarget: reviewTargetKey,
    claimBoundary: input.claimBoundary,
    records: uniqueStable(records, (item) => item.recordId),
    semanticNotes: link.ambiguous === true ? [AMBIGUOUS_LINK_NOTE] : [],
  };
}

export function buildGraphEdgeProvenance(input: {
  caseDetail: RunCaseDetail | null | undefined;
  edge: GraphProvenanceEdgeRef | null | undefined;
  claimBoundary: string;
}): ProvenanceInspectorState | null {
  if (!input.caseDetail || !input.edge) {
    return null;
  }

  const edge = input.edge;
  const reviewTargetKey = findEdgeReviewTargetKey(input.caseDetail, edge.id);
  const sourceEdge = Array.isArray(input.caseDetail.source_edge_provenance)
    ? input.caseDetail.source_edge_provenance.find(
        (item) => isRecord(item) && normalizeText(item.edge_id) === edge.id,
      )
    : null;

  const projectedEdge =
    input.caseDetail.dataset === "tep" &&
    (edge.source.startsWith("faultanchor:") ||
      edge.target.startsWith("faultanchor:"));
  const records: ProvenanceRecord[] = [
    {
      recordId: `edge-meta:${edge.id}`,
      sourceType: "edge_metadata",
      sourceLabel: normalizeText(edge.relation, edge.id),
      sourcePathOrId:
        readStringValue(edge.attributes, "source") ??
        edge.origin?.filePath ??
        edge.id,
      snippetOrPreview:
        readStringValue(edge.attributes, "evidence") ??
        `${edge.source} —${edge.relation}→ ${edge.target}`,
      previewUrl: null,
      confidence: typeof edge.confidence === "number" ? edge.confidence : null,
      claimBoundary: input.claimBoundary,
      reviewTargetKey,
      tags: projectedEdge ? ["projected"] : ["source-grounded"],
      multiline: false,
    },
  ];

  if (sourceEdge && isRecord(sourceEdge)) {
    records.push({
      recordId: `edge-provenance:${edge.id}`,
      sourceType: "edge_provenance",
      sourceLabel: normalizeText(
        sourceEdge.relation,
        normalizeText(edge.relation, edge.id),
      ),
      sourcePathOrId: normalizeText(sourceEdge.source, edge.id),
      snippetOrPreview:
        normalizeText(sourceEdge.evidence) ||
        `${normalizeText(sourceEdge.source)} —${normalizeText(sourceEdge.relation)}→ ${normalizeText(sourceEdge.target)}`,
      previewUrl: null,
      confidence: normalizeNumber(sourceEdge.confidence),
      claimBoundary: input.claimBoundary,
      reviewTargetKey,
      tags: projectedEdge ? ["projected"] : ["source-grounded"],
      multiline: false,
    });
  }

  return {
    targetKind: "edge",
    targetId: edge.id,
    summary: `${edge.source} —${edge.relation}→ ${edge.target}`,
    contextLabel: input.caseDetail.case_label ?? input.caseDetail.case_id,
    linkedReviewTarget: reviewTargetKey,
    claimBoundary: input.claimBoundary,
    records: uniqueStable(records, (item) => item.recordId),
    semanticNotes: projectedEdge ? [TEP_PROJECTION_NOTE] : [],
  };
}

function buildSourceMaterialRecords(input: {
  sourceIds: string[];
  materials: ProvenanceSourceMaterial[];
  claimBoundary: string;
}): ProvenanceRecord[] {
  const catalog = new Map(input.materials.map((item) => [item.sourceId, item]));

  return input.sourceIds.map((sourceId) => {
    const material = catalog.get(sourceId);
    return {
      recordId: `source-material:${sourceId}`,
      sourceType: "source_material",
      sourceLabel: material?.title ?? sourceId,
      sourcePathOrId: material?.path ?? sourceId,
      snippetOrPreview:
        material?.note ?? material?.sourceType ?? "linked source material",
      previewUrl: null,
      confidence: null,
      claimBoundary: input.claimBoundary,
      reviewTargetKey: null,
      tags: ["source-grounded"],
      multiline: false,
    };
  });
}

export function buildGraphCorrectionProvenance(input: {
  caseDetail: RunCaseDetail | null | undefined;
  correctionId: string | null | undefined;
  claimBoundary: string;
}): ProvenanceInspectorState | null {
  if (!input.caseDetail || !input.correctionId) {
    return null;
  }

  const correction =
    (Array.isArray(input.caseDetail.correction_candidates)
      ? input.caseDetail.correction_candidates.find(
          (item) =>
            isRecord(item) &&
            normalizeText(item.candidate_id) === input.correctionId,
        )
      : null) ?? null;
  if (!correction) {
    return null;
  }

  const reviewTargetKey = findCorrectionReviewTargetKey(
    input.caseDetail,
    input.correctionId,
  );
  const observation = resolveObservationForSelection(
    input.caseDetail,
    normalizeNullableText(correction.target_obs_id),
  );
  const records: ProvenanceRecord[] = [
    {
      recordId: `correction:${input.correctionId}`,
      sourceType: "correction",
      sourceLabel: normalizeText(
        correction.suggested_value,
        input.correctionId,
      ),
      sourcePathOrId: normalizeText(
        correction.suggested_entity_id,
        input.correctionId,
      ),
      snippetOrPreview: `${normalizeText(correction.reason, "correction")} · ${JSON.stringify(correction.original_value ?? null)} -> ${normalizeText(correction.suggested_value, input.correctionId)}`,
      previewUrl: null,
      confidence: normalizeNumber(correction.score),
      claimBoundary: input.claimBoundary,
      reviewTargetKey,
      tags: ["source-grounded"],
      multiline: false,
    },
  ];

  if (observation) {
    records.push(
      ...observation.rawEvidenceRefs.map((rawRef, index) =>
        buildRawRefRecord({
          recordId: `correction-raw-ref:${input.correctionId}:${index}`,
          claimBoundary: input.claimBoundary,
          reviewTargetKey,
          observationId: observation.id,
          rawRef,
        }),
      ),
    );
    records.push(
      ...buildVisualEvidenceRecords({
        visualEvidence: input.caseDetail.visual_evidence,
        observation,
        claimBoundary: input.claimBoundary,
        reviewTargetKey,
      }),
    );
  }

  const supportingEdgeIds = readStringArray(correction.supporting_edge_ids);
  for (const edgeId of supportingEdgeIds) {
    const sourceEdge = Array.isArray(input.caseDetail.source_edge_provenance)
      ? input.caseDetail.source_edge_provenance.find(
          (item) => isRecord(item) && normalizeText(item.edge_id) === edgeId,
        )
      : null;

    if (sourceEdge && isRecord(sourceEdge)) {
      records.push({
        recordId: `correction-edge:${edgeId}`,
        sourceType: "edge_provenance",
        sourceLabel: normalizeText(sourceEdge.relation, edgeId),
        sourcePathOrId: normalizeText(sourceEdge.source, edgeId),
        snippetOrPreview:
          normalizeText(sourceEdge.evidence) ||
          `${normalizeText(sourceEdge.source)} —${normalizeText(sourceEdge.relation)}→ ${normalizeText(sourceEdge.target)}`,
        previewUrl: null,
        confidence: normalizeNumber(sourceEdge.confidence),
        claimBoundary: input.claimBoundary,
        reviewTargetKey,
        tags: ["source-grounded"],
        multiline: false,
      });
    }
  }

  return {
    targetKind: "correction",
    targetId: input.correctionId,
    summary: normalizeText(correction.suggested_value, input.correctionId),
    contextLabel: input.caseDetail.case_label ?? input.caseDetail.case_id,
    linkedReviewTarget: reviewTargetKey,
    claimBoundary: input.claimBoundary,
    records: uniqueStable(records, (item) => item.recordId),
    semanticNotes: [],
  };
}

export function buildMaterialsBuildProvenance(input: {
  buildDetail: KGConstructionBuildDetail | null | undefined;
  buildValidation: KGConstructionBuildValidationResponse | null | undefined;
  materials: ProvenanceSourceMaterial[];
  claimBoundary: string;
}): ProvenanceInspectorState | null {
  if (!input.buildDetail) {
    return null;
  }

  const build = input.buildDetail.build;
  const records: ProvenanceRecord[] = [
    {
      recordId: `build-manifest:${build.run_id}`,
      sourceType: "manifest",
      sourceLabel: "Build manifest",
      sourcePathOrId: build.manifest_path,
      snippetOrPreview: formatJsonSnippet(input.buildDetail.manifest),
      previewUrl: null,
      confidence: null,
      claimBoundary: input.claimBoundary,
      reviewTargetKey: null,
      tags: ["generated"],
      multiline: true,
    },
    {
      recordId: `build-summary:${build.run_id}`,
      sourceType: "summary",
      sourceLabel: "Build summary",
      sourcePathOrId: build.summary_path,
      snippetOrPreview: formatJsonSnippet(input.buildDetail.summary),
      previewUrl: null,
      confidence: null,
      claimBoundary: input.claimBoundary,
      reviewTargetKey: null,
      tags: ["generated"],
      multiline: true,
    },
  ];

  if (input.buildValidation) {
    records.push({
      recordId: `build-qa:${build.run_id}`,
      sourceType: "qa_report",
      sourceLabel: "QA report",
      sourcePathOrId: `${build.run_id}:qa_report`,
      snippetOrPreview: formatJsonSnippet(input.buildValidation.qa_report),
      previewUrl: null,
      confidence: null,
      claimBoundary: input.claimBoundary,
      reviewTargetKey: null,
      tags: ["generated"],
      multiline: true,
    });
  }

  records.push(
    ...buildSourceMaterialRecords({
      sourceIds: build.source_ids,
      materials: input.materials,
      claimBoundary: input.claimBoundary,
    }),
  );

  return {
    targetKind: "build",
    targetId: build.run_id,
    summary: build.run_id,
    contextLabel: `${build.source_count} source(s) · ${build.node_count} node(s) / ${build.edge_count} edge(s)`,
    linkedReviewTarget: null,
    claimBoundary: input.claimBoundary,
    records: uniqueStable(records, (item) => item.recordId),
    semanticNotes: [GENERATED_BUILD_NOTE],
  };
}

export function buildMaterialsBuildEdgeProvenance(input: {
  buildDetail: KGConstructionBuildDetail | null | undefined;
  edge: KGConstructionReviewQueueEdge | null | undefined;
  materials: ProvenanceSourceMaterial[];
  claimBoundary: string;
}): ProvenanceInspectorState | null {
  if (!input.buildDetail || !input.edge) {
    return null;
  }

  const material =
    input.materials.find((item) => item.sourceId === input.edge?.source) ??
    null;
  const records: ProvenanceRecord[] = [
    {
      recordId: `build-edge:${input.edge.target_key}`,
      sourceType: "review_queue",
      sourceLabel: `${input.edge.head} —${input.edge.relation}→ ${input.edge.tail}`,
      sourcePathOrId: input.edge.source || input.edge.target_key,
      snippetOrPreview:
        input.edge.evidence ||
        "当前 review queue edge 未附带 evidence snippet。",
      previewUrl: null,
      confidence: input.edge.confidence,
      claimBoundary: input.claimBoundary,
      reviewTargetKey: input.edge.target_key,
      tags: input.edge.source ? ["source-grounded"] : ["generated"],
      multiline: false,
    },
  ];

  if (material) {
    records.push({
      recordId: `build-edge-source:${input.edge.target_key}`,
      sourceType: "source_material",
      sourceLabel: material.title,
      sourcePathOrId: material.path ?? material.sourceId,
      snippetOrPreview:
        material.note ?? material.sourceType ?? "linked source material",
      previewUrl: null,
      confidence: null,
      claimBoundary: input.claimBoundary,
      reviewTargetKey: input.edge.target_key,
      tags: ["source-grounded"],
      multiline: false,
    });
  }

  return {
    targetKind: "build_edge",
    targetId: input.edge.target_key,
    summary: `${input.edge.head} —${input.edge.relation}→ ${input.edge.tail}`,
    contextLabel: input.buildDetail.build.run_id,
    linkedReviewTarget: input.edge.target_key,
    claimBoundary: input.claimBoundary,
    records: uniqueStable(records, (item) => item.recordId),
    semanticNotes: [],
  };
}
