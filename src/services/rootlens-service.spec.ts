import { canSubmitReviewTargetType } from '@/services/rootlens-service'
import { describe, expect, it } from 'vitest'

describe('review target feedback gating', () => {
  it('allows supported feedback target types', () => {
    expect(canSubmitReviewTargetType('path')).toBe(true)
    expect(canSubmitReviewTargetType('edge')).toBe(true)
    expect(canSubmitReviewTargetType('entity_link')).toBe(true)
    expect(canSubmitReviewTargetType('correction')).toBe(true)
  })

  it('allows root cause candidate feedback once backend mode catches up', () => {
    expect(canSubmitReviewTargetType('root_cause_candidate')).toBe(true)
  })
})
