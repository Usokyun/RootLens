import type {
  RunCaseDetail,
  RunDetail,
  RunReasoningMetadata,
  VisualEvidenceItem,
} from '@/api/contracts'

const CLAIM_BOUNDARY_FALLBACK = '候选/合理解释，仅供研判；并非已验证的根因标签'
const SCORING_METHOD_LABELS: Record<string, string> = {
  relation_weighted_path: '关系加权路径',
  artifact_bridge: '工件桥接',
  heuristic_path_support: '启发式路径支持',
  tep_root_kgd: 'TEP Root-KGD 排序',
  tep_artifact_bridge: 'TEP 工件桥接',
  root_score_fusion: 'RootScore 融合',
}
const REASONER_ADAPTER_LABELS: Record<string, string> = {
  generic_graph_path: 'Generic Path',
  tep_root_kgd: 'TEP Root-KGD',
}
const REASONING_SELECTION_MODE_LABELS: Record<string, string> = {
  default: 'Auto',
  explicit: 'Explicit',
  direct: 'Direct',
}

export interface RunReasoningSummary {
  adapter: string | null
  profileId: string | null
  selectionMode: string | null
  requestedProfileId: string | null
  requestedAdapter: string | null
  fallbackApplied: boolean
  fallbackReason: string | null
  source: 'case' | 'summary' | 'analysis' | 'run' | 'none'
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function normalizeNullableText(value: unknown) {
  return typeof value === 'string' && value.trim().length ? value.trim() : null
}

function normalizeNullableBoolean(value: unknown) {
  return typeof value === 'boolean' ? value : null
}

function hasReasoningMetadataValue(metadata: RunReasoningMetadata | null | undefined) {
  if (!metadata) {
    return false
  }

  return [
    metadata.reasoning_profile_id,
    metadata.reasoner_adapter,
    metadata.selection_mode,
    metadata.requested_reasoning_profile_id,
    metadata.requested_reasoner_adapter,
    metadata.fallback_reason,
  ].some((item) => normalizeNullableText(item)) || metadata.fallback_applied === true
}

function readReasoningMetadata(value: unknown): RunReasoningMetadata | null {
  if (!isRecord(value)) {
    return null
  }

  return {
    reasoning_profile_id: normalizeNullableText(value.reasoning_profile_id),
    reasoner_adapter: normalizeNullableText(value.reasoner_adapter),
    selection_mode: normalizeNullableText(value.selection_mode),
    requested_reasoning_profile_id: normalizeNullableText(value.requested_reasoning_profile_id),
    requested_reasoner_adapter: normalizeNullableText(value.requested_reasoner_adapter),
    fallback_applied: normalizeNullableBoolean(value.fallback_applied),
    fallback_reason: normalizeNullableText(value.fallback_reason),
  }
}

function mergeReasoningMetadata(
  primary: RunReasoningMetadata | null,
  fallback: RunReasoningMetadata | null,
): RunReasoningMetadata | null {
  if (!primary && !fallback) {
    return null
  }

  return {
    reasoning_profile_id: primary?.reasoning_profile_id ?? fallback?.reasoning_profile_id ?? null,
    reasoner_adapter: primary?.reasoner_adapter ?? fallback?.reasoner_adapter ?? null,
    selection_mode: primary?.selection_mode ?? fallback?.selection_mode ?? null,
    requested_reasoning_profile_id:
      primary?.requested_reasoning_profile_id ?? fallback?.requested_reasoning_profile_id ?? null,
    requested_reasoner_adapter:
      primary?.requested_reasoner_adapter ?? fallback?.requested_reasoner_adapter ?? null,
    fallback_applied: primary?.fallback_applied ?? fallback?.fallback_applied ?? null,
    fallback_reason: primary?.fallback_reason ?? fallback?.fallback_reason ?? null,
  }
}

function readRunSummaryReasoningMetadata(runDetail: RunDetail | null | undefined) {
  return readReasoningMetadata(isRecord(runDetail?.summary) ? runDetail?.summary.pipeline : null)
}

function readRunAnalysisReasoningMetadata(runDetail: RunDetail | null | undefined) {
  return readReasoningMetadata(isRecord(runDetail?.analysis) ? runDetail?.analysis.reasoning_metadata : null)
}

function readRunTopLevelReasoningMetadata(runDetail: RunDetail | null | undefined) {
  return readReasoningMetadata(runDetail?.reasoning_metadata)
}

export function formatClaimBoundaryCopy(value: string | null | undefined) {
  if (!value) {
    return '候选结论边界加载中'
  }

  const normalized = value.trim()
  if (!normalized) {
    return '候选结论边界加载中'
  }

  if (
    normalized === 'candidate/plausible explanation only; not a verified root-cause label' ||
    /candidate\/plausible explanation only/i.test(normalized) ||
    /not a verified root-cause label/i.test(normalized)
  ) {
    return CLAIM_BOUNDARY_FALLBACK
  }

  return normalized
}

export function formatScoringMethodLabel(value: string | null | undefined) {
  if (!value) {
    return '未标注'
  }

  return SCORING_METHOD_LABELS[value] ?? value
}

export function formatReasonerAdapterLabel(value: string | null | undefined) {
  if (!value) {
    return '--'
  }

  return REASONER_ADAPTER_LABELS[value] ?? value
}

export function formatReasoningSelectionModeLabel(value: string | null | undefined) {
  if (!value) {
    return 'Auto'
  }

  return REASONING_SELECTION_MODE_LABELS[value] ?? value
}

export function resolveRunReasoningSummary(
  runDetail: RunDetail | null | undefined,
  caseDetail: RunCaseDetail | null | undefined,
): RunReasoningSummary {
  const caseMetadata = readReasoningMetadata(caseDetail?.reasoning_metadata)
  const summaryMetadata = readRunSummaryReasoningMetadata(runDetail)
  const analysisMetadata = readRunAnalysisReasoningMetadata(runDetail)
  const runMetadata = readRunTopLevelReasoningMetadata(runDetail)
  const merged = mergeReasoningMetadata(
    mergeReasoningMetadata(
      mergeReasoningMetadata(caseMetadata, summaryMetadata),
      analysisMetadata,
    ),
    runMetadata,
  )

  let source: RunReasoningSummary['source'] = 'none'
  if (hasReasoningMetadataValue(caseMetadata)) {
    source = 'case'
  } else if (hasReasoningMetadataValue(summaryMetadata)) {
    source = 'summary'
  } else if (hasReasoningMetadataValue(analysisMetadata)) {
    source = 'analysis'
  } else if (hasReasoningMetadataValue(runMetadata)) {
    source = 'run'
  }

  return {
    adapter: normalizeNullableText(merged?.reasoner_adapter),
    profileId: normalizeNullableText(merged?.reasoning_profile_id),
    selectionMode: normalizeNullableText(merged?.selection_mode),
    requestedProfileId: normalizeNullableText(merged?.requested_reasoning_profile_id),
    requestedAdapter: normalizeNullableText(merged?.requested_reasoner_adapter),
    fallbackApplied: merged?.fallback_applied === true,
    fallbackReason: normalizeNullableText(merged?.fallback_reason),
    source,
  }
}

export function resolveVisualEvidenceUrl(
  item: Pick<VisualEvidenceItem, 'url' | 'preview_path' | 'source_path'> | null | undefined,
) {
  return item?.url ?? item?.preview_path ?? item?.source_path ?? null
}
