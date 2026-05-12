import {
  buildAnalysisWorkspaceScope,
  loadAnalysisWorkspace,
  parseAnalysisWorkspaceSnapshot,
  restoreAnalysisWorkspace,
  type AnalysisWorkspaceStorage,
} from '@/services/analysis-workspace'
import {
  loadAnalysisFocus,
  parseAnalysisFocusSnapshot,
  restoreAnalysisFocus,
  type AnalysisFocusState,
} from '@/services/analysis-focus'
import { parseRootLensRuntimeFile, parseUnifiedGraphsFile } from '@/contracts/runtime'
import {
  getImportedSessionSummary,
  getLocalSessionMeta,
  loadRootLensRuntime,
  loadUnifiedGraphs,
  saveImportedSession,
  type LocalSessionMeta,
} from '@/services/rootlens-data'
import type { LocalImportSummary } from '@/services/browser-runtime'
import type { UnifiedGraphsFile } from '@/types/graph'
import type { RootLensRuntimeFile } from '@/types/rootlens'

export interface SessionExportArtifacts {
  sessionMeta: LocalSessionMeta | null
  importSummary: LocalImportSummary | null
  graphs: UnifiedGraphsFile | null
  runtime: RootLensRuntimeFile | null
  analysisWorkspace: AnalysisWorkspaceStorage | null
  analysisFocus: AnalysisFocusState | null
}

export interface RootLensSessionExport extends SessionExportArtifacts {
  schema_version: 'rootlens-session-export.v1'
  exported_at: string
}

export interface AnalysisWorkspaceExportPayload {
  schema_version: 'rootlens-analysis-workspace-export.v1'
  exported_at: string
  session_meta?: LocalSessionMeta | null
  analysis_workspace?: AnalysisWorkspaceStorage | null
  analysis_focus?: AnalysisFocusState | null
}

export type SessionImportKind = 'session-bundle' | 'workspace-export'

export interface SessionImportResult {
  kind: SessionImportKind
  summary: string
  warnings: string[]
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

async function tryResolve<T>(loader: () => Promise<T>): Promise<T | null> {
  try {
    return await loader()
  } catch {
    return null
  }
}

function compactTimestamp(value: string | undefined): string {
  const date = value ? new Date(value) : new Date()

  if (Number.isNaN(date.getTime())) {
    return new Date().toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z')
  }

  return date.toISOString().replace(/[-:]/g, '').replace(/\.\d{3}Z$/, 'Z')
}

export function buildSessionExportBaseName(sessionMeta: LocalSessionMeta | null): string {
  const sessionLabel = sessionMeta?.source === 'import' ? 'import' : 'demo'
  return `rootlens-${sessionLabel}-${compactTimestamp(sessionMeta?.updatedAt)}`
}

export async function collectCurrentSessionArtifacts(): Promise<SessionExportArtifacts> {
  const sessionMeta = getLocalSessionMeta()
  const sessionScope = buildAnalysisWorkspaceScope(sessionMeta)

  const [graphs, runtime] = await Promise.all([
    tryResolve(loadUnifiedGraphs),
    tryResolve(loadRootLensRuntime),
  ])

  return {
    sessionMeta,
    importSummary: getImportedSessionSummary(),
    graphs,
    runtime,
    analysisWorkspace: loadAnalysisWorkspace(sessionScope),
    analysisFocus: loadAnalysisFocus(sessionScope),
  }
}

export async function buildCurrentSessionExport(): Promise<RootLensSessionExport> {
  const artifacts = await collectCurrentSessionArtifacts()

  return {
    schema_version: 'rootlens-session-export.v1',
    exported_at: new Date().toISOString(),
    ...artifacts,
  }
}

function normalizeExportSummary(
  graphs: UnifiedGraphsFile | null,
  runtime: RootLensRuntimeFile | null,
): string {
  return `${graphs?.datasets.length ?? 0} dataset(s), ${runtime?.cases.length ?? 0} case(s)`
}

function normalizeStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return []
  }

  return value.filter((item): item is string => typeof item === 'string')
}

function inferImportSourceMode(
  graphs: UnifiedGraphsFile | null,
  runtime: RootLensRuntimeFile | null,
): LocalImportSummary['sourceMode'] {
  if (graphs && !runtime) {
    return 'graphs-only'
  }

  if (graphs && runtime && runtime.generator === 'browser-import') {
    return 'graphs+evidence'
  }

  return 'runtime'
}

function buildImportSummaryFromArtifacts(
  graphs: UnifiedGraphsFile | null,
  runtime: RootLensRuntimeFile | null,
): LocalImportSummary | null {
  if (!graphs && !runtime) {
    return null
  }

  return {
    sourceMode: inferImportSourceMode(graphs, runtime),
    detectedFiles: [],
    datasets:
      graphs?.datasets.map((dataset) => ({
        id: dataset.id,
        label: dataset.label,
        nodeCount: dataset.nodes.length,
        edgeCount: dataset.edges.length,
      })) ?? [],
    cases:
      runtime?.cases.map((caseItem) => ({
        caseId: caseItem.case_id,
        caseLabel: caseItem.case_label,
        dataset: caseItem.dataset,
      })) ?? [],
    warnings: [],
  }
}

