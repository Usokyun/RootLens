import { describe, expect, it } from 'vitest'
import { savedTentativeCandidates, traceValue } from './unified-reasoning-display'

describe('stored unified reasoning traces', () => {
  it('does not conflate false and missing or turn scores into probabilities', () => {
    expect(traceValue(false)).toBe('false')
    expect(traceValue(null)).toBe('—')
    expect(traceValue(-0.25)).toBe('-0.25')
    expect(traceValue({ kind: 'candidate_set', items: ['scratch'], exhaustive: false })).toBe('scratch（开放集合）')
    expect(traceValue('<script>raw</script>')).toBe('<script>raw</script>')
  })
  it('reads only saved tentative items and does not promote strict failures or old snapshots', () => {
    const strict = { candidate_id: 'no-match', eligible_for_ranking: false }
    const saved = { candidate_id: 'tentative', rule_id: 'saved-rule', counter_obs_ids: ['stored-observation'] }
    expect(savedTentativeCandidates({ candidate_evaluations: [strict] })).toEqual([])
    expect(savedTentativeCandidates({ candidate_evaluations: [strict], tentative_candidates: [null, {}, saved] })).toEqual([saved])
  })
})
