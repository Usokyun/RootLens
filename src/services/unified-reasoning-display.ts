/** Read stored backend traces for display only; never execute rules in the browser. */
export type TraceRecord = Record<string, unknown>

export function traceRecord(value: unknown): TraceRecord {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
    ? value as TraceRecord : {}
}

export function traceRows(value: unknown): TraceRecord[] {
  return Array.isArray(value) ? value.filter((v) => v !== null && typeof v === 'object' && !Array.isArray(v)) as TraceRecord[] : []
}

/** Optional on new saved results; never derive tentative items from old unranked rows. */
export function savedTentativeCandidates(result: unknown) {
  return traceRows(traceRecord(result).tentative_candidates).filter(
    (row): row is TraceRecord & { candidate_id: string } => typeof row.candidate_id === 'string' && row.candidate_id.length > 0,
  )
}

export type SavedGradedCandidate = TraceRecord & { candidate_id: string; status: 'supported' | 'pending' }

export function isSavedGradedResult(result: unknown) {
  return traceRecord(result).scoring_method === 'graded_joint_abduction_v1'
}

export function savedGradedCandidates(result: unknown): SavedGradedCandidate[] {
  if (!isSavedGradedResult(result)) return []
  return traceRows(traceRecord(result).graded_candidates).filter((row): row is SavedGradedCandidate =>
    typeof row.candidate_id === 'string' && !!row.candidate_id && (row.status === 'supported' || row.status === 'pending'))
}

export function traceValue(value: unknown): string {
  if (value === null || value === undefined) return '—'
  if (typeof value === 'number') return Number.isFinite(value) ? Number(value.toPrecision(6)).toString() : '—'
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (Array.isArray(value)) return value.map(traceValue).join(' · ') || '∅'
  if (typeof value === 'object') {
    const row = traceRecord(value)
    if (row.kind === 'number') return `${traceValue(row.number)} ${row.unit ?? ''}`.trim()
    if (row.kind === 'boolean') return traceValue(row.boolean)
    if (row.kind === 'category') return String(row.category)
    if (row.kind === 'candidate_set') return `${traceValue(row.items)}${row.exhaustive === false ? '（开放集合）' : ''}`
    return JSON.stringify(value)
  }
  return String(value)
}

export function traceOutcome(value: unknown): string {
  return ({ supported: '存在支持候选', ambiguous: '多个候选并列', no_match: '条件未形成完整支持', insufficient_evidence: '证据不足', not_applicable: '知识不适用', search_incomplete: '搜索未完成' } as Record<string, string>)[String(value)] ?? String(value ?? '—')
}
