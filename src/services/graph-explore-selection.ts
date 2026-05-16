import type { PathGraph, RankedRootCause, ReviewTarget } from '@/api/contracts'
import type { WorkbenchState } from '@/services/workbench-state'
import type { UnifiedGraphDataset } from '@/types/graph'

export type GraphExploreSelectionState = Pick<
  WorkbenchState,
  | 'selectedCandidateId'
  | 'selectedPathId'
  | 'selectedReviewTargetKey'
  | 'selectedGraphNodeId'
  | 'subgraphMode'
  | 'selectedSubgraphNodeId'
  | 'selectedSubgraphEdgeId'
>

export interface TotalGraphSelectionPayload {
  type: 'node'
  nodeId: string
}

export interface LocalGraphSelectionPayload {
  type: 'node' | 'edge'
  id: string
}

export function resolveSelectedRootCause(
  list: RankedRootCause[] | null | undefined,
  selectedCandidateId: string | null | undefined,
) {
  if (!list?.length || !selectedCandidateId) {
    return null
  }

  return list.find((item) => item.ranking_id === selectedCandidateId) ?? null
}

export function findBestPathForCandidateInGraph(
  candidate: RankedRootCause | null,
  graph: PathGraph | null | undefined,
) {
  if (!candidate || !graph) {
    return null
  }

  return (
    graph.paths.find((path) => path.target_entity_id === candidate.candidate_id) ??
    graph.paths.find((path) => path.path_id === candidate.ranking_id.replace(/^ranking:/, '')) ??
    graph.paths.find((path) =>
      path.nodes.some((node) => node.node_id === candidate.candidate_id || node.label === candidate.candidate_name),
    ) ??
    graph.paths[0] ??
    null
  )
}

export function findReviewTargetInList(
  list: ReviewTarget[] | null | undefined,
  type: ReviewTarget['target_type'],
  targetId: string | null | undefined,
) {
  if (!list || !targetId) {
    return null
  }

  return list.find((item) => item.target_type === type && item.target_id === targetId) ?? null
}

export function findCandidateForGraphNode(
  nodeId: string,
  candidates: RankedRootCause[] | null | undefined,
  totalGraphDataset: UnifiedGraphDataset | null | undefined,
) {
  const list = candidates ?? []
  const graphNode = totalGraphDataset?.nodes.find((node) => node.id === nodeId) ?? null
  const normalizedNodeName = graphNode?.name.trim().toLowerCase() ?? null

  return (
    list.find((candidate) => candidate.candidate_id === nodeId || candidate.ranking_id === nodeId) ??
    list.find((candidate) => {
      const candidateNames = [candidate.candidate_name, candidate.candidate_label]
        .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
        .map((item) => item.trim().toLowerCase())

      return normalizedNodeName ? candidateNames.includes(normalizedNodeName) : false
    }) ??
    null
  )
}

function buildClearGraphSelectionPatch(): Partial<GraphExploreSelectionState> {
  return {
    selectedGraphNodeId: null,
    subgraphMode: 'path',
    selectedSubgraphNodeId: null,
    selectedSubgraphEdgeId: null,
  }
}

export function buildClearRootCauseSelectionPatch(
  state: Pick<GraphExploreSelectionState, 'selectedPathId'>,
  reviewTargets: ReviewTarget[] | null | undefined,
): Partial<GraphExploreSelectionState> {
  return {
    selectedCandidateId: null,
    selectedReviewTargetKey: findReviewTargetInList(reviewTargets, 'path', state.selectedPathId)?.target_key ?? null,
    selectedGraphNodeId: null,
    subgraphMode: 'path',
    selectedSubgraphNodeId: null,
    selectedSubgraphEdgeId: null,
  }
}

interface BuildCandidateSelectionPatchOptions {
  state: GraphExploreSelectionState
  candidateId: string
  candidates: RankedRootCause[] | null | undefined
  pathGraph: PathGraph | null | undefined
  reviewTargets: ReviewTarget[] | null | undefined
  totalGraphDataset: UnifiedGraphDataset | null | undefined
}

