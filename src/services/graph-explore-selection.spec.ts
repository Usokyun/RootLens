import { describe, expect, it } from 'vitest'

import type { RankedRootCause, ReviewTarget } from '@/api/contracts'
import {
  buildCandidateSelectionPatch,
  buildLocalGraphSelectionPatch,
  buildTotalGraphSelectionPatch,
  resolveSelectedRootCause,
  type GraphExploreSelectionState,
} from '@/services/graph-explore-selection'
import type { UnifiedGraphDataset } from '@/types/graph'

const candidates: RankedRootCause[] = [
  {
    ranking_id: 'ranking:rc-1',
    rank: 1,
    candidate_id: 'node-a',
    candidate_name: 'Node A',
  },
  {
    ranking_id: 'ranking:rc-2',
    rank: 2,
    candidate_id: 'node-b',
    candidate_name: 'Node B',
  },
]

const reviewTargets: ReviewTarget[] = [
  {
    target_type: 'root_cause_candidate',
    target_id: 'ranking:rc-1',
    target_key: 'candidate-target-1',
    label: 'Candidate 1',
  },
  {
    target_type: 'root_cause_candidate',
    target_id: 'ranking:rc-2',
    target_key: 'candidate-target-2',
    label: 'Candidate 2',
  },
  {
    target_type: 'path',
    target_id: 'path-1',
    target_key: 'path-target-1',
    label: 'Path 1',
  },
  {
    target_type: 'path',
    target_id: 'path-2',
    target_key: 'path-target-2',
    label: 'Path 2',
  },
]

const totalGraphDataset: UnifiedGraphDataset = {
  id: 'demo',
  label: 'Demo',
  description: 'Demo dataset',
  graphKind: 'candidate-graph',
  projectRoot: 'demo',
  sourceFiles: [],
  nodes: [
    {
      id: 'node-a',
      name: 'Node A',
      category: 'demo',
      kind: 'fault',
      description: 'Candidate node A',
      aliases: [],
      degree: 2,
      inDegree: 1,
      outDegree: 1,
      attributes: {},
      origin: {
        projectId: 'demo',
        projectLabel: 'Demo',
        filePath: 'demo',
        layer: 'demo',
        rowNumber: 1,
      },
    },
    {
      id: 'node-b',
      name: 'Node B',
      category: 'demo',
      kind: 'fault',
      description: 'Candidate node B',
      aliases: [],
      degree: 2,
      inDegree: 1,
      outDegree: 1,
      attributes: {},
      origin: {
        projectId: 'demo',
        projectLabel: 'Demo',
        filePath: 'demo',
        layer: 'demo',
        rowNumber: 2,
      },
    },
    {
      id: 'node-c',
      name: 'Node C',
      category: 'demo',
      kind: 'component',
      description: 'Non-candidate node C',
      aliases: [],
      degree: 1,
      inDegree: 0,
      outDegree: 1,
      attributes: {},
      origin: {
        projectId: 'demo',
        projectLabel: 'Demo',
        filePath: 'demo',
        layer: 'demo',
        rowNumber: 3,
      },
    },
  ],
  edges: [],
  metadata: {},
}

const pathGraph = {
  paths: [
    {
      path_id: 'path-1',
      target_key: 'path-target-1',
      target_entity_id: 'node-a',
      supporting_evidence: [],
      nodes: [
        {
          node_id: 'node-a',
          label: 'Node A',
          role: 'target',
        },
      ],
      edges: [],
    },
    {
      path_id: 'path-2',
      target_key: 'path-target-2',
      target_entity_id: 'node-b',
      supporting_evidence: [],
      nodes: [
        {
          node_id: 'node-b',
          label: 'Node B',
          role: 'target',
        },
      ],
      edges: [],
    },
  ],
  path_count: 2,
  node_count: 2,
  edge_count: 0,
}

const baseState: GraphExploreSelectionState = {
  selectedCandidateId: 'ranking:rc-1',
  selectedPathId: 'path-1',
  selectedReviewTargetKey: 'candidate-target-1',
  selectedGraphNodeId: 'node-a',
  subgraphMode: 'neighborhood',
  selectedSubgraphNodeId: null,
  selectedSubgraphEdgeId: null,
}

