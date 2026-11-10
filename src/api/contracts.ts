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

export interface UnifiedWorkingGraphPackage {
  schema_version: "rootlens-working-graph.v2";
  graph_id?: string | null;
  title: string;
  dataset: string;
  build_id: string;
  knowledge: Record<string, unknown>;
}

export type WorkingGraphPackage = UnifiedWorkingGraphPackage
