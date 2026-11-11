import { describe, expect, it } from 'vitest'
import { newAnalysisIntent, newAnalysisRoute, savedAnalysisIntent, savedAnalysisRoute } from '@/services/analysis-entry'

describe('original page analysis links', () => {
  it('carries a fresh explicit graph without the prior run context', () => {
    const route = newAnalysisRoute('chosen-graph')
    expect(route).toEqual({ name: 'evidence', query: { intent: 'new-analysis', graph: 'chosen-graph' } })
    expect(newAnalysisIntent(route.query)).toEqual({ graphId: 'chosen-graph' })
    expect(newAnalysisIntent({ graph: 'ordinary-history' })).toBeNull()
  })
  it('hands the same native analysis ID, source and Frame between the original pages', () => {
    const graphRoute = savedAnalysisRoute('graphs', 'analysis-1', 'window-2')
    const intent = savedAnalysisIntent(graphRoute.query)
    expect(intent).toEqual({ runId: 'analysis-1', frameId: 'window-2' })
    expect(graphRoute).toEqual({
      name: 'graphs', query: { source: 'analysis-v2', run_id: 'analysis-1', case_id: 'window-2' },
    })
    expect(savedAnalysisRoute('evidence', intent!.runId, intent!.frameId)).toEqual({
      name: 'saved-analysis', params: { runId: 'analysis-1' }, query: { case_id: 'window-2' },
    })
    expect(savedAnalysisIntent({ run_id: 'legacy', case_id: 'case' })).toBeNull()
  })

  it('places the Frame and selected tab on the official run path without a source selector', () => {
    expect(savedAnalysisRoute('evidence', 'a', 'b', 'evidence')).toEqual({
      name: 'saved-analysis', params: { runId: 'a' }, query: { case_id: 'b', tab: 'evidence' },
    })
  })
})
