import { describe, expect, it } from 'vitest'

import type { RunCaseDetail, RunDetail } from '@/api/contracts'
import {
  resolveRunReasoningSummary,
  resolveVisualEvidenceUrl,
} from '@/services/ui-copy'

function buildRunDetail(overrides?: Partial<RunDetail>): RunDetail {
  return {
    run: {
      run_id: 'run-1',
      created_at: '2026-05-17T00:00:00Z',
      mode: 'records',
      source_filename: 'records.jsonl',
      top_k: 5,
      run_dir: '/tmp/run-1',
      status: 'completed',
      dataset: 'tep',
      case_count: 1,
      evidence_count: 1,
      label: 'Run 1',
      model_preset: null,
      model_backend: null,
    },
    workflow_steps: [],
    claim_boundary: 'candidate/plausible explanation only; not a verified root-cause label',
    evidence: null,
    evidence_summary: null,
    evidence_with_analysis: null,
    analysis: null,
    summary: null,
    cases: [],
    linked_entities: [],
    correction_candidates: [],
    top_k_paths: [],
    ranked_root_causes: [],
    path_graph: {
      paths: [],
      path_count: 0,
      node_count: 0,
      edge_count: 0,
    },
    source_edge_provenance: [],
    review_targets: [],
    artifacts: {},
    visual_evidence: [],
    ...overrides,
  }
}

describe('ui-copy reasoning helpers', () => {
  it('keeps case metadata higher priority than summary, analysis, and top-level run metadata', () => {
    const runDetail = buildRunDetail({
      summary: {
        pipeline: {
          reasoning_profile_id: 'generic_graph_path_default',
          reasoner_adapter: 'generic_graph_path',
          selection_mode: 'default',
        },
      },
      analysis: {
        reasoning_metadata: {
          reasoning_profile_id: 'analysis_profile',
          reasoner_adapter: 'analysis_adapter',
          selection_mode: 'explicit',
        },
      },
      reasoning_metadata: {
        reasoning_profile_id: 'run_profile',
        reasoner_adapter: 'run_adapter',
        selection_mode: 'explicit',
      },
    })
    const caseDetail: RunCaseDetail = {
      case_id: 'case-1',
      reasoning_metadata: {
        reasoning_profile_id: 'tep_root_kgd_default',
        reasoner_adapter: 'tep_root_kgd',
        selection_mode: 'explicit',
      },
    }

    const summary = resolveRunReasoningSummary(runDetail, caseDetail)

    expect(summary.profileId).toBe('tep_root_kgd_default')
    expect(summary.adapter).toBe('tep_root_kgd')
    expect(summary.selectionMode).toBe('explicit')
    expect(summary.source).toBe('case')
  })

  it('falls back to top-level run reasoning metadata when case, summary, and analysis are absent', () => {
    const runDetail = buildRunDetail({
      reasoning_metadata: {
        reasoning_profile_id: 'generic_graph_path_default',
        reasoner_adapter: 'generic_graph_path',
        selection_mode: 'default',
      },
    })

    const summary = resolveRunReasoningSummary(runDetail, null)

    expect(summary.profileId).toBe('generic_graph_path_default')
    expect(summary.adapter).toBe('generic_graph_path')
    expect(summary.selectionMode).toBe('default')
    expect(summary.source).toBe('run')
  })

  it('prefers browser-safe artifact urls over preview_path and source_path', () => {
    expect(
      resolveVisualEvidenceUrl({
        url: '/api/runs/run-1/artifacts/preview.png',
        preview_path: '/tmp/preview.png',
        source_path: '/tmp/source.png',
      }),
    ).toBe('/api/runs/run-1/artifacts/preview.png')
  })
})
