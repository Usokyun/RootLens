export type UploadMode = "evidence" | "records" | "image";
export type ReviewAction = "accept" | "reject" | "needs_review";
export type ReviewTargetType =
  | "path"
  | "edge"
  | "entity_link"
  | "correction"
  | "root_cause_candidate"
  | "case"
  | "link";
export interface WorkflowStep {
  step_id: string;
  title: string;
  status: "completed" | "failed";
  summary: string;
  details: Record<string, unknown>;
}

export type RunSourceContract = "legacy-run" | "analysis-v2";

export interface RunSummary {
  run_id: string;
  created_at: string;
  mode: UploadMode | "process" | "wafer";
  source_contract?: RunSourceContract;
  source_filename: string;
  top_k: number | null;
  run_dir: string;
  status: "completed" | "failed";
  dataset: string | null;
  case_count: number;
  evidence_count: number | null;
  label: string;
  model_preset: string | null;
  model_backend: string | null;
}

export interface EvidenceSummary {
  case_id?: string;
  dataset?: string;
  source?: string;
  object?: string | null;
  anomaly_type?: string | null;
  location?: string | null;
  morphology?: string | null;
  severity?: number | null;
  confidence?: number | null;
  observation_count?: number;
  [key: string]: unknown;
}

export interface ReviewTarget {
  target_type: ReviewTargetType;
  target_id: string;
  target_key: string;
  label: string;
}

export interface PathGraphNode {
  node_id: string;
  label: string;
  role: "source" | "intermediate" | "target" | string;
}

export interface PathGraphEdge {
  edge_id: string;
  target_key: string;
  source_node_id: string;
  target_node_id: string;
  relation: string;
  source?: string | null;
  evidence?: string | null;
  confidence?: number | null;
  review_status?: string | null;
}

export interface PathGraphPath {
  path_id: string;
  target_key: string;
  source_entity_id?: string | null;
  target_entity_id?: string | null;
  score?: number | null;
  confidence?: number | null;
  supporting_evidence: unknown[];
  nodes: PathGraphNode[];
  edges: PathGraphEdge[];
}

export interface PathGraph {
  paths: PathGraphPath[];
  path_count: number;
  node_count: number;
  edge_count: number;
}

export interface RankedRootCause {
  ranking_id: string;
  rank: number;
  candidate_id: string;
  candidate_name: string;
  candidate_label?: string | null;
  candidate_role?: string | null;
  score?: number | null;
  confidence?: number | null;
  evidence_match?: number | null;
  explanation_paths?: unknown[];
  supporting_edges?: unknown[];
  supporting_evidence?: unknown[];
  scoring_method?: string | null;
  scoring_details?: Record<string, unknown> | null;
  source?: string | null;
  review_status?: string | null;
  [key: string]: unknown;
}

export interface WorkingGraphSummary {
  graph_id: string;
  title: string;
  dataset: "mvtec" | "wafer" | "tep";
  build_id: string;
  status: "loading" | "ready" | "failed";
  enabled?: boolean;
  node_count: number;
  edge_count: number;
  knowledge?: Record<string, unknown> | null;
}

export interface LegacyWorkingGraphPackage {
  schema_version: "rootlens-working-graph.v1";
  graph_id?: string | null;
  title: string;
  dataset: "mvtec" | "wafer" | "tep";
  build_id: string;
  nodes: Array<{ id: string; name: string; label: string; scenario: string; aliases: string[]; description: string }>;
  edges: Array<Record<string, unknown> & { head: string; relation: string; tail: string; scenario: string }>;
  profiles: Record<string, unknown>;
}

export interface UnifiedWorkingGraphPackage {
  schema_version: "rootlens-working-graph.v2";
  graph_id?: string | null;
  title: string;
  dataset: string;
  build_id: string;
  knowledge: Record<string, unknown>;
}

export type WorkingGraphPackage = LegacyWorkingGraphPackage | UnifiedWorkingGraphPackage;