export function buildCandidateSelectionPatch({
  state,
  candidateId,
  candidates,
  pathGraph,
  reviewTargets,
  totalGraphDataset,
}: BuildCandidateSelectionPatchOptions): Partial<GraphExploreSelectionState> {
  if (state.selectedCandidateId === candidateId) {
    return buildClearRootCauseSelectionPatch(state, reviewTargets)
  }

  const list = candidates ?? []
  const candidate = list.find((item) => item.ranking_id === candidateId) ?? null
  const matchedPath = findBestPathForCandidateInGraph(candidate, pathGraph)
  const matchedCandidateTarget =
    findReviewTargetInList(reviewTargets, 'root_cause_candidate', candidateId) ??
    findReviewTargetInList(reviewTargets, 'root_cause_candidate', candidate?.candidate_id)
  const matchedNodeId = findGraphNodeIdForCandidate(candidate, totalGraphDataset)

  return {
    selectedCandidateId: candidateId,
    selectedPathId: matchedPath?.path_id ?? state.selectedPathId,
    selectedReviewTargetKey:
      matchedCandidateTarget?.target_key ??
      findReviewTargetInList(reviewTargets, 'path', matchedPath?.path_id)?.target_key ??
      null,
    selectedGraphNodeId: matchedNodeId,
    subgraphMode: matchedNodeId ? 'neighborhood' : 'path',
    selectedSubgraphNodeId: null,
    selectedSubgraphEdgeId: null,
  }
}

interface BuildTotalGraphSelectionPatchOptions {
  state: GraphExploreSelectionState
  payload: TotalGraphSelectionPayload | null
  candidates: RankedRootCause[] | null | undefined
  pathGraph: PathGraph | null | undefined
  reviewTargets: ReviewTarget[] | null | undefined
  totalGraphDataset: UnifiedGraphDataset | null | undefined
}

export function buildTotalGraphSelectionPatch({
  state,
  payload,
  candidates,
  pathGraph,
  reviewTargets,
  totalGraphDataset,
}: BuildTotalGraphSelectionPatchOptions): Partial<GraphExploreSelectionState> {
  if (!payload) {
    return buildClearGraphSelectionPatch()
  }

  if (state.selectedGraphNodeId === payload.nodeId) {
    return buildClearGraphSelectionPatch()
  }

  const candidate = findCandidateForGraphNode(payload.nodeId, candidates, totalGraphDataset)

  if (!candidate) {
    return {
      selectedGraphNodeId: payload.nodeId,
      subgraphMode: 'neighborhood',
      selectedSubgraphNodeId: null,
      selectedSubgraphEdgeId: null,
      selectedCandidateId: null,
      selectedReviewTargetKey: findReviewTargetInList(reviewTargets, 'path', state.selectedPathId)?.target_key ?? null,
    }
  }

  const nextPathId = findBestPathForCandidateInGraph(candidate, pathGraph)?.path_id ?? state.selectedPathId
  const nextReviewTarget =
    findReviewTargetInList(reviewTargets, 'root_cause_candidate', candidate.ranking_id) ??
    findReviewTargetInList(reviewTargets, 'root_cause_candidate', candidate.candidate_id) ??
    findReviewTargetInList(reviewTargets, 'path', nextPathId)

  return {
    selectedGraphNodeId: payload.nodeId,
    subgraphMode: 'neighborhood',
    selectedSubgraphNodeId: null,
    selectedSubgraphEdgeId: null,
    selectedCandidateId: candidate.ranking_id,
    selectedPathId: nextPathId,
    selectedReviewTargetKey: nextReviewTarget?.target_key ?? null,
  }
}

export function buildLocalGraphSelectionPatch(
  state: Pick<GraphExploreSelectionState, 'selectedSubgraphNodeId' | 'selectedSubgraphEdgeId'>,
  payload: LocalGraphSelectionPayload | null,
): Partial<GraphExploreSelectionState> {
  if (!payload) {
    return {
      selectedSubgraphNodeId: null,
      selectedSubgraphEdgeId: null,
    }
  }

  if (payload.type === 'node') {
    if (state.selectedSubgraphNodeId === payload.id) {
      return {
        selectedSubgraphNodeId: null,
        selectedSubgraphEdgeId: null,
      }
    }

    return {
      selectedSubgraphNodeId: payload.id,
      selectedSubgraphEdgeId: null,
    }
  }

  if (state.selectedSubgraphEdgeId === payload.id) {
    return {
      selectedSubgraphNodeId: null,
      selectedSubgraphEdgeId: null,
    }
  }

  return {
    selectedSubgraphNodeId: null,
    selectedSubgraphEdgeId: payload.id,
  }
}

function findGraphNodeIdForCandidate(
  candidate: RankedRootCause | null,
  dataset: UnifiedGraphDataset | null | undefined,
) {
  if (!candidate || !dataset) {
    return null
  }

  const exactNode = dataset.nodes.find((node) => node.id === candidate.candidate_id || node.id === candidate.ranking_id)
  if (exactNode) {
    return exactNode.id
  }

  const normalizedNames = new Set(
    [candidate.candidate_name, candidate.candidate_label]
      .filter((item): item is string => typeof item === 'string' && item.trim().length > 0)
      .map((item) => item.trim().toLowerCase()),
  )

  if (!normalizedNames.size) {
    return null
  }

  const fuzzyNode = dataset.nodes.find((node) => normalizedNames.has(node.name.trim().toLowerCase()))
  return fuzzyNode?.id ?? null
}
