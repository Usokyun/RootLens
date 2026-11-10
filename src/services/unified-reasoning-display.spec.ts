import { describe, expect, it } from 'vitest'
import { queryLabel, selectTraceCandidate, traceQueryIndex, traceTruth, traceValue, unifiedQueries } from './unified-reasoning-display'

describe('stored unified reasoning traces', () => {
  it('keeps legacy results hidden and pairs each focused query with its own frame', () => {
    expect(unifiedQueries({ reasoner: 'legacy', trace: [] })).toEqual([])
    const queries = unifiedQueries({ query_results: [{ schema_version: 'rootlens-reasoning-result.v2', case_id: 'one' }, { schema_version: 'rootlens-reasoning-result.v2', case_id: 'two' }], evidence_frames: [{ case_id: 'one' }, { case_id: 'two' }] })
    expect(queries.map((q) => q.frame.case_id)).toEqual(['one', 'two'])
    expect(traceQueryIndex(queries, 'two')).toBe(1)
    const mixed = unifiedQueries({ query_results: [null, { schema_version: 'rootlens-reasoning-result.v2', case_id: 'two' }], evidence_frames: [{ case_id: 'one' }, { case_id: 'two' }] })
    expect(mixed[0]?.frame.case_id).toBe('two')
  })
  it('does not conflate false and missing or turn scores into probabilities', () => {
    expect(traceTruth(false)).toBe('不满足')
    expect(traceTruth(null)).toBe('未知 / 缺测')
    expect(traceValue(-0.25)).toBe('-0.25')
    expect(traceValue({ kind: 'candidate_set', items: ['scratch'], exhaustive: false })).toBe('scratch（开放集合）')
    expect(traceValue('<script>raw</script>')).toBe('<script>raw</script>')
  })
  it('selects all evaluated candidates including excluded competitors without changing ranking', () => {
    const rows = [{ candidate_id: 'conflict', eligible_for_ranking: false }, { candidate_id: 'support', eligible_for_ranking: true }]
    const result = { candidate_evaluations: rows }
    expect(selectTraceCandidate(result, null)?.candidate_id).toBe('support')
    expect(selectTraceCandidate(result, 'conflict')?.candidate_id).toBe('conflict')
    expect(rows[0]?.eligible_for_ranking).toBe(false)
  })
  it('labels actual process windows from their scope', () => {
    expect(queryLabel({ task: { scope_id: 'window' }, scopes: [{ scope_id: 'window', kind: 'time_window', sample_start: 161, sample_end: 260 }] }, 0)).toBe('窗口 161–260')
  })
})
