import { beforeEach, describe, expect, it } from 'vitest'

import { getWorkbenchState, resetWorkbenchState, updateWorkbenchState } from '@/services/workbench-state'

describe('workbench state persistence', () => {
  beforeEach(() => {
    window.localStorage.clear()
  })

  it('persists the new Phase B observation and filter fields', () => {
    updateWorkbenchState({
      selectedObservationId: 'obs-1',
      evidenceFilterGraph: 'demo-graph',
      evidenceFilterModality: 'time_series',
      evidenceFilterSource: 'image',
      evidenceFilterKeyword: 'feed_flow',
      evidenceFilterConfidenceBand: 'medium',
      evidenceFilterTimeFrom: '2026-05-16T09:00:00Z',
      evidenceFilterTimeTo: '2026-05-16T10:00:00Z',
    })

    expect(getWorkbenchState()).toMatchObject({
      selectedObservationId: 'obs-1',
      evidenceFilterGraph: 'demo-graph',
      evidenceFilterModality: 'time_series',
      evidenceFilterSource: 'image',
      evidenceFilterKeyword: 'feed_flow',
      evidenceFilterConfidenceBand: 'medium',
      evidenceFilterTimeFrom: '2026-05-16T09:00:00Z',
      evidenceFilterTimeTo: '2026-05-16T10:00:00Z',
    })
  })

  it('normalizes unsupported observation filter values back to safe defaults', () => {
    updateWorkbenchState({
      evidenceFilterModality: 'invalid' as never,
      evidenceFilterConfidenceBand: 'invalid' as never,
      evidenceFilterKeyword: '   ',
    })

    expect(getWorkbenchState()).toMatchObject({
      evidenceFilterModality: null,
      evidenceFilterConfidenceBand: 'all',
      evidenceFilterKeyword: null,
    })
  })

  it('resets the new fields to defaults', () => {
    updateWorkbenchState({
      selectedObservationId: 'obs-1',
      evidenceFilterGraph: 'demo-graph',
      evidenceFilterConfidenceBand: 'high',
    })

    expect(resetWorkbenchState()).toMatchObject({
      selectedObservationId: null,
      evidenceFilterGraph: null,
      evidenceFilterConfidenceBand: 'all',
    })
  })
})
