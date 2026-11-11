import { describe, expect, it } from 'vitest'
import { newAnalysisIntent, newAnalysisRoute, savedAnalysisRoute } from '@/services/analysis-entry'

describe('original page analysis links', () => {
  it('carries a fresh explicit graph without the prior run context', () => {
    const route = newAnalysisRoute('chosen-graph')
    expect(route).toEqual({ name: 'evidence', query: { intent: 'new-analysis', graph: 'chosen-graph' } })
    expect(newAnalysisIntent(route.query)).toEqual({ graphId: 'chosen-graph' })
    expect(newAnalysisIntent({ graph: 'ordinary-history' })).toBeNull()
  })
  it('places the Frame and selected tab on the official run path without a source selector', () => {
    expect(savedAnalysisRoute('a', 'b', 'graph')).toEqual({
      name: 'saved-analysis', params: { runId: 'a' }, query: { case_id: 'b', tab: 'graph' },
    })
  })
})
