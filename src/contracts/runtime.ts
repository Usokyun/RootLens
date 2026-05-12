import type {
  JsonValue,
  UnifiedGraphDataset,
  UnifiedGraphEdge,
  UnifiedGraphNode,
  UnifiedGraphOrigin,
  UnifiedGraphSourceFile,
  UnifiedGraphsFile,
} from '@/types/graph'
import type {
  AnalysisResult,
  ChannelContribution,
  ConsistencyCheck,
  CorrectionCandidate,
  CrossRouteSignal,
  EntityCandidate,
  EvidenceObservation,
  GraphSnapshot,
  LinkedEntity,
  PathEdgeDetail,
  RankedPath,
  RawEvidenceRef,
  RootKGDCandidate,
  RootLensRuntimeCase,
  RootLensRuntimeFile,
  Route1Result,
  Route2Result,
  UnifiedEvidence,
} from '@/types/rootlens'

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function assertRecord(value: unknown, path: string): asserts value is Record<string, unknown> {
  if (!isRecord(value)) {
    throw new Error(`${path} must be an object`)
  }
}

function assertString(value: unknown, path: string): asserts value is string {
  if (typeof value !== 'string') {
    throw new Error(`${path} must be a string`)
  }
}

function assertNumber(value: unknown, path: string): asserts value is number {
  if (typeof value !== 'number' || Number.isNaN(value)) {
    throw new Error(`${path} must be a valid number`)
  }
}

function assertBoolean(value: unknown, path: string): asserts value is boolean {
  if (typeof value !== 'boolean') {
    throw new Error(`${path} must be a boolean`)
  }
}

function assertArray(value: unknown, path: string): asserts value is unknown[] {
  if (!Array.isArray(value)) {
    throw new Error(`${path} must be an array`)
  }
}

function assertNullableNumber(value: unknown, path: string): asserts value is number | null {
  if (value !== null) {
    assertNumber(value, path)
  }
}

function assertNullableString(value: unknown, path: string): asserts value is string | null {
  if (value !== null) {
    assertString(value, path)
  }
}

function assertStringArray(value: unknown, path: string): asserts value is string[] {
  assertArray(value, path)
  value.forEach((item, index) => assertString(item, `${path}[${index}]`))
}

function isJsonValue(value: unknown): value is JsonValue {
  if (
    value === null ||
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean'
  ) {
    return true
  }

  if (Array.isArray(value)) {
    return value.every((item) => isJsonValue(item))
  }

  if (isRecord(value)) {
    return Object.values(value).every((item) => isJsonValue(item))
  }

  return false
}

function parseJsonRecord(value: unknown, path: string): Record<string, JsonValue> {
  assertRecord(value, path)

  for (const [key, entry] of Object.entries(value)) {
    if (!isJsonValue(entry)) {
      throw new Error(`${path}.${key} must be JSON-serializable`)
    }
  }

  return value as Record<string, JsonValue>
}

function parseOrigin(value: unknown, path: string): UnifiedGraphOrigin {
  assertRecord(value, path)
  assertString(value.projectId, `${path}.projectId`)
  assertString(value.projectLabel, `${path}.projectLabel`)
  assertString(value.filePath, `${path}.filePath`)
  assertString(value.layer, `${path}.layer`)
  assertNumber(value.rowNumber, `${path}.rowNumber`)

  return {
    projectId: value.projectId,
    projectLabel: value.projectLabel,
    filePath: value.filePath,
    layer: value.layer,
    rowNumber: value.rowNumber,
  }
}

function parseSourceFile(value: unknown, path: string): UnifiedGraphSourceFile {
  assertRecord(value, path)
  assertString(value.path, `${path}.path`)
  assertString(value.role, `${path}.role`)
  assertString(value.layer, `${path}.layer`)
  assertNumber(value.rowCount, `${path}.rowCount`)
  assertStringArray(value.fields, `${path}.fields`)

  return {
    path: value.path,
    role: value.role,
    layer: value.layer,
    rowCount: value.rowCount,
    fields: value.fields,
  }
}

