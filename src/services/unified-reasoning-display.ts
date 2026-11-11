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

export function unifiedQueries(metadata: unknown) {
  const data = traceRecord(metadata)
  const frames = Array.isArray(data.evidence_frames) ? data.evidence_frames : []
  const results = Array.isArray(data.query_results) ? data.query_results : []
  return results.flatMap((value, index) => {
    const result = traceRecord(value)
    return result.schema_version === 'rootlens-reasoning-result.v2'
      ? [{ result, frame: traceRecord(frames[index]), id: String(result.case_id) }] : []
  })
}

export function traceQueryIndex(queries: Array<{ id: string }>, queryId: unknown) {
  const index = queries.findIndex((q) => q.id === queryId)
  return index >= 0 ? index : 0
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

export function traceTruth(value: unknown): string {
  return value === true ? '满足' : value === false ? '不满足' : '未知 / 缺测'
}

export function traceOutcome(value: unknown): string {
  return ({ supported: '存在支持候选', ambiguous: '多个候选并列', no_match: '条件未形成完整支持', insufficient_evidence: '证据不足', not_applicable: '知识不适用', search_incomplete: '搜索未完成' } as Record<string, string>)[String(value)] ?? String(value ?? '—')
}

export function queryLabel(frame: TraceRecord, index: number): string {
  const task = traceRecord(frame.task)
  const scope = traceRows(frame.scopes).find((s) => s.scope_id === task.scope_id)
  if (scope?.kind === 'time_window') return `窗口 ${scope.sample_start}–${scope.sample_end}`
  return `问题 ${index + 1} · ${String(task.scope_id ?? 'scope')}`
}

export function selectTraceCandidate(result: TraceRecord, preferred: string | null | undefined) {
  const rows = traceRows(result.candidate_evaluations)
  return rows.find((r) => r.candidate_id === preferred) ?? rows.find((r) => r.eligible_for_ranking === true) ?? rows[0] ?? null
}
