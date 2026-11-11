import type {
  KGMaterialChunkListResponse,
  KGMaterialChunkRecord,
  KGMaterialDetailResponse,
  KGMaterialExtractionArtifactListResponse,
  KGMaterialExtractionArtifactRecord,
  KGMaterialExtractionRunListResponse,
  KGMaterialExtractionRunRecord,
  KGMaterialListResponse,
  KGMaterialRecord,
  PathGraph,
  RankedRootCause,
  ReviewLedgerListRequest,
  ReviewLedgerListResponse,
  ReviewLedgerRecord,
  ReviewRequest,
  ReviewTarget,
  ReviewTargetType,
  RunCaseDetail,
  RunDetail,
  RunReasoningMetadata,
  RunSummary,
  UploadMode,
  VisualEvidenceItem,
} from "@/api/contracts";
import {
  getLocalSessionMeta,
  loadStoredImportedRuntime,
  loadBundledRootLensRuntime,
} from "@/services/rootlens-data";
import type {
  RootKGDCandidate,
  RootLensRuntimeCase,
  RootLensRuntimeFile,
  RankedPath,
} from "@/types/rootlens";
import heroImage from "@/assets/hero.png";

const CLAIM_BOUNDARY =
  "candidate/plausible explanation only; not a verified root-cause label";
const MOCK_STORAGE_KEY = "rootlens.mock-backend-state";
const PAPER_DEMO_RUN_ID = "paper-demo-curated";
const IMPORTED_REPLAY_RUN_ID = "imported-runtime-replay";
const PAPER_DEMO_CASE_IDS = [
  "mvtec_fixture_clean_scratch",
  "mvtec_noisy_0001",
  "tep_0001",
  "wafer_0001",
] as const;
const REVIEWABLE_FEEDBACK_TARGETS = new Set<ReviewTargetType>([
  "path",
  "edge",
  "entity_link",
  "correction",
  "root_cause_candidate",
]);

interface MockFeedbackRecord {
  feedback_id: string;
  created_at: string;
  request: ReviewRequest;
}

interface MockPersistentState extends Record<string, unknown> {
  feedback_records: MockFeedbackRecord[];
  material_records: KGMaterialRecord[];
  material_chunks: KGMaterialChunkRecord[];
  material_extraction_runs: KGMaterialExtractionRunRecord[];
  material_artifacts: KGMaterialExtractionArtifactRecord[];
}

let demoRuns: Promise<RunDetail[]> | null = null;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function normalizeNullableText(value: unknown): string | null {
  return typeof value === "string" && value.trim().length ? value.trim() : null;
}