describe('graph explore selection helpers', () => {
  it('resolves no active root cause when selection has been cleared', () => {
    expect(resolveSelectedRootCause(candidates, null)).toBeNull()
  })

  it('clears the graph selection when the canvas background is clicked', () => {
    expect(
      buildTotalGraphSelectionPatch({
        state: baseState,
        payload: null,
        candidates,
        pathGraph,
        reviewTargets,
        totalGraphDataset,
      }),
    ).toEqual({
      selectedGraphNodeId: null,
      subgraphMode: 'path',
      selectedSubgraphNodeId: null,
      selectedSubgraphEdgeId: null,
    })
  })

  it('clears the graph selection when the already selected node is clicked again', () => {
    expect(
      buildTotalGraphSelectionPatch({
        state: baseState,
        payload: {
          type: 'node',
          nodeId: 'node-a',
        },
        candidates,
        pathGraph,
        reviewTargets,
        totalGraphDataset,
      }),
    ).toEqual({
      selectedGraphNodeId: null,
      subgraphMode: 'path',
      selectedSubgraphNodeId: null,
      selectedSubgraphEdgeId: null,
    })
  })

  it('switches the active root cause when another candidate node is selected on the graph', () => {
    expect(
      buildTotalGraphSelectionPatch({
        state: baseState,
        payload: {
          type: 'node',
          nodeId: 'node-b',
        },
        candidates,
        pathGraph,
        reviewTargets,
        totalGraphDataset,
      }),
    ).toEqual({
      selectedGraphNodeId: 'node-b',
      subgraphMode: 'neighborhood',
      selectedSubgraphNodeId: null,
      selectedSubgraphEdgeId: null,
      selectedCandidateId: 'ranking:rc-2',
      selectedPathId: 'path-2',
      selectedReviewTargetKey: 'candidate-target-2',
    })
  })

  it('clears the active root cause when a non-candidate node is selected on the graph', () => {
    expect(
      buildTotalGraphSelectionPatch({
        state: baseState,
        payload: {
          type: 'node',
          nodeId: 'node-c',
        },
        candidates,
        pathGraph,
        reviewTargets,
        totalGraphDataset,
      }),
    ).toEqual({
      selectedGraphNodeId: 'node-c',
      subgraphMode: 'neighborhood',
      selectedSubgraphNodeId: null,
      selectedSubgraphEdgeId: null,
      selectedCandidateId: null,
      selectedReviewTargetKey: 'path-target-1',
    })
  })

  it('toggles off the active root-cause item and returns to path mode', () => {
    expect(
      buildCandidateSelectionPatch({
        state: baseState,
        candidateId: 'ranking:rc-1',
        candidates,
        pathGraph,
        reviewTargets,
        totalGraphDataset,
      }),
    ).toEqual({
      selectedCandidateId: null,
      selectedReviewTargetKey: 'path-target-1',
      selectedGraphNodeId: null,
      subgraphMode: 'path',
      selectedSubgraphNodeId: null,
      selectedSubgraphEdgeId: null,
    })
  })

  it('selects a new root-cause item and syncs path and graph state', () => {
    expect(
      buildCandidateSelectionPatch({
        state: baseState,
        candidateId: 'ranking:rc-2',
        candidates,
        pathGraph,
        reviewTargets,
        totalGraphDataset,
      }),
    ).toEqual({
      selectedCandidateId: 'ranking:rc-2',
      selectedPathId: 'path-2',
      selectedReviewTargetKey: 'candidate-target-2',
      selectedGraphNodeId: 'node-b',
      subgraphMode: 'neighborhood',
      selectedSubgraphNodeId: null,
      selectedSubgraphEdgeId: null,
    })
  })

  it('clears local selection when the subgraph background is clicked', () => {
    expect(
      buildLocalGraphSelectionPatch(
        {
          selectedSubgraphNodeId: 'node-a',
          selectedSubgraphEdgeId: 'edge-1',
        },
        null,
      ),
    ).toEqual({
      selectedSubgraphNodeId: null,
      selectedSubgraphEdgeId: null,
    })
  })

  it('toggles off a local node when it is clicked again', () => {
    expect(
      buildLocalGraphSelectionPatch(
        {
          selectedSubgraphNodeId: 'node-a',
          selectedSubgraphEdgeId: null,
        },
        {
          type: 'node',
          id: 'node-a',
        },
      ),
    ).toEqual({
      selectedSubgraphNodeId: null,
      selectedSubgraphEdgeId: null,
    })
  })

  it('toggles off a local edge when it is clicked again', () => {
    expect(
      buildLocalGraphSelectionPatch(
        {
          selectedSubgraphNodeId: null,
          selectedSubgraphEdgeId: 'edge-1',
        },
        {
          type: 'edge',
          id: 'edge-1',
        },
      ),
    ).toEqual({
      selectedSubgraphNodeId: null,
      selectedSubgraphEdgeId: null,
    })
  })
})