function parseGraphNode(value: unknown, path: string): UnifiedGraphNode {
  assertRecord(value, path)
  assertString(value.id, `${path}.id`)
  assertString(value.name, `${path}.name`)
  assertString(value.category, `${path}.category`)
  assertString(value.kind, `${path}.kind`)
  assertString(value.description, `${path}.description`)
  assertStringArray(value.aliases, `${path}.aliases`)
  assertNumber(value.degree, `${path}.degree`)
  assertNumber(value.inDegree, `${path}.inDegree`)
  assertNumber(value.outDegree, `${path}.outDegree`)

  return {
    id: value.id,
    name: value.name,
    category: value.category,
    kind: value.kind,
    description: value.description,
    aliases: value.aliases,
    degree: value.degree,
    inDegree: value.inDegree,
    outDegree: value.outDegree,
    attributes: parseJsonRecord(value.attributes, `${path}.attributes`),
    origin: parseOrigin(value.origin, `${path}.origin`),
  }
}

function parseGraphEdge(value: unknown, path: string): UnifiedGraphEdge {
  assertRecord(value, path)
  assertString(value.id, `${path}.id`)
  assertString(value.source, `${path}.source`)
  assertString(value.target, `${path}.target`)
  assertString(value.relation, `${path}.relation`)
  assertString(value.category, `${path}.category`)
  assertString(value.label, `${path}.label`)
  assertNullableNumber(value.confidence, `${path}.confidence`)
  assertNullableNumber(value.weight, `${path}.weight`)
  assertBoolean(value.directed, `${path}.directed`)

  return {
    id: value.id,
    source: value.source,
    target: value.target,
    relation: value.relation,
    category: value.category,
    label: value.label,
    confidence: value.confidence,
    weight: value.weight,
    directed: value.directed,
    attributes: parseJsonRecord(value.attributes, `${path}.attributes`),
    origin: parseOrigin(value.origin, `${path}.origin`),
  }
}

function parseGraphDataset(value: unknown, path: string): UnifiedGraphDataset {
  assertRecord(value, path)
  assertString(value.id, `${path}.id`)
  assertString(value.label, `${path}.label`)
  assertString(value.description, `${path}.description`)
  assertString(value.graphKind, `${path}.graphKind`)
  assertString(value.projectRoot, `${path}.projectRoot`)
  assertArray(value.sourceFiles, `${path}.sourceFiles`)
  assertArray(value.nodes, `${path}.nodes`)
  assertArray(value.edges, `${path}.edges`)

  return {
    id: value.id,
    label: value.label,
    description: value.description,
    graphKind: value.graphKind,
    projectRoot: value.projectRoot,
    sourceFiles: value.sourceFiles.map((item, index) =>
      parseSourceFile(item, `${path}.sourceFiles[${index}]`),
    ),
    nodes: value.nodes.map((item, index) => parseGraphNode(item, `${path}.nodes[${index}]`)),
    edges: value.edges.map((item, index) => parseGraphEdge(item, `${path}.edges[${index}]`)),
    metadata: parseJsonRecord(value.metadata, `${path}.metadata`),
  }
}

export function parseUnifiedGraphsFile(value: unknown): UnifiedGraphsFile {
  assertRecord(value, 'unifiedGraphs')
  assertString(value.schemaVersion, 'unifiedGraphs.schemaVersion')
  assertString(value.generatedAt, 'unifiedGraphs.generatedAt')
  assertString(value.generator, 'unifiedGraphs.generator')
  assertArray(value.datasets, 'unifiedGraphs.datasets')

  return {
    schemaVersion: value.schemaVersion,
    generatedAt: value.generatedAt,
    generator: value.generator,
    datasets: value.datasets.map((item, index) =>
      parseGraphDataset(item, `unifiedGraphs.datasets[${index}]`),
    ),
  }
}

