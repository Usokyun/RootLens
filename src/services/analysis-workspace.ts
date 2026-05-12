import { parseRootLensRuntimeFile } from '@/contracts/runtime'
import type { LocalSessionMeta } from '@/services/rootlens-data'
import type { RootLensRuntimeCase } from '@/types/rootlens'

const ANALYSIS_WORKSPACE_PREFIX = 'rootlens.analysis-workspace'
const ANALYSIS_WORKSPACE_EVENT = 'rootlens:analysis-workspace-change'
const ANALYSIS_WORKSPACE_SCHEMA = 'analysis-workspace.v1'

export type AnalystFeedbackTarget = 'route1-path' | 'route2-candidate'
export type AnalystFeedbackVerdict = 'accepted' | 'rejected'

export interface AnalystFeedbackEntry {
  feedback_id: string
  target_kind: AnalystFeedbackTarget
  target_id: string
  verdict: AnalystFeedbackVerdict | null
  note: string | null
  updated_at: string
}

export interface AnalysisCaseWorkspace {
  case_id: string
  draft_case: RootLensRuntimeCase | null
  feedback_items: AnalystFeedbackEntry[]
}

export interface AnalysisWorkspaceStorage {
  schema_version: string
  session_scope: string
  updated_at: string
  cases: AnalysisCaseWorkspace[]
}

interface ParsedWorkspaceSnapshot {
  cases: AnalysisCaseWorkspace[]
}

function readLocalStorage(key: string): unknown | null {
  if (typeof window === 'undefined') {
    return null
  }

  const raw = window.localStorage.getItem(key)
  if (!raw) {
    return null
  }

  return JSON.parse(raw)
}

function writeLocalStorage(key: string, value: unknown) {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(key, JSON.stringify(value))
}

function removeLocalStorage(key: string) {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.removeItem(key)
}

function getStorageKey(sessionScope: string) {
  return `${ANALYSIS_WORKSPACE_PREFIX}:${sessionScope}`
}

function parseDraftCase(value: unknown): RootLensRuntimeCase | null {
  if (!value) {
    return null
  }

  return parseRootLensRuntimeFile({
    schema_version: 'rootlens-runtime.v1',
    generated_at: new Date(0).toISOString(),
    generator: 'analysis-workspace',
    cases: [value],
  }).cases[0] ?? null
}

function isFeedbackTarget(value: unknown): value is AnalystFeedbackTarget {
  return value === 'route1-path' || value === 'route2-candidate'
}

function isFeedbackVerdict(value: unknown): value is AnalystFeedbackVerdict {
  return value === 'accepted' || value === 'rejected'
}

function normalizeFeedbackNote(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null
  }

  const normalized = value.trim()
  return normalized.length ? normalized : null
}

function hasMeaningfulFeedbackEntry(entry: AnalystFeedbackEntry): boolean {
  return Boolean(entry.verdict || entry.note)
}

function parseFeedbackEntry(value: unknown): AnalystFeedbackEntry | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }

  const candidate = value as Record<string, unknown>
  if (
    typeof candidate.feedback_id !== 'string' ||
    !isFeedbackTarget(candidate.target_kind) ||
    typeof candidate.target_id !== 'string' ||
    typeof candidate.updated_at !== 'string'
  ) {
    return null
  }

  if (candidate.verdict !== null && candidate.verdict !== undefined && !isFeedbackVerdict(candidate.verdict)) {
    return null
  }

  return {
    feedback_id: candidate.feedback_id,
    target_kind: candidate.target_kind,
    target_id: candidate.target_id,
    verdict: candidate.verdict ?? null,
    note: normalizeFeedbackNote(candidate.note),
    updated_at: candidate.updated_at,
  }
}

function parseCaseWorkspace(value: unknown): AnalysisCaseWorkspace | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }

  const candidate = value as Record<string, unknown>
  if (typeof candidate.case_id !== 'string' || !Array.isArray(candidate.feedback_items)) {
    return null
  }

  return {
    case_id: candidate.case_id,
    draft_case: parseDraftCase(candidate.draft_case ?? null),
    feedback_items: candidate.feedback_items
      .map((item) => parseFeedbackEntry(item))
      .filter((item): item is AnalystFeedbackEntry => Boolean(item))
      .filter((item) => hasMeaningfulFeedbackEntry(item)),
  }
}

function parseWorkspaceSnapshot(value: unknown): ParsedWorkspaceSnapshot | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }

  const candidate = value as Record<string, unknown>
  if (!Array.isArray(candidate.cases)) {
    return null
  }

  return {
    cases: candidate.cases
      .map((item) => parseCaseWorkspace(item))
      .filter((item): item is AnalysisCaseWorkspace => Boolean(item)),
  }
}

