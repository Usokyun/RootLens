import type {
  PathGraph,
  RankedRootCause,
  RunCaseDetail,
  RunDetail,
} from "@/api/contracts";
import {
  buildObservationBrowseItems,
  type ObservationBrowseItem,
  type ObservationModality,
} from "@/services/evidence-observation";

export interface CandidateInspectionSummary {
  candidateId: string;
  rankingId: string;
  candidateName: string;
  rank: number | null;
  score: number | null;
  scoringMethod: string | null;
  role: string | null;
  linkedEntityCount: number;
  supportingObservationCount: number;
  selectedPathId: string | null;
}

export interface ReasoningObservationSummary {
  obsId: string;
  sharedObservationId: string;
  parentObservationId: string | null;
  title: string;
  facet: string;
  modality: ObservationModality;
  confidence: number | null;
  linkedEntityCount: number;
  source: string;
  timeLabel: string;
  rawRefCount: number;
  linkedEntityIds: string[];
  linkedEntityHints: string[];
  isDerived: boolean;
}

export interface ReasoningLinkedEntitySummary {
  linkId: string;
  obsId: string | null;
  sharedObservationId: string | null;
  field: string;
  mention: string;
  entityId: string | null;
  entityName: string;
  score: number | null;
  matchType: string | null;
  ambiguous: boolean;
}

export interface ReasoningPathSummary {
  pathId: string;
  targetEntityId: string | null;
  targetEntityName: string;
  nodeIds: string[];
  nodeNames: string[];
  relationSequence: string[];
  edgeIds: string[];
  score: number | null;
  confidence: number | null;
  supportObservationIds: string[];
  signature: string;
}

export type TraceStepKind = "observation" | "entity" | "path" | "candidate";
export type TraceStepEmphasis = "primary" | "supporting" | "linked" | "result";

export interface TraceStep {
  stepId: string;
  kind: TraceStepKind;
  emphasis: TraceStepEmphasis;
  label: string;
  subtitle: string;
  observationId?: string;
  sharedObservationId?: string;
  entityId?: string | null;
  pathId?: string | null;
  candidateId?: string | null;
  graphNodeId?: string | null;
  focusNodeIds: string[];
  focusEdgeIds: string[];
}

export interface RecurrenceCaseHit {
  caseId: string;
  caseLabel: string;
  matchedPathIds: string[];
  matchedObservationIds: string[];
  matchedEntityIds: string[];
}

export interface RecurringEntitySummary {
  entityId: string;
  entityName: string;
  occurrenceCount: number;
  currentObservationIds: string[];
  caseHits: RecurrenceCaseHit[];
}

export interface RecurringPathSummary {
  signature: string;
  targetEntityId: string | null;
  targetEntityName: string;
  relationSequence: string[];
  occurrenceCount: number;
  caseHits: RecurrenceCaseHit[];
}

export interface CrossCaseRecurrenceSummary {
  currentCaseId: string;
  currentCaseLabel: string;
  candidateId: string | null;
  relatedCaseCount: number;
  recurringEntities: RecurringEntitySummary[];
  recurringPaths: RecurringPathSummary[];
}

export interface GraphReasoningInspectionResult {
  candidate: CandidateInspectionSummary | null;
  primaryObservation: ReasoningObservationSummary | null;
  supportingObservations: ReasoningObservationSummary[];
  linkedEntities: ReasoningLinkedEntitySummary[];
  selectedPath: ReasoningPathSummary | null;
  traceSteps: TraceStep[];
  crossCaseRecurrence: CrossCaseRecurrenceSummary | null;
}

export interface BuildGraphReasoningInspectionOptions {
  runDetail: RunDetail | null | undefined;
  caseDetail: RunCaseDetail | null | undefined;
  selectedCandidateId: string | null | undefined;
  selectedObservationId: string | null | undefined;
  selectedPathId: string | null | undefined;
}

interface ObservationInspectionIndex {
  observations: ReasoningObservationSummary[];
  byId: Map<string, ReasoningObservationSummary>;
  bySelectionId: Map<string, ReasoningObservationSummary>;
  linksByObsId: Map<string, ReasoningLinkedEntitySummary[]>;
  linksBySelectionId: Map<string, ReasoningLinkedEntitySummary[]>;
}

interface EntityOccurrence {
  entityId: string;
  entityName: string;
  matchedPathIds: Set<string>;
  matchedObservationIds: Set<string>;
}

