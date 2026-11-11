import { describe, expect, it } from 'vitest'
import type { SavedAnalysisListItem, WorkTask } from '@/api/two-loop'
import { analysisTaskStages, buildAnalysisHistory, completedAnalysisId, emptyAnalysisFilters, filterAnalysisHistory, rememberAnalysisList, restoreAnalysisList, savedConclusion } from './analysis-history'

const analysis: SavedAnalysisListItem = { run_id: 'same', title: 'd04 多窗口', dataset: 'tep', input_mode: 'evidence',
  reasoner_id: 'tep_rootkgd', status: 'completed', created_at: '2026-11-11T06:00:00Z', source_filename: 'd04.json' }
function task(status: WorkTask['status'], result: WorkTask['result'] = null): WorkTask {
  return { task_id: `${status}-task`, kind: 'inference', title: '失败样本', status, result, created_at: '2026-11-11T05:00:00Z',
    updated_at: '', stage: 'adapter', stage_label: '测量模型', progress: { indeterminate: true }, events: [], error: null,
    request: { dataset: 'mvtec', input_mode: 'evidence', source_filename: 'other.json' } }
}
describe('analysis list separates task execution from saved result', () => {
  it('keeps missing and empty outcome projections unknown, without deriving a negative from candidate count', () => {
    expect(savedConclusion(analysis).label).toBe('打开查看')
    expect(savedConclusion({ outcome_counts: {} }).label).toBe('打开查看')
  })
  it('distinguishes saved ambiguity, insufficiency and only an explicitly recorded normal gate', () => {
    expect(savedConclusion({ outcome_counts: { ambiguous: 1 } })).toEqual({ label: '候选并列', color: 'orange' })
    expect(savedConclusion({ outcome_counts: { ambiguous: 2 } }).label).toBe('候选并列（2 个范围）')
    expect(savedConclusion({ outcome_counts: { insufficient_evidence: 1 } }).label).toBe('证据不足')
    expect(savedConclusion({ outcome_counts: { no_match: 1 } }).label).toBe('无匹配')
    expect(savedConclusion({ outcome_counts: { ambiguous: 2 }, normal_gate_count: 1 }).label).toBe('候选并列 ×2 · 正常门控 ×1')
    expect(savedConclusion({ outcome_counts: {}, normal_gate_count: 1 }).label).toBe('正常门控')
    expect(savedConclusion({ outcome_counts: { no_match: 1 }, normal_gate_count: 1 }).label).toBe('无匹配 ×1 · 正常门控 ×1')
  })
  it('opens only a completed inference task’s actual result ID; failure and active never borrow another Run', () => {
    expect(completedAnalysisId(task('running', { run_id: 'wrong' }))).toBeNull()
    expect(completedAnalysisId(task('failed', { run_id: 'wrong' }))).toBeNull()
    expect(completedAnalysisId(task('completed', { run_id: 'actual' }))).toBe('actual')
    expect(completedAnalysisId(task('completed'))).toBeNull()
  })
  it('deduplicates actual saved results and keeps a task failure as an inspectable task', () => {
    const failed = task('failed', { run_id: 'not-allowed' })
    const rows = buildAnalysisHistory([analysis], [task('running'), failed, task('completed', { run_id: 'same' })])
    expect(rows.map(row => [row.id, row.runId, row.status, row.conclusion.label])).toEqual([
      ['run:same', 'same', 'completed', '打开查看'], ['task:failed-task', null, 'failed', '未生成结果'],
    ])
    expect(rows[1]?.task).toBe(failed)
    expect(filterAnalysisHistory(rows, { search: 'D04.JSON', dataset: 'tep', status: 'completed' })).toHaveLength(1)
    expect(filterAnalysisHistory(rows, { search: '', dataset: 'tep', status: 'failed' })).toHaveLength(0)
  })
  it('retains an exact completed link while its summary is not yet in the index', () => {
    expect(buildAnalysisHistory([], [task('completed', { run_id: 'actual' })])[0]).toMatchObject({ runId: 'actual', status: 'completed' })
    expect(buildAnalysisHistory([], [task('completed')])[0]).toMatchObject({ runId: null, conclusion: { label: '未返回分析编号' } })
  })
  it('restores filter and scroll position within the same backend, not in another source', () => {
    const filters = { search: '玻璃', dataset: 'mvtec' as const, status: 'completed' as const }
    rememberAnalysisList('http://api-a:8012/', { filters, scrollTop: 314, taskId: 'task' })
    filters.search = 'changed'
    expect(restoreAnalysisList('http://api-a:8012')).toEqual({ filters: { search: '玻璃', dataset: 'mvtec', status: 'completed' }, scrollTop: 314, taskId: 'task' })
    expect(restoreAnalysisList('http://api-b:8012')).toEqual({ filters: emptyAnalysisFilters(), scrollTop: 0, taskId: null })
  })
  it('does not pretend an unreported extraction phase happened for Evidence input', () => {
    const stages = analysisTaskStages(task('running'))
    expect(stages.find(stage => stage.key === 'measure')).toEqual({ key: 'measure', label: '读取已有 Frame', state: 'active' })
    expect(stages.find(stage => stage.key === 'queue')?.state).toBe('unseen')
    expect(stages.find(stage => stage.key === 'save')?.state).toBe('unseen')
  })
})