export function parseAnalysisWorkspaceSnapshot(value: unknown): AnalysisCaseWorkspace[] | null {
  return parseWorkspaceSnapshot(value)?.cases ?? null
}

function buildEmptyWorkspace(sessionScope: string): AnalysisWorkspaceStorage {
  return {
    schema_version: ANALYSIS_WORKSPACE_SCHEMA,
    session_scope: sessionScope,
    updated_at: new Date().toISOString(),
    cases: [],
  }
}

function persistWorkspace(workspace: AnalysisWorkspaceStorage) {
  if (!workspace.cases.length) {
    removeLocalStorage(getStorageKey(workspace.session_scope))
  } else {
    writeLocalStorage(getStorageKey(workspace.session_scope), workspace)
  }

  if (typeof window !== 'undefined') {
    window.dispatchEvent(
      new CustomEvent(ANALYSIS_WORKSPACE_EVENT, {
        detail: {
          sessionScope: workspace.session_scope,
        },
      }),
    )
  }
}

function normalizeWorkspaceForScope(
  sessionScope: string,
  snapshot: ParsedWorkspaceSnapshot | null,
): AnalysisWorkspaceStorage {
  return {
    schema_version: ANALYSIS_WORKSPACE_SCHEMA,
    session_scope: sessionScope,
    updated_at: new Date().toISOString(),
    cases:
      snapshot?.cases
        .map((item) => ({
          ...item,
          feedback_items: item.feedback_items.filter((feedback) => hasMeaningfulFeedbackEntry(feedback)),
        }))
        .filter((item) => item.draft_case || item.feedback_items.length > 0) ?? [],
  }
}

function updateWorkspace(
  sessionScope: string,
  mutate: (workspace: AnalysisWorkspaceStorage) => AnalysisWorkspaceStorage,
) {
  const nextWorkspace = mutate(loadAnalysisWorkspace(sessionScope) ?? buildEmptyWorkspace(sessionScope))
  nextWorkspace.updated_at = new Date().toISOString()
  nextWorkspace.cases = nextWorkspace.cases.map((item) => ({
    ...item,
    feedback_items: item.feedback_items.filter((feedback) => hasMeaningfulFeedbackEntry(feedback)),
  }))
  nextWorkspace.cases = nextWorkspace.cases.filter(
    (item) => item.draft_case || item.feedback_items.length > 0,
  )
  persistWorkspace(nextWorkspace)
}

function upsertCaseWorkspace(
  workspace: AnalysisWorkspaceStorage,
  caseId: string,
): AnalysisCaseWorkspace {
  const existing =
    workspace.cases.find((item) => item.case_id === caseId) ??
    {
      case_id: caseId,
      draft_case: null,
      feedback_items: [],
    }

  if (!workspace.cases.some((item) => item.case_id === caseId)) {
    workspace.cases.push(existing)
  }

  return existing
}

export function getAnalysisWorkspaceEventName() {
  return ANALYSIS_WORKSPACE_EVENT
}

export function buildAnalysisWorkspaceScope(meta: LocalSessionMeta | null): string {
  return `${meta?.source ?? 'demo'}:${meta?.updatedAt ?? 'initial'}`
}

export function loadAnalysisWorkspace(sessionScope: string): AnalysisWorkspaceStorage | null {
  const payload = readLocalStorage(getStorageKey(sessionScope))
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return null
  }

  const candidate = payload as Record<string, unknown>
  if (
    candidate.schema_version !== ANALYSIS_WORKSPACE_SCHEMA ||
    candidate.session_scope !== sessionScope ||
    typeof candidate.updated_at !== 'string' ||
    !Array.isArray(candidate.cases)
  ) {
    return null
  }

  return {
    schema_version: ANALYSIS_WORKSPACE_SCHEMA,
    session_scope: sessionScope,
    updated_at: candidate.updated_at,
    cases: candidate.cases
      .map((item) => parseCaseWorkspace(item))
      .filter((item): item is AnalysisCaseWorkspace => Boolean(item)),
  }
}

export function restoreAnalysisWorkspace(
  sessionScope: string,
  value: unknown,
): AnalysisWorkspaceStorage | null {
  const snapshot = parseWorkspaceSnapshot(value)
  const workspace = normalizeWorkspaceForScope(sessionScope, snapshot)

  persistWorkspace(workspace)

  return workspace.cases.length ? workspace : null
}

export function overlayWorkspaceCases(
  baseCases: RootLensRuntimeCase[],
  workspace: AnalysisWorkspaceStorage | null,
): RootLensRuntimeCase[] {
  if (!workspace) {
    return baseCases
  }

  const draftByCaseId = new Map(
    workspace.cases
      .filter((item) => item.draft_case)
      .map((item) => [item.case_id, item.draft_case as RootLensRuntimeCase]),
  )

  return baseCases.map((caseItem) => draftByCaseId.get(caseItem.case_id) ?? caseItem)
}