function parseRawEvidenceRef(value: unknown, path: string): RawEvidenceRef {
  assertRecord(value, path)
  assertString(value.ref_id, `${path}.ref_id`)
  assertString(value.label, `${path}.label`)
  assertString(value.role, `${path}.role`)
  assertString(value.file_path, `${path}.file_path`)

  if (value.line !== null) {
    assertNumber(value.line, `${path}.line`)
  }

  return {
    ref_id: value.ref_id,
    label: value.label,
    role: value.role,
    file_path: value.file_path,
    line: value.line === null ? null : value.line,
  }
}

function parseObservationBase(value: Record<string, unknown>, path: string) {
  assertString(value.obs_id, `${path}.obs_id`)
  assertString(value.facet, `${path}.facet`)
  assertNumber(value.confidence, `${path}.confidence`)
  assertStringArray(value.linked_entity_hints, `${path}.linked_entity_hints`)
  assertArray(value.raw_evidence_refs, `${path}.raw_evidence_refs`)

  return {
    obs_id: value.obs_id,
    facet: value.facet,
    confidence: value.confidence,
    linked_entity_hints: value.linked_entity_hints,
    raw_evidence_refs: value.raw_evidence_refs.map((item, index) =>
      parseRawEvidenceRef(item, `${path}.raw_evidence_refs[${index}]`),
    ),
    attributes: value.attributes
      ? parseJsonRecord(value.attributes, `${path}.attributes`)
      : undefined,
  }
}

function parseEvidenceObservation(value: unknown, path: string): EvidenceObservation {
  assertRecord(value, path)
  const base = parseObservationBase(value, path)

  if (value.facet === 'variable') {
    assertString(value.variable_name, `${path}.variable_name`)
    assertNumber(value.contribution, `${path}.contribution`)
    assertString(value.direction, `${path}.direction`)

    if (value.time_window !== undefined) {
      assertRecord(value.time_window, `${path}.time_window`)
      assertString(value.time_window.start, `${path}.time_window.start`)
      assertString(value.time_window.end, `${path}.time_window.end`)
    }

    const timeWindow = value.time_window
      ? {
          start: value.time_window.start as string,
          end: value.time_window.end as string,
        }
      : undefined

    return {
      ...base,
      facet: 'variable',
      variable_name: value.variable_name,
      contribution: value.contribution,
      direction: value.direction as 'increase' | 'decrease' | 'unknown',
      time_window: timeWindow,
    }
  }

  if (value.facet === 'image_defect') {
    assertString(value.object, `${path}.object`)
    assertString(value.anomaly_type, `${path}.anomaly_type`)
    assertString(value.location, `${path}.location`)
    assertNumber(value.severity, `${path}.severity`)

    let image_region:
      | {
          x: number
          y: number
          w: number
          h: number
        }
      | undefined

    if (value.image_region !== undefined) {
      assertRecord(value.image_region, `${path}.image_region`)
      assertNumber(value.image_region.x, `${path}.image_region.x`)
      assertNumber(value.image_region.y, `${path}.image_region.y`)
      assertNumber(value.image_region.w, `${path}.image_region.w`)
      assertNumber(value.image_region.h, `${path}.image_region.h`)
      image_region = {
        x: value.image_region.x,
        y: value.image_region.y,
        w: value.image_region.w,
        h: value.image_region.h,
      }
    }

    return {
      ...base,
      facet: 'image_defect',
      object: value.object,
      anomaly_type: value.anomaly_type,
      location: value.location,
      morphology: parseJsonRecord(value.morphology, `${path}.morphology`),
      severity: value.severity,
      image_region,
    }
  }

  if (value.facet === 'log_event') {
    assertString(value.event_type, `${path}.event_type`)
    assertString(value.event_code, `${path}.event_code`)
    assertString(value.message, `${path}.message`)
    assertString(value.equipment, `${path}.equipment`)

    return {
      ...base,
      facet: 'log_event',
      event_type: value.event_type,
      event_code: value.event_code,
      message: value.message,
      equipment: value.equipment,
    }
  }

  throw new Error(`${path}.facet must be a supported observation facet`)
}

