import {
  buildObservationPatchDiff,
  buildObservationPatchPreview,
  splitHintText,
} from '@/services/what-if'
import type { EvidenceObservation } from '@/types/rootlens'
import { describe, expect, it } from 'vitest'

const variableObservation: EvidenceObservation = {
  obs_id: 'obs-var-1',
  facet: 'variable',
  variable_name: 'xmeas_1',
  contribution: 0.82,
  direction: 'decrease',
  confidence: 0.95,
  linked_entity_hints: ['variable:xmeas_1', 'stream:stream_1_a_feed'],
  raw_evidence_refs: [],
}

const logObservation: EvidenceObservation = {
  obs_id: 'obs-log-1',
  facet: 'log_event',
  event_code: 'ALM-42',
  event_type: 'alarm',
  message: 'pressure alarm',
  equipment: 'reactor-feed-valve',
  confidence: 0.71,
  linked_entity_hints: ['equipment:reactor-feed-valve'],
  raw_evidence_refs: [],
}

describe('buildObservationPatchDiff', () => {
  it('reports only fields that actually changed for variable observations', () => {
    const diff = buildObservationPatchDiff(variableObservation, {
      ...buildObservationPatchPreview(variableObservation),
      contribution: 0.9,
      linked_entity_hints: splitHintText('variable:xmeas_1\nfaultanchor:stream_1_a_feed_loss'),
    })

    expect(diff).toEqual([
      {
        key: 'contribution',
        label: 'contribution',
        before: '0.82',
        after: '0.9',
      },
      {
        key: 'linked_entity_hints',
        label: 'linked entity hints',
        before: 'variable:xmeas_1 / stream:stream_1_a_feed',
        after: 'variable:xmeas_1 / faultanchor:stream_1_a_feed_loss',
      },
    ])
  })

  it('returns an empty diff when patch values equal the current observation', () => {
    expect(
      buildObservationPatchDiff(logObservation, buildObservationPatchPreview(logObservation)),
    ).toEqual([])
  })
})