const OBSERVATION_FIELD_ORDER = [
  "anomaly_type",
  "morphology",
  "location",
  "object",
  "variable",
  "log_event",
];

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

function humanizeIdentifier(value: string) {
  return value.replace(/_/g, " ");
}

function formatFieldLabel(value: string) {
  return humanizeIdentifier(value);
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

function readStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.map((item) => normalizeText(item)).filter(Boolean);
}

function readObservationSource(caseDetail: RunCaseDetail) {
  return normalizeText(caseDetail.source, "unknown");
}

function toModalityFromField(
  field: string,
  fallback: ObservationModality = "document",
): ObservationModality {
  switch (field) {
    case "anomaly_type":
    case "location":
    case "morphology":
    case "object":
      return "image";
    case "variable":
      return "time_series";
    case "log_event":
    case "equipment":
      return "log";
    default:
      return fallback;
  }
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

function buildDerivedObservationTitle(
  field: string | null,
  mention: string | null,
  fallbackId: string,
) {
  if (!field || !mention) {
    return humanizeIdentifier(fallbackId);
  }

  return `${formatFieldLabel(field)} / ${humanizeIdentifier(mention)}`;
}

function buildPathTargetName(
  pathRecord: Record<string, unknown>,
  graphPath: PathGraph["paths"][number] | null,
) {
  const lastGraphNode =
    graphPath && graphPath.nodes.length
      ? graphPath.nodes[graphPath.nodes.length - 1]
      : null;

  return (
    normalizeText(pathRecord.target_entity_name) ||
    normalizeText(lastGraphNode?.label) ||
    normalizeText(pathRecord.target_entity_id) ||
    normalizeText(graphPath?.target_entity_id) ||
    "--"
  );
}

function extractTopKPaths(caseDetail: RunCaseDetail): ReasoningPathSummary[] {
  const topKPaths = Array.isArray(caseDetail.top_k_paths)
    ? caseDetail.top_k_paths.filter(isRecord)
    : [];
  const pathGraphById = new Map(
    (caseDetail.path_graph?.paths ?? []).map((item) => [item.path_id, item]),
  );

  if (!topKPaths.length && caseDetail.path_graph?.paths?.length) {
    return caseDetail.path_graph.paths.map((graphPath) => {
      const relationSequence = graphPath.edges
        .map((edge) => normalizeText(edge.relation))
        .filter(Boolean);
      const targetEntityId = normalizeNullableText(graphPath.target_entity_id);
      return {
        pathId: graphPath.path_id,
        targetEntityId,
        targetEntityName: normalizeText(
          graphPath.nodes[graphPath.nodes.length - 1]?.label,
          targetEntityId ?? graphPath.path_id,
        ),
        nodeIds: graphPath.nodes.map((node) => node.node_id),
        nodeNames: graphPath.nodes.map((node) =>
          normalizeText(node.label, node.node_id),
        ),
        relationSequence,
        edgeIds: graphPath.edges.map((edge) => edge.edge_id),
        score: normalizeNumber(graphPath.score),
        confidence: normalizeNumber(graphPath.confidence),
        supportObservationIds: readStringArray(graphPath.supporting_evidence),
        signature: buildPathSignature({
          targetEntityId,
          relationSequence,
        }),
      };
    });
  }

  return topKPaths.map((pathRecord, index) => {
    const pathId = normalizeText(pathRecord.path_id, `path-${index + 1}`);
    const graphPath = pathGraphById.get(pathId) ?? null;
    const nodeIds = readStringArray(pathRecord.nodes);
    const nodeNames = readStringArray(pathRecord.node_names);
    const relationSequence = readStringArray(pathRecord.relations);
    const sourceEdges = Array.isArray(pathRecord.source_edges)
      ? pathRecord.source_edges.filter(isRecord)
      : [];
    const edgeIds = sourceEdges
      .map((item, edgeIndex) =>
        normalizeText(item.edge_id, graphPath?.edges[edgeIndex]?.edge_id ?? ""),
      )
      .filter(Boolean);
    const graphPathRelations =
      graphPath?.edges
        .map((edge) => normalizeText(edge.relation))
        .filter(Boolean) ?? [];
    const supportObservationIds = uniqueStable(
      [
        ...readStringArray(pathRecord.support_obs_ids),
        ...readStringArray(pathRecord.supporting_evidence),
        ...readStringArray(graphPath?.supporting_evidence),
      ],
      (item) => item,
    );
    const targetEntityId =
      normalizeNullableText(pathRecord.target_entity_id) ??
      normalizeNullableText(graphPath?.target_entity_id);

    return {
      pathId,
      targetEntityId,
      targetEntityName: buildPathTargetName(pathRecord, graphPath),
      nodeIds: nodeIds.length
        ? nodeIds
        : (graphPath?.nodes.map((node) => node.node_id) ?? []),
      nodeNames: nodeNames.length
        ? nodeNames
        : (graphPath?.nodes.map((node) =>
            normalizeText(node.label, node.node_id),
          ) ?? []),
      relationSequence: relationSequence.length
        ? relationSequence
        : graphPathRelations,
      edgeIds: edgeIds.length
        ? edgeIds
        : (graphPath?.edges.map((edge) => edge.edge_id) ?? []),
      score:
        normalizeNumber(pathRecord.score) ?? normalizeNumber(graphPath?.score),
      confidence:
        normalizeNumber(pathRecord.confidence) ??
        normalizeNumber(graphPath?.confidence),
      supportObservationIds,
      signature: buildPathSignature({
        targetEntityId,
        relationSequence: relationSequence.length
          ? relationSequence
          : graphPathRelations,
      }),
    };
  });
}

function extractCandidateSupportingObservationIds(
  candidate: RankedRootCause | null,
) {
  if (!candidate) {
    return [];
  }

  return uniqueStable(
    [
      ...readStringArray(candidate.supporting_evidence),
      ...readStringArray(candidate.support_evidence_ids),
    ],
    (item) => item,
  );
}

function doesPathMatchCandidate(
  path: ReasoningPathSummary,
  candidate: RankedRootCause | null,
) {
  if (!candidate) {
    return false;
  }

  if (
    path.targetEntityId &&
    path.targetEntityId === normalizeText(candidate.candidate_id)
  ) {
    return true;
  }

  if (
    path.pathId === normalizeText(candidate.ranking_id).replace(/^ranking:/, "")
  ) {
    return true;
  }

  if (path.nodeIds.includes(normalizeText(candidate.candidate_id))) {
    return true;
  }

  const candidateNames = new Set(
    [candidate.candidate_name, candidate.candidate_label]
      .map((item) => normalizeComparable(item))
      .filter(Boolean),
  );

  return candidateNames.has(normalizeComparable(path.targetEntityName));
}

function buildObservationInspectionIndex(
  caseDetail: RunCaseDetail,
  supportObservationIds: string[],
): ObservationInspectionIndex {
  const observationItems = buildObservationBrowseItems(caseDetail);
  const actualById = new Map(observationItems.map((item) => [item.id, item]));
  const linksByObsId = new Map<string, ReasoningLinkedEntitySummary[]>();
  const aggregateLinksByParentId = new Map<
    string,
    ReasoningLinkedEntitySummary[]
  >();
  const parentObservationIdByDerivedId = new Map<string, string | null>();
  const linkedEntities = Array.isArray(caseDetail.linked_entities)
    ? caseDetail.linked_entities.filter(isRecord)
    : [];

  for (const link of linkedEntities) {
    const linkId = normalizeText(link.link_id, normalizeText(link.field));
    if (!linkId) {
      continue;
    }

    const obsId = normalizeNullableText(link.obs_id);
    if (!obsId) {
      continue;
    }

    const field = normalizeText(link.field, "--");
    const mention = normalizeText(link.mention, "--");
    const parentObservation =
      actualById.get(obsId) ??
      findParentObservationForField(
        observationItems,
        normalizeNullableText(link.field),
        normalizeNullableText(link.mention),
      );
    const parentObservationId = parentObservation?.id ?? null;
    const sharedObservationId = parentObservationId ?? obsId;
    const linkSummary: ReasoningLinkedEntitySummary = {
      linkId,
      obsId,
      sharedObservationId,
      field,
      mention,
      entityId: normalizeNullableText(link.selected_entity_id),
      entityName:
        normalizeText(link.selected_entity_name) ||
        normalizeText(link.selected_entity_id) ||
        mention ||
        linkId,
      score: normalizeNumber(link.score),
      matchType: normalizeNullableText(link.match_type),
      ambiguous: link.ambiguous === true,
    };

    const directLinks = linksByObsId.get(obsId) ?? [];
    directLinks.push(linkSummary);
    linksByObsId.set(obsId, directLinks);
    parentObservationIdByDerivedId.set(obsId, parentObservationId);

    if (parentObservationId) {
      const parentLinks =
        aggregateLinksByParentId.get(parentObservationId) ?? [];
      parentLinks.push(linkSummary);
      aggregateLinksByParentId.set(parentObservationId, parentLinks);
    }
  }

  const byId = new Map<string, ReasoningObservationSummary>();
  const bySelectionId = new Map<string, ReasoningObservationSummary>();
  const linksBySelectionId = new Map<string, ReasoningLinkedEntitySummary[]>();

  const registerObservation = (summary: ReasoningObservationSummary) => {
    byId.set(summary.obsId, summary);
    bySelectionId.set(summary.obsId, summary);
    bySelectionId.set(summary.sharedObservationId, summary);
    if (summary.parentObservationId) {
      bySelectionId.set(summary.parentObservationId, summary);
    }

    const directLinks = linksByObsId.get(summary.obsId) ?? [];
    const parentLinks = summary.parentObservationId
      ? (aggregateLinksByParentId.get(summary.parentObservationId) ?? [])
      : [];
    const mergedLinks = uniqueStable(
      [...directLinks, ...parentLinks],
      (item) => item.linkId,
    );
    linksBySelectionId.set(summary.obsId, mergedLinks);
    linksBySelectionId.set(summary.sharedObservationId, mergedLinks);
    if (summary.parentObservationId) {
      linksBySelectionId.set(summary.parentObservationId, mergedLinks);
    }

    return summary;
  };

  for (const observation of observationItems) {
    const aggregatedLinks = uniqueStable(
      [
        ...(aggregateLinksByParentId.get(observation.id) ?? []),
        ...(linksByObsId.get(observation.id) ?? []),
      ],
      (item) => item.linkId,
    );

    registerObservation({
      obsId: observation.id,
      sharedObservationId: observation.id,
      parentObservationId: observation.id,
      title: observation.title,
      facet: observation.facet,
      modality: observation.modality,
      confidence: observation.confidence,
      linkedEntityCount:
        aggregatedLinks.length || observation.linkedEntityCount,
      source: observation.source,
      timeLabel: observation.timeLabel,
      rawRefCount: observation.rawRefCount,
      linkedEntityIds: uniqueStable(
        aggregatedLinks
          .map((item) => item.entityId)
          .filter((item): item is string => Boolean(item)),
        (item) => item,
      ),
      linkedEntityHints: uniqueStable(
        aggregatedLinks.map((item) => item.entityName).filter(Boolean),
        (item) => item,
      ),
      isDerived: false,
    });
  }

  const allRequestedObservationIds = uniqueStable(
    [...linksByObsId.keys(), ...supportObservationIds],
    (item) => item,
  );

  for (const obsId of allRequestedObservationIds) {
    if (byId.has(obsId)) {
      continue;
    }

    const parsedTail = parseObservationIdTail(obsId);
    const parentObservation =
      (parsedTail
        ? findParentObservationForField(
            observationItems,
            parsedTail.field,
            parsedTail.mention,
          )
        : null) ??
      (parentObservationIdByDerivedId.get(obsId)
        ? (actualById.get(
            parentObservationIdByDerivedId.get(obsId) as string,
          ) ?? null)
        : null);
    const directLinks = uniqueStable(
      linksByObsId.get(obsId) ?? [],
      (item) => item.linkId,
    );
    const sharedObservationId =
      parentObservation?.id ??
      parentObservationIdByDerivedId.get(obsId) ??
      obsId;

    registerObservation({
      obsId,
      sharedObservationId,
      parentObservationId: parentObservation?.id ?? null,
      title: buildDerivedObservationTitle(
        parsedTail?.field ?? directLinks[0]?.field ?? null,
        parsedTail?.mention ?? directLinks[0]?.mention ?? null,
        obsId,
      ),
      facet:
        parentObservation?.facet ??
        parsedTail?.field ??
        directLinks[0]?.field ??
        "document",
      modality: toModalityFromField(
        parsedTail?.field ?? directLinks[0]?.field ?? "",
        parentObservation?.modality ?? "document",
      ),
      confidence:
        parentObservation?.confidence ?? directLinks[0]?.score ?? null,
      linkedEntityCount: directLinks.length,
      source: parentObservation?.source ?? readObservationSource(caseDetail),
      timeLabel: parentObservation?.timeLabel ?? "--",
      rawRefCount: parentObservation?.rawRefCount ?? 0,
      linkedEntityIds: uniqueStable(
        directLinks
          .map((item) => item.entityId)
          .filter((item): item is string => Boolean(item)),
        (item) => item,
      ),
      linkedEntityHints: uniqueStable(
        directLinks.map((item) => item.entityName).filter(Boolean),
        (item) => item,
      ),
      isDerived: true,
    });
  }

  const observations = uniqueStable([...byId.values()], (item) => item.obsId);
  observations.sort((left, right) => left.obsId.localeCompare(right.obsId));

  return {
    observations,
    byId,
    bySelectionId,
    linksByObsId,
    linksBySelectionId,
  };
}

export function findReasoningObservationBySelection(
  observations: ReasoningObservationSummary[] | null | undefined,
  selectionId: string | null | undefined,
) {
  if (!observations?.length || !selectionId) {
    return null;
  }

  return (
    observations.find(
      (item) =>
        item.obsId === selectionId ||
        item.sharedObservationId === selectionId ||
        item.parentObservationId === selectionId,
    ) ?? null
  );
}

function buildObservationSupportList(
  options: {
    caseDetail: RunCaseDetail;
    candidate: RankedRootCause | null;
    selectedPath: ReasoningPathSummary | null;
    candidatePaths: ReasoningPathSummary[];
    selectedObservationId: string | null | undefined;
  },
  observationIndex: ObservationInspectionIndex,
) {
  const orderedIds = uniqueStable(
    [
      ...(options.selectedPath?.supportObservationIds ?? []),
      ...options.candidatePaths.flatMap((item) => item.supportObservationIds),
      ...extractCandidateSupportingObservationIds(options.candidate),
    ],
    (item) => item,
  );

  const supportingObservations = orderedIds
    .map(
      (obsId) =>
        observationIndex.byId.get(obsId) ??
        observationIndex.bySelectionId.get(obsId) ??
        null,
    )
    .filter((item): item is ReasoningObservationSummary => item !== null);

  if (!supportingObservations.length && options.selectedObservationId) {
    const fallbackObservation = observationIndex.bySelectionId.get(
      options.selectedObservationId,
    );
    if (fallbackObservation) {
      supportingObservations.push(fallbackObservation);
    }
  }

  const primaryObservationId =
    options.selectedPath?.supportObservationIds[0] ??
    options.selectedObservationId ??
    supportingObservations[0]?.obsId ??
    null;
  const primaryObservation =
    (primaryObservationId
      ? (observationIndex.byId.get(primaryObservationId) ??
        observationIndex.bySelectionId.get(primaryObservationId))
      : null) ??
    supportingObservations[0] ??
    null;

  const mergedObservations = uniqueStable(
    primaryObservation
      ? [primaryObservation, ...supportingObservations]
      : supportingObservations,
    (item) => item.obsId,
  );

  return {
    primaryObservation,
    supportingObservations: mergedObservations,
  };
}

function buildLinkedEntityList(
  supportingObservations: ReasoningObservationSummary[],
  observationIndex: ObservationInspectionIndex,
) {
  const linkedEntities: ReasoningLinkedEntitySummary[] = [];

  for (const observation of supportingObservations) {
    const links = uniqueStable(
      observationIndex.linksBySelectionId.get(observation.obsId) ??
        observationIndex.linksBySelectionId.get(
          observation.sharedObservationId,
        ) ??
        [],
      (item) => item.linkId,
    );
    linkedEntities.push(...links);
  }

  return uniqueStable(linkedEntities, (item) => item.linkId);
}

function buildTraceSteps(input: {
  candidate: RankedRootCause | null;
  primaryObservation: ReasoningObservationSummary | null;
  supportingObservations: ReasoningObservationSummary[];
  linkedEntities: ReasoningLinkedEntitySummary[];
  selectedPath: ReasoningPathSummary | null;
}) {
  const steps: TraceStep[] = [];
  const primaryObservationId = input.primaryObservation?.obsId ?? null;

  for (const observation of input.supportingObservations) {
    steps.push({
      stepId: `observation:${observation.obsId}`,
      kind: "observation",
      emphasis:
        observation.obsId === primaryObservationId ? "primary" : "supporting",
      label: observation.title,
      subtitle: `${observation.modality} · ${observation.obsId}`,
      observationId: observation.obsId,
      sharedObservationId: observation.sharedObservationId,
      focusNodeIds: observation.linkedEntityIds,
      focusEdgeIds: [],
    });
  }

  for (const entity of input.linkedEntities) {
    steps.push({
      stepId: `entity:${entity.linkId}`,
      kind: "entity",
      emphasis: "linked",
      label: entity.entityName,
      subtitle: `${formatFieldLabel(entity.field)} · ${entity.mention}`,
      observationId: entity.obsId ?? undefined,
      sharedObservationId: entity.sharedObservationId ?? undefined,
      entityId: entity.entityId,
      graphNodeId: entity.entityId,
      focusNodeIds: entity.entityId ? [entity.entityId] : [],
      focusEdgeIds: [],
    });
  }

  if (input.selectedPath) {
    steps.push({
      stepId: `path:${input.selectedPath.pathId}`,
      kind: "path",
      emphasis: "result",
      label: input.selectedPath.pathId,
      subtitle: input.selectedPath.relationSequence.length
        ? input.selectedPath.relationSequence.join(" → ")
        : input.selectedPath.targetEntityName,
      pathId: input.selectedPath.pathId,
      focusNodeIds: input.selectedPath.nodeIds,
      focusEdgeIds: input.selectedPath.edgeIds,
    });
  }

  if (input.candidate) {
    steps.push({
      stepId: `candidate:${input.candidate.ranking_id}`,
      kind: "candidate",
      emphasis: "result",
      label: input.candidate.candidate_name,
      subtitle: normalizeText(input.candidate.candidate_role, "candidate"),
      candidateId: input.candidate.ranking_id,
      graphNodeId: input.candidate.candidate_id,
      focusNodeIds: input.candidate.candidate_id
        ? [input.candidate.candidate_id]
        : [],
      focusEdgeIds: [],
    });
  }

  return steps;
}

function addEntityOccurrence(
  entityMap: Map<string, EntityOccurrence>,
  entityId: string | null | undefined,
  entityName: string | null | undefined,
  pathId?: string | null,
  observationIds?: string[],
) {
  const normalizedEntityId = normalizeNullableText(entityId);
  if (!normalizedEntityId) {
    return;
  }

  const existing = entityMap.get(normalizedEntityId) ?? {
    entityId: normalizedEntityId,
    entityName: normalizeText(entityName, normalizedEntityId),
    matchedPathIds: new Set<string>(),
    matchedObservationIds: new Set<string>(),
  };

  if (pathId) {
    existing.matchedPathIds.add(pathId);
  }

  for (const observationId of observationIds ?? []) {
    if (observationId) {
      existing.matchedObservationIds.add(observationId);
    }
  }

  entityMap.set(normalizedEntityId, existing);
}

function buildEntityOccurrenceMap(
  caseDetail: RunCaseDetail,
  extractedPaths: ReasoningPathSummary[],
) {
  const entityMap = new Map<string, EntityOccurrence>();

  for (const path of extractedPaths) {
    path.nodeIds.forEach((nodeId, index) => {
      addEntityOccurrence(
        entityMap,
        nodeId,
        path.nodeNames[index] ?? nodeId,
        path.pathId,
        path.supportObservationIds,
      );
    });
  }

  const linkedEntities = Array.isArray(caseDetail.linked_entities)
    ? caseDetail.linked_entities.filter(isRecord)
    : [];
  for (const link of linkedEntities) {
    addEntityOccurrence(
      entityMap,
      normalizeNullableText(link.selected_entity_id),
      normalizeText(
        link.selected_entity_name,
        normalizeText(link.selected_entity_id),
      ),
      null,
      readStringArray(link.obs_id ? [link.obs_id] : []),
    );
  }

  const candidates = Array.isArray(caseDetail.ranked_root_causes)
    ? caseDetail.ranked_root_causes
    : [];
  for (const candidate of candidates) {
    addEntityOccurrence(
      entityMap,
      candidate.candidate_id,
      candidate.candidate_name,
      null,
      extractCandidateSupportingObservationIds(candidate),
    );
  }

  return entityMap;
}

export function buildPathSignature(input: {
  targetEntityId: string | null | undefined;
  relationSequence: string[] | null | undefined;
}) {
  const targetEntityId = normalizeText(input.targetEntityId, "unknown-target");
  const relationSequence =
    (input.relationSequence ?? []).filter(Boolean).join(">") || "no-relations";
  return `${targetEntityId}::${relationSequence}`;
}

function buildCrossCaseRecurrenceSummary(input: {
  runDetail: RunDetail | null | undefined;
  caseDetail: RunCaseDetail;
  candidate: RankedRootCause | null;
  selectedPath: ReasoningPathSummary | null;
  candidatePaths: ReasoningPathSummary[];
  linkedEntities: ReasoningLinkedEntitySummary[];
}) {
  const runDetail = input.runDetail;
  if (!runDetail) {
    return null;
  }

  const currentExtractedPaths = extractTopKPaths(input.caseDetail);
  const currentEntityMap = buildEntityOccurrenceMap(
    input.caseDetail,
    currentExtractedPaths,
  );
  const relevantEntityIds = uniqueStable(
    [
      ...(input.candidate?.candidate_id ? [input.candidate.candidate_id] : []),
      ...(input.selectedPath?.nodeIds ?? []),
      ...input.linkedEntities
        .map((item) => item.entityId)
        .filter((item): item is string => Boolean(item)),
    ],
    (item) => item,
  );

  const recurringEntities: RecurringEntitySummary[] = [];
  for (const entityId of relevantEntityIds) {
    const currentOccurrence = currentEntityMap.get(entityId);
    if (!currentOccurrence) {
      continue;
    }

    const caseHits: RecurrenceCaseHit[] = [];
    for (const caseItem of runDetail.cases) {
      if (caseItem.case_id === input.caseDetail.case_id) {
        continue;
      }

      const otherPaths = extractTopKPaths(caseItem);
      const otherEntityMap = buildEntityOccurrenceMap(caseItem, otherPaths);
      const otherOccurrence = otherEntityMap.get(entityId);
      if (!otherOccurrence) {
        continue;
      }

      caseHits.push({
        caseId: caseItem.case_id,
        caseLabel: caseItem.case_label ?? caseItem.label ?? caseItem.case_id,
        matchedPathIds: [...otherOccurrence.matchedPathIds],
        matchedObservationIds: [...otherOccurrence.matchedObservationIds],
        matchedEntityIds: [entityId],
      });
    }

    if (!caseHits.length) {
      continue;
    }

    recurringEntities.push({
      entityId,
      entityName: currentOccurrence.entityName,
      occurrenceCount: caseHits.length,
      currentObservationIds: [...currentOccurrence.matchedObservationIds],
      caseHits,
    });
  }

  const orderedCurrentPaths = uniqueStable(
    [
      ...(input.selectedPath ? [input.selectedPath] : []),
      ...input.candidatePaths,
    ],
    (item) => item.signature,
  );
  const recurringPaths: RecurringPathSummary[] = [];

  for (const currentPath of orderedCurrentPaths) {
    const caseHits: RecurrenceCaseHit[] = [];
    for (const caseItem of runDetail.cases) {
      if (caseItem.case_id === input.caseDetail.case_id) {
        continue;
      }

      const matchedPaths = extractTopKPaths(caseItem).filter(
        (item) => item.signature === currentPath.signature,
      );
      if (!matchedPaths.length) {
        continue;
      }

      caseHits.push({
        caseId: caseItem.case_id,
        caseLabel: caseItem.case_label ?? caseItem.label ?? caseItem.case_id,
        matchedPathIds: matchedPaths.map((item) => item.pathId),
        matchedObservationIds: uniqueStable(
          matchedPaths.flatMap((item) => item.supportObservationIds),
          (item) => item,
        ),
        matchedEntityIds: uniqueStable(
          matchedPaths.flatMap((item) => item.nodeIds),
          (item) => item,
        ),
      });
    }

    if (!caseHits.length) {
      continue;
    }

    recurringPaths.push({
      signature: currentPath.signature,
      targetEntityId: currentPath.targetEntityId,
      targetEntityName: currentPath.targetEntityName,
      relationSequence: currentPath.relationSequence,
      occurrenceCount: caseHits.length,
      caseHits,
    });
  }

  recurringEntities.sort((left, right) => {
    if (right.occurrenceCount !== left.occurrenceCount) {
      return right.occurrenceCount - left.occurrenceCount;
    }
    return left.entityName.localeCompare(right.entityName);
  });
  recurringPaths.sort((left, right) => {
    if (right.occurrenceCount !== left.occurrenceCount) {
      return right.occurrenceCount - left.occurrenceCount;
    }
    return left.targetEntityName.localeCompare(right.targetEntityName);
  });

  return {
    currentCaseId: input.caseDetail.case_id,
    currentCaseLabel:
      input.caseDetail.case_label ??
      input.caseDetail.label ??
      input.caseDetail.case_id,
    candidateId: input.candidate?.ranking_id ?? null,
    relatedCaseCount: Math.max(0, runDetail.cases.length - 1),
    recurringEntities,
    recurringPaths,
  };
}

export function buildGraphReasoningInspection(
  options: BuildGraphReasoningInspectionOptions,
): GraphReasoningInspectionResult {
  if (!options.caseDetail) {
    return {
      candidate: null,
      primaryObservation: null,
      supportingObservations: [],
      linkedEntities: [],
      selectedPath: null,
      traceSteps: [],
      crossCaseRecurrence: null,
    };
  }

  const caseDetail = options.caseDetail;
  const candidates = Array.isArray(caseDetail.ranked_root_causes)
    ? caseDetail.ranked_root_causes
    : [];
  const candidate =
    candidates.find(
      (item) => item.ranking_id === options.selectedCandidateId,
    ) ?? null;

  if (!candidate) {
    return {
      candidate: null,
      primaryObservation: null,
      supportingObservations: [],
      linkedEntities: [],
      selectedPath: null,
      traceSteps: [],
      crossCaseRecurrence: null,
    };
  }

  const extractedPaths = extractTopKPaths(caseDetail);
  const candidatePaths = extractedPaths.filter((item) =>
    doesPathMatchCandidate(item, candidate),
  );
  const preferredSelectedPath = options.selectedPathId
    ? (extractedPaths.find((item) => item.pathId === options.selectedPathId) ??
      null)
    : null;
  const selectedPath = preferredSelectedPath || candidatePaths[0] || null;
  const observationIndex = buildObservationInspectionIndex(
    caseDetail,
    uniqueStable(
      [
        ...(selectedPath?.supportObservationIds ?? []),
        ...candidatePaths.flatMap((item) => item.supportObservationIds),
        ...extractCandidateSupportingObservationIds(candidate),
        ...(options.selectedObservationId
          ? [options.selectedObservationId]
          : []),
      ],
      (item) => item,
    ),
  );
  const observationSupport = buildObservationSupportList(
    {
      caseDetail,
      candidate,
      selectedPath,
      candidatePaths,
      selectedObservationId: options.selectedObservationId,
    },
    observationIndex,
  );
  const linkedEntities = buildLinkedEntityList(
    observationSupport.supportingObservations,
    observationIndex,
  );
  const candidateSummary: CandidateInspectionSummary = {
    candidateId: candidate.candidate_id,
    rankingId: candidate.ranking_id,
    candidateName: candidate.candidate_name,
    rank: typeof candidate.rank === "number" ? candidate.rank : null,
    score: normalizeNumber(candidate.score),
    scoringMethod: normalizeNullableText(candidate.scoring_method),
    role: normalizeNullableText(candidate.candidate_role),
    linkedEntityCount: uniqueStable(
      linkedEntities
        .map((item) => item.entityId)
        .filter((item): item is string => Boolean(item)),
      (item) => item,
    ).length,
    supportingObservationCount:
      observationSupport.supportingObservations.length,
    selectedPathId: selectedPath?.pathId ?? null,
  };

  return {
    candidate: candidateSummary,
    primaryObservation: observationSupport.primaryObservation,
    supportingObservations: observationSupport.supportingObservations,
    linkedEntities,
    selectedPath,
    traceSteps: buildTraceSteps({
      candidate,
      primaryObservation: observationSupport.primaryObservation,
      supportingObservations: observationSupport.supportingObservations,
      linkedEntities,
      selectedPath,
    }),
    crossCaseRecurrence: buildCrossCaseRecurrenceSummary({
      runDetail: options.runDetail,
      caseDetail,
      candidate,
      selectedPath,
      candidatePaths,
      linkedEntities,
    }),
  };
}
