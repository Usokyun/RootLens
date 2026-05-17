import { parse as parseCsv } from "csv-parse/browser/esm/sync";

import type {
  AnalyzeEnvelope,
  AnalyzeRequest,
  DashboardBootstrap,
  KGDraftListRequest,
  KGDraftListResponse,
  KGDraftRecord,
  KGDraftRequest,
  KGMaterialBuildSourcesRequest,
  KGMaterialBuildSourcesResponse,
  KGMaterialChunkListResponse,
  KGMaterialChunkRecord,
  KGMaterialDetailResponse,
  KGMaterialExtractRequest,
  KGMaterialExtractResponse,
  KGMaterialExtractionArtifactListResponse,
  KGMaterialExtractionArtifactRecord,
  KGMaterialExtractionRunListResponse,
  KGMaterialExtractionRunRecord,
  KGMaterialListResponse,
  KGMaterialMutationResponse,
  KGMaterialRecord,
  KGMaterialRegisterUrlRequest,
  KGSourceDraftEdge,
  KGSourceDraftRequest,
  KGSourceDraftResponse,
  KGStudioGraphEdge,
  KGStudioGraphNode,
  KGStudioPayload,
  KGConstructionBuildDetail,
  KGConstructionBuildListResponse,
  KGConstructionBuildRecord,
  KGConstructionBuildRequest,
  KGConstructionBuildResponse,
  KGConstructionBuildValidationResponse,
  KGConstructionEdgeReviewRequest,
  KGConstructionEdgeReviewResponse,
  KGConstructionPublishRequest,
  KGConstructionPublishResponse,
  KGConstructionReviewQueueEdge,
  KGConstructionReviewQueueRequest,
  KGConstructionReviewQueueResponse,
  KGConstructionReviewQueueSummary,
  KGConstructionSourceListResponse,
  KGConstructionUploadedSource,
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
  RunSummary,
  UploadMode,
  UploadRequest,
  VisualEvidenceItem,
  WhatIfRequest,
} from "@/api/contracts";
import {
  getLocalSessionMeta,
  getStoredImportedRuntime,
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

interface MockDraftRecord {
  draft_id: string;
  created_at: string;
  request: KGDraftRequest;
}

interface MockConstructionBuild {
  build: KGConstructionBuildRecord;
  summary: Record<string, unknown>;
  manifest: Record<string, unknown>;
  qa_report: Record<string, unknown>;
  edges: KGConstructionReviewQueueEdge[];
}

interface MockPersistentState {
  uploaded_runs: RunDetail[];
  feedback_records: MockFeedbackRecord[];
  kg_draft_records: MockDraftRecord[];
  source_uploads: KGConstructionUploadedSource[];
  construction_builds: MockConstructionBuild[];
  material_records: KGMaterialRecord[];
  material_chunks: KGMaterialChunkRecord[];
  material_extraction_runs: KGMaterialExtractionRunRecord[];
  material_artifacts: KGMaterialExtractionArtifactRecord[];
}

interface SeedBundle {
  runs: RunDetail[];
  bootstrap: DashboardBootstrap;
  kgStudio: KGStudioPayload;
  constructionBuilds: MockConstructionBuild[];
}

let seedBundlePromise: Promise<SeedBundle> | null = null;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function compactList<T>(items: Array<T | null | undefined>): T[] {
  return items.filter((item): item is T => item !== null && item !== undefined);
}

function normalizeScore(value: unknown, fallback = 0): number {
  if (typeof value !== "number" || Number.isNaN(value)) {
    return fallback;
  }

  return value;
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

function safeNumber(value: unknown, fallback = 0): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
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
  if (
    typeof window === "undefined" ||
    typeof window.localStorage === "undefined"
  ) {
    return {
      uploaded_runs: [],
      feedback_records: [],
      kg_draft_records: [],
      source_uploads: [],
      construction_builds: [],
      material_records: [],
      material_chunks: [],
      material_extraction_runs: [],
      material_artifacts: [],
    };
  }

  try {
    const raw = window.localStorage.getItem(MOCK_STORAGE_KEY);
    if (!raw) {
      return {
        uploaded_runs: [],
        feedback_records: [],
        kg_draft_records: [],
        source_uploads: [],
        construction_builds: [],
        material_records: [],
        material_chunks: [],
        material_extraction_runs: [],
        material_artifacts: [],
      };
    }

    const parsed = JSON.parse(raw) as Partial<MockPersistentState>;
    return {
      uploaded_runs: Array.isArray(parsed.uploaded_runs)
        ? (parsed.uploaded_runs as RunDetail[])
        : [],
      feedback_records: Array.isArray(parsed.feedback_records)
        ? (parsed.feedback_records as MockFeedbackRecord[])
        : [],
      kg_draft_records: Array.isArray(parsed.kg_draft_records)
        ? (parsed.kg_draft_records as MockDraftRecord[])
        : [],
      source_uploads: Array.isArray(parsed.source_uploads)
        ? (parsed.source_uploads as KGConstructionUploadedSource[])
        : [],
      construction_builds: Array.isArray(parsed.construction_builds)
        ? (parsed.construction_builds as MockConstructionBuild[])
        : [],
      material_records: Array.isArray(parsed.material_records)
        ? (parsed.material_records as KGMaterialRecord[])
        : [],
      material_chunks: Array.isArray(parsed.material_chunks)
        ? (parsed.material_chunks as KGMaterialChunkRecord[])
        : [],
      material_extraction_runs: Array.isArray(parsed.material_extraction_runs)
        ? (parsed.material_extraction_runs as KGMaterialExtractionRunRecord[])
        : [],
      material_artifacts: Array.isArray(parsed.material_artifacts)
        ? (parsed.material_artifacts as KGMaterialExtractionArtifactRecord[])
        : [],
    };
  } catch {
    return {
      uploaded_runs: [],
      feedback_records: [],
      kg_draft_records: [],
      source_uploads: [],
      construction_builds: [],
      material_records: [],
      material_chunks: [],
      material_extraction_runs: [],
      material_artifacts: [],
    };
  }
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

async function fetchPublicJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`模拟资产读取失败：${path}`);
  }
  return (await response.json()) as T;
}