export interface RunReasoningMetadata {
  query_results?: Array<Record<string, unknown>>;
  evidence_frames?: Array<Record<string, unknown>>;
  aggregation?: string;
  graph_id?: string | null;
  outcome?: string | null;
  reasoning_profile_id?: string | null;
  reasoner_adapter?: string | null;
  selection_mode?: string | null;
  requested_reasoning_profile_id?: string | null;
  requested_reasoner_adapter?: string | null;
  fallback_applied?: boolean | null;
  fallback_reason?: string | null;
}

export interface VisualEvidenceItem {
  artifact_id: string;
  case_id: string;
  dataset: string;
  kind: "image" | "mask" | "heatmap" | "wafer_map" | string;
  title: string;
  source_key: string;
  source_path: string | null;
  url: string | null;
  preview_path: string | null;
  available: boolean;
  note: string;
  metadata: Record<string, unknown>;
}

export interface RunCaseDetail {
  case_id: string;
  dataset?: string;
  label?: string;
  case_label?: string;
  source?: string;
  generated_evidence?: Record<string, unknown> | null;
  generated_evidence_path?: string | null;
  linked_entities?: Array<Record<string, unknown>>;
  consistency_score?: number | null;
  inconsistent_fields?: string[];
  correction_candidates?: Array<Record<string, unknown>>;
  top_k_paths?: Array<Record<string, unknown>>;
  ranked_root_causes?: RankedRootCause[];
  source_edge_provenance?: Array<Record<string, unknown>>;
  path_graph?: PathGraph;
  review_targets?: ReviewTarget[];
  visual_evidence?: VisualEvidenceItem[];
  reasoning_metadata?: RunReasoningMetadata | null;
  [key: string]: unknown;
}

export interface RunDetail {
  run: RunSummary;
  workflow_steps: WorkflowStep[];
  claim_boundary: string;
  evidence: Record<string, unknown> | null;
  evidence_summary: EvidenceSummary | null;
  evidence_with_analysis: Record<string, unknown> | null;
  analysis: Record<string, unknown> | null;
  summary: Record<string, unknown> | null;
  cases: RunCaseDetail[];
  linked_entities: Array<Record<string, unknown>>;
  correction_candidates: Array<Record<string, unknown>>;
  top_k_paths: Array<Record<string, unknown>>;
  ranked_root_causes: RankedRootCause[];
  reasoning_metadata?: RunReasoningMetadata | null;
  path_graph: PathGraph;
  source_edge_provenance: Array<Record<string, unknown>>;
  review_targets: ReviewTarget[];
  artifacts: Record<string, string>;
  visual_evidence: VisualEvidenceItem[];
}

export interface ReviewRequest {
  run_id?: string;
  case_id?: string;
  target_type: ReviewTargetType;
  target_id?: string;
  action: ReviewAction;
  note?: string;
  reviewer?: string;
  source: string;
  metadata?: Record<string, unknown>;
}

export interface ReviewLedgerListRequest {
  run_id?: string;
  case_id?: string;
  target_type?: ReviewTargetType;
  target_id?: string;
  offset?: number;
  limit?: number;
}

export interface ReviewLedgerRecord {
  feedback_id: string;
  created_at: string;
  run_id: string | null;
  case_id: string | null;
  target_type: ReviewTargetType;
  target_id: string;
  target_key: string | null;
  action: ReviewAction;
  note: string | null;
  reviewer: string | null;
  source: string;
  metadata: Record<string, unknown> | null;
}

export interface ReviewLedgerListResponse {
  records: ReviewLedgerRecord[];
  total_count: number;
  returned_count: number;
  offset: number;
  limit: number;
  claim_boundary: string;
}

export interface KGMaterialRecord {
  status: string;
  material_id: string;
  title: string;
  scenario: string;
  material_type?: string;
  source_kind?: string;
  source_uri?: string;
  metadata_path?: string;
  registered_at?: string;
  updated_at?: string;
  archived_at?: string | null;
  original_filename?: string | null;
  content_type?: string | null;
  size_bytes?: number;
  metadata?: Record<string, unknown>;
  extraction?: Record<string, unknown>;
  claim_boundary?: string;
  source_type: string;
  source_format?: string | null;
  path?: string | null;
  url?: string | null;
  uri?: string | null;
  filename?: string | null;
  processing_status: string;
  extraction_status?: string | null;
  chunk_count?: number | null;
  page_count?: number | null;
  source_id?: string | null;
  notes?: string | null;
  created_at?: string | null;
}

