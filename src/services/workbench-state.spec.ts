import { beforeEach, describe, expect, it } from 'vitest'

import { getWorkbenchState, loadedRunSelectionPatch, sourceSelectionReset, resetWorkbenchState, updateWorkbenchState } from '@/services/workbench-state'

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

  it('preserves a selected non-first window and proof when returning from Graphs', () => {
    const state = { ...getWorkbenchState(), selectedRunId: 'run', selectedCaseId: 'window-2', selectedCandidateId: 'candidate', selectedPathId: 'proof' }
    const patch = loadedRunSelectionPatch(state, 'run', ['window-1', 'window-2'])
    expect({ ...state, ...patch }).toMatchObject({ selectedCaseId: 'window-2', selectedCandidateId: 'candidate', selectedPathId: 'proof' })
    expect(loadedRunSelectionPatch(state, 'other-run', ['window-1', 'window-2'])).toMatchObject({ selectedCaseId: 'window-1', selectedCandidateId: null, selectedPathId: null })
    expect(loadedRunSelectionPatch(state, 'run', [])).toMatchObject({ selectedCaseId: null, selectedPathId: null })
  })

  it('records the saved-analysis source and selects the exact requested Frame, clearing old proof focus', () => {
    const state = { ...getWorkbenchState(), selectedRunId: 'saved', selectedCaseId: 'window-1', selectedPathId: 'old-path' }
    const patch = loadedRunSelectionPatch(state, 'saved', ['window-1', 'window-2'], { source: 'analysis-v2', frameId: 'window-2' })
    expect(updateWorkbenchState(patch)).toMatchObject({ selectedRunId: 'saved', selectedRunSource: 'analysis-v2', selectedCaseId: 'window-2', selectedPathId: null })
    expect(updateWorkbenchState({ selectedRunId: 'old-run' }).selectedRunSource).toBeNull()
  })
})

it('clears only source-bound selection while preserving user filters',()=>{
  updateWorkbenchState({selectedRunId:'demo',selectedCaseId:'case',selectedPathId:'path',evidenceFilterKeyword:'temperature'})
  const next=updateWorkbenchState(sourceSelectionReset());expect(next).toMatchObject({selectedRunId:null,selectedCaseId:null,selectedPathId:null,evidenceFilterKeyword:'temperature'})
})
