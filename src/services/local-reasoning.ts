import type {
  JsonValue,
  UnifiedGraphDataset,
  UnifiedGraphEdge,
  UnifiedGraphNode,
} from '@/types/graph'
import type {
  AffectedVariable,
  AnalysisResult,
  ConsistencyCheck,
  CorrectionCandidate,
  CrossRouteSignal,
  EntityCandidate,
  EvidenceObservation,
  LinkedEntity,
  RankedPath,
  RootKGDCandidate,
  Route1Result,
  Route2Result,
  UnifiedEvidence,
} from '@/types/rootlens'

const ROUTE1_LINK_TOP_K = 3
const ROUTE1_LINK_MIN_SCORE = 0.45
const ROUTE1_AMBIGUOUS_THRESHOLD = 0.08
const ROUTE1_COVERAGE_WEIGHT = 0.4
const ROUTE1_RELATION_WEIGHT = 0.6
const ROUTE1_MAX_DEPTH = 5
const ROUTE1_MAX_PATHS_PER_PAIR = 6
const ROUTE1_SCORE_ALPHA = 0.55
const ROUTE1_SCORE_BETA = 0.35
const ROUTE1_SCORE_GAMMA = 0.1

const ROUTE2_TOP_VARIABLE_COUNT = 8
const ROUTE2_CANDIDATE_MAX_HOPS = 2
const ROUTE2_PROPAGATION_MAX_DEPTH = 4
const ROUTE2_PROPAGATION_MAX_PATHS = 8
const ROUTE2_COVERAGE_PENALTY_WEIGHT = 0.12
const ROUTE2_ENTROPY_PENALTY_WEIGHT = 0.03
const ROUTE2_DISCRIMINATOR_BONUS_WEIGHT = 0.08

const ALLOWED_ROUTE2_CANDIDATE_TYPES = new Set([
  'equipment',
  'stream',
  'variable',
  'component',
  'faultanchor',
])

const ROUTE2_TYPE_BIAS: Record<string, number> = {
  faultanchor: 0.08,
  equipment: 0.05,
  stream: 0.04,
  component: 0.03,
  variable: 0.01,
}

const ROUTE2_ROLE_BIAS: Record<string, number> = {
  root_cause_anchor: 0.05,
  equipment_anchor: 0.03,
  stream_anchor: 0.025,
  actuator: 0.02,
  composition_anchor: 0.015,
}

type RelationFamily =
  | 'FAULT_SOURCE'
  | 'CONTROL'
  | 'MATERIAL_FLOW'
  | 'ENERGY_TRANSFER'
  | 'PHASE_CHANGE'
  | 'COMPOSITION'
  | 'OBSERVATION'

const RELATION_FAMILY_PARAMS: Record<RelationFamily, { sigma: number; priority: number }> = {
  FAULT_SOURCE: { sigma: 0.1, priority: 7 },
  CONTROL: { sigma: 0.14, priority: 6 },
  MATERIAL_FLOW: { sigma: 0.2, priority: 5 },
  ENERGY_TRANSFER: { sigma: 0.26, priority: 4 },
  PHASE_CHANGE: { sigma: 0.3, priority: 3 },
  COMPOSITION: { sigma: 0.24, priority: 2 },
  OBSERVATION: { sigma: 0.32, priority: 1 },
}

interface GraphNeighbor {
  edge: UnifiedGraphEdge
  nodeId: string
}

interface GraphIndex {
  nodeById: Map<string, UnifiedGraphNode>
  neighborsByNodeId: Map<string, GraphNeighbor[]>
  linkedNodeIds: Set<string>
}

interface ObservationMention {
  obsId: string
  facet: EvidenceObservation['facet']
  field: string
  mention: string
  hints: string[]
}

interface SimplePath {
  nodeIds: string[]
  edges: UnifiedGraphEdge[]
}

interface Route2CandidateSeed {
  candidateNode: UnifiedGraphNode
  hopCount: number
  seedVariableId: string
  seedVariableName: string
  seedContribution: number
}

interface PropagatedVariableScore {
  obsId: string
  propagatedScore: number
  supportPath: string[]
  variableId: string
  variableName: string
  contribution: number
}

function clamp(value: number, min = 0, max = 1): number {
  return Math.min(max, Math.max(min, value))
}

function normalizeScore(value: number): number {
  return clamp(Number.isFinite(value) ? value : 0)
}

function normalizeText(value: string): string {
  return value
    .trim()
    .toLowerCase()
    .replace(/[_-]+/g, ' ')
    .replace(/[^\p{L}\p{N}\s]+/gu, ' ')
    .replace(/\s+/g, ' ')
}

function collectNodeTerms(node: UnifiedGraphNode): string[] {
  return [
    node.id,
    node.name,
    node.category,
    node.kind,
    node.description,
    ...node.aliases,
  ]
    .map((item) => normalizeText(item))
    .filter(Boolean)
}

function scoreNodeMatch(mention: string, node: UnifiedGraphNode): number {
  const normalizedMention = normalizeText(mention)
  if (!normalizedMention) {
    return 0
  }

  const terms = collectNodeTerms(node)
  let bestScore = 0

  for (const term of terms) {
    if (!term) {
      continue
    }

    if (term === normalizedMention) {
      return 0.99
    }

    if (term.includes(normalizedMention) || normalizedMention.includes(term)) {
      bestScore = Math.max(bestScore, 0.86)
      continue
    }

    const mentionTokens = new Set(normalizedMention.split(' '))
    const termTokens = new Set(term.split(' '))
    const intersectionSize = [...mentionTokens].filter((token) => termTokens.has(token)).length
    if (!intersectionSize) {
      continue
    }

    const overlap = intersectionSize / Math.max(mentionTokens.size, termTokens.size)
    bestScore = Math.max(bestScore, 0.45 + overlap * 0.35)
  }

  return bestScore
}