async function fetchPublicText(path: string): Promise<string> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`模拟资产读取失败：${path}`);
  }
  return response.text();
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
    },
    summary: {
      run_id: run.run_id,
      case_count: run.case_count,
      evidence_count: run.evidence_count,
      review_target_count: aggregate.reviewTargets.length,
      path_count: aggregate.topKPaths.length,
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
    throw new Error(`论文演示 mock 缺少预设 case：${missing.join(", ")}`);
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

function parseCsvRecords(text: string): Record<string, string>[] {
  return parseCsv(text, {
    columns: true,
    skip_empty_lines: true,
    bom: true,
  }) as Record<string, string>[];
}

function countBy<T extends string>(items: T[]): Record<string, number> {
  return items.reduce<Record<string, number>>((accumulator, item) => {
    accumulator[item] = (accumulator[item] ?? 0) + 1;
    return accumulator;
  }, {});
}

function buildKgStudioReviewTargets(
  edges: KGStudioGraphEdge[],
): ReviewTarget[] {
  return edges.map((edge) => ({
    target_type: "edge",
    target_id: edge.edge_id,
    target_key: edge.target_key,
    label: `${edge.head} ${edge.relation} ${edge.tail}`,
  }));
}

async function buildSeedKgStudio(): Promise<{
  kgStudio: KGStudioPayload;
  build: MockConstructionBuild;
}> {
  const [nodesCsv, edgesCsv, validationReport, generationSummary] =
    await Promise.all([
      fetchPublicText("/generated/mvtec-candidate-kg/nodes_candidate.csv"),
      fetchPublicText("/generated/mvtec-candidate-kg/edges_candidate.csv"),
      fetchPublicJson<Record<string, unknown>>(
        "/generated/mvtec-candidate-kg/validation_report.json",
      ),
      fetchPublicJson<Record<string, unknown>>(
        "/generated/mvtec-candidate-kg/kg_generation_summary.json",
      ),
    ]);

  const nodeRows = parseCsvRecords(nodesCsv);
  const edgeRows = parseCsvRecords(edgesCsv);

  const graphNodes: KGStudioGraphNode[] = nodeRows.slice(0, 36).map((row) => ({
    node_id: normalizeText(row.id),
    label: normalizeText(row.name, normalizeText(row.id)),
    node_type: normalizeText(row.label),
    scenario: normalizeText(row.scenario, "shared"),
    description: normalizeText(row.description),
  }));

  const graphEdges: KGStudioGraphEdge[] = edgeRows.slice(0, 72).map((row) => {
    const edgeId = `${normalizeText(row.head)}|${normalizeText(row.relation)}|${normalizeText(row.tail)}|${normalizeText(row.scenario, "shared")}`;
    return {
      edge_id: edgeId,
      target_key: edgeId,
      head: normalizeText(row.head),
      relation: normalizeText(row.relation),
      tail: normalizeText(row.tail),
      scenario: normalizeText(row.scenario, "shared"),
      source: normalizeText(row.source),
      evidence: normalizeText(row.evidence),
      confidence: safeNumber(row.confidence, 0),
      weight: safeNumber(row.weight, 0),
      review_status: normalizeText(row.review_status, "auto"),
    };
  });

  const reviewTargets = buildKgStudioReviewTargets(graphEdges);
  const reviewStatusCounts = countBy(
    graphEdges.map((edge) => edge.review_status),
  );
  const scenarioCounts = countBy(graphEdges.map((edge) => edge.scenario));
  const sourceCounts = countBy(graphEdges.map((edge) => edge.source));
  const confidenceValues = graphEdges.map((edge) => edge.confidence ?? 0);
  const avgConfidence = confidenceValues.length
    ? confidenceValues.reduce((sum, value) => sum + value, 0) /
      confidenceValues.length
    : 0;

  const buildRecord: KGConstructionBuildRecord = {
    run_id: "mock-construction-seed",
    status: "completed",
    created_at: toIsoDate(40),
    output_dir: "/generated/mvtec-candidate-kg",
    nodes_path: "/generated/mvtec-candidate-kg/nodes_candidate.csv",
    edges_path: "/generated/mvtec-candidate-kg/edges_candidate.csv",
    summary_path: "/generated/mvtec-candidate-kg/validation_report.json",
    manifest_path: "/generated/mvtec-candidate-kg/kg_generation_summary.json",
    source_ids: [
      "wm811k_low_confidence_investigation_rule",
      "wafer_factory_sop_private_summary",
    ],
    source_count: 2,
    node_count: nodeRows.length,
    edge_count: edgeRows.length,
    scenarios: scenarioCounts,
    review_status_counts: reviewStatusCounts,
    claim_boundary: CLAIM_BOUNDARY,
  };

  const reviewQueueEdges: KGConstructionReviewQueueEdge[] = edgeRows.map(
    (row) => ({
      target_key: `${normalizeText(row.head)}|${normalizeText(row.relation)}|${normalizeText(row.tail)}|${normalizeText(row.scenario, "shared")}`,
      head: normalizeText(row.head),
      relation: normalizeText(row.relation),
      tail: normalizeText(row.tail),
      scenario: normalizeText(row.scenario, "shared"),
      source: normalizeText(row.source),
      evidence: normalizeText(row.evidence),
      confidence: safeNumber(row.confidence, 0),
      weight: safeNumber(row.weight, 0),
      review_status: normalizeText(row.review_status, "auto"),
      feedback_count: safeNumber(row.feedback_count, 0),
      accepted_count: safeNumber(row.accepted_count, 0),
      rejected_count: safeNumber(row.rejected_count, 0),
    }),
  );

  const build: MockConstructionBuild = {
    build: buildRecord,
    summary: generationSummary,
    manifest: generationSummary,
    qa_report: validationReport,
    edges: reviewQueueEdges,
  };

  return {
    kgStudio: {
      status: "ok",
      claim_boundary: CLAIM_BOUNDARY,
      candidate_dir: "/generated/mvtec-candidate-kg",
      nodes_path: "/generated/mvtec-candidate-kg/nodes_candidate.csv",
      edges_path: "/generated/mvtec-candidate-kg/edges_candidate.csv",
      summary_path: "/generated/mvtec-candidate-kg/validation_report.json",
      manifest_path: "/generated/mvtec-candidate-kg/kg_generation_summary.json",
      source_registry_path: "mock://source_registry.csv",
      node_count: nodeRows.length,
      edge_count: edgeRows.length,
      scenario_counts: scenarioCounts,
      review_status_counts: reviewStatusCounts,
      source_counts: sourceCounts,
      confidence_summary: {
        average: Number(avgConfidence.toFixed(3)),
        min: Math.min(...confidenceValues),
        max: Math.max(...confidenceValues),
      },
      validation_summary:
        (validationReport.summary as Record<string, unknown>) ??
        validationReport,
      construction_manifest: generationSummary,
      sources: [
        {
          source_id: "wm811k_low_confidence_investigation_rule",
          title: "WM811K 低置信度排查规则",
          source_type: "manual_table",
          path_or_url: "/generated/mvtec-candidate-kg/edges_candidate.csv",
          used_for: "模拟候选图谱预览",
          notes: "前端模拟来源登记条目。",
        },
        {
          source_id: "wafer_factory_sop_private_summary",
          title: "晶圆工厂 SOP 摘要",
          source_type: "structured_records",
          path_or_url: "/generated/mvtec-candidate-kg/validation_report.json",
          used_for: "构建校验摘要",
          notes: "由仓库内公开资产整理出的模拟来源登记条目。",
        },
      ],
      source_documents: [
        {
          path: "/generated/mvtec-candidate-kg/top_case_explanations.md",
          title: "案例解释摘要",
          line_count: 12,
        },
      ],
      graph_nodes: graphNodes,
      graph_edges: graphEdges,
      review_targets: reviewTargets.map((target) => ({
        target_type: "edge",
        target_id: target.target_id,
        target_key: target.target_key,
        label: target.label,
        source:
          graphEdges.find((edge) => edge.edge_id === target.target_id)
            ?.source ?? "",
        confidence:
          graphEdges.find((edge) => edge.edge_id === target.target_id)
            ?.confidence ?? null,
        review_status:
          graphEdges.find((edge) => edge.edge_id === target.target_id)
            ?.review_status ?? "auto",
      })),
      note: "模拟图谱工坊基于仓库内已提交的候选图谱资产构建。",
    },
    build,
  };
}

async function ensureSeedBundle(): Promise<SeedBundle> {
  if (!seedBundlePromise) {
    seedBundlePromise = Promise.all([
      loadBundledRootLensRuntime(),
      buildSeedKgStudio(),
    ]).then(([runtime, kgSeed]) => {
      const runs = buildSeedRuns(runtime);
      const bootstrap: DashboardBootstrap = {
        status: "ok",
        api_version: "mock-paper-demo-1.0",
        claim_boundary: CLAIM_BOUNDARY,
        supported_datasets: ["mvtec", "tep", "wafer"],
        supported_feedback_targets: [
          "path",
          "edge",
          "entity_link",
          "correction",
        ],
        supported_feedback_actions: ["accept", "reject", "needs_review"],
        upload_modes: [
          {
            mode: "records",
            label: "批量记录",
            description:
              "论文演示模式固定使用 4 个预设 case；上传仅在 backend 模式启用。",
            accepted_extensions: [".json", ".jsonl", ".csv"],
            required_fields: [],
          },
          {
            mode: "evidence",
            label: "证据 JSON",
            description:
              "论文演示模式固定使用静态 evidence 快照；真实上传请切换 backend。",
            accepted_extensions: [".json"],
            required_fields: [],
          },
          {
            mode: "image",
            label: "MVTec 图像",
            description:
              "论文演示模式不开放 mock 图像上传；截图请直接切换预设 case。",
            accepted_extensions: [".png", ".jpg", ".jpeg"],
            required_fields: ["dataset", "object_name", "model_preset"],
          },
        ],
        mvtec_model_presets: {
          default_preset: "mock-default",
          presets: [
            { preset: "mock-default", note: "仓库内置的模拟图像预设" },
            { preset: "mock-high-recall", note: "更高召回率的模拟图像预设" },
          ],
        },
        recent_runs: runs.map((run) => run.run),
      };

      return {
        runs,
        bootstrap,
        kgStudio: kgSeed.kgStudio,
        constructionBuilds: [kgSeed.build],
      };
    });
  }

  return seedBundlePromise;
}

async function loadCurrentState() {
  const seed = await ensureSeedBundle();
  return {
    seed,
    persistentState: readPersistentState(),
  };
}

function mergedRuns(seed: SeedBundle): RunDetail[] {
  const sessionMeta = getLocalSessionMeta();

  if (sessionMeta?.source === "import") {
    const importedRuntime = getStoredImportedRuntime();
    return buildImportedReplayRuns(
      importedRuntime ?? {
        schema_version: "rootlens-runtime.v1",
        generated_at: sessionMeta.updatedAt,
        generator: "browser-import",
        cases: [],
      },
    ).sort((left, right) =>
      right.run.created_at.localeCompare(left.run.created_at),
    );
  }

  return [...seed.runs].sort((left, right) =>
    right.run.created_at.localeCompare(left.run.created_at),
  );
}

function selectSeedRun(
  seedRuns: RunDetail[],
  options: { dataset?: string; mode?: UploadMode },
): RunDetail {
  return (
    seedRuns.find(
      (run) =>
        run.run.dataset === options.dataset && run.run.mode === options.mode,
    ) ??
    seedRuns.find((run) => run.run.dataset === options.dataset) ??
    seedRuns.find((run) => run.run.mode === options.mode) ??
    seedRuns[0]
  );
}

function findRunById(runs: RunDetail[], runId: string): RunDetail {
  const run = runs.find((item) => item.run.run_id === runId);
  if (!run) {
    throw new Error(`未找到模拟运行：${runId}`);
  }

  return deepClone(run);
}

function findCaseById(runs: RunDetail[], caseId: string): RunCaseDetail | null {
  for (const run of runs) {
    const match = run.cases.find((caseItem) => caseItem.case_id === caseId);
    if (match) {
      return deepClone(match);
    }
  }

  return null;
}

function buildEnvelopeFromCase(
  caseDetail: RunCaseDetail,
  note?: string,
): AnalyzeEnvelope {
  const evidence = deepClone(
    (caseDetail.generated_evidence ?? {}) as Record<string, unknown>,
  );
  const analysis = {
    linked_entities: caseDetail.linked_entities ?? [],
    correction_candidates: caseDetail.correction_candidates ?? [],
    top_k_paths: caseDetail.top_k_paths ?? [],
    ranked_root_causes: caseDetail.ranked_root_causes ?? [],
    note: note ?? null,
  };

  return {
    case: {
      case_id: caseDetail.case_id,
      dataset: caseDetail.dataset,
      label: caseDetail.case_label ?? caseDetail.label ?? caseDetail.case_id,
      observation_count: Array.isArray(evidence.observations)
        ? evidence.observations.length
        : 0,
    },
    evidence,
    analysis,
    evidence_with_analysis: {
      ...evidence,
      kg_analysis: analysis,
    },
    workflow_steps: [
      {
        step_id: "analysis",
        title: "模拟分析",
        status: "completed",
        summary: note ?? "模拟分析接口已返回可复核的结果载荷。",
        details: {
          case_id: caseDetail.case_id,
        },
      },
    ],
    claim_boundary: CLAIM_BOUNDARY,
  };
}

function applyMockWhatIf(
  caseDetail: RunCaseDetail,
  request: WhatIfRequest,
): AnalyzeEnvelope {
  const envelope = buildEnvelopeFromCase(
    caseDetail,
    "模拟假设分析已重新计算并返回可复核的结果载荷。",
  );
  envelope.evidence = {
    ...envelope.evidence,
    anomaly_type: request.anomaly_type,
    location:
      request.location ?? (envelope.evidence.location as string | null) ?? null,
    morphology:
      request.morphology ??
      (envelope.evidence.morphology as string | null) ??
      null,
    severity:
      request.severity ?? (envelope.evidence.severity as number | null) ?? null,
    confidence:
      request.confidence ??
      (envelope.evidence.confidence as number | null) ??
      null,
    raw_evidence: {
      ...(isRecord(envelope.evidence.raw_evidence)
        ? envelope.evidence.raw_evidence
        : {}),
      variables: request.variables ?? [],
      log_events: request.log_events ?? [],
    },
  };
  envelope.evidence_with_analysis = {
    ...envelope.evidence,
    kg_analysis: envelope.analysis,
  };

  const rankedRootCauses = Array.isArray(envelope.analysis.ranked_root_causes)
    ? deepClone(envelope.analysis.ranked_root_causes as RankedRootCause[])
    : [];
  if (rankedRootCauses.length > 1) {
    const [first, second, ...rest] = rankedRootCauses;
    envelope.analysis.ranked_root_causes = [
      { ...second, rank: 1, score: normalizeScore(second.score, 0) + 0.03 },
      {
        ...first,
        rank: 2,
        score: Math.max(0, normalizeScore(first.score, 0) - 0.02),
      },
      ...rest.map((item, index) => ({ ...item, rank: index + 3 })),
    ];
  }

  return envelope;
}

function parseDraftLines(request: KGSourceDraftRequest): KGSourceDraftEdge[] {
  const lines = request.source_text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);

  return lines.map((line, index) => {
    const parts = line.split(",").map((part) => part.trim());
    const [
      head,
      relation,
      tail,
      scenario = request.default_scenario,
      evidence = line,
    ] = parts;
    const edgeId = `${head || "Source"}|${relation || "SUGGESTS_PLAUSIBLE_MECHANISM"}|${tail || "Target"}|${scenario}`;
    return {
      edge_id: edgeId,
      head: head || `Source_${index + 1}`,
      relation: relation || "SUGGESTS_PLAUSIBLE_MECHANISM",
      tail: tail || `Target_${index + 1}`,
      scenario,
      source: request.source_id,
      evidence,
      confidence: request.confidence,
      weight: Number((request.confidence * 0.9).toFixed(2)),
      review_status: "auto",
    };
  });
}

