import type {
  AnalystFeedbackEntry,
  AnalystFeedbackTarget,
  AnalystFeedbackVerdict,
} from '@/services/analysis-workspace'
import type { RankedPath, RootKGDCandidate } from '@/types/rootlens'

export interface FeedbackSummaryItem {
  feedback_id: string
  target_kind: AnalystFeedbackTarget
  target_id: string
  verdict: AnalystFeedbackVerdict | null
  note: string | null
  updated_at: string
  target_kind_label: string
  title: string
  subtitle: string
  action_label: string
  target_available: boolean
}

function formatPathSummary(path: RankedPath): string {
  return path.node_names.join(' -> ')
}

function buildRoute1Summary(
  entry: AnalystFeedbackEntry,
  path: RankedPath | null,
): FeedbackSummaryItem {
  return {
    feedback_id: entry.feedback_id,
    target_kind: entry.target_kind,
    target_id: entry.target_id,
    verdict: entry.verdict,
    note: entry.note,
    updated_at: entry.updated_at,
    target_kind_label: 'Route 1 Path',
    title: path?.target_entity_name ?? entry.target_id,
    subtitle: path ? formatPathSummary(path) : '该路径已不在当前推理结果中。',
    action_label: '定位路径',
    target_available: Boolean(path),
  }
}

function buildRoute2Summary(
  entry: AnalystFeedbackEntry,
  candidate: RootKGDCandidate | null,
): FeedbackSummaryItem {
  return {
    feedback_id: entry.feedback_id,
    target_kind: entry.target_kind,
    target_id: entry.target_id,
    verdict: entry.verdict,
    note: entry.note,
    updated_at: entry.updated_at,
    target_kind_label: 'Route 2 Candidate',
    title: candidate ? `#${candidate.rank} ${candidate.candidate_name}` : entry.target_id,
    subtitle: candidate
      ? `${candidate.candidate_type} / ${candidate.candidate_role}`
      : '该候选已不在当前推理结果中。',
    action_label: '定位候选',
    target_available: Boolean(candidate),
  }
}

function sortByUpdatedAtDesc(a: FeedbackSummaryItem, b: FeedbackSummaryItem) {
  const aTime = Date.parse(a.updated_at)
  const bTime = Date.parse(b.updated_at)

  if (Number.isNaN(aTime) || Number.isNaN(bTime)) {
    return b.updated_at.localeCompare(a.updated_at)
  }

  return bTime - aTime
}

export function buildFeedbackSummaryItems(
  entries: AnalystFeedbackEntry[],
  rankedPaths: RankedPath[],
  rankedCandidates: RootKGDCandidate[],
): FeedbackSummaryItem[] {
  const pathById = new Map(rankedPaths.map((path) => [path.path_id, path]))
  const candidateById = new Map(
    rankedCandidates.map((candidate) => [candidate.candidate_id, candidate]),
  )

  return entries
    .map((entry) =>
      entry.target_kind === 'route1-path'
        ? buildRoute1Summary(entry, pathById.get(entry.target_id) ?? null)
        : buildRoute2Summary(entry, candidateById.get(entry.target_id) ?? null),
    )
    .sort(sortByUpdatedAtDesc)
}