export interface KGMaterialListResponse {
  status: string;
  material_dir: string;
  material_root: string;
  count: number;
  materials: KGMaterialRecord[];
  note: string;
}

export interface KGMaterialDetailResponse {
  status: string;
  material: KGMaterialRecord;
}

export interface KGMaterialChunkRecord {
  chunk_id: string;
  material_id: string;
  chunk_index: number;
  source_locator: string | null;
  text_content: string;
  char_start: number | null;
  char_end: number | null;
  metadata: Record<string, unknown>;
  created_at: string | null;
}

export interface KGMaterialChunkListResponse {
  status: string;
  material: KGMaterialRecord;
  count: number;
  chunks: KGMaterialChunkRecord[];
  claim_boundary: string;
}

export interface KGMaterialExtractionRunRecord {
  extraction_run_id: string;
  material_id: string;
  status: string;
  provider: string | null;
  source_format: string | null;
  structured_records_path: string | null;
  source_id: string | null;
  extractor_name: string | null;
  extractor_version: string | null;
  record_count: number | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
  parameters: Record<string, unknown>;
  result_summary: Record<string, unknown>;
}

export interface KGMaterialExtractionRunListResponse {
  status: string;
  material: KGMaterialRecord;
  count: number;
  runs: KGMaterialExtractionRunRecord[];
  claim_boundary: string;
}

export interface KGMaterialExtractionArtifactRecord {
  artifact_id: string;
  material_id: string;
  extraction_run_id: string | null;
  artifact_type: string;
  uri: string | null;
  media_type: string | null;
  payload: Record<string, unknown>;
  created_at: string | null;
}

export interface KGMaterialExtractionArtifactListResponse {
  status: string;
  material: KGMaterialRecord;
  count: number;
  artifacts: KGMaterialExtractionArtifactRecord[];
  claim_boundary: string;
}

export interface KGMaterialRegisterUrlRequest {
  url: string;
  title?: string | null;
  scenario?: string;
  source_type?: string;
  notes?: string | null;
  metadata?: Record<string, unknown>;
  material_id?: string | null;
}

export interface KGMaterialMutationResponse {
  status: string;
  material: KGMaterialRecord;
  note: string;
}

export interface KGStudioSource {
  source_id: string;
  title: string;
  source_type: string;
  path_or_url: string;
  used_for: string;
  notes: string;
}

export interface KGStudioSourceDocument {
  path: string;
  title: string;
  line_count: number;
}

export interface KGStudioGraphNode {
  node_id: string;
  label: string;
  node_type: string;
  scenario: string;
  description: string;
  aliases?: string[];
}

export interface KGStudioGraphEdge {
  edge_id: string;
  target_key: string;
  head: string;
  relation: string;
  tail: string;
  scenario: string;
  source: string;
  evidence: string;
  confidence: number | null;
  weight: number | null;
  review_status: string;
}

export interface KGStudioReviewTarget {
  target_type: "edge" | string;
  target_id: string;
  target_key: string;
  label: string;
  source: string;
  confidence: number | null;
  review_status: string;
}

export interface KGStudioPayload {
  graph_id?: string | null;
  status: "ok" | "empty" | string;
  claim_boundary: string;
  candidate_dir: string | null;
  nodes_path: string | null;
  edges_path: string | null;
  summary_path?: string | null;
  manifest_path?: string | null;
  source_registry_path: string;
  node_count: number;
  edge_count: number;
  scenario_counts: Record<string, number>;
  review_status_counts: Record<string, number>;
  source_counts: Record<string, number>;
  confidence_summary: Record<string, number | null>;
  validation_summary: Record<string, unknown> | null;
  construction_manifest?: Record<string, unknown> | null;
  sources: KGStudioSource[];
  source_documents: KGStudioSourceDocument[];
  graph_nodes: KGStudioGraphNode[];
  graph_edges: KGStudioGraphEdge[];
  review_targets: KGStudioReviewTarget[];
  note: string;
}