function parseUnifiedEvidenceValue(value: unknown, path: string): UnifiedEvidence {
  assertRecord(value, path)
  assertString(value.case_id, `${path}.case_id`)
  assertString(value.case_label, `${path}.case_label`)
  assertString(value.dataset, `${path}.dataset`)
  assertString(value.source, `${path}.source`)
  assertString(value.timestamp, `${path}.timestamp`)
  assertString(value.summary, `${path}.summary`)
  assertString(value.graph_dataset_id, `${path}.graph_dataset_id`)
  assertArray(value.observations, `${path}.observations`)

  return {
    case_id: value.case_id,
    case_label: value.case_label,
    dataset: value.dataset as UnifiedEvidence['dataset'],
    source: value.source as UnifiedEvidence['source'],
    timestamp: value.timestamp,
    summary: value.summary,
    graph_dataset_id: value.graph_dataset_id,
    observations: value.observations.map((item, index) =>
      parseEvidenceObservation(item, `${path}.observations[${index}]`),
    ),
  }
}

export function parseUnifiedEvidenceContract(value: unknown): UnifiedEvidence {
  return parseUnifiedEvidenceValue(value, 'unifiedEvidence')
}

function parseEntityCandidate(value: unknown, path: string): EntityCandidate {
  assertRecord(value, path)
  assertString(value.entity_id, `${path}.entity_id`)
  assertString(value.entity_name, `${path}.entity_name`)
  assertString(value.entity_type, `${path}.entity_type`)
  assertNumber(value.score, `${path}.score`)

  return {
    entity_id: value.entity_id,
    entity_name: value.entity_name,
    entity_type: value.entity_type,
    score: value.score,
  }
}

function parseLinkedEntity(value: unknown, path: string): LinkedEntity {
  assertRecord(value, path)
  assertString(value.link_id, `${path}.link_id`)
  assertString(value.field, `${path}.field`)
  assertString(value.mention, `${path}.mention`)
  assertNullableString(value.selected_entity_id, `${path}.selected_entity_id`)
  assertNullableString(value.selected_entity_name, `${path}.selected_entity_name`)
  assertNumber(value.score, `${path}.score`)
  assertString(value.match_type, `${path}.match_type`)
  assertBoolean(value.ambiguous, `${path}.ambiguous`)
  assertArray(value.candidates, `${path}.candidates`)

  return {
    link_id: value.link_id,
    field: value.field,
    mention: value.mention,
    selected_entity_id: value.selected_entity_id,
    selected_entity_name: value.selected_entity_name,
    score: value.score,
    match_type: value.match_type as LinkedEntity['match_type'],
    ambiguous: value.ambiguous,
    candidates: value.candidates.map((item, index) =>
      parseEntityCandidate(item, `${path}.candidates[${index}]`),
    ),
    obs_id: typeof value.obs_id === 'string' ? value.obs_id : undefined,
    facet: typeof value.facet === 'string' ? (value.facet as LinkedEntity['facet']) : undefined,
  }
}

function parseConsistencyCheck(value: unknown, path: string): ConsistencyCheck {
  assertRecord(value, path)
  assertString(value.source_field, `${path}.source_field`)
  assertString(value.target_field, `${path}.target_field`)
  assertString(value.source_entity_id, `${path}.source_entity_id`)
  assertString(value.target_entity_id, `${path}.target_entity_id`)
  assertStringArray(value.relations, `${path}.relations`)
  assertBoolean(value.passed, `${path}.passed`)
  assertNullableString(value.matched_relation, `${path}.matched_relation`)

  return {
    source_field: value.source_field,
    target_field: value.target_field,
    source_entity_id: value.source_entity_id,
    target_entity_id: value.target_entity_id,
    relations: value.relations,
    passed: value.passed,
    matched_relation: value.matched_relation,
  }
}

