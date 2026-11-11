import { describe, expect, it } from 'vitest'
import { formatClaimBoundaryCopy } from './ui-copy'

describe('material claim boundary', () => {
  it('translates the default boundary but preserves a specific saved claim', () => {
    expect(formatClaimBoundaryCopy('candidate/plausible explanation only; not a verified root-cause label')).toContain('并非已验证')
    expect(formatClaimBoundaryCopy('只描述失效图案')).toBe('只描述失效图案')
  })
})