function scoreHintMatch(hint: string, node: UnifiedGraphNode): number {
  const normalizedHint = normalizeText(hint)
  if (!normalizedHint) {
    return 0
  }

  if (normalizedHint === normalizeText(node.id)) {
    return 1
  }

  const terms = collectNodeTerms(node)
  if (terms.some((term) => term === normalizedHint)) {
    return 0.985
  }

  if (terms.some((term) => term.includes(normalizedHint) || normalizedHint.includes(term))) {
    return 0.9
  }

  return 0
}

function isFieldCompatible(field: string, node: UnifiedGraphNode): boolean {
  const category = normalizeText(node.category)
  const kind = normalizeText(node.kind)

  switch (field) {
    case 'object':
      return (
        category.includes('object') ||
        category.includes('equipment') ||
        category.includes('processunit')
      )
    case 'anomaly_type':
      return category.includes('anomaly') || category.includes('fault') || kind.includes('anomaly')
    case 'location':
      return category.includes('location')
    case 'morphology':
      return category.includes('morphology')
    case 'variable':
      return category.includes('variable') || category.includes('signal')
    case 'equipment':
      return (
        category.includes('equipment') ||
        category.includes('processunit') ||
        category.includes('unit') ||
        category.includes('stream') ||
        category.includes('component')
      )
    case 'log_event':
      return category.includes('log') || category.includes('event')
    default:
      return true
  }
}

function buildGraphIndex(dataset: UnifiedGraphDataset): GraphIndex {
  const nodeById = new Map(dataset.nodes.map((node) => [node.id, node]))
  const neighborsByNodeId = new Map<string, GraphNeighbor[]>()

  for (const node of dataset.nodes) {
    neighborsByNodeId.set(node.id, [])
  }

  for (const edge of dataset.edges) {
    neighborsByNodeId.get(edge.source)?.push({ edge, nodeId: edge.target })
    neighborsByNodeId.get(edge.target)?.push({ edge, nodeId: edge.source })
  }

  return {
    nodeById,
    neighborsByNodeId,
    linkedNodeIds: new Set<string>(),
  }
}

function extractObservationMentions(observation: EvidenceObservation): ObservationMention[] {
  const hints = observation.linked_entity_hints

  switch (observation.facet) {
    case 'variable':
      return [
        {
          obsId: observation.obs_id,
          facet: observation.facet,
          field: 'variable',
          mention: observation.variable_name,
          hints,
        },
      ]
    case 'image_defect': {
      const mentions: ObservationMention[] = [
        {
          obsId: observation.obs_id,
          facet: observation.facet,
          field: 'object',
          mention: observation.object,
          hints,
        },
        {
          obsId: observation.obs_id,
          facet: observation.facet,
          field: 'anomaly_type',
          mention: observation.anomaly_type,
          hints,
        },
        {
          obsId: observation.obs_id,
          facet: observation.facet,
          field: 'location',
          mention: observation.location,
          hints,
        },
      ]

      const canonicalMorphology = observation.morphology.canonical
      if (typeof canonicalMorphology === 'string') {
        mentions.push({
          obsId: observation.obs_id,
          facet: observation.facet,
          field: 'morphology',
          mention: canonicalMorphology,
          hints,
        })
      }

      return mentions
    }
    case 'log_event':
      return [
        {
          obsId: observation.obs_id,
          facet: observation.facet,
          field: 'log_event',
          mention: observation.event_code || observation.event_type,
          hints,
        },
        {
          obsId: observation.obs_id,
          facet: observation.facet,
          field: 'equipment',
          mention: observation.equipment,
          hints,
        },
      ]
  }
}

function buildCandidates(
  mention: string,
  field: string,
  dataset: UnifiedGraphDataset,
  hints: string[] = [],
): EntityCandidate[] {
  return dataset.nodes
    .map((node) => {
      const mentionScore = scoreNodeMatch(mention, node)
      const hintScore = hints.reduce((best, hint) => Math.max(best, scoreHintMatch(hint, node)), 0)
      const compatibilityMultiplier = isFieldCompatible(field, node) ? 1 : 0.35

      return {
        entity_id: node.id,
        entity_name: node.name,
        entity_type: node.category,
        score: normalizeScore(Math.max(mentionScore, hintScore) * compatibilityMultiplier),
      }
    })
    .filter((candidate) => candidate.score >= ROUTE1_LINK_MIN_SCORE)
    .sort((left, right) => right.score - left.score)
    .slice(0, ROUTE1_LINK_TOP_K)
}

