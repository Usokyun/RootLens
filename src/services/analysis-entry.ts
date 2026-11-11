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
export function savedAnalysisRoute(runId: string, frameId?: string | null, tab?: string | null) {
  return { name: 'saved-analysis', params: { runId },
    query: { ...(frameId ? { case_id: frameId } : {}), ...(tab ? { tab } : {}) } } as const
}