function parseCorrectionCandidate(value: unknown, path: string): CorrectionCandidate {
  assertRecord(value, path)
  assertString(value.candidate_id, `${path}.candidate_id`)
  assertString(value.source_field, `${path}.source_field`)
  assertString(value.source_entity_id, `${path}.source_entity_id`)
  assertString(value.target_field, `${path}.target_field`)
  if (value.target_obs_id !== undefined) {
    assertString(value.target_obs_id, `${path}.target_obs_id`)
  }
  if (value.target_facet !== undefined) {
    assertString(value.target_facet, `${path}.target_facet`)
  }
  assertString(value.suggested_entity_id, `${path}.suggested_entity_id`)
  assertString(value.suggested_value, `${path}.suggested_value`)
  assertNumber(value.score, `${path}.score`)
  assertString(value.reason, `${path}.reason`)
  assertStringArray(value.supporting_edge_ids, `${path}.supporting_edge_ids`)

  if (!isJsonValue(value.original_value)) {
    throw new Error(`${path}.original_value must be JSON-serializable`)
  }

  return {
    candidate_id: value.candidate_id,
    source_field: value.source_field,
    source_entity_id: value.source_entity_id,
    target_field: value.target_field,
    target_obs_id: typeof value.target_obs_id === 'string' ? value.target_obs_id : undefined,
    target_facet:
      typeof value.target_facet === 'string'
        ? (value.target_facet as CorrectionCandidate['target_facet'])
        : undefined,
    original_value: value.original_value,
    suggested_entity_id: value.suggested_entity_id,
    suggested_value: value.suggested_value,
    score: value.score,
    reason: value.reason,
    supporting_edge_ids: value.supporting_edge_ids,
  }
}

function parsePathEdgeDetail(value: unknown, path: string): PathEdgeDetail {
  assertRecord(value, path)
  assertString(value.edge_id, `${path}.edge_id`)
  assertString(value.source, `${path}.source`)
  assertString(value.target, `${path}.target`)
  assertString(value.relation, `${path}.relation`)
  assertNullableNumber(value.confidence, `${path}.confidence`)

  return {
    edge_id: value.edge_id,
    source: value.source,
    target: value.target,
    relation: value.relation,
    confidence: value.confidence,
  }
}

function parseRankedPath(value: unknown, path: string): RankedPath {
  assertRecord(value, path)
  assertString(value.path_id, `${path}.path_id`)
  assertString(value.source_entity_id, `${path}.source_entity_id`)
  assertString(value.target_entity_id, `${path}.target_entity_id`)
  assertString(value.target_entity_name, `${path}.target_entity_name`)
  assertStringArray(value.nodes, `${path}.nodes`)
  assertStringArray(value.node_names, `${path}.node_names`)
  assertStringArray(value.relations, `${path}.relations`)
  assertNumber(value.score, `${path}.score`)
  assertNumber(value.confidence, `${path}.confidence`)
  assertNumber(value.evidence_match, `${path}.evidence_match`)
  assertNumber(value.length, `${path}.length`)
  assertArray(value.source_edges, `${path}.source_edges`)
  assertStringArray(value.support_obs_ids, `${path}.support_obs_ids`)

  return {
    path_id: value.path_id,
    source_entity_id: value.source_entity_id,
    target_entity_id: value.target_entity_id,
    target_entity_name: value.target_entity_name,
    nodes: value.nodes,
    node_names: value.node_names,
    relations: value.relations,
    score: value.score,
    confidence: value.confidence,
    evidence_match: value.evidence_match,
    length: value.length,
    source_edges: value.source_edges.map((item, index) =>
      parsePathEdgeDetail(item, `${path}.source_edges[${index}]`),
    ),
    support_obs_ids: value.support_obs_ids,
  }
}