function buildLinkedEntities(
  dataset: UnifiedGraphDataset,
  evidence: UnifiedEvidence,
  graphIndex: GraphIndex,
): LinkedEntity[] {
  const linkedEntities: LinkedEntity[] = []

  for (const observation of evidence.observations) {
    for (const mentionEntry of extractObservationMentions(observation)) {
      const candidates = buildCandidates(
        mentionEntry.mention,
        mentionEntry.field,
        dataset,
        mentionEntry.hints,
      )
      const selectedCandidate = candidates[0] ?? null
      const secondCandidate = candidates[1] ?? null

      if (selectedCandidate?.entity_id) {
        graphIndex.linkedNodeIds.add(selectedCandidate.entity_id)
      }

      linkedEntities.push({
        link_id: `${mentionEntry.obsId}:${mentionEntry.field}`,
        field: mentionEntry.field,
        mention: mentionEntry.mention,
        selected_entity_id: selectedCandidate?.entity_id ?? null,
        selected_entity_name: selectedCandidate?.entity_name ?? null,
        score: selectedCandidate?.score ?? 0,
        match_type: selectedCandidate
          ? selectedCandidate.score >= 0.995
            ? 'exact'
            : selectedCandidate.score >= 0.9
              ? 'alias'
              : 'fuzzy'
          : 'unmatched',
        ambiguous: Boolean(
          selectedCandidate &&
            secondCandidate &&
            Math.abs(selectedCandidate.score - secondCandidate.score) < ROUTE1_AMBIGUOUS_THRESHOLD,
        ),
        candidates,
        obs_id: mentionEntry.obsId,
        facet: mentionEntry.facet,
      })
    }
  }

  return linkedEntities
}

function findMatchingRelationEdges(
  graphIndex: GraphIndex,
  sourceEntityId: string,
  targetEntityId: string,
  expectedRelations: string[],
): UnifiedGraphEdge[] {
  const neighbors = graphIndex.neighborsByNodeId.get(sourceEntityId) ?? []
  return neighbors
    .filter(
      ({ edge, nodeId }) =>
        nodeId === targetEntityId && expectedRelations.includes(edge.relation),
    )
    .map(({ edge }) => edge)
}

function buildConsistencyRules(linkedEntities: LinkedEntity[]) {
  const linkedByField = new Map<string, LinkedEntity[]>()

  for (const entity of linkedEntities) {
    const list = linkedByField.get(entity.field) ?? []
    list.push(entity)
    linkedByField.set(entity.field, list)
  }

  return [
    {
      sourceField: 'object',
      targetField: 'anomaly_type',
      relations: ['HAS_ANOMALY'],
      sourceItems: linkedByField.get('object') ?? [],
      targetItems: linkedByField.get('anomaly_type') ?? [],
    },
    {
      sourceField: 'anomaly_type',
      targetField: 'morphology',
      relations: ['HAS_MORPHOLOGY'],
      sourceItems: linkedByField.get('anomaly_type') ?? [],
      targetItems: linkedByField.get('morphology') ?? [],
    },
    {
      sourceField: 'anomaly_type',
      targetField: 'location',
      relations: ['OCCURS_ON', 'HAS_LOCATION'],
      sourceItems: linkedByField.get('anomaly_type') ?? [],
      targetItems: linkedByField.get('location') ?? [],
    },
    {
      sourceField: 'variable',
      targetField: 'equipment',
      relations: ['OBSERVED_BY', 'MEASURED_IN', 'BELONGS_TO_UNIT'],
      sourceItems: linkedByField.get('variable') ?? [],
      targetItems: linkedByField.get('equipment') ?? [],
    },
    {
      sourceField: 'anomaly_type',
      targetField: 'log_event',
      relations: ['ASSOCIATED_WITH_EVENT', 'INDICATES'],
      sourceItems: linkedByField.get('anomaly_type') ?? [],
      targetItems: linkedByField.get('log_event') ?? [],
    },
  ]
}

function buildCorrectionSuggestions(
  graphIndex: GraphIndex,
  sourceItem: LinkedEntity,
  targetItem: LinkedEntity,
  relations: string[],
): CorrectionCandidate[] {
  if (!sourceItem.selected_entity_id) {
    return []
  }

  const suggestions = new Map<string, CorrectionCandidate>()

  for (const neighbor of graphIndex.neighborsByNodeId.get(sourceItem.selected_entity_id) ?? []) {
    if (!relations.includes(neighbor.edge.relation)) {
      continue
    }

    const suggestedNode = graphIndex.nodeById.get(neighbor.nodeId)
    if (!suggestedNode) {
      continue
    }

    if (targetItem.selected_entity_id && targetItem.selected_entity_id === suggestedNode.id) {
      continue
    }

    const edgeConfidence = neighbor.edge.confidence ?? neighbor.edge.weight ?? 0.5
    const targetHintScore = scoreNodeMatch(targetItem.mention, suggestedNode)
    const score = normalizeScore(edgeConfidence * 0.7 + targetHintScore * 0.3)
    const candidateId = `${sourceItem.link_id}:${targetItem.link_id}:${suggestedNode.id}`

    suggestions.set(candidateId, {
      candidate_id: candidateId,
      source_field: sourceItem.field,
      source_entity_id: sourceItem.selected_entity_id,
      target_field: targetItem.field,
      target_obs_id: targetItem.obs_id,
      target_facet: targetItem.facet,
      original_value: (targetItem.selected_entity_name ?? targetItem.mention) as JsonValue,
      suggested_entity_id: suggestedNode.id,
      suggested_value: suggestedNode.name,
      score,
      reason: `${sourceItem.selected_entity_id} ${neighbor.edge.relation} ${suggestedNode.id}`,
      supporting_edge_ids: [neighbor.edge.id],
    })
  }

  return [...suggestions.values()].sort((left, right) => right.score - left.score).slice(0, 5)
}