function parseConstructionSourceRows(
  source: KGConstructionBuildRequest["sources"][number],
): Array<Record<string, unknown>> {
  const sourceText = source.source_text?.trim();
  if (!sourceText) {
    return [];
  }

  if (source.source_format === "csv") {
    try {
      return parseCsv(sourceText, {
        columns: true,
        skip_empty_lines: true,
        trim: true,
      }) as Array<Record<string, unknown>>;
    } catch {
      return [];
    }
  }

  if (source.source_format === "json") {
    try {
      const parsed = JSON.parse(sourceText) as unknown;
      if (Array.isArray(parsed)) {
        return parsed.filter(isRecord);
      }
      if (isRecord(parsed) && Array.isArray(parsed.records)) {
        return parsed.records.filter(isRecord);
      }
    } catch {
      return [];
    }
  }

  if (source.source_format === "jsonl") {
    return sourceText
      .split("\n")
      .map((line) => line.trim())
      .filter(Boolean)
      .map((line) => {
        try {
          return JSON.parse(line) as unknown;
        } catch {
          return null;
        }
      })
      .filter(isRecord);
  }

  return [];
}

function parseConstructionSourceEdges(
  source: KGConstructionBuildRequest["sources"][number],
): KGConstructionReviewQueueEdge[] {
  const rows = parseConstructionSourceRows(source);
  if (rows.length) {
    return compactList(
      rows.map((row, index) => {
        const head = normalizeText(row.head ?? row.subject ?? row.source_node);
        const relation = normalizeText(
          row.relation ?? row.predicate ?? row.edge_type,
        );
        const tail = normalizeText(row.tail ?? row.object ?? row.target_node);

        if (!head || !relation || !tail) {
          return null;
        }

        const scenario = normalizeText(row.scenario, source.scenario);
        const sourceId = normalizeText(
          row.source ?? row.source_id,
          source.source_id,
        );
        return {
          target_key: `${head}|${relation}|${tail}|${scenario}`,
          head,
          relation,
          tail,
          scenario,
          source: sourceId,
          evidence: normalizeText(row.evidence, `${sourceId}:${index + 1}`),
          confidence: safeNumber(row.confidence, 0.62),
          weight: safeNumber(row.weight, 0.56),
          review_status: normalizeText(row.review_status, "auto"),
          feedback_count: safeNumber(row.feedback_count, 0),
          accepted_count: safeNumber(row.accepted_count, 0),
          rejected_count: safeNumber(row.rejected_count, 0),
        } satisfies KGConstructionReviewQueueEdge;
      }),
    );
  }

  if (!source.source_text) {
    return [];
  }

  return parseDraftLines({
    source_id: source.source_id,
    source_text: source.source_text,
    provider: "heuristic",
    default_scenario: source.scenario,
    confidence: 0.62,
  }).map((edge) => ({
    target_key: edge.edge_id,
    head: edge.head,
    relation: edge.relation,
    tail: edge.tail,
    scenario: edge.scenario,
    source: edge.source,
    evidence: edge.evidence,
    confidence: edge.confidence,
    weight: edge.weight,
    review_status: edge.review_status,
    feedback_count: 0,
    accepted_count: 0,
    rejected_count: 0,
  }));
}

