import type { JsonValue } from '@/types/graph'

export type EvidenceDataset = 'tep' | 'mvtec' | 'wafer' | 'wm811k'

export type EvidenceSource = 'time_series' | 'image' | 'log' | 'multimodal'

export type ObservationFacet = 'variable' | 'image_defect' | 'log_event'

export type ObservationDirection = 'increase' | 'decrease' | 'unknown'

export type EntityMatchType = 'exact' | 'fuzzy' | 'alias' | 'unmatched'

export interface EvidenceTimeWindow {
  start: string
  end: string
}

export interface RawEvidenceRef {
  ref_id: string
  label: string
  role: string
  file_path: string
  line: number | null
}

export interface ObservationBase {
  obs_id: string
  facet: ObservationFacet
  confidence: number
  linked_entity_hints: string[]
  raw_evidence_refs: RawEvidenceRef[]
  attributes?: Record<string, JsonValue>
}

export interface VariableObservation extends ObservationBase {
  facet: 'variable'
  variable_name: string
  contribution: number
  direction: ObservationDirection
  time_window?: EvidenceTimeWindow
}

export interface ImageDefectObservation extends ObservationBase {
  facet: 'image_defect'
  object: string
  anomaly_type: string
  location: string
  morphology: Record<string, JsonValue>
  severity: number
  image_region?: {
    x: number
    y: number
    w: number
    h: number
  }
}

export interface LogEventObservation extends ObservationBase {
  facet: 'log_event'
  event_type: string
  event_code: string
  message: string
  equipment: string
}

export type EvidenceObservation =
  | VariableObservation
  | ImageDefectObservation
  | LogEventObservation

export interface UnifiedEvidence {
  case_id: string
  case_label: string
  dataset: EvidenceDataset
  source: EvidenceSource
  timestamp: string
  summary: string
  graph_dataset_id: string
  observations: EvidenceObservation[]
}

export interface EntityCandidate {
  entity_id: string
  entity_name: string
  entity_type: string
  score: number
}

export interface LinkedEntity {
  link_id: string
  field: string
  mention: string
  selected_entity_id: string | null
  selected_entity_name: string | null
  score: number
  match_type: EntityMatchType
  ambiguous: boolean
  candidates: EntityCandidate[]
  obs_id?: string
  facet?: ObservationFacet
}

export interface ConsistencyCheck {
  source_field: string
  target_field: string
  source_entity_id: string
  target_entity_id: string
  relations: string[]
  passed: boolean
  matched_relation: string | null
}

export interface CorrectionCandidate {
  candidate_id: string
  source_field: string
  source_entity_id: string
  target_field: string
  target_obs_id?: string
  target_facet?: ObservationFacet
  original_value: JsonValue
  suggested_entity_id: string
  suggested_value: string
  score: number
  reason: string
  supporting_edge_ids: string[]
}

export interface PathEdgeDetail {
  edge_id: string
  source: string
  target: string
  relation: string
  confidence: number | null
}

export interface RankedPath {
  path_id: string
  source_entity_id: string
  target_entity_id: string
  target_entity_name: string
  nodes: string[]
  node_names: string[]
  relations: string[]
  score: number
  confidence: number
  evidence_match: number
  length: number
  source_edges: PathEdgeDetail[]
  support_obs_ids: string[]
}

export interface Route1Result {
  linked_entities: LinkedEntity[]
  consistency_score: number
  inconsistent_fields: string[]
  consistency_checks: ConsistencyCheck[]
  correction_candidates: CorrectionCandidate[]
  ranked_paths: RankedPath[]
}

export interface ChannelContribution {
  entity_id: string
  name: string
  contribution: number
  rank: number
}

export interface AffectedVariable {
  entity_id: string
  name: string
  propagated_score: number
  rbc_contribution: number
}

export interface RootKGDCandidate {
  scenario_id: string
  fault_number: number
  simulation_run: number
  rank: number
  candidate_id: string
  candidate_name: string
  candidate_type: string
  candidate_role: string
  priority_level: number
  seed_variable_id: string
  seed_score: number
  root_score: number
  ranking_score: number
  structural_ranking_score: number
  ranking_adjustment: number
  covered_contribution_mass: number
  active_variable_count: number
  pattern_entropy: number
  discriminator_alignment: number
  anchor_contribution_alignment: number
  anchor_dynamic_alignment: number
  anchor_unique_contribution_alignment: number
  anchor_memory_bonus: number
  anchor_memory_scenario_count: number
  top_affected_variables: AffectedVariable[]
  top_support_paths: string[][]
  support_evidence_ids: string[]
}

export interface Route2Result {
  fault_signature: {
    contribution_vector: Record<string, number>
    ordered_variables: string[]
    top_channels: ChannelContribution[]
    graph_contributions: Record<string, number>
  }
  ranked_candidates: RootKGDCandidate[]
}

export interface CrossRouteSignal {
  candidate_id: string
  candidate_name: string
  route1_path_ids: string[]
  route2_rank: number | null
  shared_obs_ids: string[]
}

export interface AnalysisResult {
  case_id: string
  timestamp: string
  graph_dataset_id: string
  route1: Route1Result | null
  route2: Route2Result | null
  cross_route_signals: CrossRouteSignal[]
  notes: string[]
}

export interface GraphSnapshot {
  dataset_id: string
  label: string
  graph_kind: string
  description: string
}

export interface RootLensRuntimeCase {
  case_id: string
  case_label: string
  dataset: EvidenceDataset
  source: EvidenceSource
  summary: string
  graph_snapshot: GraphSnapshot
  evidence: UnifiedEvidence
  analysis: AnalysisResult
}

export interface RootLensRuntimeFile {
  schema_version: string
  generated_at: string
  generator: string
  cases: RootLensRuntimeCase[]
}