function buildConsistencyAndCorrections(
  graphIndex: GraphIndex,
  linkedEntities: LinkedEntity[],
): {
  consistencyChecks: ConsistencyCheck[]
  correctionCandidates: CorrectionCandidate[]
  consistencyScore: number
  inconsistentFields: string[]
} {
  const consistencyChecks: ConsistencyCheck[] = []
  const correctionCandidateMap = new Map<string, CorrectionCandidate>()
  const inconsistentFields = new Set<string>()
  const participantItems = new Map<string, LinkedEntity>()
  let passedChecks = 0
  let totalChecks = 0

  for (const rule of buildConsistencyRules(linkedEntities)) {
    for (const sourceItem of rule.sourceItems) {
      participantItems.set(sourceItem.link_id, sourceItem)

      for (const targetItem of rule.targetItems) {
        participantItems.set(targetItem.link_id, targetItem)

        if (!sourceItem.selected_entity_id) {
          inconsistentFields.add(rule.sourceField)
          continue
        }

        const matchedEdge = targetItem.selected_entity_id
          ? findMatchingRelationEdges(
              graphIndex,
              sourceItem.selected_entity_id,
              targetItem.selected_entity_id,
              rule.relations,
            )[0] ??
            findMatchingRelationEdges(
              graphIndex,
              targetItem.selected_entity_id,
              sourceItem.selected_entity_id,
              rule.relations,
            )[0] ??
            null
          : null

        if (targetItem.selected_entity_id) {
          totalChecks += 1
          const passed = Boolean(matchedEdge)

          consistencyChecks.push({
            source_field: rule.sourceField,
            target_field: rule.targetField,
            source_entity_id: sourceItem.selected_entity_id,
            target_entity_id: targetItem.selected_entity_id,
            relations: rule.relations,
            passed,
            matched_relation: matchedEdge?.relation ?? null,
          })

          if (passed) {
            passedChecks += 1
            continue
          }
        }

        inconsistentFields.add(rule.targetField)
        for (const candidate of buildCorrectionSuggestions(
          graphIndex,
          sourceItem,
          targetItem,
          rule.relations,
        )) {
          const existing = correctionCandidateMap.get(candidate.candidate_id)
          if (!existing || candidate.score > existing.score) {
            correctionCandidateMap.set(candidate.candidate_id, candidate)
          }
        }
      }
    }
  }

  const coverageParticipants = [...participantItems.values()]
  const linkedParticipantCount = coverageParticipants.filter((item) => item.selected_entity_id).length
  const entityCoverage = coverageParticipants.length
    ? linkedParticipantCount / coverageParticipants.length
    : 1
  const relationPassRate = totalChecks ? passedChecks / totalChecks : 1
  const consistencyScore =
    entityCoverage * ROUTE1_COVERAGE_WEIGHT + relationPassRate * ROUTE1_RELATION_WEIGHT

  return {
    consistencyChecks,
    correctionCandidates: [...correctionCandidateMap.values()].sort(
      (left, right) => right.score - left.score,
    ),
    consistencyScore: normalizeScore(consistencyScore),
    inconsistentFields: [...inconsistentFields],
  }
}

function isRootCauseNode(node: UnifiedGraphNode): boolean {
  const category = normalizeText(node.category)
  const kind = normalizeText(node.kind)

  return (
    category === 'rootcause' ||
    category === 'causecategory' ||
    category === 'faultanchor' ||
    category === 'faulttype' ||
    kind.includes('root cause') ||
    kind.includes('root_cause') ||
    kind.includes('fault source') ||
    kind.includes('root cause anchor')
  )
}

function buildAnchorEntityIds(linkedEntities: LinkedEntity[]): string[] {
  const primaryAnchors = linkedEntities
    .filter(
      (item) =>
        item.selected_entity_id &&
        ['anomaly_type', 'variable', 'log_event'].includes(item.field),
    )
    .map((item) => item.selected_entity_id as string)

  if (primaryAnchors.length) {
    return [...new Set(primaryAnchors)]
  }

  const fallbackAnchors = linkedEntities
    .filter(
      (item) => item.selected_entity_id && ['object', 'equipment'].includes(item.field),
    )
    .map((item) => item.selected_entity_id as string)

  return [...new Set(fallbackAnchors)]
}

function sortedNeighbors(graphIndex: GraphIndex, nodeId: string): GraphNeighbor[] {
  return [...(graphIndex.neighborsByNodeId.get(nodeId) ?? [])].sort(
    (left, right) =>
      (right.edge.confidence ?? right.edge.weight ?? 0) - (left.edge.confidence ?? left.edge.weight ?? 0),
  )
}

function findSimplePaths(
  graphIndex: GraphIndex,
  startNodeId: string,
  targetNodeId: string,
  maxDepth: number,
  maxPaths: number,
): SimplePath[] {
  if (startNodeId === targetNodeId) {
    return [{ nodeIds: [startNodeId], edges: [] }]
  }

  const results: SimplePath[] = []

  const walk = (
    currentNodeId: string,
    nodeIds: string[],
    edges: UnifiedGraphEdge[],
    visited: Set<string>,
  ) => {
    if (results.length >= maxPaths || edges.length >= maxDepth) {
      return
    }

    for (const neighbor of sortedNeighbors(graphIndex, currentNodeId)) {
      if (visited.has(neighbor.nodeId)) {
        continue
      }

      const nextNodeIds = [...nodeIds, neighbor.nodeId]
      const nextEdges = [...edges, neighbor.edge]

      if (neighbor.nodeId === targetNodeId) {
        results.push({ nodeIds: nextNodeIds, edges: nextEdges })
        if (results.length >= maxPaths) {
          return
        }
        continue
      }

      walk(
        neighbor.nodeId,
        nextNodeIds,
        nextEdges,
        new Set([...visited, neighbor.nodeId]),
      )

      if (results.length >= maxPaths) {
        return
      }
    }
  }

  walk(startNodeId, [startNodeId], [], new Set([startNodeId]))
  return results
}

