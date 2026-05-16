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
export type KGConstructionSourceType =
  | "structured_records"
  | "manual_table"
  | "tep_semantic_lift"
  | "tep_variable_mapping";
export type KGConstructionSourceFormat = "csv" | "json" | "jsonl";
export type ConstructionReviewStatus = "auto" | "reviewed" | "rejected";

export interface WorkflowStep {
  step_id: string;
  title: string;
  status: "completed" | "failed";
  summary: string;
  details: Record<string, unknown>;
}

export interface RunSummary {
  run_id: string;
  created_at: string;
  mode: UploadMode;
  source_filename: string;
  top_k: number;
  run_dir: string;
  status: "completed" | "failed";
  dataset: string | null;
  case_count: number;
  evidence_count: number;
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
  path_graph: PathGraph;
  source_edge_provenance: Array<Record<string, unknown>>;
  review_targets: ReviewTarget[];
  artifacts: Record<string, string>;
  visual_evidence: VisualEvidenceItem[];
}

export interface UploadModeInfo {
  mode: UploadMode;
  label: string;
  description: string;
  accepted_extensions: string[];
  required_fields: string[];
}

export interface DashboardBootstrap {
  status: string;
  api_version: string;
  claim_boundary: string;
  supported_datasets: string[];
  supported_feedback_targets: string[];
  supported_feedback_actions: string[];
  upload_modes: UploadModeInfo[];
  mvtec_model_presets: {
    default_preset: string;
    presets: Array<Record<string, unknown>>;
  };
  recent_runs: RunSummary[];
}

export interface AnalyzeEnvelope {
  case: Record<string, unknown> | null;
  evidence: Record<string, unknown>;
  analysis: Record<string, unknown>;
  evidence_with_analysis: Record<string, unknown>;
  workflow_steps: WorkflowStep[];
  claim_boundary: string;
}

export interface AnalyzeEvidenceInput {
  case_id?: string;
  dataset: string;
  source: string;
  object?: string | null;
  anomaly_type?: string | null;
  location?: string | null;
  morphology?: string | null;
  severity?: number | null;
  confidence?: number | null;
  timestamp?: string | null;
  raw_evidence?: Record<string, unknown>;
  normalized_evidence?: Record<string, unknown>;
  kg_analysis?: Record<string, unknown>;
}

export interface AnalyzeRequest {
  case_id?: string;
  evidence?: AnalyzeEvidenceInput;
  top_k: number;
}

export interface WhatIfRequest {
  case_id: string;
  anomaly_type: string;
  location?: string | null;
  morphology?: string | null;
  variables?: string[];
  log_events?: string[];
  severity?: number | null;
  confidence?: number | null;
  top_k: number;
}