function parseImportSummary(
  value: unknown,
  graphs: UnifiedGraphsFile | null,
  runtime: RootLensRuntimeFile | null,
): LocalImportSummary | null {
  if (!isRecord(value)) {
    return buildImportSummaryFromArtifacts(graphs, runtime)
  }

  const datasets = Array.isArray(value.datasets) ? value.datasets : null
  const cases = Array.isArray(value.cases) ? value.cases : null

  if (
    (value.sourceMode !== 'runtime' &&
      value.sourceMode !== 'graphs+evidence' &&
      value.sourceMode !== 'graphs-only') ||
    !Array.isArray(value.detectedFiles) ||
    !datasets ||
    !cases ||
    !Array.isArray(value.warnings)
  ) {
    return buildImportSummaryFromArtifacts(graphs, runtime)
  }

  return {
    sourceMode: value.sourceMode,
    detectedFiles: normalizeStringArray(value.detectedFiles),
    datasets: datasets
      .filter(
        (item): item is Record<string, unknown> =>
          typeof item === 'object' && item !== null && !Array.isArray(item),
      )
      .map((item) => ({
        id: typeof item.id === 'string' ? item.id : '',
        label: typeof item.label === 'string' ? item.label : '',
        nodeCount: typeof item.nodeCount === 'number' ? item.nodeCount : 0,
        edgeCount: typeof item.edgeCount === 'number' ? item.edgeCount : 0,
      })),
    cases: cases
      .filter(
        (item): item is Record<string, unknown> =>
          typeof item === 'object' && item !== null && !Array.isArray(item),
      )
      .map((item) => ({
        caseId: typeof item.caseId === 'string' ? item.caseId : '',
        caseLabel: typeof item.caseLabel === 'string' ? item.caseLabel : '',
        dataset: typeof item.dataset === 'string' ? item.dataset : '',
      })),
    warnings: normalizeStringArray(value.warnings),
  }
}

function collectWorkspaceCaseIds(workspaceCases: ReturnType<typeof parseAnalysisWorkspaceSnapshot>): string[] {
  if (!workspaceCases?.length) {
    return []
  }

  return [...new Set(workspaceCases.map((item) => item.case_id).filter(Boolean))]
}

function buildWorkspaceRestoreWarnings(
  workspaceCases: ReturnType<typeof parseAnalysisWorkspaceSnapshot>,
  focus: ReturnType<typeof parseAnalysisFocusSnapshot>,
  runtime: RootLensRuntimeFile | null,
): string[] {
  const warnings: string[] = []
  const workspaceCaseIds = collectWorkspaceCaseIds(workspaceCases)
  const runtimeCaseIds = new Set(runtime?.cases.map((caseItem) => caseItem.case_id) ?? [])

  if (!runtime?.cases.length) {
    if (workspaceCaseIds.length || focus?.active_case_id) {
      warnings.push(
        '当前会话没有 runtime case；workspace 已恢复，但草稿、反馈和共享焦点要等 case 导入后才会在 Evidence / RCA 中生效。',
      )
    }

    return warnings
  }

  if (workspaceCaseIds.length) {
    const matchedCaseCount = workspaceCaseIds.filter((caseId) => runtimeCaseIds.has(caseId)).length
    const unmatchedCaseCount = workspaceCaseIds.length - matchedCaseCount

    if (matchedCaseCount === 0) {
      warnings.push(
        `导入的 workspace 与当前会话 case_id 不匹配（0/${workspaceCaseIds.length} 命中）；草稿和反馈已保存，但不会映射到当前案例。`,
      )
    } else if (unmatchedCaseCount > 0) {
      warnings.push(
        `导入的 workspace 仅匹配当前会话中的 ${matchedCaseCount}/${workspaceCaseIds.length} 个 case；其余 ${unmatchedCaseCount} 个 case_id 将保留但不会在当前会话显示。`,
      )
    }
  }

  if (focus?.active_case_id && !runtimeCaseIds.has(focus.active_case_id)) {
    warnings.push('导入的共享焦点指向的 case 不在当前会话中，跨页联动不会自动定位到目标案例。')
  }

  return warnings
}

