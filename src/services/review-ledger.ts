import type {
  ReviewAction,
  ReviewLedgerRecord,
  ReviewTargetType,
  RunCaseDetail,
} from "@/api/contracts";

export type BoundedReviewTargetType =
  | "path"
  | "edge"
  | "entity_link"
  | "correction";
export type ReviewLedgerTargetFilter = "all" | BoundedReviewTargetType;

export interface ReviewLedgerDisplayItem extends ReviewLedgerRecord {
  targetTypeLabel: string;
  actionLabel: string;
  title: string;
  subtitle: string;
  targetAvailable: boolean;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function normalizeText(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.trim().length
    ? value.trim()
    : fallback;
}

function readStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value.map((item) => normalizeText(item)).filter(Boolean);
}

export function isBoundedReviewTargetType(
  value: string | null | undefined,
): value is BoundedReviewTargetType {
  return (
    value === "path" ||
    value === "edge" ||
    value === "entity_link" ||
    value === "correction"
  );
}

export function formatReviewLedgerTargetType(value: ReviewTargetType | string) {
  switch (value) {
    case "path":
      return "Path";
    case "edge":
      return "Edge";
    case "entity_link":
      return "Entity Link";
    case "correction":
      return "Correction";
    default:
      return value;
  }
}

export function formatReviewLedgerAction(value: ReviewAction | string) {
  switch (value) {
    case "accept":
      return "接受";
    case "reject":
      return "拒绝";
    case "needs_review":
      return "needs_review";
    default:
      return value;
  }
}

function sortByCreatedAtDesc(
  left: ReviewLedgerRecord,
  right: ReviewLedgerRecord,
) {
  const leftTime = Date.parse(left.created_at);
  const rightTime = Date.parse(right.created_at);

  if (Number.isNaN(leftTime) || Number.isNaN(rightTime)) {
    return right.created_at.localeCompare(left.created_at);
  }

  return rightTime - leftTime;
}

export function filterReviewLedgerRecords(
  records: ReviewLedgerRecord[],
  filterTargetType: ReviewLedgerTargetFilter,
) {
  const boundedRecords = records.filter((item) =>
    isBoundedReviewTargetType(item.target_type),
  );

  if (filterTargetType === "all") {
    return [...boundedRecords].sort(sortByCreatedAtDesc);
  }

  return boundedRecords
    .filter((item) => item.target_type === filterTargetType)
    .sort(sortByCreatedAtDesc);
}

function resolvePathTitle(
  caseDetail: RunCaseDetail | null | undefined,
  targetId: string,
) {
  const pathRecord =
    (Array.isArray(caseDetail?.top_k_paths)
      ? caseDetail?.top_k_paths.find(
          (item) => isRecord(item) && item.path_id === targetId,
        )
      : null) ?? null;
  const pathGraphRecord =
    caseDetail?.path_graph?.paths.find((item) => item.path_id === targetId) ??
    null;
  const relationSequence = readStringArray(pathRecord?.relations);
  const pathLabel = normalizeText(pathRecord?.target_entity_name);
  const lastPathNode =
    pathGraphRecord && pathGraphRecord.nodes.length
      ? pathGraphRecord.nodes[pathGraphRecord.nodes.length - 1]
      : null;
  const targetLabel = normalizeText(lastPathNode?.label);

  if (pathRecord || pathGraphRecord) {
    return {
      title: pathLabel || targetLabel || targetId,
      subtitle: relationSequence.join(" → ") || targetId,
      targetAvailable: true,
    };
  }

  return {
    title: targetId,
    subtitle: "该 path 已不在当前 case 结果中。",
    targetAvailable: false,
  };
}

function resolveEdgeTitle(
  caseDetail: RunCaseDetail | null | undefined,
  targetId: string,
) {
  const sourceEdge =
    (Array.isArray(caseDetail?.source_edge_provenance)
      ? caseDetail?.source_edge_provenance.find(
          (item) => isRecord(item) && normalizeText(item.edge_id) === targetId,
        )
      : null) ?? null;
  const pathEdge =
    caseDetail?.path_graph?.paths
      .flatMap((item) => item.edges)
      .find((item) => item.edge_id === targetId) ?? null;

  if (sourceEdge || pathEdge) {
    const source = normalizeText(sourceEdge?.source, pathEdge?.source_node_id);
    const relation = normalizeText(sourceEdge?.relation, pathEdge?.relation);
    const target = normalizeText(sourceEdge?.target, pathEdge?.target_node_id);
    return {
      title: `${source} —${relation}→ ${target}`,
      subtitle: normalizeText(sourceEdge?.evidence, targetId) || targetId,
      targetAvailable: true,
    };
  }

  return {
    title: targetId,
    subtitle: "该 edge 已不在当前 case 结果中。",
    targetAvailable: false,
  };
}

function resolveEntityLinkTitle(
  caseDetail: RunCaseDetail | null | undefined,
  targetId: string,
) {
  const link =
    (Array.isArray(caseDetail?.linked_entities)
      ? caseDetail?.linked_entities.find(
          (item) => isRecord(item) && normalizeText(item.link_id) === targetId,
        )
      : null) ?? null;

  if (link) {
    return {
      title:
        normalizeText(link.selected_entity_name) ||
        normalizeText(link.selected_entity_id) ||
        targetId,
      subtitle: `${normalizeText(link.field, "field")} · ${normalizeText(link.mention, "--")}`,
      targetAvailable: true,
    };
  }

  return {
    title: targetId,
    subtitle: "该 entity link 已不在当前 case 结果中。",
    targetAvailable: false,
  };
}

function resolveCorrectionTitle(
  caseDetail: RunCaseDetail | null | undefined,
  targetId: string,
) {
  const correction =
    (Array.isArray(caseDetail?.correction_candidates)
      ? caseDetail?.correction_candidates.find(
          (item) =>
            isRecord(item) && normalizeText(item.candidate_id) === targetId,
        )
      : null) ?? null;

  if (correction) {
    return {
      title: normalizeText(correction.suggested_value, targetId),
      subtitle: normalizeText(correction.reason, targetId),
      targetAvailable: true,
    };
  }

  return {
    title: targetId,
    subtitle: "该 correction 已不在当前 case 结果中。",
    targetAvailable: false,
  };
}

export function buildReviewLedgerDisplayItems(
  records: ReviewLedgerRecord[],
  caseDetail: RunCaseDetail | null | undefined,
): ReviewLedgerDisplayItem[] {
  return [...records]
    .filter((item) => isBoundedReviewTargetType(item.target_type))
    .sort(sortByCreatedAtDesc)
    .map((item) => {
      const resolved =
        item.target_type === "path"
          ? resolvePathTitle(caseDetail, item.target_id)
          : item.target_type === "edge"
            ? resolveEdgeTitle(caseDetail, item.target_id)
            : item.target_type === "entity_link"
              ? resolveEntityLinkTitle(caseDetail, item.target_id)
              : resolveCorrectionTitle(caseDetail, item.target_id);

      return {
        ...item,
        targetTypeLabel: formatReviewLedgerTargetType(item.target_type),
        actionLabel: formatReviewLedgerAction(item.action),
        title: resolved.title,
        subtitle: resolved.subtitle,
        targetAvailable: resolved.targetAvailable,
      };
    });
}
