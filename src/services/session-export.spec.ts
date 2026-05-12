import { readFileSync } from 'node:fs'

import { parseRootLensRuntimeFile, parseUnifiedGraphsFile } from '@/contracts/runtime'
import {
  buildAnalysisWorkspaceScope,
  loadAnalysisWorkspace,
} from '@/services/analysis-workspace'
import { loadAnalysisFocus } from '@/services/analysis-focus'
import {
  getImportedSessionSummary,
  getLocalSessionMeta,
  saveImportedSession,
} from '@/services/rootlens-data'
import { restoreSessionImportPayload } from '@/services/session-export'
import type { AnalysisFocusState } from '@/services/analysis-focus'
import type { AnalysisWorkspaceStorage } from '@/services/analysis-workspace'
import type { RootLensRuntimeCase } from '@/types/rootlens'
import { beforeEach, describe, expect, it } from 'vitest'

function readJsonFixture<T>(relativePath: string): T {
  return JSON.parse(readFileSync(new URL(relativePath, import.meta.url), 'utf8')) as T
}

function clone<T>(value: T): T {
  return structuredClone(value)
}

const demoGraphs = parseUnifiedGraphsFile(
  readJsonFixture('../../public/generated/unified-graphs.json'),
)
const demoRuntime = parseRootLensRuntimeFile(
  readJsonFixture('../../public/generated/rootlens-runtime.json'),
)

function buildWorkspaceSnapshot(caseItem: RootLensRuntimeCase): AnalysisWorkspaceStorage {
  return {
    schema_version: 'analysis-workspace.v1',
    session_scope: 'exported-scope',
    updated_at: new Date().toISOString(),
    cases: [
      {
        case_id: caseItem.case_id,
        draft_case: {
          ...clone(caseItem),
          case_label: `${caseItem.case_label} (draft)`,
        },
        feedback_items: [
          {
            feedback_id: 'route2-candidate:feedback-target',
            target_kind: 'route2-candidate',
            target_id: 'feedback-target',
            verdict: 'accepted',
            note: 'analyst confirmation note',
            updated_at: new Date().toISOString(),
          },
        ],
      },
    ],
  }
}

function buildFocusSnapshot(caseId: string): AnalysisFocusState {
  return {
    schema_version: 'analysis-focus.v1',
    session_scope: 'exported-scope',
    updated_at: new Date().toISOString(),
    active_case_id: caseId,
    active_dataset_id: demoRuntime.cases[0].analysis.graph_dataset_id,
    selected_observation_id: null,
    selected_route1_path_ids: [],
    selected_route2_candidate_ids: [],
    highlighted_node_ids: [],
    highlighted_edge_ids: [],
    highlighted_obs_ids: [],
    focus_kind: 'case',
    focus_label: caseId,
    source_view: 'reasoning',
  }
}

describe('restoreSessionImportPayload', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('restores session bundles with import summary, workspace, and focus', async () => {
    const targetCase = clone(demoRuntime.cases[0])
    const payload = {
      schema_version: 'rootlens-session-export.v1' as const,
      exported_at: new Date().toISOString(),
      sessionMeta: {
        source: 'import' as const,
        updatedAt: '2026-05-12T00:00:00.000Z',
        summary: 'exported bundle',
      },
      importSummary: {
        sourceMode: 'graphs+evidence' as const,
        detectedFiles: ['unified-graphs.json', 'evidence.json'],
        datasets: [
          {
            id: demoGraphs.datasets[0].id,
            label: demoGraphs.datasets[0].label,
            nodeCount: demoGraphs.datasets[0].nodes.length,
            edgeCount: demoGraphs.datasets[0].edges.length,
          },
        ],
        cases: [
          {
            caseId: targetCase.case_id,
            caseLabel: targetCase.case_label,
            dataset: targetCase.dataset,
          },
        ],
        warnings: ['preserved warning from export'],
      },
      graphs: clone(demoGraphs),
      runtime: parseRootLensRuntimeFile({
        schema_version: 'rootlens-runtime.v1',
        generated_at: new Date().toISOString(),
        generator: 'browser-import',
        cases: [targetCase],
      }),
      analysisWorkspace: buildWorkspaceSnapshot(targetCase),
      analysisFocus: buildFocusSnapshot(targetCase.case_id),
    }

    const result = await restoreSessionImportPayload(payload)
    const sessionMeta = getLocalSessionMeta()
    const sessionScope = buildAnalysisWorkspaceScope(sessionMeta)
    const summary = getImportedSessionSummary()
    const workspace = loadAnalysisWorkspace(sessionScope)
    const focus = loadAnalysisFocus(sessionScope)

    expect(result.kind).toBe('session-bundle')
    expect(result.warnings).toEqual([])
    expect(summary?.sourceMode).toBe('graphs+evidence')
    expect(summary?.warnings).toContain('preserved warning from export')
    expect(workspace?.cases).toHaveLength(1)
    expect(workspace?.cases[0]?.case_id).toBe(targetCase.case_id)
    expect(workspace?.cases[0]?.feedback_items[0]?.note).toBe('analyst confirmation note')
    expect(focus?.active_case_id).toBe(targetCase.case_id)
  })

  it('warns when restoring workspace onto a session with mismatched case ids', async () => {
    const currentCase = clone(demoRuntime.cases[0])

    saveImportedSession({
      graphs: clone(demoGraphs),
      runtime: parseRootLensRuntimeFile({
        schema_version: 'rootlens-runtime.v1',
        generated_at: new Date().toISOString(),
        generator: 'browser-import',
        cases: [currentCase],
      }),
      summary: 'current imported session',
    })

    const result = await restoreSessionImportPayload({
      schema_version: 'rootlens-analysis-workspace-export.v1',
      exported_at: new Date().toISOString(),
      analysis_workspace: {
        schema_version: 'analysis-workspace.v1',
        session_scope: 'foreign-scope',
        updated_at: new Date().toISOString(),
        cases: [
          {
            case_id: 'missing-case',
            draft_case: {
              ...clone(currentCase),
              case_id: 'missing-case',
              case_label: 'Missing Case',
              evidence: {
                ...clone(currentCase.evidence),
                case_id: 'missing-case',
                case_label: 'Missing Case',
              },
              analysis: {
                ...clone(currentCase.analysis),
                case_id: 'missing-case',
              },
            },
            feedback_items: [],
          },
        ],
      },
      analysis_focus: buildFocusSnapshot('missing-case'),
    })

    expect(result.kind).toBe('workspace-export')
    expect(result.warnings).toContain(
      '导入的 workspace 与当前会话 case_id 不匹配（0/1 命中）；草稿和反馈已保存，但不会映射到当前案例。',
    )
    expect(result.warnings).toContain(
      '导入的共享焦点指向的 case 不在当前会话中，跨页联动不会自动定位到目标案例。',
    )
  })

  it('warns when restoring workspace before any runtime cases exist', async () => {
    saveImportedSession({
      graphs: clone(demoGraphs),
      runtime: null,
      summary: 'graphs only session',
    })

    const result = await restoreSessionImportPayload({
      schema_version: 'rootlens-analysis-workspace-export.v1',
      exported_at: new Date().toISOString(),
      analysis_workspace: buildWorkspaceSnapshot(clone(demoRuntime.cases[0])),
      analysis_focus: buildFocusSnapshot(demoRuntime.cases[0].case_id),
    })

    expect(result.kind).toBe('workspace-export')
    expect(result.warnings).toEqual([
      '当前会话没有 runtime case；workspace 已恢复，但草稿、反馈和共享焦点要等 case 导入后才会在 Evidence / RCA 中生效。',
    ])
  })
})
