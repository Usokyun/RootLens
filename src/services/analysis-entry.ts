/** A graph-to-analysis link starts a fresh draft; ordinary /evidence restores history. */
export function newAnalysisRoute(graphId: string) {
  return { name: 'evidence', query: { intent: 'new-analysis', graph: graphId } } as const
}

export function newAnalysisIntent(query: Record<string, unknown>): { graphId: string } | null {
  if (query.intent !== 'new-analysis') return null
  return { graphId: typeof query.graph === 'string' ? query.graph.trim() : '' }
}