function buildConstructionReviewSummary(
  edges: KGConstructionReviewQueueEdge[],
): KGConstructionReviewQueueSummary {
  return {
    review_status_counts: countBy(edges.map((edge) => edge.review_status)),
    relation_counts: countBy(edges.map((edge) => edge.relation)),
    scenario_counts: countBy(edges.map((edge) => edge.scenario)),
    source_counts: countBy(edges.map((edge) => edge.source)),
  };
}

function buildConstructionBuildFromRequest(
  request: KGConstructionBuildRequest,
): MockConstructionBuild {
  const createdAt = new Date().toISOString();
  const runId = request.run_id || `mock-build-${Date.now()}`;
  const sourceIds = request.sources.map((source) => source.source_id);
  const edges: KGConstructionReviewQueueEdge[] = request.sources.flatMap(
    (source, sourceIndex) => {
      const parsedEdges = parseConstructionSourceEdges(source);

      if (parsedEdges.length) {
        return parsedEdges;
      }

      return [
        {
          target_key: `${source.source_id}|SUGGESTS_PLAUSIBLE_MECHANISM|Candidate_${sourceIndex + 1}|${source.scenario}`,
          head: source.source_id,
          relation: "SUGGESTS_PLAUSIBLE_MECHANISM",
          tail: `Candidate_${sourceIndex + 1}`,
          scenario: source.scenario,
          source: source.source_id,
          evidence:
            source.path ?? source.source_text ?? "Mock construction source",
          confidence: 0.58,
          weight: 0.51,
          review_status: "auto",
          feedback_count: 0,
          accepted_count: 0,
          rejected_count: 0,
        },
      ];
    },
  );

  const buildRecord: KGConstructionBuildRecord = {
    run_id: runId,
    status: "completed",
    created_at: createdAt,
    output_dir: `mock://construction/${request.output_name}`,
    nodes_path: `mock://construction/${request.output_name}/nodes.csv`,
    edges_path: `mock://construction/${request.output_name}/edges.csv`,
    summary_path: `mock://construction/${request.output_name}/summary.json`,
    manifest_path: `mock://construction/${request.output_name}/manifest.json`,
    source_ids: sourceIds,
    source_count: sourceIds.length,
    node_count: Math.max(2, sourceIds.length * 2),
    edge_count: edges.length,
    scenarios: countBy(edges.map((edge) => edge.scenario)),
    review_status_counts: countBy(edges.map((edge) => edge.review_status)),
    claim_boundary: CLAIM_BOUNDARY,
  };

  return {
    build: buildRecord,
    summary: {
      output_name: request.output_name,
      overwrite: request.overwrite,
      source_ids: sourceIds,
      edge_count: edges.length,
    },
    manifest: {
      generated_at: createdAt,
      request,
    },
    qa_report: {
      summary: {
        passed: true,
        issue_count: 0,
        warning_count: edges.some((edge) => edge.confidence < 0.6) ? 1 : 0,
      },
      edges,
    },
    edges,
  };
}

