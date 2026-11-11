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
    const intent = savedAnalysisIntent(savedAnalysisRoute('evidence', 'analysis-1', 'window-2').query)
    expect(intent).toEqual({ runId: 'analysis-1', frameId: 'window-2' })
    expect(savedAnalysisRoute('graphs', intent!.runId, intent!.frameId)).toEqual({
      name: 'graphs', query: { source: 'analysis-v2', run_id: 'analysis-1', case_id: 'window-2' },
    })
    expect(savedAnalysisIntent({ run_id: 'legacy', case_id: 'case' })).toBeNull()
  })
})