function parseRoute1Result(value: unknown, path: string): Route1Result {
  assertRecord(value, path)
  assertArray(value.linked_entities, `${path}.linked_entities`)
  assertNumber(value.consistency_score, `${path}.consistency_score`)
  assertStringArray(value.inconsistent_fields, `${path}.inconsistent_fields`)
  assertArray(value.consistency_checks, `${path}.consistency_checks`)
  assertArray(value.correction_candidates, `${path}.correction_candidates`)
  assertArray(value.ranked_paths, `${path}.ranked_paths`)

  return {
    linked_entities: value.linked_entities.map((item, index) =>
      parseLinkedEntity(item, `${path}.linked_entities[${index}]`),
    ),
    consistency_score: value.consistency_score,
    inconsistent_fields: value.inconsistent_fields,
    consistency_checks: value.consistency_checks.map((item, index) =>
      parseConsistencyCheck(item, `${path}.consistency_checks[${index}]`),
    ),
    correction_candidates: value.correction_candidates.map((item, index) =>
      parseCorrectionCandidate(item, `${path}.correction_candidates[${index}]`),
    ),
    ranked_paths: value.ranked_paths.map((item, index) =>
      parseRankedPath(item, `${path}.ranked_paths[${index}]`),
    ),
  }
}

function parseChannelContribution(value: unknown, path: string): ChannelContribution {
  assertRecord(value, path)
  assertString(value.entity_id, `${path}.entity_id`)
  assertString(value.name, `${path}.name`)
  assertNumber(value.contribution, `${path}.contribution`)
  assertNumber(value.rank, `${path}.rank`)

  return {
    entity_id: value.entity_id,
    name: value.name,
    contribution: value.contribution,
    rank: value.rank,
  }
}

function parseAffectedVariable(value: unknown, path: string) {
  assertRecord(value, path)
  assertString(value.entity_id, `${path}.entity_id`)
  assertString(value.name, `${path}.name`)
  assertNumber(value.propagated_score, `${path}.propagated_score`)
  assertNumber(value.rbc_contribution, `${path}.rbc_contribution`)

  return {
    entity_id: value.entity_id,
    name: value.name,
    propagated_score: value.propagated_score,
    rbc_contribution: value.rbc_contribution,
  }
}

