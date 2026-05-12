import type { UnifiedGraphDataset } from '@/types/graph'
import { buildLocalAnalysisResult } from '@/services/local-reasoning'
import type {
  CorrectionCandidate,
  EvidenceObservation,
  ObservationDirection,
  ObservationFacet,
  RootLensRuntimeCase,
} from '@/types/rootlens'

export interface ObservationWhatIfPatch {
  confidence?: number
  linked_entity_hints?: string[]
  variable_name?: string
  contribution?: number
  direction?: ObservationDirection
  object?: string
  anomaly_type?: string
  location?: string
  severity?: number
  event_code?: string
  event_type?: string
  equipment?: string
}

export interface ObservationPatchDiffItem {
  key: keyof ObservationWhatIfPatch
  label: string
  before: string
  after: string
}

function cloneCase(caseItem: RootLensRuntimeCase): RootLensRuntimeCase {
  return JSON.parse(JSON.stringify(caseItem)) as RootLensRuntimeCase
}

function normalizeHints(hints: string[] | undefined): string[] | undefined {
  if (!hints) {
    return undefined
  }

  return [...new Set(hints.map((item) => item.trim()).filter(Boolean))]
}

function normalizeComparableValue(value: unknown): unknown {
  if (Array.isArray(value)) {
    return normalizeHints(value.map((item) => String(item))) ?? []
  }

  return value
}

function formatDiffValue(value: unknown): string {
  if (Array.isArray(value)) {
    return value.length ? value.join(' / ') : 'empty'
  }

  if (value === null || value === undefined || value === '') {
    return 'empty'
  }

  return typeof value === 'string' ? value : JSON.stringify(value)
}

function getDiffFields(
  observation: EvidenceObservation,
): Array<{ key: keyof ObservationWhatIfPatch; label: string }> {
  const commonFields = [
    { key: 'confidence' as const, label: 'confidence' },
    { key: 'linked_entity_hints' as const, label: 'linked entity hints' },
  ]

  switch (observation.facet) {
    case 'variable':
      return [
        { key: 'variable_name', label: 'variable name' },
        { key: 'contribution', label: 'contribution' },
        { key: 'direction', label: 'direction' },
        ...commonFields,
      ]
    case 'image_defect':
      return [
        { key: 'object', label: 'object' },
        { key: 'anomaly_type', label: 'anomaly type' },
        { key: 'location', label: 'location' },
        { key: 'severity', label: 'severity' },
        ...commonFields,
      ]
    case 'log_event':
      return [
        { key: 'event_code', label: 'event code' },
        { key: 'event_type', label: 'event type' },
        { key: 'equipment', label: 'equipment' },
        ...commonFields,
      ]
  }
}

function readObservationFieldValue(
  observation: EvidenceObservation,
  key: keyof ObservationWhatIfPatch,
): unknown {
  switch (key) {
    case 'confidence':
      return observation.confidence
    case 'linked_entity_hints':
      return observation.linked_entity_hints
    case 'variable_name':
      return observation.facet === 'variable' ? observation.variable_name : undefined
    case 'contribution':
      return observation.facet === 'variable' ? observation.contribution : undefined
    case 'direction':
      return observation.facet === 'variable' ? observation.direction : undefined
    case 'object':
      return observation.facet === 'image_defect' ? observation.object : undefined
    case 'anomaly_type':
      return observation.facet === 'image_defect' ? observation.anomaly_type : undefined
    case 'location':
      return observation.facet === 'image_defect' ? observation.location : undefined
    case 'severity':
      return observation.facet === 'image_defect' ? observation.severity : undefined
    case 'event_code':
      return observation.facet === 'log_event' ? observation.event_code : undefined
    case 'event_type':
      return observation.facet === 'log_event' ? observation.event_type : undefined
    case 'equipment':
      return observation.facet === 'log_event' ? observation.equipment : undefined
  }
}

function patchObservation(
  observation: EvidenceObservation,
  patch: ObservationWhatIfPatch,
): EvidenceObservation {
  const commonFields = {
    confidence: patch.confidence ?? observation.confidence,
    linked_entity_hints:
      normalizeHints(patch.linked_entity_hints) ?? observation.linked_entity_hints,
  }

  switch (observation.facet) {
    case 'variable':
      return {
        ...observation,
        ...commonFields,
        variable_name: patch.variable_name ?? observation.variable_name,
        contribution: patch.contribution ?? observation.contribution,
        direction: patch.direction ?? observation.direction,
      }
    case 'image_defect':
      return {
        ...observation,
        ...commonFields,
        object: patch.object ?? observation.object,
        anomaly_type: patch.anomaly_type ?? observation.anomaly_type,
        location: patch.location ?? observation.location,
        severity: patch.severity ?? observation.severity,
      }
    case 'log_event':
      return {
        ...observation,
        ...commonFields,
        event_code: patch.event_code ?? observation.event_code,
        event_type: patch.event_type ?? observation.event_type,
        equipment: patch.equipment ?? observation.equipment,
      }
  }
}

function buildUpdatedCase(
  caseItem: RootLensRuntimeCase,
  dataset: UnifiedGraphDataset,
  mutate: (draft: RootLensRuntimeCase) => void,
  note: string,
): RootLensRuntimeCase {
  const draft = cloneCase(caseItem)
  mutate(draft)
  const nextAnalysis = buildLocalAnalysisResult(dataset, draft.evidence)
  draft.analysis = {
    ...nextAnalysis,
    notes: [note, ...nextAnalysis.notes],
  }

  return draft
}