function buildRankedPaths(
  dataset: UnifiedGraphDataset,
  graphIndex: GraphIndex,
  linkedEntities: LinkedEntity[],
): RankedPath[] {
  const rootNodes = dataset.nodes.filter(isRootCauseNode)
  const anchorEntityIds = buildAnchorEntityIds(linkedEntities)
  const rankedPaths: RankedPath[] = []
  const seenPathKeys = new Set<string>()

  for (const anchorEntityId of anchorEntityIds) {
    for (const rootNode of rootNodes) {
      if (anchorEntityId === rootNode.id) {
        continue
      }

      for (const [index, path] of findSimplePaths(
        graphIndex,
        anchorEntityId,
        rootNode.id,
        ROUTE1_MAX_DEPTH,
        ROUTE1_MAX_PATHS_PER_PAIR,
      ).entries()) {
        const pathKey = path.nodeIds.join('>')
        if (seenPathKeys.has(pathKey)) {
          continue
        }

        seenPathKeys.add(pathKey)

        const averageConfidence =
          path.edges.reduce((sum, edge) => sum + (edge.confidence ?? edge.weight ?? 0.35), 0) /
          Math.max(path.edges.length, 1)
        const evidenceMatch =
          path.nodeIds.filter((nodeId) => graphIndex.linkedNodeIds.has(nodeId)).length /
          Math.max(graphIndex.linkedNodeIds.size, 1)
        const lengthPenalty = Math.max(path.nodeIds.length - 1, 0) / ROUTE1_MAX_DEPTH
        const supportObsIds = linkedEntities
          .filter((entity) => entity.selected_entity_id && path.nodeIds.includes(entity.selected_entity_id))
          .map((entity) => entity.obs_id)
          .filter((item): item is string => Boolean(item))
        const score =
          averageConfidence * ROUTE1_SCORE_ALPHA +
          evidenceMatch * ROUTE1_SCORE_BETA -
          lengthPenalty * ROUTE1_SCORE_GAMMA

        rankedPaths.push({
          path_id: `${anchorEntityId}->${rootNode.id}:${index + 1}`,
          source_entity_id: anchorEntityId,
          target_entity_id: rootNode.id,
          target_entity_name: rootNode.name,
          nodes: path.nodeIds,
          node_names: path.nodeIds.map((nodeId) => graphIndex.nodeById.get(nodeId)?.name ?? nodeId),
          relations: path.edges.map((edge) => edge.relation),
          score,
          confidence: averageConfidence,
          evidence_match: evidenceMatch,
          length: Math.max(path.nodeIds.length - 1, 0),
          source_edges: path.edges.map((edge) => ({
            edge_id: edge.id,
            source: edge.source,
            target: edge.target,
            relation: edge.relation,
            confidence: edge.confidence,
          })),
          support_obs_ids: [...new Set(supportObsIds)],
        })
      }
    }
  }

  return rankedPaths
    .sort((left, right) => right.score - left.score)
    .slice(0, 10)
}

function buildRoute1Result(dataset: UnifiedGraphDataset, evidence: UnifiedEvidence): Route1Result {
  const graphIndex = buildGraphIndex(dataset)
  const linkedEntities = buildLinkedEntities(dataset, evidence, graphIndex)
  const consistency = buildConsistencyAndCorrections(graphIndex, linkedEntities)

  return {
    linked_entities: linkedEntities,
    consistency_score: consistency.consistencyScore,
    inconsistent_fields: consistency.inconsistentFields,
    consistency_checks: consistency.consistencyChecks,
    correction_candidates: consistency.correctionCandidates,
    ranked_paths: buildRankedPaths(dataset, graphIndex, linkedEntities),
  }
}

function extractVariableSupport(
  evidence: UnifiedEvidence,
  route1: Route1Result,
): Array<{
  observation: Extract<EvidenceObservation, { facet: 'variable' }>
  entityId: string
  entityName: string
}> {
  const variableLinks = new Map(
    route1.linked_entities
      .filter(
        (item) =>
          item.field === 'variable' &&
          item.obs_id &&
          item.selected_entity_id &&
          item.selected_entity_name,
      )
      .map((item) => [
        item.obs_id as string,
        {
          entityId: item.selected_entity_id as string,
          entityName: item.selected_entity_name as string,
        },
      ]),
  )

  return evidence.observations
    .filter(
      (item): item is Extract<EvidenceObservation, { facet: 'variable' }> => item.facet === 'variable',
    )
    .map((observation) => {
      const linked = variableLinks.get(observation.obs_id)
      if (!linked) {
        return null
      }

      return {
        observation,
        entityId: linked.entityId,
        entityName: linked.entityName,
      }
    })
    .filter((item): item is NonNullable<typeof item> => Boolean(item))
}