function parseRootKGDCandidate(value: unknown, path: string): RootKGDCandidate {
  assertRecord(value, path)
  assertString(value.scenario_id, `${path}.scenario_id`)
  assertNumber(value.fault_number, `${path}.fault_number`)
  assertNumber(value.simulation_run, `${path}.simulation_run`)
  assertNumber(value.rank, `${path}.rank`)
  assertString(value.candidate_id, `${path}.candidate_id`)
  assertString(value.candidate_name, `${path}.candidate_name`)
  assertString(value.candidate_type, `${path}.candidate_type`)
  assertString(value.candidate_role, `${path}.candidate_role`)
  assertNumber(value.priority_level, `${path}.priority_level`)
  assertString(value.seed_variable_id, `${path}.seed_variable_id`)
  assertNumber(value.seed_score, `${path}.seed_score`)
  assertNumber(value.root_score, `${path}.root_score`)
  assertNumber(value.ranking_score, `${path}.ranking_score`)
  assertNumber(value.structural_ranking_score, `${path}.structural_ranking_score`)
  assertNumber(value.ranking_adjustment, `${path}.ranking_adjustment`)
  assertNumber(value.covered_contribution_mass, `${path}.covered_contribution_mass`)
  assertNumber(value.active_variable_count, `${path}.active_variable_count`)
  assertNumber(value.pattern_entropy, `${path}.pattern_entropy`)
  assertNumber(value.discriminator_alignment, `${path}.discriminator_alignment`)
  assertNumber(value.anchor_contribution_alignment, `${path}.anchor_contribution_alignment`)
  assertNumber(value.anchor_dynamic_alignment, `${path}.anchor_dynamic_alignment`)
  assertNumber(
    value.anchor_unique_contribution_alignment,
    `${path}.anchor_unique_contribution_alignment`,
  )
  assertNumber(value.anchor_memory_bonus, `${path}.anchor_memory_bonus`)
  assertNumber(value.anchor_memory_scenario_count, `${path}.anchor_memory_scenario_count`)
  assertArray(value.top_affected_variables, `${path}.top_affected_variables`)
  assertArray(value.top_support_paths, `${path}.top_support_paths`)
  assertStringArray(value.support_evidence_ids, `${path}.support_evidence_ids`)

  value.top_support_paths.forEach((item, index) =>
    assertStringArray(item, `${path}.top_support_paths[${index}]`),
  )

  return {
    scenario_id: value.scenario_id,
    fault_number: value.fault_number,
    simulation_run: value.simulation_run,
    rank: value.rank,
    candidate_id: value.candidate_id,
    candidate_name: value.candidate_name,
    candidate_type: value.candidate_type,
    candidate_role: value.candidate_role,
    priority_level: value.priority_level,
    seed_variable_id: value.seed_variable_id,
    seed_score: value.seed_score,
    root_score: value.root_score,
    ranking_score: value.ranking_score,
    structural_ranking_score: value.structural_ranking_score,
    ranking_adjustment: value.ranking_adjustment,
    covered_contribution_mass: value.covered_contribution_mass,
    active_variable_count: value.active_variable_count,
    pattern_entropy: value.pattern_entropy,
    discriminator_alignment: value.discriminator_alignment,
    anchor_contribution_alignment: value.anchor_contribution_alignment,
    anchor_dynamic_alignment: value.anchor_dynamic_alignment,
    anchor_unique_contribution_alignment: value.anchor_unique_contribution_alignment,
    anchor_memory_bonus: value.anchor_memory_bonus,
    anchor_memory_scenario_count: value.anchor_memory_scenario_count,
    top_affected_variables: value.top_affected_variables.map((item, index) =>
      parseAffectedVariable(item, `${path}.top_affected_variables[${index}]`),
    ),
    top_support_paths: value.top_support_paths as string[][],
    support_evidence_ids: value.support_evidence_ids,
  }
}

function parseRoute2Result(value: unknown, path: string): Route2Result {
  assertRecord(value, path)
  assertRecord(value.fault_signature, `${path}.fault_signature`)
  assertRecord(value.fault_signature.contribution_vector, `${path}.fault_signature.contribution_vector`)
  assertStringArray(value.fault_signature.ordered_variables, `${path}.fault_signature.ordered_variables`)
  assertArray(value.fault_signature.top_channels, `${path}.fault_signature.top_channels`)
  assertRecord(value.fault_signature.graph_contributions, `${path}.fault_signature.graph_contributions`)
  assertArray(value.ranked_candidates, `${path}.ranked_candidates`)

  for (const [key, entry] of Object.entries(value.fault_signature.contribution_vector)) {
    assertNumber(entry, `${path}.fault_signature.contribution_vector.${key}`)
  }

  for (const [key, entry] of Object.entries(value.fault_signature.graph_contributions)) {
    assertNumber(entry, `${path}.fault_signature.graph_contributions.${key}`)
  }

  return {
    fault_signature: {
      contribution_vector: value.fault_signature.contribution_vector as Record<string, number>,
      ordered_variables: value.fault_signature.ordered_variables,
      top_channels: value.fault_signature.top_channels.map((item, index) =>
        parseChannelContribution(item, `${path}.fault_signature.top_channels[${index}]`),
      ),
      graph_contributions:
        value.fault_signature.graph_contributions as Record<string, number>,
    },
    ranked_candidates: value.ranked_candidates.map((item, index) =>
      parseRootKGDCandidate(item, `${path}.ranked_candidates[${index}]`),
    ),
  }
}

