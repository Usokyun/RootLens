import { parseRootLensRuntimeFile, parseUnifiedGraphsFile } from '@/contracts/runtime'
import type { UnifiedGraphsFile } from '@/types/graph'
import type { RootLensRuntimeFile } from '@/types/rootlens'
import type { LocalImportSummary } from '@/services/browser-runtime'

const LOCAL_GRAPHS_KEY = 'rootlens.local.unified-graphs'
const LOCAL_RUNTIME_KEY = 'rootlens.local.runtime'
const LOCAL_META_KEY = 'rootlens.local.meta'
const LOCAL_IMPORT_SUMMARY_KEY = 'rootlens.local.import-summary'
const SESSION_EVENT = 'rootlens:session-change'

async function fetchJson(url: string): Promise<unknown> {
  const response = await fetch(url)

  if (!response.ok) {
    throw new Error(`${url} request failed: ${response.status}`)
  }

  return response.json()
}

let unifiedGraphsPromise: Promise<UnifiedGraphsFile> | null = null
let runtimePromise: Promise<RootLensRuntimeFile> | null = null
let bundledUnifiedGraphsPromise: Promise<UnifiedGraphsFile> | null = null
let bundledRuntimePromise: Promise<RootLensRuntimeFile> | null = null

function readLocalJson(key: string): unknown | null {
  if (typeof window === 'undefined') {
    return null
  }

  const raw = window.localStorage.getItem(key)
  if (!raw) {
    return null
  }

  return JSON.parse(raw)
}

function writeLocalJson(key: string, value: unknown) {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.setItem(key, JSON.stringify(value))
}

function removeLocalJson(key: string) {
  if (typeof window === 'undefined') {
    return
  }

  window.localStorage.removeItem(key)
}

function resetPromises() {
  unifiedGraphsPromise = null
  runtimePromise = null
  bundledUnifiedGraphsPromise = null
  bundledRuntimePromise = null
}

function notifySessionChange() {
  if (typeof window === 'undefined') {
    return
  }

  window.dispatchEvent(new CustomEvent(SESSION_EVENT))
}

export interface LocalSessionMeta {
  source: 'demo' | 'import'
  updatedAt: string
  summary?: string
}

export function getLocalSessionEventName() {
  return SESSION_EVENT
}

export function getLocalSessionMeta(): LocalSessionMeta | null {
  const payload = readLocalJson(LOCAL_META_KEY)
  if (!payload || typeof payload !== 'object') {
    return null
  }

  const candidate = payload as Record<string, unknown>
  if (
    (candidate.source !== 'demo' && candidate.source !== 'import') ||
    typeof candidate.updatedAt !== 'string'
  ) {
    return null
  }

  return {
    source: candidate.source,
    updatedAt: candidate.updatedAt,
    summary: typeof candidate.summary === 'string' ? candidate.summary : undefined,
  }
}

function buildSessionSummaryFromStorage(): LocalImportSummary | null {
  try {
    const localGraphs = readLocalJson(LOCAL_GRAPHS_KEY)
    const localRuntime = readLocalJson(LOCAL_RUNTIME_KEY)
    const graphs = localGraphs ? parseUnifiedGraphsFile(localGraphs) : null
    const runtime = localRuntime ? parseRootLensRuntimeFile(localRuntime) : null

    if (!graphs && !runtime) {
      return null
    }

    let sourceMode: LocalImportSummary['sourceMode'] = 'runtime'

    if (graphs && runtime) {
      sourceMode = runtime.generator === 'browser-import' ? 'graphs+evidence' : 'runtime'
    } else if (graphs) {
      sourceMode = 'graphs-only'
    }

    return {
      sourceMode,
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
  } catch {
    return null
  }
}

export function getImportedSessionSummary(): LocalImportSummary | null {
  const payload = readLocalJson(LOCAL_IMPORT_SUMMARY_KEY)
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) {
    return buildSessionSummaryFromStorage()
  }

  const candidate = payload as Record<string, unknown>

  if (
    (candidate.sourceMode !== 'runtime' &&
      candidate.sourceMode !== 'graphs+evidence' &&
      candidate.sourceMode !== 'graphs-only') ||
    !Array.isArray(candidate.detectedFiles) ||
    !Array.isArray(candidate.datasets) ||
    !Array.isArray(candidate.cases) ||
    !Array.isArray(candidate.warnings)
  ) {
    return buildSessionSummaryFromStorage()
  }

  return {
    sourceMode: candidate.sourceMode,
    detectedFiles: candidate.detectedFiles.filter(
      (item): item is string => typeof item === 'string',
    ),
    datasets: candidate.datasets
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
    cases: candidate.cases
      .filter(
        (item): item is Record<string, unknown> =>
          typeof item === 'object' && item !== null && !Array.isArray(item),
      )
      .map((item) => ({
        caseId: typeof item.caseId === 'string' ? item.caseId : '',
        caseLabel: typeof item.caseLabel === 'string' ? item.caseLabel : '',
        dataset: typeof item.dataset === 'string' ? item.dataset : '',
      })),
    warnings: candidate.warnings.filter((item): item is string => typeof item === 'string'),
  }
}

