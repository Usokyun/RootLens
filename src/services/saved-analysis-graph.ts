/** Read-only links from a saved Frame/path to the restored graph inspector. */
import { backendResourceUrl } from '@/api/two-loop'
import type { PathGraphPath, RunCaseDetail } from '@/api/contracts'
import { selectVisualEvidenceForObservation, type ObservationBrowseItem } from './evidence-observation'
import { buildGraphPathProvenance, type ProvenanceRecord } from './provenance-inspector'
import { traceRecord, traceRows } from './unified-reasoning-display'

export function savedPathsForCandidate(caseDetail: RunCaseDetail | null | undefined, candidateId: string | null | undefined) {
  return candidateId ? caseDetail?.path_graph?.paths.filter(path => path.target_entity_id === candidateId) ?? [] : []
}

export function savedPathForEdge(
  caseDetail: RunCaseDetail | null | undefined,
  edgeId: string,
  candidateId?: string | null,
  pathId?: string | null,
) {
  const paths = caseDetail?.path_graph?.paths.filter(path => path.edges.some(edge => edge.edge_id === edgeId)) ?? []
  return paths.find(path => path.path_id === pathId)
    ?? paths.find(path => candidateId && path.target_entity_id === candidateId)
    ?? paths[0] ?? null
}

export function savedPathObservation(path: PathGraphPath | null | undefined, preferredId?: string | null) {
  const ids = path?.supporting_evidence.filter((item): item is string => typeof item === 'string') ?? []
  return preferredId && ids.includes(preferredId) ? preferredId : ids[0] ?? null
}

const finite = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const valueText = (value: unknown) => typeof value === 'string' && value.length ? value : null
const numbers = (value: unknown, size: number) => Array.isArray(value) && value.length === size && value.every(finite) ? value as number[] : null

export function savedObservationLocation(caseDetail: RunCaseDetail, observation: ObservationBrowseItem, apiBase: string) {
  const saved = traceRecord(observation.rawObservation.observation_location)
  if (saved.obs_id !== observation.id) return null
  const scope = traceRecord(saved.scope)
  const feature = valueText(observation.rawObservation.feature_id)
  const value = observation.rawObservation.value
  if (scope.kind === 'image_region') {
    const media = selectVisualEvidenceForObservation(observation, caseDetail.visual_evidence).flatMap(item => {
      const url = backendResourceUrl(apiBase, item.url)
      return url ? [{ ...item, url }] : []
    })
    return {
      kind: 'image_region' as const, feature, value, scopeId: valueText(scope.scope_id),
      bbox: numbers(scope.bbox_xyxy, 4), imageShape: numbers(scope.image_shape_hw, 2),
      coordinateSpace: valueText(scope.coordinate_space), media,
    }
  }
  if (scope.kind === 'time_window' && finite(scope.sample_start) && finite(scope.sample_end)) {
    const channel = valueText(saved.subject_external_id) ?? valueText(observation.rawObservation.subject_external_id)
    const trend = traceRows(caseDetail.process_trends).find(item => item.channel === channel)
    const samples = Array.isArray(trend?.samples) && trend.samples.length && trend.samples.every(finite)
      ? trend.samples as number[] : null
    return {
      kind: 'time_window' as const, feature, value, channel, samples,
      start: scope.sample_start, end: scope.sample_end,
      samplingSeconds: finite(scope.sampling_seconds) ? scope.sampling_seconds : null,
    }
  }
  return null
}

function sourceLocator(value: unknown) {
  if (typeof value !== 'string') return ''
  try {
    const locator = traceRecord(JSON.parse(value))
    if (finite(locator.page)) return `PDF 第 ${locator.page} 页`
    if (finite(locator.start_line)) return `第 ${locator.start_line}–${locator.end_line ?? locator.start_line} 行`
  } catch { /* An older snapshot may carry an already formatted locator. */ }
  return value
}

export function buildSavedPathProvenance(caseDetail: RunCaseDetail, pathId: string, claimBoundary: string, apiBase: string) {
  const base = buildGraphPathProvenance({ caseDetail, pathId, claimBoundary })
  const path = caseDetail.path_graph?.paths.find(item => item.path_id === pathId)
  if (!base || !path) return base
  const record = caseDetail.top_k_paths?.find(item => item.path_id === pathId)
  const sourceRecords: ProvenanceRecord[] = traceRows(record?.source_assertions).flatMap(assertion => {
    const id = valueText(assertion.assertion_id)
    if (!id) return []
    return [{
      recordId: `assertion:${id}`, sourceType: 'source_material',
      sourceLabel: valueText(assertion.origin) ?? '保存的资料断言',
      sourcePathOrId: [valueText(assertion.source_id), sourceLocator(assertion.locator), valueText(assertion.source_unit_id)].filter(Boolean).join(' · ') || id,
      snippetOrPreview: valueText(assertion.text), previewUrl: null, confidence: null,
      claimBoundary, reviewTargetKey: null, tags: ['source-grounded'], multiline: false,
    }]
  })
  const edgeRecords: ProvenanceRecord[] = path.edges.map(edge => ({
    recordId: `saved-edge:${edge.edge_id}`, sourceType: 'edge_provenance',
    sourceLabel: edge.relation, sourcePathOrId: edge.edge_id,
    snippetOrPreview: `${edge.source_node_id} → ${edge.target_node_id}`,
    previewUrl: null, confidence: edge.confidence ?? null, claimBoundary,
    reviewTargetKey: null, tags: [], multiline: false,
  }))
  return {
    ...base,
    records: [
      ...sourceRecords, ...edgeRecords,
      ...base.records.filter(item => item.sourceType !== 'edge_provenance').map(item => ({
        ...item, previewUrl: backendResourceUrl(apiBase, item.previewUrl),
      })),
    ],
  }
}