function parseCrossRouteSignal(value: unknown, path: string): CrossRouteSignal {
  assertRecord(value, path)
  assertString(value.candidate_id, `${path}.candidate_id`)
  assertString(value.candidate_name, `${path}.candidate_name`)
  assertStringArray(value.route1_path_ids, `${path}.route1_path_ids`)

  if (value.route2_rank !== null) {
    assertNumber(value.route2_rank, `${path}.route2_rank`)
  }

  assertStringArray(value.shared_obs_ids, `${path}.shared_obs_ids`)

  return {
    candidate_id: value.candidate_id,
    candidate_name: value.candidate_name,
    route1_path_ids: value.route1_path_ids,
    route2_rank: value.route2_rank === null ? null : value.route2_rank,
    shared_obs_ids: value.shared_obs_ids,
  }
}

function parseAnalysisResult(value: unknown, path: string): AnalysisResult {
  assertRecord(value, path)
  assertString(value.case_id, `${path}.case_id`)
  assertString(value.timestamp, `${path}.timestamp`)
  assertString(value.graph_dataset_id, `${path}.graph_dataset_id`)
  assertArray(value.cross_route_signals, `${path}.cross_route_signals`)
  assertStringArray(value.notes, `${path}.notes`)

  return {
    case_id: value.case_id,
    timestamp: value.timestamp,
    graph_dataset_id: value.graph_dataset_id,
    route1: value.route1 === null ? null : parseRoute1Result(value.route1, `${path}.route1`),
    route2: value.route2 === null ? null : parseRoute2Result(value.route2, `${path}.route2`),
    cross_route_signals: value.cross_route_signals.map((item, index) =>
      parseCrossRouteSignal(item, `${path}.cross_route_signals[${index}]`),
    ),
    notes: value.notes,
  }
}

function parseGraphSnapshot(value: unknown, path: string): GraphSnapshot {
  assertRecord(value, path)
  assertString(value.dataset_id, `${path}.dataset_id`)
  assertString(value.label, `${path}.label`)
  assertString(value.graph_kind, `${path}.graph_kind`)
  assertString(value.description, `${path}.description`)

  return {
    dataset_id: value.dataset_id,
    label: value.label,
    graph_kind: value.graph_kind,
    description: value.description,
  }
}

function parseRuntimeCase(value: unknown, path: string): RootLensRuntimeCase {
  assertRecord(value, path)
  assertString(value.case_id, `${path}.case_id`)
  assertString(value.case_label, `${path}.case_label`)
  assertString(value.dataset, `${path}.dataset`)
  assertString(value.source, `${path}.source`)
  assertString(value.summary, `${path}.summary`)

  return {
    case_id: value.case_id,
    case_label: value.case_label,
    dataset: value.dataset as RootLensRuntimeCase['dataset'],
    source: value.source as RootLensRuntimeCase['source'],
    summary: value.summary,
    graph_snapshot: parseGraphSnapshot(value.graph_snapshot, `${path}.graph_snapshot`),
    evidence: parseUnifiedEvidenceValue(value.evidence, `${path}.evidence`),
    analysis: parseAnalysisResult(value.analysis, `${path}.analysis`),
  }
}

export function parseRootLensRuntimeFile(value: unknown): RootLensRuntimeFile {
  assertRecord(value, 'rootLensRuntime')
  assertString(value.schema_version, 'rootLensRuntime.schema_version')
  assertString(value.generated_at, 'rootLensRuntime.generated_at')
  assertString(value.generator, 'rootLensRuntime.generator')
  assertArray(value.cases, 'rootLensRuntime.cases')

  return {
    schema_version: value.schema_version,
    generated_at: value.generated_at,
    generator: value.generator,
    cases: value.cases.map((item, index) =>
      parseRuntimeCase(item, `rootLensRuntime.cases[${index}]`),
    ),
  }
}