function readFaultNumber(node: UnifiedGraphNode): number {
  const faultNumbers = node.attributes.fault_numbers
  if (Array.isArray(faultNumbers) && faultNumbers.length) {
    const parsed = Number(faultNumbers[0])
    return Number.isFinite(parsed) ? parsed : 0
  }

  const faultNumber = Number(node.attributes.fault_number)
  return Number.isFinite(faultNumber) ? faultNumber : 0
}

function buildPatternEntropy(values: number[]): number {
  if (values.length <= 1) {
    return 0
  }

  const total = values.reduce((sum, value) => sum + value, 0)
  if (!total) {
    return 0
  }

  const normalized = values.map((value) => value / total)
  const entropy = normalized.reduce((sum, value) => {
    if (!value) {
      return sum
    }

    return sum - value * Math.log2(value)
  }, 0)

  return entropy / Math.max(Math.log2(normalized.length), 1)
}

function isAllowedRoute2Candidate(node: UnifiedGraphNode): boolean {
  const category = normalizeText(node.category)
  const kind = normalizeText(node.kind)

  if (!ALLOWED_ROUTE2_CANDIDATE_TYPES.has(category)) {
    return kind.includes('root cause anchor') || kind.includes('root_cause_anchor')
  }

  if (category === 'variable' && (kind === 'observation' || kind === 'support only' || kind === 'support_only')) {
    return false
  }

  return true
}

function enumerateRoute2Candidates(
  graphIndex: GraphIndex,
  variableSupport: Array<{
    observation: Extract<EvidenceObservation, { facet: 'variable' }>
    entityId: string
    entityName: string
  }>,
): Route2CandidateSeed[] {
  const candidateById = new Map<string, Route2CandidateSeed>()
  const topVariables = variableSupport
    .slice()
    .sort((left, right) => right.observation.contribution - left.observation.contribution)
    .slice(0, ROUTE2_TOP_VARIABLE_COUNT)

  for (const variable of topVariables) {
    const queue: Array<{
      nodeId: string
      hopCount: number
      visited: Set<string>
    }> = [
      {
        nodeId: variable.entityId,
        hopCount: 0,
        visited: new Set([variable.entityId]),
      },
    ]

    while (queue.length) {
      const current = queue.shift()
      if (!current || current.hopCount > ROUTE2_CANDIDATE_MAX_HOPS) {
        continue
      }

      const currentNode = graphIndex.nodeById.get(current.nodeId)
      if (currentNode && current.hopCount > 0 && isAllowedRoute2Candidate(currentNode)) {
        const existing = candidateById.get(currentNode.id)
        if (
          !existing ||
          current.hopCount < existing.hopCount ||
          (current.hopCount === existing.hopCount &&
            variable.observation.contribution > existing.seedContribution)
        ) {
          candidateById.set(currentNode.id, {
            candidateNode: currentNode,
            hopCount: current.hopCount,
            seedVariableId: variable.entityId,
            seedVariableName: variable.entityName,
            seedContribution: variable.observation.contribution,
          })
        }
      }

      if (current.hopCount >= ROUTE2_CANDIDATE_MAX_HOPS) {
        continue
      }

      for (const neighbor of sortedNeighbors(graphIndex, current.nodeId)) {
        if (current.visited.has(neighbor.nodeId)) {
          continue
        }

        queue.push({
          nodeId: neighbor.nodeId,
          hopCount: current.hopCount + 1,
          visited: new Set([...current.visited, neighbor.nodeId]),
        })
      }
    }
  }

  return [...candidateById.values()]
}

function relationFamilyForEdge(edge: UnifiedGraphEdge): RelationFamily {
  const relation = normalizeText(edge.relation)

  if (
    relation === 'causes' ||
    relation === 'has plausible cause' ||
    relation === 'indicates'
  ) {
    return 'FAULT_SOURCE'
  }

  if (relation === 'acts on' || relation === 'controls') {
    return 'CONTROL'
  }

  if (
    relation === 'flows to' ||
    relation === 'connects to' ||
    relation === 'supplies' ||
    relation === 'drives demand for'
  ) {
    return 'MATERIAL_FLOW'
  }

  if (relation.includes('heat') || relation.includes('energy') || relation.includes('cool')) {
    return 'ENERGY_TRANSFER'
  }

  if (relation.includes('phase') || relation.includes('condens') || relation.includes('evapor')) {
    return 'PHASE_CHANGE'
  }

  if (
    relation === 'part of' ||
    relation === 'has component' ||
    relation === 'carries component' ||
    relation === 'realizes'
  ) {
    return 'COMPOSITION'
  }

  return 'OBSERVATION'
}

function scorePropagationPath(path: SimplePath, graphIndex: GraphIndex): number {
  let signal = 1

  for (const [index, edge] of path.edges.entries()) {
    const family = relationFamilyForEdge(edge)
    const params = RELATION_FAMILY_PARAMS[family]
    const edgeWeight = edge.weight ?? edge.confidence ?? 0.55
    const receiverNodeId = path.nodeIds[index + 1]
    const receiverDegree = graphIndex.neighborsByNodeId.get(receiverNodeId)?.length ?? 1
    const priorityFactor = 0.55 + params.priority / 10
    const stepGain =
      edgeWeight * priorityFactor * Math.exp(-params.sigma * (index + 1)) /
      Math.max(Math.sqrt(receiverDegree), 1)

    signal *= Math.min(1, stepGain)
  }

  return normalizeScore(signal)
}

