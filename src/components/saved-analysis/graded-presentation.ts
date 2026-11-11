import type { PathGraphPath } from '@/api/contracts'
import type { SavedAnalysisFrame } from '@/services/saved-analysis-reader'
import { isSavedGradedResult, savedGradedCandidates, traceRecord, traceRows, traceValue, type TraceRecord } from '@/services/unified-reasoning-display'
import { featureLabel, getPathObs, nativePath, number, predicateLabel, strings, text, type PathFocus } from './presentation'

export function gradedCandidateGroups(result: unknown) {
  const rows = savedGradedCandidates(result)
  return {
    supported: rows.filter(row => row.status === 'supported'),
    pending: rows.filter(row => row.status === 'pending'),
  }
}

export function gradedUnranked(result: TraceRecord | null | undefined) {
  if (!isSavedGradedResult(result) || result?.reason === 'anomaly_gate_is_false') return []
  // Candidates beyond the stored group cutoff aren't "unranked" evaluations.
  return traceRows(result?.candidate_evaluations).filter(row =>
    !!text(row.candidate_id) && !['supported', 'pending'].includes(text(row.status))
    && traceRows(row.graded_conditions).length > 0)
}

export function gradedScore(row: TraceRecord | null) {
  const score = traceRecord(row?.scoring_details)
  return { score: number(score.score), support: number(score.support), conflict: number(score.conflict), coverage: number(score.coverage) }
}

export function signedContribution(value: unknown) {
  const finite = number(value)
  return finite === null ? '—' : finite > 0 ? `+${traceValue(finite)}` : finite < 0 ? `−${traceValue(-finite)}` : '0'
}

export function contributionPolarity(value: unknown) {
  const finite = number(value) ?? 0
  return finite > 0 ? 'positive' : finite < 0 ? 'negative' : 'zero'
}

export function gradedPathFocus(frame: SavedAnalysisFrame, path: PathGraphPath, id: string): PathFocus | null {
  const saved = nativePath(frame, path.path_id)
  if (!isSavedGradedResult(frame.result) || saved?.path_kind !== 'graded_contribution' || !getPathObs(frame, path).includes(id)) return null
  const predicate = text(saved.predicate_id)
  if (!predicate || !path.edges.length) return null
  const exactEdges = path.edges.filter(edge => edge.source_node_id === predicate || edge.target_node_id === predicate)
  return { pathId: path.path_id, obsId: id, edgeId: exactEdges.length === 1 ? exactEdges[0]!.edge_id : undefined }
}

export function gradedConditionRows(frame: SavedAnalysisFrame, candidate: TraceRecord | null) {
  const candidateId = text(candidate?.candidate_id)
  if (!isSavedGradedResult(frame.result) || !candidateId) return []
  const paths = (frame.pathsByCandidateId.get(candidateId) ?? []).flatMap(path => {
    const saved = nativePath(frame, path.path_id)
    return saved?.path_kind === 'graded_contribution' ? [{ path, saved }] : []
  })
  return traceRows(candidate?.graded_conditions).flatMap(condition => {
    const predicateId = text(condition.predicate_id), ruleId = text(condition.rule_id)
    if (!predicateId || !ruleId) return []
    const savedPaths = paths.filter(item => item.saved.predicate_id === predicateId && item.saved.rule_id === ruleId)
    const observations = [...new Set(strings(condition.obs_ids))].flatMap(id => {
      const obs = frame.observationsById.get(id)
      if (!obs) return []
      const focus = savedPaths.map(({ path }) => gradedPathFocus(frame, path, id)).find(link => link) ?? null
      return [{ id, obs, focus }]
    })
    return [{
      key: JSON.stringify([ruleId, predicateId]), condition, observations,
      label: text(condition.label) || predicateLabel(condition, featureLabel(condition.feature_id)),
    }]
  })
}

export function gradedObservationUsage(candidate: TraceRecord | null) {
  return {
    support: new Set(strings(candidate?.support_obs_ids)),
    conflict: new Set(strings(candidate?.counter_obs_ids)),
  }
}

export function gradedStatus(row: TraceRecord) {
  if (row.role === 'presence_gate') return row.hard_constraint_satisfied === true ? { label: '前置已满足', color: 'gray' }
    : { label: row.status === 'unknown' ? '前置未核验' : '前置不满足', color: 'orange' }
  switch (row.status) {
    case 'supported': return { label: '正证', color: 'green' }
    case 'conflicting': return { label: '反证', color: 'red' }
    case 'neutral': return { label: '中性', color: 'gray' }
    default: return { label: '未核验', color: 'orange' }
  }
}

export function gradedReason(value: unknown) {
  return ({
    fewer_than_two_supported_measurements: '获得实测正证的不同测量槽不足两项。',
    no_declared_anomaly_prerequisite: '未声明适用的异常前置。',
    hard_constraint_unverified: '必要前置或范围尚未核验。',
    hard_constraint_refuted: '必要约束受到反证。',
    no_legal_joint_scope: '这些观测未形成同一有效范围内的分支。',
    anchor_without_measured_net_support: '所选分支仍有判别锚点未获净支持。',
    nonpositive_branch_score: '分支净相容分不为正。',
    incompatible_normal_reference: '没有使用同一正常参考的适用实测。',
    ambiguous_measurement_scope: '存在不同范围的实测，无法选定同一测量。',
    inconsistent_repeated_measurement: '重复实测不一致。',
  } as Record<string, string>)[text(value)] ?? ''
}