export interface UploadRequest {
  file: File;
  mode: UploadMode;
  dataset?: string;
  object_name?: string;
  defect_type?: string;
  model_preset?: string;
  top_k: number;
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

export type KGDraftAction = "keep" | "revise" | "reject" | "promote_later";

export interface KGDraftRequest {
  target_type: "edge";
  target_id: string;
  target_key?: string;
  draft_action: KGDraftAction;
  proposed_relation?: string;
  proposed_evidence?: string;
  proposed_confidence?: number;
  note?: string;
  reviewer?: string;
  source: string;
  metadata?: Record<string, unknown>;
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

export interface KGSourceDraftRequest {
  source_id: string;
  source_text: string;
  provider: "heuristic";
  default_scenario: string;
  confidence: number;
}

export interface KGSourceDraftEdge {
  edge_id: string;
  head: string;
  relation: string;
  tail: string;
  scenario: string;
  source: string;
  evidence: string;
  confidence: number;
  weight: number;
  review_status: string;
}

export interface KGSourceDraftResponse {
  provider: "heuristic";
  source_id: string;
  claim_boundary: string;
  candidate_edges: KGSourceDraftEdge[];
  note: string;
}

export interface KGConstructionSourceInput {
  source_id: string;
  source_type: KGConstructionSourceType;
  scenario: string;
  path?: string;
  source_text?: string;
  source_format?: KGConstructionSourceFormat;
  semantic_nodes_path?: string;
  semantic_edges_path?: string;
  metadata?: Record<string, unknown>;
}

export interface KGConstructionBuildRequest {
  sources: KGConstructionSourceInput[];
  output_name: string;
  overwrite: boolean;
  run_id?: string;
}

export interface KGConstructionBuildResponse {
  status: string;
  run_id: string;
  output_dir: string;
  nodes_path: string;
  edges_path: string;
  summary_path: string;
  manifest_path: string;
  summary: Record<string, unknown>;
  claim_boundary: string;
}

export interface KGConstructionUploadedSource {
  status: string;
  source_id: string;
  source_type: KGConstructionSourceType;
  scenario: string;
  source_format: KGConstructionSourceFormat;
  filename: string;
  path: string;
  metadata_path: string;
  size_bytes: number;
  uploaded_at: string;
  build_source: KGConstructionSourceInput;
  claim_boundary: string;
}

export interface KGConstructionSourceListResponse {
  source_root: string;
  sources: KGConstructionUploadedSource[];
}

export interface KGConstructionBuildRecord {
  run_id: string;
  status: string;
  created_at?: string | null;
  output_dir: string;
  nodes_path: string;
  edges_path: string;
  summary_path: string;
  manifest_path: string;
  source_ids: string[];
  source_count: number;
  node_count: number;
  edge_count: number;
  scenarios: Record<string, number>;
  review_status_counts: Record<string, number>;
  claim_boundary: string;
}

export interface KGConstructionBuildListResponse {
  build_root: string;
  builds: KGConstructionBuildRecord[];
}

export interface KGConstructionBuildDetail {
  build: KGConstructionBuildRecord;
  summary: Record<string, unknown>;
  manifest: Record<string, unknown>;
}

export interface KGConstructionBuildValidationResponse {
  build: KGConstructionBuildRecord;
  qa_report: Record<string, unknown>;
  claim_boundary: string;
}

export interface KGConstructionPublishRequest {
  dry_run?: boolean;
  include_defaults?: boolean;
  confirm_publish?: boolean;
  config_path?: string;
  uri?: string;
  user?: string;
  password?: string;
  database?: string;
}

export interface KGConstructionImportSummary {
  node_count: number;
  edge_count: number;
  dry_run: boolean;
}

export interface KGConstructionPublishResponse {
  build: KGConstructionBuildRecord;
  import_summary: KGConstructionImportSummary;
  include_defaults: boolean;
  node_paths: string[];
  edge_paths: string[];
  claim_boundary: string;
}

export interface KGConstructionEdgeReviewRequest {
  action: "accept" | "reject";
  target_key?: string;
  head?: string;
  relation?: string;
  tail?: string;
  scenario?: string;
  reviewer?: string;
  note?: string;
  proposed_payload?: Record<string, unknown>;
  metadata?: Record<string, unknown>;
}

export interface KGConstructionEdgeReviewResponse {
  build: KGConstructionBuildRecord;
  decision: Record<string, unknown>;
  edge: Record<string, unknown>;
  summary: Record<string, unknown>;
  manifest_path: string;
  edges_path: string;
  claim_boundary: string;
}

export interface KGConstructionReviewQueueRequest {
  review_status?: ConstructionReviewStatus;
  source?: string;
  scenario?: string;
  relation?: string;
  query?: string;
  offset?: number;
  limit?: number;
}

export interface KGConstructionReviewQueueEdge {
  target_key: string;
  head: string;
  relation: string;
  tail: string;
  scenario: string;
  source: string;
  evidence: string;
  confidence: number;
  weight: number;
  review_status: string;
  feedback_count: number;
  accepted_count: number;
  rejected_count: number;
}

export interface KGConstructionReviewQueueSummary {
  review_status_counts: Record<string, number>;
  relation_counts: Record<string, number>;
  scenario_counts: Record<string, number>;
  source_counts: Record<string, number>;
}

export interface KGConstructionReviewQueueResponse {
  build: KGConstructionBuildRecord;
  filters: KGConstructionReviewQueueRequest;
  total_count: number;
  returned_count: number;
  offset: number;
  limit: number;
  edges: KGConstructionReviewQueueEdge[];
  summary: KGConstructionReviewQueueSummary;
  claim_boundary: string;
}