function bestPropagationPathForCandidate(
  graphIndex: GraphIndex,
  candidateId: string,
  variableId: string,
): { path: SimplePath; score: number } | null {
  let best: { path: SimplePath; score: number } | null = null

  for (const path of findSimplePaths(
    graphIndex,
    candidateId,
    variableId,
    ROUTE2_PROPAGATION_MAX_DEPTH,
    ROUTE2_PROPAGATION_MAX_PATHS,
  )) {
    const score = scorePropagationPath(path, graphIndex)
    if (!best || score > best.score) {
      best = { path, score }
    }
  }

  return best
}

function cosineSimilarity(
  observed: Record<string, number>,
  predicted: Record<string, number>,
): number {
  const keys = new Set([...Object.keys(observed), ...Object.keys(predicted)])
  let dot = 0
  let observedNorm = 0
  let predictedNorm = 0

  for (const key of keys) {
    const observedValue = observed[key] ?? 0
    const predictedValue = predicted[key] ?? 0
    dot += observedValue * predictedValue
    observedNorm += observedValue * observedValue
    predictedNorm += predictedValue * predictedValue
  }

  if (!observedNorm || !predictedNorm) {
    return 0
  }

  return normalizeScore(dot / (Math.sqrt(observedNorm) * Math.sqrt(predictedNorm)))
}

function typeBiasForNode(node: UnifiedGraphNode): number {
  return ROUTE2_TYPE_BIAS[normalizeText(node.category)] ?? 0
}

function roleBiasForNode(node: UnifiedGraphNode): number {
  return ROUTE2_ROLE_BIAS[normalizeText(node.kind)] ?? 0
}

function priorityLevelForCandidate(seed: Route2CandidateSeed): number {
  if (normalizeText(seed.candidateNode.kind).includes('root cause anchor')) {
    return 1
  }

  return seed.hopCount <= 1 ? 1 : 2
}

function fallbackRoute2Candidates(dataset: UnifiedGraphDataset): Route2CandidateSeed[] {
  return dataset.nodes
    .filter((node) => isRootCauseNode(node) || isAllowedRoute2Candidate(node))
    .map((candidateNode) => ({
      candidateNode,
      hopCount: 2,
      seedVariableId: '',
      seedVariableName: '',
      seedContribution: 0,
    }))
}

function buildRoute2Result(
  dataset: UnifiedGraphDataset,
  evidence: UnifiedEvidence,
  route1: Route1Result,
): Route2Result | null {
  const variableSupport = extractVariableSupport(evidence, route1)
  if (!variableSupport.length) {
    return null
  }

  const graphIndex = buildGraphIndex(dataset)
  const totalContribution = variableSupport.reduce(
    (sum, item) => sum + item.observation.contribution,
    0,
  )
  const contributionVector = Object.fromEntries(
    variableSupport.map((item) => [item.entityId, item.observation.contribution]),
  )
  const candidateSeeds = enumerateRoute2Candidates(graphIndex, variableSupport)
  const effectiveSeeds = candidateSeeds.length ? candidateSeeds : fallbackRoute2Candidates(dataset)

  const rankedCandidates = effectiveSeeds
    .map<RootKGDCandidate | null>((seed) => {
      const variableScores: PropagatedVariableScore[] = []

      for (const variable of variableSupport) {
        const bestPath = bestPropagationPathForCandidate(
          graphIndex,
          seed.candidateNode.id,
          variable.entityId,
        )
        if (!bestPath) {
          continue
        }

        variableScores.push({
          obsId: variable.observation.obs_id,
          propagatedScore: variable.observation.contribution * bestPath.score,
          supportPath: bestPath.path.nodeIds.map(
            (nodeId) => graphIndex.nodeById.get(nodeId)?.name ?? nodeId,
          ),
          variableId: variable.entityId,
          variableName: variable.entityName,
          contribution: variable.observation.contribution,
        })
      }

      if (!variableScores.length) {
        return null
      }

      variableScores.sort((left, right) => right.propagatedScore - left.propagatedScore)
      const predictedVector = Object.fromEntries(
        variableScores.map((item) => [item.variableId, item.propagatedScore]),
      )
      const rootScore = cosineSimilarity(contributionVector, predictedVector)
      const coveredContributionMass =
        variableScores.reduce(
          (sum, item) => sum + Math.min(item.contribution, item.propagatedScore),
          0,
        ) / Math.max(totalContribution, 1)
      const patternEntropy = buildPatternEntropy(
        variableScores.map((item) => item.propagatedScore),
      )
      const totalPredicted = variableScores.reduce((sum, item) => sum + item.propagatedScore, 0)
      const discriminatorAlignment = totalPredicted
        ? variableScores[0].propagatedScore / totalPredicted
        : 0
      const anchorContributionAlignment = coveredContributionMass
      const anchorDynamicAlignment = variableScores[0]
        ? normalizeScore(variableScores[0].propagatedScore / Math.max(variableScores[0].contribution, 1e-6))
        : 0
      const anchorUniqueContributionAlignment =
        variableScores.length > 1 && variableScores[0].propagatedScore
          ? normalizeScore(
              (variableScores[0].propagatedScore - variableScores[1].propagatedScore) /
                variableScores[0].propagatedScore,
            )
          : variableScores[0]
            ? 1
            : 0

      const coveragePenalty = (1 - coveredContributionMass) * ROUTE2_COVERAGE_PENALTY_WEIGHT
      const entropyPenalty = patternEntropy * ROUTE2_ENTROPY_PENALTY_WEIGHT
      const typeBias = typeBiasForNode(seed.candidateNode)
      const roleBias = roleBiasForNode(seed.candidateNode)
      const discriminatorBonus = discriminatorAlignment * ROUTE2_DISCRIMINATOR_BONUS_WEIGHT
      const rankingAdjustment =
        typeBias + roleBias + discriminatorBonus - coveragePenalty - entropyPenalty
      const structuralRankingScore = normalizeScore(rootScore * 0.7 + coveredContributionMass * 0.3)
      const rankingScore = normalizeScore(structuralRankingScore + rankingAdjustment)

      return {
        scenario_id: evidence.case_id,
        fault_number: readFaultNumber(seed.candidateNode),
        simulation_run: 1,
        rank: 0,
        candidate_id: seed.candidateNode.id,
        candidate_name: seed.candidateNode.name,
        candidate_type: seed.candidateNode.category,
        candidate_role: seed.candidateNode.kind,
        priority_level: priorityLevelForCandidate(seed),
        seed_variable_id: seed.seedVariableId || variableScores[0]?.variableId || '',
        seed_score: seed.seedContribution || variableScores[0]?.contribution || 0,
        root_score: rootScore,
        ranking_score: rankingScore,
        structural_ranking_score: structuralRankingScore,
        ranking_adjustment: rankingAdjustment,
        covered_contribution_mass: normalizeScore(coveredContributionMass),
        active_variable_count: variableScores.length,
        pattern_entropy: patternEntropy,
        discriminator_alignment: discriminatorAlignment,
        anchor_contribution_alignment: anchorContributionAlignment,
        anchor_dynamic_alignment: anchorDynamicAlignment,
        anchor_unique_contribution_alignment: anchorUniqueContributionAlignment,
        anchor_memory_bonus: 0,
        anchor_memory_scenario_count: 0,
        top_affected_variables: variableScores.slice(0, 5).map<AffectedVariable>((item) => ({
          entity_id: item.variableId,
          name: item.variableName,
          propagated_score: item.propagatedScore,
          rbc_contribution: item.contribution,
        })),
        top_support_paths: variableScores.slice(0, 5).map((item) => item.supportPath),
        support_evidence_ids: [
          ...new Set(variableScores.slice(0, 5).map((item) => item.obsId)),
        ],
      }
    })
    .filter((item): item is RootKGDCandidate => Boolean(item))
    .sort((left, right) => right.ranking_score - left.ranking_score)
    .slice(0, 8)
    .map((candidate, index) => ({
      ...candidate,
      rank: index + 1,
    }))

  if (!rankedCandidates.length) {
    return null
  }

  const topChannels = variableSupport
    .slice()
    .sort((left, right) => right.observation.contribution - left.observation.contribution)
    .map((item, index) => ({
      entity_id: item.entityId,
      name: item.entityName,
      contribution: item.observation.contribution,
      rank: index + 1,
    }))
    .slice(0, ROUTE2_TOP_VARIABLE_COUNT)

  return {
    fault_signature: {
      contribution_vector: contributionVector,
      ordered_variables: topChannels.map((item) => item.entity_id),
      top_channels: topChannels,
      graph_contributions: contributionVector,
    },
    ranked_candidates: rankedCandidates,
  }
}

