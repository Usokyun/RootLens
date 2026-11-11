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

export interface UnifiedWorkingGraphPackage {
  schema_version: "rootlens-working-graph.v2";
  graph_id?: string | null;
  title: string;
  dataset: string;
  build_id: string;
  knowledge: Record<string, unknown>;
}

export type WorkingGraphPackage = UnifiedWorkingGraphPackage;

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
