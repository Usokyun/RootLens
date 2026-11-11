import {
  clearFeedbackVerdict,
  getFeedbackNote,
  getFeedbackVerdict,
  loadAnalysisWorkspace,
  setFeedbackNote,
  setFeedbackVerdict,
} from '@/services/analysis-workspace'
import { beforeEach, describe, expect, it } from 'vitest'

const SESSION_SCOPE = 'import:test-session'
const CASE_ID = 'case-001'
const TARGET_KIND = 'route2-candidate'
const TARGET_ID = 'candidate-001'

describe('analysis workspace feedback notes', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('persists analyst notes without requiring a verdict', () => {
    setFeedbackNote(SESSION_SCOPE, CASE_ID, TARGET_KIND, TARGET_ID, 'Investigate compressor branch first.')

    const workspace = loadAnalysisWorkspace(SESSION_SCOPE)

    expect(workspace?.cases).toHaveLength(1)
    expect(getFeedbackVerdict(workspace ?? null, CASE_ID, TARGET_KIND, TARGET_ID)).toBeNull()
    expect(getFeedbackNote(workspace ?? null, CASE_ID, TARGET_KIND, TARGET_ID)).toBe(
      'Investigate compressor branch first.',
    )
  })

  it('keeps notes when verdict is cleared', () => {
    setFeedbackVerdict(SESSION_SCOPE, CASE_ID, TARGET_KIND, TARGET_ID, 'accepted')
    setFeedbackNote(SESSION_SCOPE, CASE_ID, TARGET_KIND, TARGET_ID, 'Accepted for follow-up sampling.')
    clearFeedbackVerdict(SESSION_SCOPE, CASE_ID, TARGET_KIND, TARGET_ID)

    const workspace = loadAnalysisWorkspace(SESSION_SCOPE)

    expect(getFeedbackVerdict(workspace ?? null, CASE_ID, TARGET_KIND, TARGET_ID)).toBeNull()
    expect(getFeedbackNote(workspace ?? null, CASE_ID, TARGET_KIND, TARGET_ID)).toBe(
      'Accepted for follow-up sampling.',
    )
  })
})
