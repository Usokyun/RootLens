import { buildFeedbackSummaryItems } from '@/services/feedback-summary'
import type { AnalystFeedbackEntry } from '@/services/analysis-workspace'
import type { RankedPath, RootKGDCandidate } from '@/types/rootlens'
import { describe, expect, it } from 'vitest'

function buildRoute1Path(): RankedPath {
  return {
    path_id: 'path-1',
    source_entity_id: 'sensor-1',
    target_entity_id: 'fault-1',
    target_entity_name: 'Reactor Feed Valve',
    nodes: ['sensor-1', 'fault-1'],
    node_names: ['Pressure Sensor', 'Reactor Feed Valve'],
    relations: ['indicates'],
    score: 0.91,
    confidence: 0.88,
    evidence_match: 0.84,
    length: 2,
    source_edges: [
      {
        edge_id: 'edge-1',
        source: 'sensor-1',
        target: 'fault-1',
        relation: 'indicates',
        confidence: 0.8,
      },
    ],
    support_obs_ids: ['obs-1'],
  }
}

function buildRoute2Candidate(): RootKGDCandidate {
  return {
    scenario_id: 'scenario-1',
    fault_number: 1,
    simulation_run: 1,
    rank: 2,
    candidate_id: 'candidate-1',
    candidate_name: 'Feed Pump Cavitation',
    candidate_type: 'equipment',
    candidate_role: 'root-cause',
    priority_level: 1,
    seed_variable_id: 'var-1',
    seed_score: 0.72,
    root_score: 0.83,
    ranking_score: 0.79,
    structural_ranking_score: 0.68,
    ranking_adjustment: 0.11,
    covered_contribution_mass: 0.62,
    active_variable_count: 4,
    pattern_entropy: 0.24,
    discriminator_alignment: 0.61,
    anchor_contribution_alignment: 0.58,
    anchor_dynamic_alignment: 0.54,
    anchor_unique_contribution_alignment: 0.51,
    anchor_memory_bonus: 0.16,
    anchor_memory_scenario_count: 3,
    top_affected_variables: [],
    top_support_paths: [],
    support_evidence_ids: ['obs-2'],
  }
}

function buildEntry(
  overrides: Partial<AnalystFeedbackEntry>,
): AnalystFeedbackEntry {
  return {
    feedback_id: 'route1-path:path-1',
    target_kind: 'route1-path',
    target_id: 'path-1',
    verdict: 'accepted',
    note: 'validated by analyst',
    updated_at: '2026-05-12T09:00:00.000Z',
    ...overrides,
  }
}

describe('buildFeedbackSummaryItems', () => {
  it('maps route1 and route2 feedback into analyst-facing summary items', () => {
    const items = buildFeedbackSummaryItems(
      [
        buildEntry({}),
        buildEntry({
          feedback_id: 'route2-candidate:candidate-1',
          target_kind: 'route2-candidate',
          target_id: 'candidate-1',
          verdict: 'rejected',
          note: '排除该候选，怀疑是伴生症状。',
          updated_at: '2026-05-12T10:00:00.000Z',
        }),
      ],
      [buildRoute1Path()],
      [buildRoute2Candidate()],
    )

    expect(items).toHaveLength(2)
    expect(items[0]).toMatchObject({
      feedback_id: 'route2-candidate:candidate-1',
      target_kind_label: 'Route 2 Candidate',
      title: '#2 Feed Pump Cavitation',
      subtitle: 'equipment / root-cause',
      action_label: '定位候选',
      target_available: true,
    })
    expect(items[1]).toMatchObject({
      feedback_id: 'route1-path:path-1',
      target_kind_label: 'Route 1 Path',
      title: 'Reactor Feed Valve',
      subtitle: 'Pressure Sensor -> Reactor Feed Valve',
      action_label: '定位路径',
      target_available: true,
    })
  })

  it('preserves note-only feedback and marks missing targets as unavailable', () => {
    const items = buildFeedbackSummaryItems(
      [
        buildEntry({
          feedback_id: 'route2-candidate:missing-candidate',
          target_kind: 'route2-candidate',
          target_id: 'missing-candidate',
          verdict: null,
          note: '需要后续人工复盘',
        }),
      ],
      [],
      [],
    )

    expect(items).toEqual([
      {
        feedback_id: 'route2-candidate:missing-candidate',
        target_kind: 'route2-candidate',
        target_id: 'missing-candidate',
        verdict: null,
        note: '需要后续人工复盘',
        updated_at: '2026-05-12T09:00:00.000Z',
        target_kind_label: 'Route 2 Candidate',
        title: 'missing-candidate',
        subtitle: '该候选已不在当前推理结果中。',
        action_label: '定位候选',
        target_available: false,
      },
    ])
  })
})
