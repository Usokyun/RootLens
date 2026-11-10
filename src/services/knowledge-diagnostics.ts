import type { RecordValue } from '@/api/workbench'
import { record, rows, text } from '@/services/presentation'

/** Count stored checks once per actual fact, never infer truth from grounded/input counts. */
export function diagnosticTruthCounts(report: RecordValue) {
  const facts = new Map<string, RecordValue>()
  for (const candidate of rows(report.candidate_checks)) for (const fact of rows(candidate.predicate_checks)) {
    const key = text(fact.fact_id) || [fact.predicate_id, fact.subject_id, fact.scope_id].join('/')
    if (key) facts.set(key, fact)
  }
  const values = [...facts.values()]
  return { total:values.length, satisfied:values.filter(f => f.value === true).length, unsatisfied:values.filter(f => f.value === false).length, unknown:values.filter(f => f.value !== true && f.value !== false).length }
}
export function diagnosticReport(result: RecordValue): RecordValue | null {
  const report = record(result.authoring_diagnostics)
  return report.schema_version === 'rootlens-candidate-discriminability.v1' ? report : null
}
export function diagnosticGroupSummary(report: RecordValue) {
  if (report.grouping_status === 'unavailable') return '本次缺少完整分组依据，暂不能判断候选可分辨性。'
  if (report.grouping_status === 'incomplete') return '本次分组检查未完成，已有分组仅供局部检查。'
  const count = rows(report.equivalence_groups).length
  const basis = report.grouping_basis === 'actual_structural_projection' ? '实际传播结构' : '当前期待条件'
  return count ? `${basis}无法区分 ${count} 组候选，需要检查区分条件与观测。` : '本次未发现相同分组签名；这不代表候选原因已经确认。'
}

export function diagnosticGroupParticipation(report:RecordValue,group:RecordValue) {
  const checks=rows(report.candidate_checks),ids=Array.isArray(group.candidate_ids)?group.candidate_ids as string[]:[]
  const selected=ids.map(id=>checks.find(check=>check.candidate_id===id))
  return {eligible:selected.filter(check=>check?.eligible_for_ranking===true).length,ineligible:selected.filter(check=>check?.eligible_for_ranking===false).length,unknown:selected.filter(check=>typeof check?.eligible_for_ranking!=='boolean').length,total:ids.length}
}
export function diagnosticGroupNote(report:RecordValue,group:RecordValue) {
  if (report.grouping_status!=='available') return '分组检查未完成，以下仅为已有条件的结构检查，不能完整判断本次支持状态。'
  const participation=diagnosticGroupParticipation(report,group)
  if (participation.eligible) return report.grouping_basis==='actual_structural_projection' ? '本组共享相同实际结构投影，当前结构比较不足以区分。' : '本组共享相同诊断条件，当前观测不足以区分。'
  if (participation.ineligible===participation.total && participation.total) return '本组本次未获支持；以下为图谱条件的结构检查，不是本次排名并列。'
  return '本组的支持状态尚未完整评估；以下为图谱条件的结构检查。'
}
