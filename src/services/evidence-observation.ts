import type { RunCaseDetail, VisualEvidenceItem } from '@/api/contracts'

export type ObservationModality = 'image' | 'time_series' | 'log' | 'document'
export type ObservationConfidenceBand = 'all' | 'high' | 'medium' | 'low'

export interface ObservationBrowseFilters {
  graph: string | null
  modality: ObservationModality | null
  source: string | null
  keyword: string | null
  confidenceBand: ObservationConfidenceBand
  timeFrom: string | null
  timeTo: string | null
}

export interface ObservationBrowseItem {
  id: string
  caseId: string
  caseLabel: string
  dataset: string
  graphDatasetId: string
  facet: string
  modality: ObservationModality
  source: string
  timestamp: string | null
  timeLabel: string
  confidence: number | null
  confidenceBand: Exclude<ObservationConfidenceBand, 'all'> | null
  title: string
  linkedEntityCount: number
  rawRefCount: number
  linkedEntityHints: string[]
  rawEvidenceRefs: Array<{
    refId: string
    label: string
    role: string
    filePath: string
    line: number | null
  }>
  rawObservation: Record<string, unknown>
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function normalizeText(value: unknown, fallback = '--') {
  return typeof value === 'string' && value.trim().length ? value.trim() : fallback
}

function normalizeNullableText(value: unknown) {
  return typeof value === 'string' && value.trim().length ? value.trim() : null
}

function normalizeNumber(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null
}

function getGraphDatasetId(caseItem: RunCaseDetail) {
  const evidence = isRecord(caseItem.generated_evidence) ? caseItem.generated_evidence : null
  const graphDatasetId = evidence ? normalizeNullableText(evidence.graph_dataset_id) : null
  return graphDatasetId ?? 'default-graph'
}

function getEvidenceSource(caseItem: RunCaseDetail) {
  const evidence = isRecord(caseItem.generated_evidence) ? caseItem.generated_evidence : null
  return normalizeText(evidence?.source ?? caseItem.source, 'unknown')
}

function getEvidenceTimestamp(caseItem: RunCaseDetail) {
  const evidence = isRecord(caseItem.generated_evidence) ? caseItem.generated_evidence : null
  return normalizeNullableText(evidence?.timestamp)
}

function getObservations(caseItem: RunCaseDetail) {
  const evidence = isRecord(caseItem.generated_evidence) ? caseItem.generated_evidence : null
  return Array.isArray(evidence?.observations) ? evidence.observations.filter(isRecord) : []
}

function toModality(facet: string): ObservationModality {
  switch (facet) {
    case 'image_defect':
      return 'image'
    case 'variable':
      return 'time_series'
    case 'log_event':
      return 'log'
    default:
      return 'document'
  }
}

function toConfidenceBand(value: number | null): Exclude<ObservationConfidenceBand, 'all'> | null {
  if (typeof value !== 'number') {
    return null
  }

  if (value >= 0.75) {
    return 'high'
  }

  if (value >= 0.4) {
    return 'medium'
  }

  return 'low'
}

function buildObservationTitle(observation: Record<string, unknown>, facet: string) {
  switch (facet) {
    case 'variable':
      return `${normalizeText(observation.variable_name)} / ${normalizeText(observation.direction, 'unknown')}`
    case 'image_defect':
      return `${normalizeText(observation.object)} / ${normalizeText(observation.anomaly_type)}`
    case 'log_event':
      return `${normalizeText(observation.event_code, normalizeText(observation.event_type))} / ${normalizeText(observation.equipment)}`
    default:
      return normalizeText(observation.obs_id, '未命名 observation')
  }
}

function buildTimeLabel(observation: Record<string, unknown>, caseTimestamp: string | null) {
  if (isRecord(observation.time_window)) {
    const start = normalizeNullableText(observation.time_window.start)
    const end = normalizeNullableText(observation.time_window.end)
    if (start && end) {
      return `${start} → ${end}`
    }
    if (start || end) {
      return start ?? end ?? '--'
    }
  }

  return caseTimestamp ?? '--'
}

function buildTimestamp(observation: Record<string, unknown>, caseTimestamp: string | null) {
  if (isRecord(observation.time_window)) {
    return normalizeNullableText(observation.time_window.start) ?? normalizeNullableText(observation.time_window.end)
  }

  return caseTimestamp
}

function buildRawEvidenceRefs(observation: Record<string, unknown>) {
  const rawRefs = Array.isArray(observation.raw_evidence_refs) ? observation.raw_evidence_refs.filter(isRecord) : []
  return rawRefs.map((item) => ({
    refId: normalizeText(item.ref_id),
    label: normalizeText(item.label),
    role: normalizeText(item.role),
    filePath: normalizeText(item.file_path),
    line: typeof item.line === 'number' ? item.line : null,
  }))
}

function toSearchText(item: ObservationBrowseItem) {
  return [
    item.caseLabel,
    item.dataset,
    item.graphDatasetId,
    item.title,
    item.modality,
    item.source,
    item.timeLabel,
    item.linkedEntityHints.join(' '),
    item.rawEvidenceRefs.map((entry) => `${entry.label} ${entry.filePath} ${entry.role}`).join(' '),
  ]
    .join(' ')
    .toLowerCase()
}

export function buildObservationBrowseItems(caseItem: RunCaseDetail): ObservationBrowseItem[] {
  const caseLabel = caseItem.case_label ?? caseItem.label ?? caseItem.case_id
  const dataset = normalizeText(caseItem.dataset, '--')
  const graphDatasetId = getGraphDatasetId(caseItem)
  const source = getEvidenceSource(caseItem)
  const caseTimestamp = getEvidenceTimestamp(caseItem)

  return getObservations(caseItem).map((observation, index) => {
    const facet = normalizeText(observation.facet, 'unknown')
    const linkedEntityHints = Array.isArray(observation.linked_entity_hints)
      ? observation.linked_entity_hints.map((item) => String(item)).filter(Boolean)
      : []
    const rawEvidenceRefs = buildRawEvidenceRefs(observation)
    const confidence = normalizeNumber(observation.confidence)

    const item: ObservationBrowseItem = {
      id: normalizeText(observation.obs_id, `${caseItem.case_id}-obs-${index + 1}`),
      caseId: caseItem.case_id,
      caseLabel,
      dataset,
      graphDatasetId,
      facet,
      modality: toModality(facet),
      source,
      timestamp: buildTimestamp(observation, caseTimestamp),
      timeLabel: buildTimeLabel(observation, caseTimestamp),
      confidence,
      confidenceBand: toConfidenceBand(confidence),
      title: buildObservationTitle(observation, facet),
      linkedEntityCount: linkedEntityHints.length,
      rawRefCount: rawEvidenceRefs.length,
      linkedEntityHints,
      rawEvidenceRefs,
      rawObservation: observation,
    }

    return item
  })
}

function matchesKeyword(item: ObservationBrowseItem, keyword: string | null) {
  if (!keyword) {
    return true
  }

  return toSearchText(item).includes(keyword.trim().toLowerCase())
}

function matchesConfidenceBand(item: ObservationBrowseItem, band: ObservationConfidenceBand) {
  if (band === 'all') {
    return true
  }

  return item.confidenceBand === band
}

function matchesTimeRange(item: ObservationBrowseItem, timeFrom: string | null, timeTo: string | null) {
  if (!timeFrom && !timeTo) {
    return true
  }

  if (!item.timestamp) {
    return false
  }

  const timestamp = Date.parse(item.timestamp)
  if (Number.isNaN(timestamp)) {
    return false
  }

  if (timeFrom) {
    const start = Date.parse(timeFrom)
    if (!Number.isNaN(start) && timestamp < start) {
      return false
    }
  }

  if (timeTo) {
    const end = Date.parse(timeTo)
    if (!Number.isNaN(end) && timestamp > end) {
      return false
    }
  }

  return true
}

export function filterObservationBrowseItems(items: ObservationBrowseItem[], filters: ObservationBrowseFilters) {
  return items.filter((item) => {
    if (filters.graph && item.graphDatasetId !== filters.graph) {
      return false
    }

    if (filters.modality && item.modality !== filters.modality) {
      return false
    }

    if (filters.source && item.source !== filters.source) {
      return false
    }

    if (!matchesConfidenceBand(item, filters.confidenceBand)) {
      return false
    }

    if (!matchesTimeRange(item, filters.timeFrom, filters.timeTo)) {
      return false
    }

    return matchesKeyword(item, filters.keyword)
  })
}

export function findObservationBrowseItem(items: ObservationBrowseItem[], observationId: string | null | undefined) {
  if (!observationId) {
    return null
  }

  return items.find((item) => item.id === observationId) ?? null
}

export function collectObservationSources(items: ObservationBrowseItem[]) {
  return [...new Set(items.map((item) => item.source).filter(Boolean))]
}

export function collectObservationModalities(items: ObservationBrowseItem[]) {
  return [...new Set(items.map((item) => item.modality))]
}

export function selectVisualEvidenceForObservation(
  observation: ObservationBrowseItem | null,
  visualEvidence: VisualEvidenceItem[] | null | undefined,
) {
  if (!observation || observation.modality !== 'image') {
    return []
  }

  return (visualEvidence ?? []).filter((item) => item.available !== false).slice(0, 3)
}
