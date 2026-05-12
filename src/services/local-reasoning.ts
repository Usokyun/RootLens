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

function buildGraphIndex(dataset: UnifiedGraphDataset): GraphIndex {
  const nodeById = new Map(dataset.nodes.map((node) => [node.id, node]))
  const neighborsByNodeId = new Map<string, GraphNeighbor[]>()

  for (const node of dataset.nodes) {
    neighborsByNodeId.set(node.id, [])
  }

  for (const edge of dataset.edges) {
    neighborsByNodeId.get(edge.source)?.push({
      edge,
      nodeId: edge.target,
    })
    neighborsByNodeId.get(edge.target)?.push({
      edge,
      nodeId: edge.source,
    })
  }

  return {
    nodeById,
    neighborsByNodeId,
    linkedNodeIds: new Set<string>(),
  }
}

function extractObservationMentions(observation: EvidenceObservation): ObservationMention[] {
  switch (observation.facet) {
    case 'variable':
      return [
        {
          obsId: observation.obs_id,
          facet: observation.facet,
          field: 'variable',
          mention: observation.variable_name,
        },
      ]
    case 'image_defect': {
      const mentions: ObservationMention[] = [
        {
          obsId: observation.obs_id,
          facet: observation.facet,
          field: 'object',
          mention: observation.object,
        },
        {
          obsId: observation.obs_id,
          facet: observation.facet,
          field: 'anomaly_type',
          mention: observation.anomaly_type,
        },
        {
          obsId: observation.obs_id,
          facet: observation.facet,
          field: 'location',
          mention: observation.location,
        },
      ]

      const canonicalMorphology = observation.morphology.canonical
      if (typeof canonicalMorphology === 'string') {
        mentions.push({
          obsId: observation.obs_id,
          facet: observation.facet,
          field: 'morphology',
          mention: canonicalMorphology,
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
        },
        {
          obsId: observation.obs_id,
          facet: observation.facet,
          field: 'equipment',
          mention: observation.equipment,
        },
      ]
  }
}

function buildCandidates(mention: string, dataset: UnifiedGraphDataset): EntityCandidate[] {
  return dataset.nodes
    .map((node) => ({
      entity_id: node.id,
      entity_name: node.name,
      entity_type: node.category,
      score: scoreNodeMatch(mention, node),
    }))
    .filter((candidate) => candidate.score >= 0.45)
    .sort((left, right) => right.score - left.score)
    .slice(0, 3)
}

function buildLinkedEntities(
  dataset: UnifiedGraphDataset,
  evidence: UnifiedEvidence,
  graphIndex: GraphIndex,
): LinkedEntity[] {
  const linkedEntities: LinkedEntity[] = []

  for (const observation of evidence.observations) {
    for (const mentionEntry of extractObservationMentions(observation)) {
      const candidates = buildCandidates(mentionEntry.mention, dataset)
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
          ? selectedCandidate.score >= 0.97
            ? 'exact'
            : selectedCandidate.score >= 0.82
              ? 'alias'
              : 'fuzzy'
          : 'unmatched',
        ambiguous: Boolean(
          selectedCandidate &&
            secondCandidate &&
            Math.abs(selectedCandidate.score - secondCandidate.score) < 0.08,
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
      relations: ['ASSOCIATED_WITH_EVENT'],
      sourceItems: linkedByField.get('anomaly_type') ?? [],
      targetItems: linkedByField.get('log_event') ?? [],
    },
  ]
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
  const correctionCandidates: CorrectionCandidate[] = []
  const inconsistentFields = new Set<string>()

  for (const rule of buildConsistencyRules(linkedEntities)) {
    for (const sourceItem of rule.sourceItems) {
      if (!sourceItem.selected_entity_id) {
        continue
      }

      for (const targetItem of rule.targetItems) {
        if (!targetItem.selected_entity_id) {
          continue
        }

        const directMatches = findMatchingRelationEdges(
          graphIndex,
          sourceItem.selected_entity_id,
          targetItem.selected_entity_id,
          rule.relations,
        )
        const reverseMatches = findMatchingRelationEdges(
          graphIndex,
          targetItem.selected_entity_id,
          sourceItem.selected_entity_id,
          rule.relations,
        )
        const matchedEdge = directMatches[0] ?? reverseMatches[0] ?? null

        consistencyChecks.push({
          source_field: rule.sourceField,
          target_field: rule.targetField,
          source_entity_id: sourceItem.selected_entity_id,
          target_entity_id: targetItem.selected_entity_id,
          relations: rule.relations,
          passed: Boolean(matchedEdge),
          matched_relation: matchedEdge?.relation ?? null,
        })

        if (matchedEdge) {
          continue
        }

        inconsistentFields.add(rule.targetField)
        const neighbors = graphIndex.neighborsByNodeId.get(sourceItem.selected_entity_id) ?? []
        const suggestedNeighbors = neighbors
          .filter(({ edge }) => rule.relations.includes(edge.relation))
          .slice(0, 5)

        for (const [index, neighbor] of suggestedNeighbors.entries()) {
          const suggestedNode = graphIndex.nodeById.get(neighbor.nodeId)
          if (!suggestedNode) {
            continue
          }

          correctionCandidates.push({
            candidate_id: `${sourceItem.link_id}:${targetItem.link_id}:${index + 1}`,
            source_field: rule.sourceField,
            source_entity_id: sourceItem.selected_entity_id,
            target_field: rule.targetField,
            target_obs_id: targetItem.obs_id,
            target_facet: targetItem.facet,
            original_value: targetItem.mention as JsonValue,
            suggested_entity_id: suggestedNode.id,
            suggested_value: suggestedNode.name,
            score: neighbor.edge.confidence ?? 0.5,
            reason: `${sourceItem.selected_entity_id} ${neighbor.edge.relation} ${suggestedNode.id}`,
            supporting_edge_ids: [neighbor.edge.id],
          })
        }
      }
    }
  }

  const passedCount = consistencyChecks.filter((item) => item.passed).length
  const consistencyScore = consistencyChecks.length ? passedCount / consistencyChecks.length : 1

  return {
    consistencyChecks,
    correctionCandidates,
    consistencyScore,
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
    kind.includes('root cause') ||
    kind.includes('root_cause') ||
    kind.includes('fault source')
  )
}

function buildAnchorEntityIds(linkedEntities: LinkedEntity[]): string[] {
  const anchors = linkedEntities
    .filter(
      (item) =>
        item.selected_entity_id &&
        ['anomaly_type', 'variable', 'log_event', 'object', 'equipment'].includes(item.field),
    )
    .map((item) => item.selected_entity_id as string)

  return [...new Set(anchors)]
}

function findShortestPath(
  graphIndex: GraphIndex,
  startNodeId: string,
  targetNodeId: string,
  maxDepth: number,
): UnifiedGraphEdge[] | null {
  if (startNodeId === targetNodeId) {
    return []
  }

  const queue: Array<{
    currentNodeId: string
    pathEdges: UnifiedGraphEdge[]
    visited: Set<string>
  }> = [
    {
      currentNodeId: startNodeId,
      pathEdges: [],
      visited: new Set([startNodeId]),
    },
  ]

  while (queue.length) {
    const current = queue.shift()
    if (!current) {
      continue
    }

    if (current.pathEdges.length >= maxDepth) {
      continue
    }

    for (const neighbor of graphIndex.neighborsByNodeId.get(current.currentNodeId) ?? []) {
      if (current.visited.has(neighbor.nodeId)) {
        continue
      }

      const nextPath = [...current.pathEdges, neighbor.edge]
      if (neighbor.nodeId === targetNodeId) {
        return nextPath
      }

      queue.push({
        currentNodeId: neighbor.nodeId,
        pathEdges: nextPath,
        visited: new Set([...current.visited, neighbor.nodeId]),
      })
    }
  }

  return null
}

function pathNodeIdsFromEdges(pathEdges: UnifiedGraphEdge[], startNodeId: string): string[] {
  const nodeIds = [startNodeId]
  let current = startNodeId

  for (const edge of pathEdges) {
    const nextNodeId = edge.source === current ? edge.target : edge.target === current ? edge.source : null

    if (!nextNodeId) {
      const fallback = nodeIds.includes(edge.source) ? edge.target : edge.source
      nodeIds.push(fallback)
      current = fallback
      continue
    }

    nodeIds.push(nextNodeId)
    current = nextNodeId
  }

  return nodeIds
}

function buildRankedPaths(
  dataset: UnifiedGraphDataset,
  graphIndex: GraphIndex,
  linkedEntities: LinkedEntity[],
): RankedPath[] {
  const rootNodes = dataset.nodes.filter(isRootCauseNode)
  const anchorEntityIds = buildAnchorEntityIds(linkedEntities)
  const rankedPaths: RankedPath[] = []

  for (const anchorEntityId of anchorEntityIds) {
    for (const rootNode of rootNodes) {
      if (anchorEntityId === rootNode.id) {
        continue
      }

      const pathEdges = findShortestPath(graphIndex, anchorEntityId, rootNode.id, 5)
      if (!pathEdges) {
        continue
      }

      const nodeIds = pathNodeIdsFromEdges(pathEdges, anchorEntityId)
      const nodeNames = nodeIds.map(
        (nodeId) => graphIndex.nodeById.get(nodeId)?.name ?? nodeId,
      )
      const averageConfidence =
        pathEdges.reduce((sum, edge) => sum + (edge.confidence ?? 0.35), 0) /
        Math.max(pathEdges.length, 1)
      const evidenceMatch =
        nodeIds.filter((nodeId) => graphIndex.linkedNodeIds.has(nodeId)).length /
        Math.max(graphIndex.linkedNodeIds.size, 1)
      const lengthPenalty = Math.max(nodeIds.length - 1, 0) / 5
      const score = averageConfidence * 0.55 + evidenceMatch * 0.35 - lengthPenalty * 0.1
      const supportObsIds = linkedEntities
        .filter((entity) => entity.selected_entity_id && nodeIds.includes(entity.selected_entity_id))
        .map((entity) => entity.obs_id)
        .filter((item): item is string => Boolean(item))

      rankedPaths.push({
        path_id: `${anchorEntityId}->${rootNode.id}`,
        source_entity_id: anchorEntityId,
        target_entity_id: rootNode.id,
        target_entity_name: rootNode.name,
        nodes: nodeIds,
        node_names: nodeNames,
        relations: pathEdges.map((edge) => edge.relation),
        score,
        confidence: averageConfidence,
        evidence_match: evidenceMatch,
        length: Math.max(nodeIds.length - 1, 0),
        source_edges: pathEdges.map((edge) => ({
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
        (item) => item.field === 'variable' && item.obs_id && item.selected_entity_id && item.selected_entity_name,
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
    .filter((item): item is Extract<EvidenceObservation, { facet: 'variable' }> => item.facet === 'variable')
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
  if (Array.isArray(faultNumbers) && typeof faultNumbers[0] === 'number') {
    return faultNumbers[0]
  }
  return 0
}

function buildPatternEntropy(values: number[]): number {
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

  return entropy / Math.max(Math.log2(normalized.length || 1), 1)
}

function isRoute2Candidate(node: UnifiedGraphNode): boolean {
  return (
    normalizeText(node.category) === 'faultanchor' ||
    normalizeText(node.kind).includes('root cause anchor') ||
    normalizeText(node.kind).includes('root_cause_anchor')
  )
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
  const candidates = dataset.nodes.filter(isRoute2Candidate)

  const rankedCandidates = candidates
    .map<RootKGDCandidate | null>((candidateNode) => {
      const variableScores: Array<{
        propagatedScore: number
        supportPath: string[]
        variableId: string
        variableName: string
        contribution: number
      }> = []

      for (const variable of variableSupport) {
        const pathEdges = findShortestPath(graphIndex, candidateNode.id, variable.entityId, 4)
        if (!pathEdges) {
          continue
        }

        const averageConfidence =
          pathEdges.reduce((sum, edge) => sum + (edge.confidence ?? 0.35), 0) /
          Math.max(pathEdges.length, 1)
        const propagatedScore =
          variable.observation.contribution *
          Math.exp(-0.55 * pathEdges.length) *
          averageConfidence
        const supportNodeIds = pathNodeIdsFromEdges(pathEdges, candidateNode.id)
        const supportPath = supportNodeIds.map(
          (nodeId) => graphIndex.nodeById.get(nodeId)?.name ?? nodeId,
        )

        variableScores.push({
          propagatedScore,
          supportPath,
          variableId: variable.entityId,
          variableName: variable.entityName,
          contribution: variable.observation.contribution,
        })
      }

      if (!variableScores.length) {
        return null
      }

      variableScores.sort((left, right) => right.propagatedScore - left.propagatedScore)
      const coveredContribution = variableScores.reduce(
        (sum, item) => sum + item.propagatedScore,
        0,
      )
      const rootScore = Math.min(1, coveredContribution / Math.max(totalContribution, 1))
      const typeBias = normalizeText(candidateNode.category) === 'faultanchor' ? 0.08 : 0
      const roleBias = normalizeText(candidateNode.kind).includes('root cause anchor') ? 0.04 : 0
      const rankingAdjustment = typeBias + roleBias
      const rankingScore = Math.min(1, rootScore + rankingAdjustment)
      const patternEntropy = buildPatternEntropy(
        variableScores.map((item) => item.propagatedScore),
      )

      return {
        scenario_id: evidence.case_id,
        fault_number: readFaultNumber(candidateNode),
        simulation_run: 1,
        rank: 0,
        candidate_id: candidateNode.id,
        candidate_name: candidateNode.name,
        candidate_type: candidateNode.category,
        candidate_role: candidateNode.kind,
        priority_level: normalizeText(candidateNode.category) === 'faultanchor' ? 1 : 2,
        seed_variable_id: variableScores[0]?.variableId ?? '',
        seed_score: variableScores[0]?.contribution ?? 0,
        root_score: rootScore,
        ranking_score: rankingScore,
        structural_ranking_score: rootScore,
        ranking_adjustment: rankingAdjustment,
        covered_contribution_mass: rootScore,
        active_variable_count: variableScores.length,
        pattern_entropy: patternEntropy,
        discriminator_alignment: rootScore,
        anchor_contribution_alignment: rootScore,
        anchor_dynamic_alignment: rootScore * 0.72,
        anchor_unique_contribution_alignment: rootScore * 0.81,
        anchor_memory_bonus: 0,
        anchor_memory_scenario_count: 0,
        top_affected_variables: variableScores.slice(0, 5).map<AffectedVariable>((item) => ({
          entity_id: item.variableId,
          name: item.variableName,
          propagated_score: item.propagatedScore,
          rbc_contribution: item.contribution,
        })),
        top_support_paths: variableScores.slice(0, 5).map((item) => item.supportPath),
        support_evidence_ids: variableSupport
          .map((item) => item.observation.obs_id)
          .slice(0, 5),
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
    .slice(0, 8)

  const contributionVector = Object.fromEntries(
    variableSupport.map((item) => [item.entityId, item.observation.contribution]),
  )

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
        ? '路线 2 为前端本地启发式版本，用于浏览器端候选排序与路径解释。'
        : '当前输入未触发路线 2，本地推理仅生成路线 1 结果。',
    ],
  }
}