function normalizeNullableBoolean(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

function readReasoningMetadata(value: unknown): RunReasoningMetadata | null {
  if (!isRecord(value)) {
    return null;
  }

  return {
    reasoning_profile_id: normalizeNullableText(value.reasoning_profile_id),
    reasoner_adapter: normalizeNullableText(value.reasoner_adapter),
    selection_mode: normalizeNullableText(value.selection_mode),
    requested_reasoning_profile_id: normalizeNullableText(
      value.requested_reasoning_profile_id,
    ),
    requested_reasoner_adapter: normalizeNullableText(
      value.requested_reasoner_adapter,
    ),
    fallback_applied: normalizeNullableBoolean(value.fallback_applied),
    fallback_reason: normalizeNullableText(value.fallback_reason),
  };
}

function inferReasoningProfileForDataset(dataset: string | null | undefined) {
  const normalized = normalizeText(dataset).toLowerCase();
  if (normalized === "tep") {
    return {
      reasoning_profile_id: "tep_root_kgd_default",
      reasoner_adapter: "tep_root_kgd",
    } satisfies Pick<
      RunReasoningMetadata,
      "reasoning_profile_id" | "reasoner_adapter"
    >;
  }

  return {
    reasoning_profile_id: "generic_graph_path_default",
    reasoner_adapter: "generic_graph_path",
  } satisfies Pick<
    RunReasoningMetadata,
    "reasoning_profile_id" | "reasoner_adapter"
  >;
}

function buildCaseReasoningMetadata(
  caseItem: RootLensRuntimeCase,
): RunReasoningMetadata {
  const caseRecord = caseItem as unknown as Record<string, unknown>;
  const caseLevel = readReasoningMetadata(caseRecord.reasoning_metadata);
  const analysisLevel = readReasoningMetadata(
    isRecord(caseRecord.analysis) ? caseRecord.analysis.reasoning_metadata : null,
  );
  const inferred = inferReasoningProfileForDataset(caseItem.dataset);

  return {
    reasoning_profile_id:
      caseLevel?.reasoning_profile_id ??
      analysisLevel?.reasoning_profile_id ??
      inferred.reasoning_profile_id,
    reasoner_adapter:
      caseLevel?.reasoner_adapter ??
      analysisLevel?.reasoner_adapter ??
      inferred.reasoner_adapter,
    selection_mode:
      caseLevel?.selection_mode ?? analysisLevel?.selection_mode ?? "default",
    requested_reasoning_profile_id:
      caseLevel?.requested_reasoning_profile_id ??
      analysisLevel?.requested_reasoning_profile_id ??
      null,
    requested_reasoner_adapter:
      caseLevel?.requested_reasoner_adapter ??
      analysisLevel?.requested_reasoner_adapter ??
      null,
    fallback_applied:
      caseLevel?.fallback_applied ?? analysisLevel?.fallback_applied ?? false,
    fallback_reason:
      caseLevel?.fallback_reason ?? analysisLevel?.fallback_reason ?? null,
  };
}

function buildRunReasoningMetadata(caseDetails: RunCaseDetail[]) {
  const firstCaseMetadata = caseDetails[0]?.reasoning_metadata ?? null;
  const inferred = inferReasoningProfileForDataset(caseDetails[0]?.dataset);

  return {
    reasoning_profile_id:
      firstCaseMetadata?.reasoning_profile_id ?? inferred.reasoning_profile_id,
    reasoner_adapter:
      firstCaseMetadata?.reasoner_adapter ?? inferred.reasoner_adapter,
    selection_mode: firstCaseMetadata?.selection_mode ?? "default",
  };
}

function normalizeText(value: unknown, fallback = ""): string {
  if (typeof value !== "string") {
    return fallback;
  }

  const normalized = value.trim();
  return normalized.length ? normalized : fallback;
}

function toIsoDate(offsetMinutes: number): string {
  return new Date(Date.now() - offsetMinutes * 60_000).toISOString();
}

function reviewTargetKey(targetType: string, targetId: string) {
  return `${targetType}:${targetId}`;
}

function uniqueByKey<T>(items: T[], getKey: (item: T) => string): T[] {
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

function readPersistentState(): MockPersistentState {
  let parsed: Record<string, unknown> = {};
  try {
    const data: unknown = JSON.parse(window.localStorage.getItem(MOCK_STORAGE_KEY) ?? "null");
    if (isRecord(data)) parsed = data;
  } catch { /* No readable local state. */ }
  const rows = <T>(key: string): T[] => Array.isArray(parsed[key]) ? parsed[key] as T[] : [];
  return {
    // Keep existing local records even when their former workbench UI is gone.
    ...parsed,
    feedback_records: rows<MockFeedbackRecord>("feedback_records"),
    material_records: rows<KGMaterialRecord>("material_records"),
    material_chunks: rows<KGMaterialChunkRecord>("material_chunks"),
    material_extraction_runs: rows<KGMaterialExtractionRunRecord>("material_extraction_runs"),
    material_artifacts: rows<KGMaterialExtractionArtifactRecord>("material_artifacts"),
  };
}

function writePersistentState(state: MockPersistentState) {
  if (
    typeof window === "undefined" ||
    typeof window.localStorage === "undefined"
  ) {
    return;
  }

  window.localStorage.setItem(MOCK_STORAGE_KEY, JSON.stringify(state));
}

function detectPathScoringMethod(caseItem: RootLensRuntimeCase): string {
  if (caseItem.dataset === "tep") {
    return "relation_weighted_path";
  }
  if (caseItem.dataset === "mvtec") {
    return "artifact_bridge";
  }
  return "heuristic_path_support";
}

function buildTopKPaths(
  caseItem: RootLensRuntimeCase,
): Array<Record<string, unknown>> {
  const rankedPaths = caseItem.analysis.route1?.ranked_paths ?? [];

  return rankedPaths.map((path) => ({
    path_id: path.path_id,
    source_entity_id: path.source_entity_id,
    target_entity_id: path.target_entity_id,
    target_entity_name: path.target_entity_name,
    score: path.score,
    confidence: path.confidence,
    evidence_match: path.evidence_match,
    length: path.length,
    nodes: path.nodes,
    node_names: path.node_names,
    relations: path.relations,
    source_edges: path.source_edges.map((edge) => ({
      edge_id: edge.edge_id,
      source: edge.source,
      target: edge.target,
      relation: edge.relation,
      confidence: edge.confidence,
      evidence: `${edge.relation} supports ${path.target_entity_name}`,
      review_status: "auto",
    })),
    supporting_evidence: path.support_obs_ids,
  }));
}

function buildRootCauseFromPath(
  path: RankedPath,
  rank: number,
  caseItem: RootLensRuntimeCase,
): RankedRootCause {
  return {
    ranking_id: `ranking:${path.path_id}`,
    rank,
    candidate_id: path.target_entity_id,
    candidate_name: path.target_entity_name,
    candidate_label: path.target_entity_name,
    candidate_role:
      caseItem.dataset === "mvtec"
        ? "plausible_mechanism"
        : "candidate_root_cause",
    score: path.score,
    confidence: path.confidence,
    evidence_match: path.evidence_match,
    explanation_paths: [path.nodes],
    supporting_edges: path.source_edges,
    supporting_evidence: path.support_obs_ids,
    scoring_method: detectPathScoringMethod(caseItem),
    scoring_details: {
      path_length: path.length,
      relation_count: path.relations.length,
    },
    source: "mock-derived-path-ranking",
    review_status: "pending",
  };
}

function buildRootCauseFromRoute2(
  candidate: RootKGDCandidate,
): RankedRootCause {
  return {
    ranking_id: `ranking:${candidate.candidate_id}`,
    rank: candidate.rank,
    candidate_id: candidate.candidate_id,
    candidate_name: candidate.candidate_name,
    candidate_label: candidate.candidate_name,
    candidate_role: candidate.candidate_role,
    score: candidate.ranking_score,
    confidence: Math.max(0.35, Math.min(0.98, candidate.root_score)),
    evidence_match: candidate.covered_contribution_mass,
    explanation_paths: candidate.top_support_paths,
    supporting_edges: candidate.top_support_paths.map((path) => ({ path })),
    supporting_evidence: candidate.support_evidence_ids,
    scoring_method: "tep_root_kgd",
    scoring_details: {
      root_score: candidate.root_score,
      ranking_adjustment: candidate.ranking_adjustment,
      covered_contribution_mass: candidate.covered_contribution_mass,
      active_variable_count: candidate.active_variable_count,
      scenario_id: candidate.scenario_id,
    },
    source: "mock-route2-candidate",
    review_status: "pending",
  };
}

function buildRankedRootCauses(
  caseItem: RootLensRuntimeCase,
): RankedRootCause[] {
  const route2Candidates = caseItem.analysis.route2?.ranked_candidates ?? [];
  if (route2Candidates.length) {
    return route2Candidates
      .slice(0, 6)
      .map((candidate) => buildRootCauseFromRoute2(candidate));
  }

  const route1Paths = caseItem.analysis.route1?.ranked_paths ?? [];
  return route1Paths
    .slice(0, 6)
    .map((path, index) => buildRootCauseFromPath(path, index + 1, caseItem));
}

function collectSourceEdgeProvenance(
  topKPaths: Array<Record<string, unknown>>,
): Array<Record<string, unknown>> {
  const edges: Array<Record<string, unknown>> = [];

  for (const path of topKPaths) {
    const sourceEdges = Array.isArray(path.source_edges)
      ? path.source_edges
      : [];
    for (const edge of sourceEdges) {
      if (isRecord(edge)) {
        edges.push(edge);
      }
    }
  }

  return uniqueByKey(edges, (edge) => normalizeText(edge.edge_id));
}

function pathGraphFromPaths(
  topKPaths: Array<Record<string, unknown>>,
): PathGraph {
  const paths: PathGraph["paths"] = [];
  const edgeIds = new Set<string>();
  const nodeIds = new Set<string>();

  topKPaths.forEach((path, index) => {
    const pathId = normalizeText(path.path_id, `path_${index}`);
    const nodes = Array.isArray(path.nodes)
      ? path.nodes.map((item) => String(item))
      : [];
    const nodeNames = Array.isArray(path.node_names)
      ? path.node_names.map((item) => String(item))
      : [];
    const relations = Array.isArray(path.relations)
      ? path.relations.map((item) => String(item))
      : [];
    const sourceEdges = Array.isArray(path.source_edges)
      ? path.source_edges
      : [];

    const graphNodes = nodes.map((nodeId, nodeIndex) => {
      nodeIds.add(nodeId);
      return {
        node_id: nodeId,
        label: nodeNames[nodeIndex] ?? nodeId,
        role:
          nodeIndex === 0
            ? "source"
            : nodeIndex === nodes.length - 1
              ? "target"
              : "intermediate",
      };
    });

    const graphEdges = relations.map((relation, edgeIndex) => {
      const sourceEdge = sourceEdges[edgeIndex];
      const sourceRecord = isRecord(sourceEdge) ? sourceEdge : {};
      const edgeId = normalizeText(
        sourceRecord.edge_id,
        `${nodes[edgeIndex] ?? "node"}|${relation}|${nodes[edgeIndex + 1] ?? "node"}|${pathId}`,
      );
      edgeIds.add(edgeId);
      return {
        edge_id: edgeId,
        target_key: reviewTargetKey("edge", edgeId),
        source_node_id: nodes[edgeIndex] ?? "",
        target_node_id: nodes[edgeIndex + 1] ?? "",
        relation,
        source:
          typeof sourceRecord.source === "string" ? sourceRecord.source : null,
        evidence:
          typeof sourceRecord.evidence === "string"
            ? sourceRecord.evidence
            : null,
        confidence:
          typeof sourceRecord.confidence === "number"
            ? sourceRecord.confidence
            : null,
        review_status:
          typeof sourceRecord.review_status === "string"
            ? sourceRecord.review_status
            : "auto",
      };
    });

    paths.push({
      path_id: pathId,
      target_key: reviewTargetKey("path", pathId),
      source_entity_id:
        typeof path.source_entity_id === "string"
          ? path.source_entity_id
          : null,
      target_entity_id:
        typeof path.target_entity_id === "string"
          ? path.target_entity_id
          : null,
      score: typeof path.score === "number" ? path.score : null,
      confidence: typeof path.confidence === "number" ? path.confidence : null,
      supporting_evidence: Array.isArray(path.supporting_evidence)
        ? path.supporting_evidence
        : [],
      nodes: graphNodes,
      edges: graphEdges,
    });
  });

  return {
    paths,
    path_count: paths.length,
    node_count: nodeIds.size,
    edge_count: edgeIds.size,
  };
}

function reviewTargetsFromArtifacts(input: {
  linkedEntities: Array<Record<string, unknown>>;
  correctionCandidates: Array<Record<string, unknown>>;
  topKPaths: Array<Record<string, unknown>>;
  sourceEdges: Array<Record<string, unknown>>;
  rankedRootCauses: RankedRootCause[];
}): ReviewTarget[] {
  const targets: ReviewTarget[] = [];

  input.topKPaths.forEach((path) => {
    const pathId = normalizeText(path.path_id);
    if (!pathId) {
      return;
    }

    targets.push({
      target_type: "path",
      target_id: pathId,
      target_key: reviewTargetKey("path", pathId),
      label: normalizeText(path.target_entity_name, pathId),
    });
  });

  input.rankedRootCauses.forEach((rootCause) => {
    const rankingId = normalizeText(
      rootCause.ranking_id || rootCause.candidate_id,
    );
    if (!rankingId) {
      return;
    }

    targets.push({
      target_type: "root_cause_candidate",
      target_id: rankingId,
      target_key: reviewTargetKey("root_cause_candidate", rankingId),
      label: normalizeText(rootCause.candidate_name, rankingId),
    });
  });

  input.sourceEdges.forEach((edge) => {
    const edgeId = normalizeText(edge.edge_id);
    if (!edgeId) {
      return;
    }

    targets.push({
      target_type: "edge",
      target_id: edgeId,
      target_key: reviewTargetKey("edge", edgeId),
      label: normalizeText(edge.relation, edgeId),
    });
  });

  input.linkedEntities.forEach((link) => {
    const linkId = normalizeText(link.link_id ?? link.field);
    if (!linkId) {
      return;
    }

    targets.push({
      target_type: "entity_link",
      target_id: linkId,
      target_key: reviewTargetKey("entity_link", linkId),
      label: normalizeText(
        link.selected_entity_name ?? link.selected_entity_id ?? linkId,
        linkId,
      ),
    });
  });

  input.correctionCandidates.forEach((candidate) => {
    const candidateId = normalizeText(candidate.candidate_id);
    if (!candidateId) {
      return;
    }

    targets.push({
      target_type: "correction",
      target_id: candidateId,
      target_key: reviewTargetKey("correction", candidateId),
      label: normalizeText(candidate.suggested_value, candidateId),
    });
  });

  return uniqueByKey(targets, (target) => target.target_key);
}

function buildVisualEvidence(
  caseItem: RootLensRuntimeCase,
): VisualEvidenceItem[] {
  if (caseItem.dataset === "tep") {
    return [];
  }

  const titlePrefix = caseItem.dataset === "mvtec" ? "MVTec" : "晶圆";
  const baseId = `${caseItem.case_id}-visual`;

  return [
    {
      artifact_id: `${baseId}-image`,
      case_id: caseItem.case_id,
      dataset: caseItem.dataset,
      kind: caseItem.dataset === "mvtec" ? "image" : "wafer_map",
      title: `${titlePrefix} 观测预览`,
      source_key: caseItem.case_id,
      source_path: `/generated/evidence/${caseItem.case_id}.json`,
      url: heroImage,
      preview_path: heroImage,
      available: true,
      note: "用于前端演示的模拟预览素材。",
      metadata: {
        mode: "mock",
      },
    },
    {
      artifact_id: `${baseId}-heatmap`,
      case_id: caseItem.case_id,
      dataset: caseItem.dataset,
      kind: caseItem.dataset === "mvtec" ? "heatmap" : "wafer_map",
      title: `${titlePrefix} 辅助可视化`,
      source_key: `${caseItem.case_id}-support`,
      source_path: null,
      url: heroImage,
      preview_path: heroImage,
      available: true,
      note: "用于前端演示的模拟辅助可视化。",
      metadata: {
        mode: "mock",
      },
    },
  ];
}

function buildCaseDetail(caseItem: RootLensRuntimeCase): RunCaseDetail {
  const linkedEntities = deepClone(
    (caseItem.analysis.route1?.linked_entities ?? []) as unknown as Array<
      Record<string, unknown>
    >,
  );
  const correctionCandidates = deepClone(
    (caseItem.analysis.route1?.correction_candidates ?? []) as unknown as Array<
      Record<string, unknown>
    >,
  );
  const topKPaths = buildTopKPaths(caseItem);
  const rankedRootCauses = buildRankedRootCauses(caseItem);
  const sourceEdgeProvenance = collectSourceEdgeProvenance(topKPaths);
  const pathGraph = pathGraphFromPaths(topKPaths);
  const reviewTargets = reviewTargetsFromArtifacts({
    linkedEntities,
    correctionCandidates,
    topKPaths,
    sourceEdges: sourceEdgeProvenance,
    rankedRootCauses,
  });
  const visualEvidence = buildVisualEvidence(caseItem);
  const reasoningMetadata = buildCaseReasoningMetadata(caseItem);

  return {
    case_id: caseItem.case_id,
    dataset: caseItem.dataset,
    label: caseItem.case_label,
    case_label: caseItem.case_label,
    source: caseItem.source,
    generated_evidence: deepClone(
      caseItem.evidence as unknown as Record<string, unknown>,
    ),
    generated_evidence_path: `/generated/evidence/${caseItem.case_id}.json`,
    linked_entities: linkedEntities,
    consistency_score: caseItem.analysis.route1?.consistency_score ?? null,
    inconsistent_fields: caseItem.analysis.route1?.inconsistent_fields ?? [],
    correction_candidates: correctionCandidates,
    top_k_paths: topKPaths,
    ranked_root_causes: rankedRootCauses,
    source_edge_provenance: sourceEdgeProvenance,
    path_graph: pathGraph,
    review_targets: reviewTargets,
    visual_evidence: visualEvidence,
    reasoning_metadata: reasoningMetadata,
    analysis_notes: caseItem.analysis.notes,
  };
}

function buildRunSummary(config: {
  runId: string;
  createdAt: string;
  mode: UploadMode;
  sourceFilename: string;
  label: string;
  topK: number;
  dataset: string | null;
  caseCount: number;
  evidenceCount: number;
  modelPreset?: string | null;
  modelBackend?: string | null;
}): RunSummary {
  return {
    run_id: config.runId,
    created_at: config.createdAt,
    mode: config.mode,
    source_filename: config.sourceFilename,
    top_k: config.topK,
    run_dir: `mock://${config.runId}`,
    status: "completed",
    dataset: config.dataset,
    case_count: config.caseCount,
    evidence_count: config.evidenceCount,
    label: config.label,
    model_preset: config.modelPreset ?? null,
    model_backend: config.modelBackend ?? null,
  };
}

function buildWorkflowSteps(
  run: RunSummary,
  caseCount: number,
): RunDetail["workflow_steps"] {
  if (run.run_id === PAPER_DEMO_RUN_ID) {
    return [
      {
        step_id: "curated_cases",
        title: "已装载论文案例",
        status: "completed",
        summary: `${caseCount} 个预设 case 已就绪，可直接截图和切换场景。`,
        details: {
          case_count: caseCount,
          mode: "paper-demo-curated",
        },
      },
      {
        step_id: "graph_snapshot",
        title: "静态图谱快照",
        status: "completed",
        summary: "总图谱与 path_graph 均来自已提交的静态资产快照。",
        details: {
          graph_source: "public/generated",
        },
      },
      {
        step_id: "analysis",
        title: "RCA 结果就绪",
        status: "completed",
        summary: "候选根因、路径和反馈目标均已预先生成，可直接联动查看。",
        details: {
          review_targets_ready: true,
        },
      },
    ];
  }

  return [
    {
      step_id: "upload",
      title: "已接收上传",
      status: "completed",
      summary: `${run.source_filename} 已按 ${run.mode} 模式接入。`,
      details: {
        dataset: run.dataset,
        case_count: caseCount,
      },
    },
    {
      step_id: "analysis",
      title: "图谱分析",
      status: "completed",
      summary: "模拟链路已生成可复核的 RCA 候选和路径图。",
      details: {
        top_k: run.top_k,
      },
    },
    {
      step_id: "enrichment",
      title: "运行补充",
      status: "completed",
      summary: "证据摘要、反馈目标和可视证据载荷已准备完成。",
      details: {
        review_targets_ready: true,
      },
    },
  ];
}

function aggregateCases(caseDetails: RunCaseDetail[]) {
  const firstCase = caseDetails[0] ?? null;
  const topKPaths = caseDetails
    .flatMap((item) => item.top_k_paths ?? [])
    .slice(0, 24);
  const rankedRootCauses = caseDetails
    .flatMap((item) => item.ranked_root_causes ?? [])
    .slice(0, 24);
  const linkedEntities = caseDetails
    .flatMap((item) => item.linked_entities ?? [])
    .slice(0, 48);
  const correctionCandidates = caseDetails
    .flatMap((item) => item.correction_candidates ?? [])
    .slice(0, 48);
  const sourceEdgeProvenance = uniqueByKey(
    caseDetails.flatMap((item) => item.source_edge_provenance ?? []),
    (edge) => normalizeText(edge.edge_id),
  );
  const reviewTargets = uniqueByKey(
    caseDetails.flatMap((item) => item.review_targets ?? []),
    (target) => target.target_key,
  );
  const visualEvidence = caseDetails.flatMap(
    (item) => item.visual_evidence ?? [],
  );

  return {
    firstCase,
    topKPaths,
    rankedRootCauses,
    linkedEntities,
    correctionCandidates,
    sourceEdgeProvenance,
    reviewTargets,
    visualEvidence,
  };
}

function buildRunDetail(config: {
  runId: string;
  createdAt: string;
  mode: UploadMode;
  sourceFilename: string;
  label: string;
  topK: number;
  dataset: string | null;
  cases: RootLensRuntimeCase[];
  modelPreset?: string | null;
  modelBackend?: string | null;
}): RunDetail {
  const caseDetails = config.cases.map((caseItem) => buildCaseDetail(caseItem));
  const aggregate = aggregateCases(caseDetails);
  const runReasoningMetadata = buildRunReasoningMetadata(caseDetails);
  const run = buildRunSummary({
    runId: config.runId,
    createdAt: config.createdAt,
    mode: config.mode,
    sourceFilename: config.sourceFilename,
    label: config.label,
    topK: config.topK,
    dataset: config.dataset,
    caseCount: caseDetails.length,
    evidenceCount: caseDetails.length,
    modelPreset: config.modelPreset,
    modelBackend: config.modelBackend,
  });

  return {
    run,
    workflow_steps: buildWorkflowSteps(run, caseDetails.length),
    claim_boundary: CLAIM_BOUNDARY,
    evidence: aggregate.firstCase?.generated_evidence ?? null,
    evidence_summary: aggregate.firstCase
      ? {
          case_id: aggregate.firstCase.case_id,
          dataset: aggregate.firstCase.dataset,
          source: aggregate.firstCase.source,
          observation_count: Array.isArray(
            aggregate.firstCase.generated_evidence?.observations,
          )
            ? aggregate.firstCase.generated_evidence.observations.length
            : 0,
          case_count: caseDetails.length,
          route1_path_count: aggregate.topKPaths.length,
          route2_candidate_count: aggregate.rankedRootCauses.length,
        }
      : null,
    evidence_with_analysis: aggregate.firstCase?.generated_evidence
      ? {
          ...deepClone(aggregate.firstCase.generated_evidence),
          kg_analysis: {
            linked_entities: aggregate.linkedEntities,
            correction_candidates: aggregate.correctionCandidates,
            top_k_paths: aggregate.topKPaths,
            ranked_root_causes: aggregate.rankedRootCauses,
          },
        }
      : null,
    analysis: {
      top_k_paths: aggregate.topKPaths,
      ranked_root_causes: aggregate.rankedRootCauses,
      reasoning_metadata: runReasoningMetadata,
    },
    summary: {
      run_id: run.run_id,
      case_count: run.case_count,
      evidence_count: run.evidence_count,
      review_target_count: aggregate.reviewTargets.length,
      path_count: aggregate.topKPaths.length,
      pipeline: runReasoningMetadata,
    },
    cases: caseDetails,
    linked_entities: aggregate.linkedEntities,
    correction_candidates: aggregate.correctionCandidates,
    top_k_paths: aggregate.topKPaths,
    ranked_root_causes: aggregate.rankedRootCauses,
    path_graph: pathGraphFromPaths(aggregate.topKPaths),
    source_edge_provenance: aggregate.sourceEdgeProvenance,
    review_targets: aggregate.reviewTargets,
    artifacts: {},
    visual_evidence: aggregate.visualEvidence,
  };
}

function selectCuratedRuntimeCases(
  runtime: RootLensRuntimeFile,
): RootLensRuntimeCase[] {
  const casesById = new Map(
    runtime.cases.map((caseItem) => [caseItem.case_id, caseItem]),
  );
  const selected = PAPER_DEMO_CASE_IDS.map((caseId) =>
    casesById.get(caseId),
  ).filter(
    (caseItem): caseItem is RootLensRuntimeCase => caseItem !== undefined,
  );

  if (selected.length !== PAPER_DEMO_CASE_IDS.length) {
    const missing = PAPER_DEMO_CASE_IDS.filter(
      (caseId) => !casesById.has(caseId),
    );
    throw new Error(`内置 Demo 缺少预设 case：${missing.join(", ")}`);
  }

  return selected;
}

function buildSeedRuns(runtime: RootLensRuntimeFile): RunDetail[] {
  const curatedCases = selectCuratedRuntimeCases(runtime);
  return [
    buildRunDetail({
      runId: PAPER_DEMO_RUN_ID,
      createdAt: toIsoDate(3),
      mode: "evidence",
      sourceFilename: "paper-demo-curated.json",
      label: "论文演示预设案例",
      topK: 5,
      dataset: null,
      cases: curatedCases,
      modelBackend: "bundled-runtime-snapshot",
    }),
  ];
}
function buildImportedReplayRuns(runtime: RootLensRuntimeFile): RunDetail[] {
  if (runtime.backend_runs?.length) return deepClone(runtime.backend_runs);
  if (!runtime.cases.length) {
    return [];
  }

  const datasets = [
    ...new Set(runtime.cases.map((caseItem) => caseItem.dataset)),
  ];
  const sessionMeta = getLocalSessionMeta();

  return [
    buildRunDetail({
      runId: IMPORTED_REPLAY_RUN_ID,
      createdAt: sessionMeta?.updatedAt ?? runtime.generated_at,
      mode: "evidence",
      sourceFilename: "rootlens-runtime.json",
      label:
        sessionMeta?.summary ?? `回放资产会话（${runtime.cases.length} cases）`,
      topK: 5,
      dataset: datasets.length === 1 ? datasets[0] : null,
      cases: runtime.cases,
      modelBackend: runtime.generator,
    }),
  ];
}

async function readSnapshotRuns(): Promise<RunDetail[]> {
  if (getLocalSessionMeta()?.source === "import") {
    const runtime = await loadStoredImportedRuntime();
    return runtime ? buildImportedReplayRuns(runtime).sort((left, right) =>
      right.run.created_at.localeCompare(left.run.created_at)) : [];
  }
  demoRuns ??= loadBundledRootLensRuntime().then(buildSeedRuns);
  return demoRuns;
}

function findRunById(runs: RunDetail[], runId: string): RunDetail {
  const run = runs.find((item) => item.run.run_id === runId);
  if (!run) {
    throw new Error(`未找到模拟运行：${runId}`);
  }

  return deepClone(run);
}

function persistFeedbackRecord(record: MockFeedbackRecord) {
  const state = readPersistentState();
  state.feedback_records = [record, ...state.feedback_records];
  writePersistentState(state);
}

function resolveLedgerTargetKey(
  runs: RunDetail[],
  request: ReviewRequest,
): string | null {
  const targetId = normalizeText(request.target_id);
  const targetType = request.target_type;
  if (!targetId) {
    return null;
  }

  const run = request.run_id
    ? (runs.find((item) => item.run.run_id === request.run_id) ?? null)
    : null;
  const caseDetail = request.case_id
    ? (run?.cases.find((item) => item.case_id === request.case_id) ??
      runs
        .flatMap((item) => item.cases)
        .find((item) => item.case_id === request.case_id) ??
      null)
    : null;
  const reviewTargets = caseDetail?.review_targets ?? run?.review_targets ?? [];

  return (
    reviewTargets.find(
      (item) => item.target_type === targetType && item.target_id === targetId,
    )?.target_key ?? null
  );
}

function buildReviewLedgerRecord(
  runs: RunDetail[],
  feedbackRecord: MockFeedbackRecord,
): ReviewLedgerRecord | null {
  const request = feedbackRecord.request;
  const targetId = normalizeText(request.target_id);
  if (!targetId) {
    return null;
  }

  return {
    feedback_id: feedbackRecord.feedback_id,
    created_at: feedbackRecord.created_at,
    run_id: normalizeText(request.run_id) || null,
    case_id: normalizeText(request.case_id) || null,
    target_type: request.target_type,
    target_id: targetId,
    target_key: resolveLedgerTargetKey(runs, request),
    action: request.action,
    note: normalizeText(request.note) || null,
    reviewer: normalizeText(request.reviewer) || null,
    source: normalizeText(request.source, "rootlens-graphs"),
    metadata: isRecord(request.metadata) ? request.metadata : null,
  };
}

function filterReviewLedgerRecords(
  records: ReviewLedgerRecord[],
  request?: ReviewLedgerListRequest,
) {
  return records.filter((record) => {
    if (request?.run_id && record.run_id !== request.run_id) {
      return false;
    }
    if (request?.case_id && record.case_id !== request.case_id) {
      return false;
    }
    if (request?.target_type && record.target_type !== request.target_type) {
      return false;
    }
    if (request?.target_id && record.target_id !== request.target_id) {
      return false;
    }
    return true;
  });
}

function listMockMaterialRecords(persistentState: MockPersistentState) {
  return [...persistentState.material_records].sort((left, right) => {
    const leftTime = Date.parse(left.updated_at ?? left.created_at ?? "");
    const rightTime = Date.parse(right.updated_at ?? right.created_at ?? "");
    if (Number.isNaN(leftTime) || Number.isNaN(rightTime)) {
      return (right.updated_at ?? right.created_at ?? "").localeCompare(
        left.updated_at ?? left.created_at ?? "",
      );
    }
    return rightTime - leftTime;
  });
}

function findMockMaterialRecord(
  persistentState: MockPersistentState,
  materialId: string,
) {
  const material = persistentState.material_records.find(
    (item) => item.material_id === materialId,
  );
  if (!material) {
    throw new Error(`未找到素材：${materialId}`);
  }
  return material;
}

function listMockMaterialChunks(
  persistentState: MockPersistentState,
  materialId: string,
) {
  return persistentState.material_chunks
    .filter((item) => item.material_id === materialId)
    .sort((left, right) => left.chunk_index - right.chunk_index);
}

function listMockMaterialExtractions(
  persistentState: MockPersistentState,
  materialId: string,
) {
  return persistentState.material_extraction_runs
    .filter((item) => item.material_id === materialId)
    .sort((left, right) =>
      (right.started_at ?? right.completed_at ?? "").localeCompare(
        left.started_at ?? left.completed_at ?? "",
      ),
    );
}

function listMockMaterialArtifacts(
  persistentState: MockPersistentState,
  materialId: string,
) {
  return persistentState.material_artifacts
    .filter((item) => item.material_id === materialId)
    .sort((left, right) =>
      (right.created_at ?? "").localeCompare(left.created_at ?? ""),
    );
}

export const mockBackend = {
  async listRuns(): Promise<RunSummary[]> {
    return (await readSnapshotRuns()).map((run) => deepClone(run.run));
  },
  async getRun(runId: string): Promise<RunDetail> {
    return findRunById(await readSnapshotRuns(), runId);
  },
  async submitReview(
    request: ReviewRequest,
  ): Promise<{ status: string; record: Record<string, unknown> }> {
    const feedbackRecord: MockFeedbackRecord = {
      feedback_id: `feedback-${Date.now()}`,
      created_at: new Date().toISOString(),
      request,
    };
    persistFeedbackRecord(feedbackRecord);
    return {
      status: "recorded",
      record: feedbackRecord as unknown as Record<string, unknown>,
    };
  },
  async listReviewLedger(
    request?: ReviewLedgerListRequest,
  ): Promise<ReviewLedgerListResponse> {
    const runs = await readSnapshotRuns();
    const persistentState = readPersistentState();
    const records = persistentState.feedback_records
      .map((item) => buildReviewLedgerRecord(runs, item))
      .filter((item): item is ReviewLedgerRecord => item !== null)
      .sort((left, right) => right.created_at.localeCompare(left.created_at));
    const filteredRecords = filterReviewLedgerRecords(records, request);
    const offset = request?.offset ?? 0;
    const limit = request?.limit ?? 50;
    const pagedRecords = filteredRecords.slice(offset, offset + limit);

    return {
      records: pagedRecords,
      total_count: filteredRecords.length,
      returned_count: pagedRecords.length,
      offset,
      limit,
      claim_boundary: CLAIM_BOUNDARY,
    };
  },
  async listKGMaterials(): Promise<KGMaterialListResponse> {
    const persistentState = readPersistentState();
    const materials = listMockMaterialRecords(persistentState);
    return {
      status: "ok",
      material_dir: "mock://materials",
      material_root: "mock://materials",
      count: materials.length,
      materials,
      note: "模拟素材库已准备完毕。",
    };
  },
  async getKGMaterial(materialId: string): Promise<KGMaterialDetailResponse> {
    const persistentState = readPersistentState();
    return {
      status: "ok",
      material: deepClone(findMockMaterialRecord(persistentState, materialId)),
    };
  },
  async getKGMaterialChunks(
    materialId: string,
  ): Promise<KGMaterialChunkListResponse> {
    const persistentState = readPersistentState();
    const material = findMockMaterialRecord(persistentState, materialId);
    const chunks = listMockMaterialChunks(persistentState, materialId);
    return {
      status: "ok",
      material: deepClone(material),
      count: chunks.length,
      chunks: deepClone(chunks),
      claim_boundary: CLAIM_BOUNDARY,
    };
  },
  async getKGMaterialExtractions(
    materialId: string,
  ): Promise<KGMaterialExtractionRunListResponse> {
    const persistentState = readPersistentState();
    const material = findMockMaterialRecord(persistentState, materialId);
    const runs = listMockMaterialExtractions(persistentState, materialId);
    return {
      status: "ok",
      material: deepClone(material),
      count: runs.length,
      runs: deepClone(runs),
      claim_boundary: CLAIM_BOUNDARY,
    };
  },
  async getKGMaterialArtifacts(
    materialId: string,
  ): Promise<KGMaterialExtractionArtifactListResponse> {
    const persistentState = readPersistentState();
    const material = findMockMaterialRecord(persistentState, materialId);
    const artifacts = listMockMaterialArtifacts(persistentState, materialId);
    return {
      status: "ok",
      material: deepClone(material),
      count: artifacts.length,
      artifacts: deepClone(artifacts),
      claim_boundary: CLAIM_BOUNDARY,
    };
  },
};

export function canSubmitReviewTarget(targetType: string) {
  return REVIEWABLE_FEEDBACK_TARGETS.has(targetType as ReviewTargetType);
}