async function restoreSessionBundle(candidate: Record<string, unknown>): Promise<SessionImportResult> {
  const graphs =
    candidate.graphs === null || candidate.graphs === undefined
      ? null
      : parseUnifiedGraphsFile(candidate.graphs)
  const runtime =
    candidate.runtime === null || candidate.runtime === undefined
      ? null
      : parseRootLensRuntimeFile(candidate.runtime)
  const workspaceCases =
    candidate.analysisWorkspace === undefined || candidate.analysisWorkspace === null
      ? null
      : parseAnalysisWorkspaceSnapshot(candidate.analysisWorkspace)
  const focusSnapshot =
    candidate.analysisFocus === undefined || candidate.analysisFocus === null
      ? null
      : parseAnalysisFocusSnapshot(candidate.analysisFocus)
  const importSummary = parseImportSummary(candidate.importSummary, graphs, runtime)
  const warnings = buildWorkspaceRestoreWarnings(workspaceCases, focusSnapshot, runtime)

  if (
    candidate.analysisWorkspace !== undefined &&
    candidate.analysisWorkspace !== null &&
    !workspaceCases
  ) {
    throw new Error('session bundle 中的 analysisWorkspace 格式无效。')
  }

  if (
    candidate.analysisFocus !== undefined &&
    candidate.analysisFocus !== null &&
    !focusSnapshot
  ) {
    throw new Error('session bundle 中的 analysisFocus 格式无效。')
  }

  saveImportedSession({
    graphs,
    runtime,
    summary: `恢复完整 bundle：${normalizeExportSummary(graphs, runtime)}`,
    importSummary: importSummary ?? undefined,
  })

  const restoredMeta = getLocalSessionMeta()
  const restoredScope = buildAnalysisWorkspaceScope(restoredMeta)

  restoreAnalysisWorkspace(restoredScope, candidate.analysisWorkspace ?? null)
  restoreAnalysisFocus(restoredScope, candidate.analysisFocus ?? null)

  return {
    kind: 'session-bundle',
    summary:
      `已恢复完整 bundle：${graphs?.datasets.length ?? 0} 个 dataset，` +
      `${runtime?.cases.length ?? 0} 个 case。`,
    warnings,
  }
}

async function restoreWorkspaceExport(
  candidate: Record<string, unknown>,
): Promise<SessionImportResult> {
  const currentMeta = getLocalSessionMeta()
  const currentScope = buildAnalysisWorkspaceScope(currentMeta)
  const workspaceCases =
    candidate.analysis_workspace === undefined || candidate.analysis_workspace === null
      ? null
      : parseAnalysisWorkspaceSnapshot(candidate.analysis_workspace)
  const focusSnapshot =
    candidate.analysis_focus === undefined || candidate.analysis_focus === null
      ? null
      : parseAnalysisFocusSnapshot(candidate.analysis_focus)

  if (
    candidate.analysis_workspace !== undefined &&
    candidate.analysis_workspace !== null &&
    !workspaceCases
  ) {
    throw new Error('workspace export 中的 analysis_workspace 格式无效。')
  }

  if (
    candidate.analysis_focus !== undefined &&
    candidate.analysis_focus !== null &&
    !focusSnapshot
  ) {
    throw new Error('workspace export 中的 analysis_focus 格式无效。')
  }

  const currentRuntime = await tryResolve(loadRootLensRuntime)
  const workspace = restoreAnalysisWorkspace(currentScope, candidate.analysis_workspace ?? null)
  const focus = restoreAnalysisFocus(currentScope, candidate.analysis_focus ?? null)
  const warnings = buildWorkspaceRestoreWarnings(workspaceCases, focusSnapshot, currentRuntime)

  return {
    kind: 'workspace-export',
    summary:
      `已恢复 analyst workspace：${workspace?.cases.length ?? 0} 个 case 草稿/反馈，` +
      `${focus ? '包含共享焦点。' : '未包含共享焦点。'}`,
    warnings,
  }
}

export async function restoreSessionImportPayload(value: unknown): Promise<SessionImportResult> {
  if (!isRecord(value) || typeof value.schema_version !== 'string') {
    throw new Error(
      '无法识别导入文件。当前仅支持 rootlens-session-export.v1 和 rootlens-analysis-workspace-export.v1。',
    )
  }

  if (value.schema_version === 'rootlens-session-export.v1') {
    return restoreSessionBundle(value)
  }

  if (value.schema_version === 'rootlens-analysis-workspace-export.v1') {
    return restoreWorkspaceExport(value)
  }

  throw new Error(
    `不支持的导入 schema: ${value.schema_version}。当前仅支持 session bundle 或 workspace export。`,
  )
}

export async function restoreSessionImportFile(file: File): Promise<SessionImportResult> {
  const content = await file.text()

  try {
    return await restoreSessionImportPayload(JSON.parse(content))
  } catch (error) {
    if (error instanceof SyntaxError) {
      throw new Error('导入文件不是合法 JSON。')
    }

    throw error
  }
}

export function downloadJsonFile(filename: string, payload: unknown) {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return
  }

  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: 'application/json;charset=utf-8',
  })
  const objectUrl = window.URL.createObjectURL(blob)
  const anchor = document.createElement('a')

  anchor.href = objectUrl
  anchor.download = filename
  anchor.style.display = 'none'

  document.body.append(anchor)
  anchor.click()
  anchor.remove()

  window.setTimeout(() => {
    window.URL.revokeObjectURL(objectUrl)
  }, 0)
}