export function hasDraftCase(
  workspace: AnalysisWorkspaceStorage | null,
  caseId: string,
): boolean {
  return Boolean(workspace?.cases.find((item) => item.case_id === caseId)?.draft_case)
}

export function getCaseFeedbackEntries(
  workspace: AnalysisWorkspaceStorage | null,
  caseId: string,
): AnalystFeedbackEntry[] {
  return workspace?.cases.find((item) => item.case_id === caseId)?.feedback_items ?? []
}

export function getFeedbackEntry(
  workspace: AnalysisWorkspaceStorage | null,
  caseId: string,
  targetKind: AnalystFeedbackTarget,
  targetId: string,
): AnalystFeedbackEntry | null {
  return (
    workspace?.cases
      .find((item) => item.case_id === caseId)
      ?.feedback_items.find(
        (item) => item.target_kind === targetKind && item.target_id === targetId,
      ) ?? null
  )
}

export function getFeedbackVerdict(
  workspace: AnalysisWorkspaceStorage | null,
  caseId: string,
  targetKind: AnalystFeedbackTarget,
  targetId: string,
): AnalystFeedbackVerdict | null {
  return getFeedbackEntry(workspace, caseId, targetKind, targetId)?.verdict ?? null
}

export function getFeedbackNote(
  workspace: AnalysisWorkspaceStorage | null,
  caseId: string,
  targetKind: AnalystFeedbackTarget,
  targetId: string,
): string {
  return getFeedbackEntry(workspace, caseId, targetKind, targetId)?.note ?? ''
}

export function saveDraftCase(sessionScope: string, draftCase: RootLensRuntimeCase) {
  updateWorkspace(sessionScope, (workspace) => {
    const caseWorkspace = upsertCaseWorkspace(workspace, draftCase.case_id)
    caseWorkspace.draft_case = draftCase
    return workspace
  })
}

export function clearDraftCase(sessionScope: string, caseId: string) {
  updateWorkspace(sessionScope, (workspace) => {
    const caseWorkspace = upsertCaseWorkspace(workspace, caseId)
    caseWorkspace.draft_case = null
    return workspace
  })
}

export function setFeedbackVerdict(
  sessionScope: string,
  caseId: string,
  targetKind: AnalystFeedbackTarget,
  targetId: string,
  verdict: AnalystFeedbackVerdict,
) {
  updateWorkspace(sessionScope, (workspace) => {
    const caseWorkspace = upsertCaseWorkspace(workspace, caseId)
    const feedbackId = `${targetKind}:${targetId}`
    const existing = caseWorkspace.feedback_items.find((item) => item.feedback_id === feedbackId)

    if (existing) {
      existing.verdict = verdict
      existing.updated_at = new Date().toISOString()
      return workspace
    }

    caseWorkspace.feedback_items.push({
      feedback_id: feedbackId,
      target_kind: targetKind,
      target_id: targetId,
      verdict,
      note: null,
      updated_at: new Date().toISOString(),
    })

    return workspace
  })
}

export function clearFeedbackVerdict(
  sessionScope: string,
  caseId: string,
  targetKind: AnalystFeedbackTarget,
  targetId: string,
) {
  updateWorkspace(sessionScope, (workspace) => {
    const caseWorkspace = upsertCaseWorkspace(workspace, caseId)
    caseWorkspace.feedback_items = caseWorkspace.feedback_items.flatMap((item) => {
      if (!(item.target_kind === targetKind && item.target_id === targetId)) {
        return [item]
      }

      if (item.note) {
        return [
          {
            ...item,
            verdict: null,
            updated_at: new Date().toISOString(),
          },
        ]
      }

      return []
    })
    return workspace
  })
}

export function setFeedbackNote(
  sessionScope: string,
  caseId: string,
  targetKind: AnalystFeedbackTarget,
  targetId: string,
  note: string,
) {
  updateWorkspace(sessionScope, (workspace) => {
    const caseWorkspace = upsertCaseWorkspace(workspace, caseId)
    const feedbackId = `${targetKind}:${targetId}`
    const existing = caseWorkspace.feedback_items.find((item) => item.feedback_id === feedbackId)
    const normalizedNote = normalizeFeedbackNote(note)

    if (existing) {
      existing.note = normalizedNote
      existing.updated_at = new Date().toISOString()
      return workspace
    }

    if (!normalizedNote) {
      return workspace
    }

    caseWorkspace.feedback_items.push({
      feedback_id: feedbackId,
      target_kind: targetKind,
      target_id: targetId,
      verdict: null,
      note: normalizedNote,
      updated_at: new Date().toISOString(),
    })
    return workspace
  })
}