function filterConstructionEdges(
  edges: KGConstructionReviewQueueEdge[],
  request: KGConstructionReviewQueueRequest | undefined,
): KGConstructionReviewQueueEdge[] {
  if (!request) {
    return edges;
  }

  return edges.filter((edge) => {
    if (request.review_status && edge.review_status !== request.review_status) {
      return false;
    }
    if (request.source && edge.source !== request.source) {
      return false;
    }
    if (request.scenario && edge.scenario !== request.scenario) {
      return false;
    }
    if (request.relation && edge.relation !== request.relation) {
      return false;
    }
    if (request.query) {
      const haystack = [
        edge.head,
        edge.relation,
        edge.tail,
        edge.source,
        edge.evidence,
      ]
        .join(" ")
        .toLowerCase();
      if (!haystack.includes(request.query.toLowerCase())) {
        return false;
      }
    }
    return true;
  });
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

function persistKGDraftRecord(record: MockDraftRecord) {
  const state = readPersistentState();
  state.kg_draft_records = [record, ...state.kg_draft_records];
  writePersistentState(state);
}

function persistConstructionSource(source: KGConstructionUploadedSource) {
  const state = readPersistentState();
  state.source_uploads = [source, ...state.source_uploads];
  writePersistentState(state);
}

function persistConstructionBuild(build: MockConstructionBuild) {
  const state = readPersistentState();
  state.construction_builds = uniqueByKey(
    [build, ...state.construction_builds],
    (item) => item.build.run_id,
  );
  writePersistentState(state);
}

function mergedConstructionBuilds(
  seed: SeedBundle,
  persistentState: MockPersistentState,
): MockConstructionBuild[] {
  return uniqueByKey(
    [...persistentState.construction_builds, ...seed.constructionBuilds],
    (item) => item.build.run_id,
  );
}

function inferMockMaterialSourceFormat(value: string | null | undefined) {
  const normalized = (value ?? "").toLowerCase();
  if (normalized.endsWith(".jsonl")) {
    return "jsonl" as const;
  }
  if (normalized.endsWith(".json")) {
    return "json" as const;
  }
  return "csv" as const;
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

function persistMockMaterialRecord(record: KGMaterialRecord) {
  const state = readPersistentState();
  state.material_records = uniqueByKey(
    [record, ...state.material_records],
    (item) => item.material_id,
  );
  writePersistentState(state);
}

function replaceMockMaterialDerivedState(input: {
  materialId: string;
  chunks?: KGMaterialChunkRecord[];
  extractionRuns?: KGMaterialExtractionRunRecord[];
  artifacts?: KGMaterialExtractionArtifactRecord[];
}) {
  const state = readPersistentState();
  if (input.chunks) {
    state.material_chunks = [
      ...state.material_chunks.filter((item) => item.material_id !== input.materialId),
      ...input.chunks,
    ];
  }
  if (input.extractionRuns) {
    state.material_extraction_runs = [
      ...state.material_extraction_runs.filter(
        (item) => item.material_id !== input.materialId,
      ),
      ...input.extractionRuns,
    ];
  }
  if (input.artifacts) {
    state.material_artifacts = [
      ...state.material_artifacts.filter((item) => item.material_id !== input.materialId),
      ...input.artifacts,
    ];
  }
  writePersistentState(state);
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

function buildMockMaterialRecord(config: {
  materialId: string;
  title: string;
  scenario: string;
  sourceType: string;
  sourceKind: string;
  sourceUri: string;
  filename?: string | null;
  contentType?: string | null;
  sizeBytes?: number;
  notes?: string | null;
  createdAt?: string;
  updatedAt?: string;
  extraction?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
  status?: string;
}) {
  const createdAt = config.createdAt ?? new Date().toISOString();
  const updatedAt = config.updatedAt ?? createdAt;
  const extraction = isRecord(config.extraction) ? config.extraction : {};
  const metadata: Record<string, unknown> = {
    ...(isRecord(config.metadata) ? config.metadata : {}),
    ...(config.notes ? { notes: config.notes } : {}),
  };
  return {
    status: config.status ?? (String(extraction.status || "not_started") === "extracted" ? "extracted" : "registered"),
    material_id: config.materialId,
    title: config.title,
    scenario: config.scenario,
    material_type: config.sourceType,
    source_kind: config.sourceKind,
    source_uri: config.sourceUri,
    metadata_path: `mock://materials/${config.materialId}/metadata.json`,
    registered_at: createdAt,
    updated_at: updatedAt,
    original_filename: config.filename ?? null,
    content_type: config.contentType ?? null,
    size_bytes: config.sizeBytes ?? 0,
    metadata,
    extraction,
    claim_boundary:
      "source materials are provenance inputs for candidate KG construction; registration or upload does not verify industrial facts or publish KG rows",
    source_type: config.sourceType,
    source_format:
      typeof extraction.source_format === "string"
        ? extraction.source_format
        : config.sourceKind === "url"
          ? null
          : inferMockMaterialSourceFormat(config.filename ?? config.sourceUri),
    path: config.sourceKind === "url" ? null : config.sourceUri,
    url: config.sourceKind === "url" ? config.sourceUri : null,
    uri: config.sourceUri,
    filename: config.filename ?? null,
    processing_status: config.status ?? (String(extraction.status || "not_started") === "extracted" ? "extracted" : "registered"),
    extraction_status:
      typeof extraction.status === "string" ? extraction.status : "not_started",
    chunk_count:
      typeof metadata.chunk_count === "number" ? metadata.chunk_count : null,
    page_count:
      typeof metadata.page_count === "number" ? metadata.page_count : null,
    source_id:
      typeof extraction.source_id === "string" ? extraction.source_id : null,
    notes: config.notes ?? null,
    created_at: createdAt,
  } satisfies KGMaterialRecord;
}

function buildMockDraftRecord(draft: MockDraftRecord): KGDraftRecord {
  const targetKey =
    draft.request.target_key ?? `edge:${draft.request.target_id}`;
  return {
    draft_id: draft.draft_id,
    created_at: draft.created_at,
    target_type: "edge",
    target_id: draft.request.target_id,
    target_key: targetKey,
    draft_action: draft.request.draft_action,
    proposed_relation: draft.request.proposed_relation ?? null,
    proposed_evidence: draft.request.proposed_evidence ?? null,
    proposed_confidence: draft.request.proposed_confidence ?? null,
    note: draft.request.note ?? null,
    reviewer: draft.request.reviewer ?? null,
    source: draft.request.source,
    metadata: draft.request.metadata ?? {},
    review_decision: {
      action: draft.request.draft_action,
      target_id: draft.request.target_id,
      target_key: targetKey,
      note: draft.request.note ?? null,
      reviewer: draft.request.reviewer ?? null,
      source: draft.request.source,
      proposed_payload: {
        ...(draft.request.proposed_relation
          ? { relation: draft.request.proposed_relation }
          : {}),
        ...(draft.request.proposed_evidence
          ? { evidence: draft.request.proposed_evidence }
          : {}),
        ...(typeof draft.request.proposed_confidence === "number"
          ? { confidence: draft.request.proposed_confidence }
          : {}),
      },
      metadata: draft.request.metadata ?? {},
    },
  };
}

function listMockDraftRecords(
  persistentState: MockPersistentState,
  request?: KGDraftListRequest,
) {
  const records = persistentState.kg_draft_records
    .map((item) => buildMockDraftRecord(item))
    .sort((left, right) => right.created_at.localeCompare(left.created_at));
  return records.filter((record) => {
    if (request?.target_type && record.target_type !== request.target_type) {
      return false;
    }
    if (request?.target_id && record.target_id !== request.target_id) {
      return false;
    }
    if (request?.target_key && record.target_key !== request.target_key) {
      return false;
    }
    if (request?.reviewer && record.reviewer !== request.reviewer) {
      return false;
    }
    if (request?.source && record.source !== request.source) {
      return false;
    }
    return true;
  });
}

export const mockBackend = {
  async bootstrap(): Promise<DashboardBootstrap> {
    const { seed } = await loadCurrentState();
    return {
      ...deepClone(seed.bootstrap),
      recent_runs: mergedRuns(seed).map((run) => run.run),
    };
  },
  async listRuns(): Promise<RunSummary[]> {
    const { seed } = await loadCurrentState();
    return mergedRuns(seed).map((run) => run.run);
  },
  async getRun(runId: string): Promise<RunDetail> {
    const { seed } = await loadCurrentState();
    return findRunById(mergedRuns(seed), runId);
  },
  async uploadRun(_request: UploadRequest): Promise<RunDetail> {
    throw new Error(
      "论文演示 mock 模式不支持上传，请切换到 backend 模式后再上传真实数据。",
    );
  },
  async analyze(request: AnalyzeRequest): Promise<AnalyzeEnvelope> {
    const { seed } = await loadCurrentState();
    const runs = mergedRuns(seed);
    if (request.case_id) {
      const caseDetail = findCaseById(runs, request.case_id);
      if (caseDetail) {
        return buildEnvelopeFromCase(caseDetail);
      }
    }
    const seedRun = selectSeedRun(runs, {
      dataset: request.evidence?.dataset ?? undefined,
    });
    return buildEnvelopeFromCase(seedRun.cases[0]);
  },
  async whatIf(request: WhatIfRequest): Promise<AnalyzeEnvelope> {
    const { seed } = await loadCurrentState();
    const caseDetail = findCaseById(mergedRuns(seed), request.case_id);
    if (!caseDetail) {
      throw new Error(`未找到模拟案例：${request.case_id}`);
    }
    return applyMockWhatIf(caseDetail, request);
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
    const { seed, persistentState } = await loadCurrentState();
    const runs = mergedRuns(seed);
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
    const { persistentState } = await loadCurrentState();
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
    const { persistentState } = await loadCurrentState();
    return {
      status: "ok",
      material: deepClone(findMockMaterialRecord(persistentState, materialId)),
    };
  },
  async uploadKGMaterial(input: {
    file: File;
    title?: string;
    scenario?: string;
    source_type?: string;
    notes?: string;
    metadata?: Record<string, unknown>;
    material_id?: string;
    overwrite?: boolean;
  }): Promise<KGMaterialMutationResponse> {
    const materialId = normalizeText(
      input.material_id,
      `mock_material_${Date.now()}`,
    );
    const sourceText = await input.file.text();
    const now = new Date().toISOString();
    const record = buildMockMaterialRecord({
      materialId,
      title: normalizeText(input.title, input.file.name),
      scenario: normalizeText(input.scenario, "shared"),
      sourceType: normalizeText(input.source_type, "text"),
      sourceKind: "uploaded_file",
      sourceUri: `mock://materials/${materialId}/${input.file.name}`,
      filename: input.file.name,
      contentType: input.file.type || "text/plain",
      sizeBytes: input.file.size,
      notes: normalizeText(input.notes) || null,
      createdAt: now,
      updatedAt: now,
      metadata: {
        ...(input.metadata ?? {}),
        source_text: sourceText,
      },
      status: "uploaded",
    });
    persistMockMaterialRecord(record);
    replaceMockMaterialDerivedState({
      materialId,
      chunks: [],
      extractionRuns: [],
      artifacts: [],
    });
    return {
      status: "uploaded",
      material: record,
      note: record.claim_boundary ?? CLAIM_BOUNDARY,
    };
  },
  async registerKGMaterialUrl(
    request: KGMaterialRegisterUrlRequest,
  ): Promise<KGMaterialMutationResponse> {
    const materialId = normalizeText(
      request.material_id,
      `mock_material_${Date.now()}`,
    );
    const now = new Date().toISOString();
    const record = buildMockMaterialRecord({
      materialId,
      title: normalizeText(request.title, request.url),
      scenario: normalizeText(request.scenario, "shared"),
      sourceType: normalizeText(request.source_type, "webpage"),
      sourceKind: "url",
      sourceUri: request.url,
      notes: normalizeText(request.notes) || null,
      createdAt: now,
      updatedAt: now,
      metadata: request.metadata ?? {},
      status: "registered",
    });
    persistMockMaterialRecord(record);
    replaceMockMaterialDerivedState({
      materialId,
      chunks: [],
      extractionRuns: [],
      artifacts: [],
    });
    return {
      status: "registered",
      material: record,
      note: record.claim_boundary ?? CLAIM_BOUNDARY,
    };
  },
  async extractKGMaterial(
    materialId: string,
    request?: KGMaterialExtractRequest,
  ): Promise<KGMaterialExtractResponse> {
    const { persistentState } = await loadCurrentState();
    const base = findMockMaterialRecord(persistentState, materialId);
    const now = new Date().toISOString();
    const sourceText =
      normalizeText(base.metadata?.source_text) ||
      normalizeText(base.notes) ||
      `${base.title} source chunk`;
    const chunk: KGMaterialChunkRecord = {
      chunk_id: `${materialId}_chunk_0000`,
      material_id: materialId,
      chunk_index: 0,
      source_locator: `chars=0-${sourceText.length}`,
      text_content: sourceText,
      char_start: 0,
      char_end: sourceText.length,
      metadata: {
        source_id: base.source_id ?? materialId,
        scenario: base.scenario,
      },
      created_at: now,
    };
    const structuredRecordsPath = `mock://materials/${materialId}/structured_records.jsonl`;
    const extractionRecord: KGMaterialExtractionRunRecord = {
      extraction_run_id: `extract-${Date.now()}`,
      material_id: materialId,
      status: "extracted",
      provider: request?.provider ?? "openai",
      source_format: request?.source_format ?? "jsonl",
      structured_records_path: structuredRecordsPath,
      source_id: materialId,
      extractor_name: "mock_document_ie",
      extractor_version: "v1",
      record_count: 3,
      error_message: null,
      started_at: now,
      completed_at: now,
      parameters: {
        max_chars: request?.max_chars ?? 2000,
        overlap_chars: request?.overlap_chars ?? 200,
        overwrite: request?.overwrite ?? false,
      },
      result_summary: {
        record_count: 3,
        structured_records_path: structuredRecordsPath,
      },
    };
    const artifact: KGMaterialExtractionArtifactRecord = {
      artifact_id: `artifact-${Date.now()}`,
      material_id: materialId,
      extraction_run_id: extractionRecord.extraction_run_id,
      artifact_type: "structured_records",
      uri: structuredRecordsPath,
      media_type: "application/jsonl",
      payload: {
        record_count: 3,
        source_text_preview: sourceText,
      },
      created_at: now,
    };
    const extractedRecord = buildMockMaterialRecord({
      materialId,
      title: base.title,
      scenario: base.scenario,
      sourceType: base.source_type,
      sourceKind: base.source_kind ?? (base.url ? "url" : "uploaded_file"),
      sourceUri: base.uri ?? base.url ?? base.path ?? `mock://materials/${materialId}`,
      filename: base.filename ?? null,
      contentType: base.content_type ?? null,
      sizeBytes: base.size_bytes ?? 0,
      notes: base.notes ?? null,
      createdAt: base.created_at ?? now,
      updatedAt: now,
      metadata: {
        ...(base.metadata ?? {}),
        source_text: sourceText,
        chunk_count: 1,
      },
      extraction: {
        status: "extracted",
        structured_records_path: structuredRecordsPath,
        source_format: request?.source_format ?? "jsonl",
        source_id: materialId,
        extractor_name: "mock_document_ie",
        extractor_version: "v1",
        extracted_at: now,
        record_count: 3,
      },
      status: "extracted",
    });
    persistMockMaterialRecord(extractedRecord);
    replaceMockMaterialDerivedState({
      materialId,
      chunks: [chunk],
      extractionRuns: [extractionRecord],
      artifacts: [artifact],
    });
    return {
      status: "extracted",
      material: extractedRecord,
      structured_records_path: structuredRecordsPath,
      record_count: 3,
      claim_boundary: CLAIM_BOUNDARY,
    };
  },
  async buildKGMaterialSources(
    request: KGMaterialBuildSourcesRequest,
  ): Promise<KGMaterialBuildSourcesResponse> {
    const { persistentState } = await loadCurrentState();
    const materials = request.material_ids.map((materialId) => {
      const material = findMockMaterialRecord(persistentState, materialId);
      if (material.extraction_status !== "extracted") {
        throw new Error(`素材尚未完成 extract：${materialId}`);
      }
      return material;
    });
    const sources = materials.map((material) => ({
      source_id: material.source_id ?? material.material_id,
      source_type: (request.source_type ?? "structured_records") as "structured_records" | "manual_table",
      scenario: material.scenario,
      path:
        typeof material.extraction?.structured_records_path === "string"
          ? material.extraction.structured_records_path
          : `mock://materials/${material.material_id}/structured_records.jsonl`,
      source_format:
        typeof material.extraction?.source_format === "string"
          ? (material.extraction.source_format as "csv" | "json" | "jsonl")
          : "jsonl",
      metadata: {
        material_id: material.material_id,
        material_title: material.title,
        material_source_kind: material.source_kind,
      },
    }));
    return {
      status: "ready",
      material_root: "mock://materials",
      request,
      materials,
      sources,
      construction_request: {
        sources,
        output_name: request.output_name,
        overwrite: request.overwrite,
        run_id: request.run_id ?? undefined,
      },
      claim_boundary: CLAIM_BOUNDARY,
    };
  },
  async getKGMaterialChunks(
    materialId: string,
  ): Promise<KGMaterialChunkListResponse> {
    const { persistentState } = await loadCurrentState();
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
    const { persistentState } = await loadCurrentState();
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
    const { persistentState } = await loadCurrentState();
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
  async listKGDrafts(
    request?: KGDraftListRequest,
  ): Promise<KGDraftListResponse> {
    const { persistentState } = await loadCurrentState();
    const records = listMockDraftRecords(persistentState, request);
    const offset = request?.offset ?? 0;
    const limit = request?.limit ?? 50;
    const paged = records.slice(offset, offset + limit);
    return {
      records: paged,
      total_count: records.length,
      returned_count: paged.length,
      offset,
      limit,
      claim_boundary:
        "KG draft records are append-only candidate review adjustments; they do not mutate candidate CSV files or publish KG rows",
    };
  },
  async kgStudio(): Promise<KGStudioPayload> {
    const { seed } = await loadCurrentState();
    return deepClone(seed.kgStudio);
  },
  async generateKGSourceDraft(
    request: KGSourceDraftRequest,
  ): Promise<KGSourceDraftResponse> {
    return {
      provider: "heuristic",
      source_id: request.source_id,
      claim_boundary: CLAIM_BOUNDARY,
      candidate_edges: parseDraftLines(request),
      note: "模拟来源草稿边已从文本框输入中解析完成。",
    };
  },
  async submitKGDraft(
    request: KGDraftRequest,
  ): Promise<{ status: string; record: Record<string, unknown> }> {
    const draftRecord: MockDraftRecord = {
      draft_id: `draft-${Date.now()}`,
      created_at: new Date().toISOString(),
      request,
    };
    persistKGDraftRecord(draftRecord);
    return {
      status: "recorded",
      record: draftRecord as unknown as Record<string, unknown>,
    };
  },
  async buildKGConstruction(
    request: KGConstructionBuildRequest,
  ): Promise<KGConstructionBuildResponse> {
    const build = buildConstructionBuildFromRequest(request);
    persistConstructionBuild(build);
    return {
      status: build.build.status,
      run_id: build.build.run_id,
      output_dir: build.build.output_dir,
      nodes_path: build.build.nodes_path,
      edges_path: build.build.edges_path,
      summary_path: build.build.summary_path,
      manifest_path: build.build.manifest_path,
      summary: build.summary,
      claim_boundary: CLAIM_BOUNDARY,
    };
  },
  async listKGConstructionBuilds(): Promise<KGConstructionBuildListResponse> {
    const { seed, persistentState } = await loadCurrentState();
    const builds = mergedConstructionBuilds(seed, persistentState);
    return {
      build_root: "mock://construction",
      builds: builds.map((build) => build.build),
    };
  },
  async getKGConstructionBuild(
    runId: string,
  ): Promise<KGConstructionBuildDetail> {
    const { seed, persistentState } = await loadCurrentState();
    const build = mergedConstructionBuilds(seed, persistentState).find(
      (item) => item.build.run_id === runId,
    );
    if (!build) {
      throw new Error(`未找到构建记录：${runId}`);
    }
    return {
      build: build.build,
      summary: build.summary,
      manifest: build.manifest,
    };
  },
  async validateKGConstructionBuild(
    runId: string,
  ): Promise<KGConstructionBuildValidationResponse> {
    const { seed, persistentState } = await loadCurrentState();
    const build = mergedConstructionBuilds(seed, persistentState).find(
      (item) => item.build.run_id === runId,
    );
    if (!build) {
      throw new Error(`未找到构建记录：${runId}`);
    }
    return {
      build: build.build,
      qa_report: build.qa_report,
      claim_boundary: CLAIM_BOUNDARY,
    };
  },
  async publishKGConstructionBuild(
    runId: string,
    request: KGConstructionPublishRequest,
  ): Promise<KGConstructionPublishResponse> {
    const { seed, persistentState } = await loadCurrentState();
    const build = mergedConstructionBuilds(seed, persistentState).find(
      (item) => item.build.run_id === runId,
    );
    if (!build) {
      throw new Error(`未找到构建记录：${runId}`);
    }
    return {
      build: build.build,
      import_summary: {
        node_count: build.build.node_count,
        edge_count: build.build.edge_count,
        dry_run: request.dry_run !== false,
      },
      include_defaults: request.include_defaults !== false,
      node_paths: [build.build.nodes_path],
      edge_paths: [build.build.edges_path],
      claim_boundary: CLAIM_BOUNDARY,
    };
  },
  async reviewKGConstructionEdge(
    runId: string,
    request: KGConstructionEdgeReviewRequest,
  ): Promise<KGConstructionEdgeReviewResponse> {
    const { seed, persistentState } = await loadCurrentState();
    const merged = mergedConstructionBuilds(seed, persistentState);
    const existing = merged.find((item) => item.build.run_id === runId);
    if (!existing) {
      throw new Error(`未找到构建记录：${runId}`);
    }
    const targetKey = normalizeText(
      request.target_key,
      `${request.head ?? ""}|${request.relation ?? ""}|${request.tail ?? ""}|${request.scenario ?? ""}`,
    );
    const reviewedBuild: MockConstructionBuild = {
      ...existing,
      build: {
        ...existing.build,
        review_status_counts: countBy(
          existing.edges.map((edge) =>
            edge.target_key === targetKey
              ? request.action === "accept"
                ? "reviewed"
                : "rejected"
              : edge.review_status,
          ),
        ),
      },
      edges: existing.edges.map((edge) =>
        edge.target_key === targetKey
          ? {
              ...edge,
              review_status:
                request.action === "accept" ? "reviewed" : "rejected",
              feedback_count: edge.feedback_count + 1,
              accepted_count:
                edge.accepted_count + (request.action === "accept" ? 1 : 0),
              rejected_count:
                edge.rejected_count + (request.action === "reject" ? 1 : 0),
            }
          : edge,
      ),
      qa_report: {
        ...existing.qa_report,
        last_review: {
          target_key: targetKey,
          action: request.action,
          reviewer: request.reviewer ?? "mock-reviewer",
          note: request.note ?? null,
        },
      },
    };
    persistConstructionBuild(reviewedBuild);
    const edge = reviewedBuild.edges.find(
      (item) => item.target_key === targetKey,
    );
    return {
      build: reviewedBuild.build,
      decision: {
        action: request.action,
        reviewer: request.reviewer ?? "mock-reviewer",
        note: request.note ?? null,
      },
      edge: edge ? (edge as unknown as Record<string, unknown>) : {},
      summary: reviewedBuild.summary,
      manifest_path: reviewedBuild.build.manifest_path,
      edges_path: reviewedBuild.build.edges_path,
      claim_boundary: CLAIM_BOUNDARY,
    };
  },
  async getKGConstructionReviewQueue(
    runId: string,
    request?: KGConstructionReviewQueueRequest,
  ): Promise<KGConstructionReviewQueueResponse> {
    const { seed, persistentState } = await loadCurrentState();
    const build = mergedConstructionBuilds(seed, persistentState).find(
      (item) => item.build.run_id === runId,
    );
    if (!build) {
      throw new Error(`未找到构建记录：${runId}`);
    }
    const filteredEdges = filterConstructionEdges(build.edges, request);
    const offset = request?.offset ?? 0;
    const limit = request?.limit ?? 50;
    const pagedEdges = filteredEdges.slice(offset, offset + limit);
    return {
      build: build.build,
      filters: request ?? {},
      total_count: filteredEdges.length,
      returned_count: pagedEdges.length,
      offset,
      limit,
      edges: pagedEdges,
      summary: buildConstructionReviewSummary(filteredEdges),
      claim_boundary: CLAIM_BOUNDARY,
    };
  },
  async listKGConstructionSources(): Promise<KGConstructionSourceListResponse> {
    const { persistentState } = await loadCurrentState();
    return {
      source_root: "mock://construction/sources",
      sources: persistentState.source_uploads,
    };
  },
  async uploadKGConstructionSource(input: {
    file: File;
    source_id: string;
    source_type?: string;
    scenario?: string;
    source_format?: string;
  }): Promise<Record<string, unknown>> {
    const uploadedSource: KGConstructionUploadedSource = {
      status: "uploaded",
      source_id: input.source_id,
      source_type:
        (input.source_type as KGConstructionUploadedSource["source_type"]) ??
        "manual_table",
      scenario: input.scenario ?? "shared",
      source_format:
        (input.source_format as KGConstructionUploadedSource["source_format"]) ??
        "csv",
      filename: input.file.name,
      path: `mock://construction/sources/${input.file.name}`,
      metadata_path: `mock://construction/sources/${input.source_id}.json`,
      size_bytes: input.file.size,
      uploaded_at: new Date().toISOString(),
      build_source: {
        source_id: input.source_id,
        source_type:
          (input.source_type as KGConstructionUploadedSource["source_type"]) ??
          "manual_table",
        scenario: input.scenario ?? "shared",
        path: `mock://construction/sources/${input.file.name}`,
        source_format:
          (input.source_format as KGConstructionUploadedSource["source_format"]) ??
          "csv",
      },
      claim_boundary: CLAIM_BOUNDARY,
    };
    persistConstructionSource(uploadedSource);
    return uploadedSource as unknown as Record<string, unknown>;
  },
};

export function canSubmitReviewTarget(targetType: string) {
  return REVIEWABLE_FEEDBACK_TARGETS.has(targetType as ReviewTargetType);
}
