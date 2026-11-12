import type { PathGraphPath, RunCaseDetail } from "@/api/contracts";
import type { UnifiedGraphDataset, UnifiedGraphEdge } from "@/types/graph";
import {
  buildGraphPathProvenance,
  type ProvenanceInspectorState,
  type ProvenanceRecord,
} from "@/services/provenance-inspector";
import { matchKnowledgeEdges } from "@/services/graph-workspace";

/** Path source/target node IDs are not document provenance. Resolve exact KG edges instead. */
export function buildWorkspaceProvenance(
  caseDetail: RunCaseDetail | null,
  path: PathGraphPath | null,
  dataset: UnifiedGraphDataset | null,
  selectedEdgeId?: string | null,
): ProvenanceInspectorState | null {
  if (!caseDetail) return null;
  const original = buildGraphPathProvenance({
    caseDetail,
    pathId: path?.path_id,
    claimBoundary: "候选解释，非已验证根因",
  });
  const direct = dataset?.edges.find((e) => e.id === selectedEdgeId);
  const pathEdges = selectedEdgeId
    ? (path?.edges.filter((e) => e.edge_id === selectedEdgeId) ?? [])
    : (path?.edges ?? []);
  const resolved = direct
    ? [direct]
    : pathEdges.flatMap((e) => matchKnowledgeEdges(e, dataset));
  const records: ProvenanceRecord[] = (original?.records ?? []).filter((r) =>
    ["raw_evidence_ref", "visual_evidence"].includes(r.sourceType),
  );
  const seen = new Set<string>();
  for (const edge of resolved) {
    if (seen.has(edge.id)) continue;
    seen.add(edge.id);
    records.push(knowledgeRecord(edge));
  }
  for (const missing of pathEdges.filter(
    (edge) => !matchKnowledgeEdges(edge, dataset).length,
  ))
    records.push({
      recordId: `missing-knowledge-source:${missing.edge_id}`,
      sourceType: "edge_provenance",
      sourceLabel: `${missing.relation} · 当前快照未找到对应知识关系`,
      sourcePathOrId: "",
      snippetOrPreview: null,
      previewUrl: null,
      confidence: null,
      claimBoundary: "缺少来源，需进一步核验",
      reviewTargetKey: null,
      tags: ["missing-source"],
      multiline: false,
    });
  return {
    targetKind: selectedEdgeId ? "edge" : "path",
    targetId: selectedEdgeId ?? path?.path_id ?? caseDetail.case_id,
    summary: selectedEdgeId
      ? "当前知识关系"
      : (original?.summary ?? "当前解释"),
    contextLabel: caseDetail.case_label ?? caseDetail.case_id,
    linkedReviewTarget: original?.linkedReviewTarget ?? null,
    claimBoundary: "候选解释，非已验证根因",
    records,
    semanticNotes: original?.semanticNotes ?? [],
  };
}
function knowledgeRecord(edge: UnifiedGraphEdge): ProvenanceRecord {
  const source =
    typeof edge.attributes.source === "string" ? edge.attributes.source : "";
  const evidence =
    typeof edge.attributes.evidence === "string"
      ? edge.attributes.evidence
      : null;
  const isDraft = edge.attributes.draft === true;
  return {
    recordId: `knowledge:${edge.id}`,
    sourceType: "edge_provenance",
    sourceLabel: edge.relation,
    sourcePathOrId: source,
    snippetOrPreview: evidence,
    previewUrl: null,
    confidence: edge.confidence,
    claimBoundary: isDraft
      ? "人工草稿，未发布"
      : source && evidence
        ? "来源可查，仍为候选知识"
        : "来源不完整",
    reviewTargetKey:
      typeof edge.attributes.target_key === "string"
        ? edge.attributes.target_key
        : null,
    tags: [
      isDraft
        ? "draft"
        : source && evidence
          ? "source-grounded"
          : "missing-source",
    ],
    multiline: false,
  };
}