function buildCrossRouteSignals(
  route1: Route1Result | null,
  route2: Route2Result | null,
): CrossRouteSignal[] {
  if (!route1 || !route2) {
    return []
  }

  const route2ById = new Map(
    route2.ranked_candidates.map((candidate) => [candidate.candidate_id, candidate]),
  )
  const grouped = new Map<
    string,
    {
      candidateId: string
      candidateName: string
      route1PathIds: string[]
      sharedObsIds: Set<string>
    }
  >()

  for (const path of route1.ranked_paths) {
    const route2Candidate = route2ById.get(path.target_entity_id)
    if (!route2Candidate) {
      continue
    }

    const existing = grouped.get(path.target_entity_id) ?? {
      candidateId: path.target_entity_id,
      candidateName: path.target_entity_name,
      route1PathIds: [],
      sharedObsIds: new Set<string>(),
    }
    existing.route1PathIds.push(path.path_id)
    path.support_obs_ids.forEach((obsId) => existing.sharedObsIds.add(obsId))
    grouped.set(path.target_entity_id, existing)
  }

  return [...grouped.values()].map((item) => ({
    candidate_id: item.candidateId,
    candidate_name: item.candidateName,
    route1_path_ids: item.route1PathIds,
    route2_rank: route2ById.get(item.candidateId)?.rank ?? null,
    shared_obs_ids: [...item.sharedObsIds],
  }))
}

export function buildLocalAnalysisResult(
  dataset: UnifiedGraphDataset,
  evidence: UnifiedEvidence,
): AnalysisResult {
  const route1 = buildRoute1Result(dataset, evidence)
  const route2 = buildRoute2Result(dataset, evidence, route1)

  return {
    case_id: evidence.case_id,
    timestamp: evidence.timestamp,
    graph_dataset_id: dataset.id,
    route1,
    route2,
    cross_route_signals: buildCrossRouteSignals(route1, route2),
    notes: [
      '当前结果由浏览器本地推理引擎生成，不依赖后端 API。',
      route2
        ? '路线 2 采用浏览器端启发式候选枚举、关系族衰减传播和结构化评分。'
        : '当前输入未触发路线 2，本地推理仅生成路线 1 结果。',
    ],
  }
}
