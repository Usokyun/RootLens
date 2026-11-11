import type { Dataset, SavedAnalysisListItem, TaskStatus, WorkTask } from '@/api/two-loop'

export interface AnalysisHistoryFilters { search: string; dataset: Dataset | 'all'; status: TaskStatus | 'all' }
export interface AnalysisListPosition { filters: AnalysisHistoryFilters; scrollTop: number; taskId: string | null }
const byBackend = new Map<string, AnalysisListPosition>()
export const emptyAnalysisFilters = (): AnalysisHistoryFilters => ({ search: '', dataset: 'all', status: 'all' })
const key = (base: string) => base.replace(/\/+$/, '')

/** Navigation state only. Saved results and tasks always come from the selected backend. */
export function restoreAnalysisList(base: string): AnalysisListPosition {
  const previous = byBackend.get(key(base))
  return previous ? { ...previous, filters: { ...previous.filters } } : { filters: emptyAnalysisFilters(), scrollTop: 0, taskId: null }
}
export function rememberAnalysisList(base: string, position: AnalysisListPosition) {
  byBackend.set(key(base), { ...position, filters: { ...position.filters } })
}

const outcomeLabels: Record<string, string> = {
  ambiguous: '候选并列', supported: '存在支持', insufficient_evidence: '证据不足', no_match: '无匹配',
  search_incomplete: '搜索未完成',
}
export interface SavedConclusion { label: string; color?: 'green' | 'orange' | 'arcoblue' }
export function savedConclusion(run: Pick<SavedAnalysisListItem, 'outcome_counts' | 'normal_gate_count'>): SavedConclusion {
  const entries = Object.entries(run.outcome_counts ?? {}).filter(([, count]) => Number.isInteger(count) && count > 0)
  const normal = typeof run.normal_gate_count === 'number' && Number.isInteger(run.normal_gate_count) ? Math.max(0, run.normal_gate_count) : 0
  if (!entries.length && !normal) return { label: '打开查看' }
  const labels: { label: string; count: number; color?: SavedConclusion['color'] }[] = []
  for (const [outcome, count] of entries) {
    labels.push({ label: outcomeLabels[outcome] ?? '其他结论', count,
      color: outcome === 'supported' ? 'arcoblue' : ['ambiguous', 'insufficient_evidence', 'search_incomplete'].includes(outcome) ? 'orange' : undefined })
  }
  // Normal reference gates are already excluded from outcome_counts by the server.
  if (normal) labels.push({ label: '正常门控', count: normal, color: 'green' })
  const only = labels[0]
  return labels.length === 1 && only ? { label: only.count === 1 ? only.label : `${only.label}（${only.count} 个范围）`, color: only.color }
    : { label: labels.map(item => `${item.label} ×${item.count}`).join(' · ') }
}

export function completedAnalysisId(task: WorkTask | null | undefined): string | null {
  const id = task?.result?.run_id
  return task?.kind === 'inference' && task.status === 'completed' && typeof id === 'string' && id.trim() ? id : null
}

export interface AnalysisHistoryRow {
  id: string
  runId: string | null
  task: WorkTask | null
  title: string
  filename: string
  dataset: string
  inputMode: string
  reasoner: string
  status: TaskStatus
  createdAt: string
  conclusion: SavedConclusion
}
export function buildAnalysisHistory(runs: SavedAnalysisListItem[], tasks: WorkTask[]): AnalysisHistoryRow[] {
  const result: AnalysisHistoryRow[] = runs.map(run => ({
    id: `run:${run.run_id}`, runId: run.run_id, task: null, title: run.title,
    filename: run.source_filename ?? '', dataset: run.dataset, inputMode: run.input_mode, reasoner: run.reasoner_id,
    status: run.status, createdAt: run.created_at, conclusion: savedConclusion(run),
  }))
  const knownRuns = new Set(runs.map(run => run.run_id))
  for (const task of tasks) {
    if (task.kind !== 'inference' || task.status === 'queued' || task.status === 'running') continue
    const runId = completedAnalysisId(task)
    if (runId && knownRuns.has(runId)) continue
    if (runId) knownRuns.add(runId)
    const field = (name: string) => typeof task.request?.[name] === 'string' ? task.request[name] as string : ''
    result.push({ id: runId ? `run:${runId}` : `task:${task.task_id}`, runId, task,
      title: task.title, filename: field('source_filename'), dataset: field('dataset'), inputMode: field('input_mode'), reasoner: field('reasoner_id'),
      status: task.status, createdAt: task.created_at,
      conclusion: { label: runId ? '打开查看' : task.status === 'completed' ? '未返回分析编号' : '未生成结果' } })
  }
  return result.sort((left, right) => right.createdAt.localeCompare(left.createdAt))
}
export function filterAnalysisHistory(rows: AnalysisHistoryRow[], filters: AnalysisHistoryFilters) {
  const query = filters.search.trim().toLocaleLowerCase()
  return rows.filter(row => (filters.dataset === 'all' || filters.dataset === row.dataset)
    && (filters.status === 'all' || filters.status === row.status)
    && (!query || `${row.title} ${row.filename}`.toLocaleLowerCase().includes(query)))
}

const stageGroups = [
  { key: 'queue', label: '排队', codes: ['queued'] },
  { key: 'input', label: '接收输入', codes: ['upload'] },
  { key: 'measure', label: '测量 / Evidence', codes: ['adapter', 'measurement'] },
  { key: 'reason', label: 'KG 推理', codes: ['reasoning'] },
  { key: 'save', label: '整理与保存', codes: ['explanation', 'completed'] },
]
/** Only attach stage state to backend codes that really occurred. No estimated durations. */
export function analysisTaskStages(task: WorkTask) {
  const input = task.request?.input_mode
  const active = task.status === 'running' || task.status === 'queued'
  return stageGroups.map(group => {
    const current = group.codes.includes(task.stage)
    const seen = task.events.some(event => group.codes.includes(event.stage))
    const label = group.key === 'measure' && input === 'evidence' ? '读取已有 Frame' : group.label
    const state = current && active ? 'active' : current && (task.status === 'failed' || task.status === 'interrupted') ? 'stopped'
      : seen || current ? 'recorded' : 'unseen'
    return { key: group.key, label, state }
  })
}
