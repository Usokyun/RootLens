import type { AnalysisCase, AnalysisRun, RecordValue } from '@/api/workbench'
import { record, rows, text, texts, friendly, channelLabel, featureNames, formatValue } from '@/services/presentation'
import { knowledgeOf, labelMap } from '@/services/knowledge'

export interface AnalysisQuery { id: string; label: string; frame: RecordValue; result: RecordValue; caseItem: AnalysisCase }
export function queryLabel(frame: RecordValue, index: number) {
  const task = record(frame.task)
  const scope = rows(frame.scopes).find((s) => s.scope_id === task.scope_id)
  if (scope?.kind === 'time_window') return `样本 ${scope.sample_start}–${scope.sample_end}`
  if (scope?.kind === 'image_region') return `异常区域 ${index + 1}`
  if (scope?.kind === 'spatial_grid') return '完整晶圆网格'
  return `观测范围 ${index + 1}`
}
export function queriesFor(caseItem: AnalysisCase): AnalysisQuery[] {
  return (caseItem.results ?? []).map((result, index) => {
    const frame = caseItem.evidence_frames?.find((f) => f.case_id === result.case_id) ?? caseItem.evidence_frames?.[index] ?? {}
    return { id: text(result.case_id, `${caseItem.case_id}/${index}`), label: queryLabel(frame, index), frame, result, caseItem }
  })
}
export function caseLabel(caseItem: AnalysisCase, index: number): string {
  const scope = rows(caseItem.evidence_frames?.[0]?.scopes).find((s) => s.kind === 'time_window')
  if (scope) return `样本 ${scope.sample_start}–${scope.sample_end}`
  const raw = caseItem.display_name
  if (raw && !/^(?:wm811k|mvtec_|process_window_|[a-f\d]{8}-)/.test(raw)) return friendly(raw, `样本 ${index + 1}`)
  return `样本 ${index + 1}`
}
export function displayLabels(run: AnalysisRun, result?: RecordValue): Map<string, string> {
  const names = labelMap(knowledgeOf(run.working_graph_snapshot))
  const labels = record(result?.display_labels)
  Object.entries(labels).forEach(([id, value]) => { if (typeof value === 'string') names.set(id, friendly(value)) })
  return names
}
export function evaluationCandidates(result: RecordValue): RecordValue[] {
  const ranked = rows(result.ranked_root_causes)
  const evaluations = rows(result.candidate_evaluations)
  const rowsToUse = evaluations.length ? evaluations : ranked
  return rowsToUse.map((candidate) => {
    const ranking = ranked.find((r) => r.candidate_id === candidate.candidate_id)
    return { ...candidate, ...(ranking ? { rank: ranking.rank, explanation_paths: ranking.explanation_paths ?? candidate.explanation_paths } : {}), eligible_for_ranking: candidate.eligible_for_ranking ?? !!ranking }
  }).sort((a, b) => Number(b.eligible_for_ranking) - Number(a.eligible_for_ranking) || Number(a.rank ?? 999) - Number(b.rank ?? 999))
}
export function pathsFor(result: RecordValue, candidate: RecordValue | null): RecordValue[] {
  if (!candidate) return []
  const own = rows(candidate.explanation_paths)
  if (own.length) return own
  const id = text(candidate.candidate_id)
  return rows(result.top_k_paths).filter((path) => path.candidate_id === id || path.target_entity_id === id || texts(path.nodes).includes(id))
}
export function observationTitle(observation: RecordValue, frame: RecordValue): string {
  const subject = rows(frame.subjects).find((s) => s.subject_id === observation.subject_id)
  const variable = subject?.kind === 'variable' || text(observation.subject_id).startsWith('variable:')
  const name = featureNames[text(observation.feature_id)] ?? friendly(observation.feature_id, '观测值')
  return variable ? `${channelLabel(subject?.external_id ?? observation.subject_id)} · ${name}` : name
}
export function scopeLabel(frame: RecordValue, scopeId: unknown): string {
  const scope = rows(frame.scopes).find((s) => s.scope_id === scopeId)
  if (!scope) return '当前范围'
  if (scope.kind === 'time_window') return `样本 ${scope.sample_start}–${scope.sample_end}`
  if (scope.kind === 'image_region') return '当前图像区域'
  if (scope.zone) return friendly(scope.zone)
  if (scope.kind === 'spatial_grid') return '完整网格'
  return '当前范围'
}
export function legacyMeasurements(caseItem: AnalysisCase, valueType: string): RecordValue {
  return record(rows(caseItem.generated_evidence?.observations).find((o) => o.value_type === valueType)?.value)
}
export function observationLocation(caseItem: AnalysisCase, observation: RecordValue | null): RecordValue {
  if (!observation) return {}
  return rows(caseItem.observation_locations).find((l) => l.obs_id === observation.obs_id || texts(l.obs_ids).includes(text(observation.obs_id))) ?? {}
}
export function humanReason(value: unknown): string {
  const reasons: Record<string, string> = {
    open_candidate_set_does_not_refute: '外观候选是开放集合，未提及不等于否定。',
    missing_or_invalid_observations: '相关观测缺失或不满足类型 / 范围要求。',
    no_matching_observation: '没有找到对应观测。', no_valid_observation: '没有可用的有效观测。',
    unknown_subject_binding: '观测主体没有绑定到当前图谱。', missing_reference: '缺少配套正常参考。',
    scope_mismatch: '观测不属于同一有效范围。', reference_mismatch: '正常参考与任务不一致。',
    no_complete_joint_support: '尚未形成完整的联合条件支持。',
    necessary_condition_missing: '缺少必要条件。', necessary_condition_conflict: '必要条件与实测冲突。',
  }
  return reasons[text(value)] ?? (value ? friendly(value) : '')
}
export function factDescription(fact: RecordValue, names: Map<string, string>) {
  return names.get(text(fact.predicate_id)) ?? (featureNames[text(record(fact.predicate_check).feature_id)] ?? '观测条件')
}
export function observationSummary(observation: RecordValue, frame: RecordValue) {
  return `${observationTitle(observation, frame)}：${formatValue(observation.value)}`
}

export function normalGateClosed(result: RecordValue): boolean { return result.reason === 'normal_reference_gate_is_false' }
export function windowSamplingSeconds(frame: RecordValue, legacy?: RecordValue): number | null {
  const value = rows(frame.scopes).find((scope) => scope.kind === 'time_window')?.sampling_seconds ?? legacy?.sampling_interval_seconds
  return typeof value === 'number' ? value : null
}
