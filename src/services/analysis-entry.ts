function queryText(value: unknown) {
  return typeof value === 'string' && value.trim() ? value.trim() : null
}

/** Carry an explicit graph without carrying the previously selected run. */
export function newAnalysisRoute(graphId: string) {
  return { name: 'evidence', query: { intent: 'new-analysis', graph: graphId } } as const
}

export function newAnalysisIntent(query: Record<string, unknown>): { graphId: string } | null {
  return query.intent === 'new-analysis' ? { graphId: queryText(query.graph) ?? '' } : null
}

/** case_id is the saved result / EvidenceFrame ID, not the enclosing input sample ID. */
export function savedAnalysisRoute(page: 'evidence' | 'graphs', runId: string, frameId?: string | null, tab?: string | null) {
  const query = frameId ? { case_id: frameId } : {}
  if (page === 'graphs') return { name: 'graphs', query: { run_id: runId, source: 'analysis-v2', ...query } } as const
  return { name: 'saved-analysis', params: { runId }, query: { ...query, ...(tab ? { tab } : {}) } } as const
}

export function savedAnalysisIntent(query: Record<string, unknown>) {
  const runId = queryText(query.run_id)
  return query.source === 'analysis-v2' && runId ? { runId, frameId: queryText(query.case_id) } : null
}