export function buildObservationPatchPreview(
  observation: EvidenceObservation,
): ObservationWhatIfPatch {
  switch (observation.facet) {
    case 'variable':
      return {
        confidence: observation.confidence,
        linked_entity_hints: [...observation.linked_entity_hints],
        variable_name: observation.variable_name,
        contribution: observation.contribution,
        direction: observation.direction,
      }
    case 'image_defect':
      return {
        confidence: observation.confidence,
        linked_entity_hints: [...observation.linked_entity_hints],
        object: observation.object,
        anomaly_type: observation.anomaly_type,
        location: observation.location,
        severity: observation.severity,
      }
    case 'log_event':
      return {
        confidence: observation.confidence,
        linked_entity_hints: [...observation.linked_entity_hints],
        event_code: observation.event_code,
        event_type: observation.event_type,
        equipment: observation.equipment,
      }
  }
}

export function buildObservationPatchDiff(
  observation: EvidenceObservation,
  patch: ObservationWhatIfPatch,
): ObservationPatchDiffItem[] {
  const patchedObservation = patchObservation(observation, patch)

  return getDiffFields(observation).flatMap((field) => {
    const before = normalizeComparableValue(readObservationFieldValue(observation, field.key))
    const after = normalizeComparableValue(readObservationFieldValue(patchedObservation, field.key))

    if (JSON.stringify(before) === JSON.stringify(after)) {
      return []
    }

    return [
      {
        key: field.key,
        label: field.label,
        before: formatDiffValue(before),
        after: formatDiffValue(after),
      },
    ]
  })
}

export function applyObservationWhatIf(
  caseItem: RootLensRuntimeCase,
  dataset: UnifiedGraphDataset,
  observationId: string,
  patch: ObservationWhatIfPatch,
): RootLensRuntimeCase {
  return buildUpdatedCase(
    caseItem,
    dataset,
    (draft) => {
      draft.evidence.observations = draft.evidence.observations.map((observation) =>
        observation.obs_id === observationId ? patchObservation(observation, patch) : observation,
      )
    },
    `what-if: 已更新 observation ${observationId} 并重新执行本地推理。`,
  )
}

function buildCorrectionPatch(
  observation: EvidenceObservation,
  correction: CorrectionCandidate,
): ObservationWhatIfPatch | null {
  const linkedHints = normalizeHints([
    ...observation.linked_entity_hints,
    correction.suggested_value,
    correction.suggested_entity_id,
  ])

  switch (correction.target_field) {
    case 'anomaly_type':
      return observation.facet === 'image_defect'
        ? {
            anomaly_type: correction.suggested_value,
            linked_entity_hints: linkedHints,
          }
        : null
    case 'location':
      return observation.facet === 'image_defect'
        ? {
            location: correction.suggested_value,
            linked_entity_hints: linkedHints,
          }
        : null
    case 'morphology':
      return null
    case 'equipment':
      return observation.facet === 'log_event'
        ? {
            equipment: correction.suggested_value,
            linked_entity_hints: linkedHints,
          }
        : null
    case 'log_event':
      return observation.facet === 'log_event'
        ? {
            event_code: correction.suggested_value,
            linked_entity_hints: linkedHints,
          }
        : null
    default:
      return null
  }
}

function applyMorphologyCanonical(
  observation: EvidenceObservation,
  correction: CorrectionCandidate,
): EvidenceObservation {
  if (correction.target_field !== 'morphology' || observation.facet !== 'image_defect') {
    return observation
  }

  return {
    ...observation,
    linked_entity_hints: normalizeHints([
      ...observation.linked_entity_hints,
      correction.suggested_value,
      correction.suggested_entity_id,
    ]) ?? observation.linked_entity_hints,
    morphology: {
      ...observation.morphology,
      canonical: correction.suggested_value,
    },
  }
}

export function canApplyCorrectionCandidate(candidate: CorrectionCandidate): boolean {
  return Boolean(candidate.target_obs_id)
}

export function applyCorrectionWhatIf(
  caseItem: RootLensRuntimeCase,
  dataset: UnifiedGraphDataset,
  correction: CorrectionCandidate,
): RootLensRuntimeCase {
  if (!correction.target_obs_id) {
    throw new Error('当前修正候选缺少 target_obs_id，无法回放 what-if。')
  }

  return buildUpdatedCase(
    caseItem,
    dataset,
    (draft) => {
      draft.evidence.observations = draft.evidence.observations.map((observation) => {
        if (observation.obs_id !== correction.target_obs_id) {
          return observation
        }

        const patch = buildCorrectionPatch(observation, correction)
        if (patch) {
          return patchObservation(observation, patch)
        }

        return applyMorphologyCanonical(observation, correction)
      })
    },
    `what-if: 已应用修正候选 ${correction.candidate_id} 并重新执行本地推理。`,
  )
}

export function splitHintText(value: string): string[] {
  return value
    .split(/[\n,;|]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

export function observationLabel(observation: EvidenceObservation): string {
  switch (observation.facet) {
    case 'variable':
      return `${observation.obs_id} · ${observation.variable_name}`
    case 'image_defect':
      return `${observation.obs_id} · ${observation.object} / ${observation.anomaly_type}`
    case 'log_event':
      return `${observation.obs_id} · ${observation.event_code}`
  }
}

export function fieldSupportsWhatIf(facet: ObservationFacet): boolean {
  return ['variable', 'image_defect', 'log_event'].includes(facet)
}
