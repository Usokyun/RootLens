import { describe, expect, it } from 'vitest'
import { newAnalysisIntent, newAnalysisRoute } from '@/services/analysis-entry'

describe('graph-to-analysis intent', () => {
  it('carries both a fresh-analysis intent and the explicitly chosen graph', () => {
    expect(newAnalysisRoute('glass-graph')).toEqual({name:'evidence',query:{intent:'new-analysis',graph:'glass-graph'}})
    expect(newAnalysisIntent({intent:'new-analysis',graph:'glass-graph'})).toEqual({graphId:'glass-graph'})
  })
  it('does not reinterpret ordinary history navigation or malformed graph values as a historical run', () => {
    expect(newAnalysisIntent({})).toBeNull()
    expect(newAnalysisIntent({graph:'glass-graph'})).toBeNull()
    expect(newAnalysisIntent({intent:'new-analysis',graph:['glass-graph']})).toEqual({graphId:''})
  })
})