export function getStoredImportedGraphs(): UnifiedGraphsFile | null {
  try {
    const payload = readLocalJson(LOCAL_GRAPHS_KEY)
    return payload ? parseUnifiedGraphsFile(payload) : null
  } catch {
    return null
  }
}

export function getStoredImportedRuntime(): RootLensRuntimeFile | null {
  try {
    const payload = readLocalJson(LOCAL_RUNTIME_KEY)
    return payload ? parseRootLensRuntimeFile(payload) : null
  } catch {
    return null
  }
}

function isImportedSessionActive(): boolean {
  return getLocalSessionMeta()?.source === 'import'
}

export function saveImportedSession(input: {
  graphs: UnifiedGraphsFile | null
  runtime: RootLensRuntimeFile | null
  summary?: string
  importSummary?: LocalImportSummary
}) {
  if (input.graphs) {
    writeLocalJson(LOCAL_GRAPHS_KEY, input.graphs)
  } else {
    removeLocalJson(LOCAL_GRAPHS_KEY)
  }

  if (input.runtime) {
    writeLocalJson(LOCAL_RUNTIME_KEY, input.runtime)
  } else {
    removeLocalJson(LOCAL_RUNTIME_KEY)
  }

  writeLocalJson(LOCAL_META_KEY, {
    source: 'import',
    updatedAt: new Date().toISOString(),
    summary: input.summary,
  } satisfies LocalSessionMeta)

  if (input.importSummary) {
    writeLocalJson(LOCAL_IMPORT_SUMMARY_KEY, input.importSummary)
  } else {
    removeLocalJson(LOCAL_IMPORT_SUMMARY_KEY)
  }

  resetPromises()
  notifySessionChange()
}

export function clearImportedSession() {
  removeLocalJson(LOCAL_GRAPHS_KEY)
  removeLocalJson(LOCAL_RUNTIME_KEY)
  removeLocalJson(LOCAL_IMPORT_SUMMARY_KEY)
  writeLocalJson(LOCAL_META_KEY, {
    source: 'demo',
    updatedAt: new Date().toISOString(),
    summary: '使用内置示例数据',
  } satisfies LocalSessionMeta)
  resetPromises()
  notifySessionChange()
}

export async function loadUnifiedGraphs(): Promise<UnifiedGraphsFile> {
  if (!unifiedGraphsPromise) {
    const localPayload = readLocalJson(LOCAL_GRAPHS_KEY)
    unifiedGraphsPromise = localPayload
      ? Promise.resolve(parseUnifiedGraphsFile(localPayload))
      : isImportedSessionActive()
        ? Promise.reject(new Error('当前本地导入会话未包含 unified-graphs.json，图谱工作台不可用。'))
        : fetchJson('/generated/unified-graphs.json').then(parseUnifiedGraphsFile)
  }

  return unifiedGraphsPromise
}

export async function loadRootLensRuntime(): Promise<RootLensRuntimeFile> {
  if (!runtimePromise) {
    const localPayload = readLocalJson(LOCAL_RUNTIME_KEY)
    runtimePromise = localPayload
      ? Promise.resolve(parseRootLensRuntimeFile(localPayload))
      : isImportedSessionActive()
        ? Promise.reject(new Error('当前回放会话未包含 rootlens-runtime.json，Evidence 与 RCA 工作台不可用。'))
        : fetchJson('/generated/rootlens-runtime.json').then(parseRootLensRuntimeFile)
  }

  return runtimePromise
}

export async function loadBundledUnifiedGraphs(): Promise<UnifiedGraphsFile> {
  if (!bundledUnifiedGraphsPromise) {
    bundledUnifiedGraphsPromise = fetchJson('/generated/unified-graphs.json').then(parseUnifiedGraphsFile)
  }

  return bundledUnifiedGraphsPromise
}

export async function loadBundledRootLensRuntime(): Promise<RootLensRuntimeFile> {
  if (!bundledRuntimePromise) {
    bundledRuntimePromise = fetchJson('/generated/rootlens-runtime.json').then(parseRootLensRuntimeFile)
  }

  return bundledRuntimePromise
}
