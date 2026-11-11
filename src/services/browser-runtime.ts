import { parseRootLensRuntimeFile, parseUnifiedGraphsFile } from '@/contracts/runtime'
import type { UnifiedGraphsFile } from '@/types/graph'
import type { RootLensRuntimeFile } from '@/types/rootlens'

interface ImportedTextFile {
  file: File
  fullName: string
  baseName: string
  content: string
}

export interface LocalImportSummary {
  sourceMode: 'runtime' | 'graphs+evidence' | 'graphs-only'
  detectedFiles: string[]
  datasets: Array<{
    id: string
    label: string
    nodeCount: number
    edgeCount: number
  }>
  cases: Array<{
    caseId: string
    caseLabel: string
    dataset: string
  }>
  warnings: string[]
}

export interface LocalImportResult {
  graphs: UnifiedGraphsFile | null
  runtime: RootLensRuntimeFile | null
  summary: LocalImportSummary
}

const SUPPORTED_REPLAY_FILES = new Set(['rootlens-runtime.json', 'unified-graphs.json'])
const LEGACY_RAW_IMPORT_HINTS = [
  'nodes.jsonl',
  'edges.jsonl',
  'nodes.csv',
  'edges.csv',
  'evidence',
  'case',
]

function normalizeFileName(value: string): string {
  return value.split('/').pop()?.toLowerCase() ?? value.toLowerCase()
}

async function loadImportedTextFiles(files: File[]): Promise<ImportedTextFile[]> {
  return Promise.all(
    files.map(async (file) => ({
      file,
      fullName: file.webkitRelativePath || file.name,
      baseName: normalizeFileName(file.webkitRelativePath || file.name),
      content: await file.text(),
    })),
  )
}

function readJson(file: ImportedTextFile): unknown {
  return JSON.parse(file.content)
}

function buildSummary(
  sourceMode: LocalImportSummary['sourceMode'],
  importedFiles: ImportedTextFile[],
  graphs: UnifiedGraphsFile,
  runtime: RootLensRuntimeFile,
  warnings: string[],
): LocalImportSummary {
  return {
    sourceMode,
    detectedFiles: importedFiles.map((file) => file.fullName),
    datasets: graphs.datasets.map((dataset) => ({
      id: dataset.id,
      label: dataset.label,
      nodeCount: dataset.nodes.length,
      edgeCount: dataset.edges.length,
    })),
    cases: runtime.cases.map((caseItem) => ({
      caseId: caseItem.case_id,
      caseLabel: caseItem.case_label,
      dataset: caseItem.dataset,
    })),
    warnings,
  }
}

function isLegacyRawImportFile(fileName: string) {
  return LEGACY_RAW_IMPORT_HINTS.some((hint) => fileName.includes(hint))
}

function buildUnsupportedImportError(fileNames: string[]) {
  if (fileNames.some((fileName) => isLegacyRawImportFile(fileName))) {
    return '当前版本仅支持导入成品回放资产（rootlens-runtime.json + unified-graphs.json）或 session bundle；不再支持从 nodes/edges/evidence 在浏览器端临时组装 runtime。'
  }

  return '未识别到可导入的回放资产。当前仅支持 rootlens-runtime.json、unified-graphs.json，以及单独导入 session bundle / workspace export。'
}

export async function buildLocalImportResult(files: File[]): Promise<LocalImportResult> {
  if (!files.length) {
    throw new Error('请至少选择一个文件')
  }

  const importedFiles = await loadImportedTextFiles(files)
  const unsupportedFiles = importedFiles
    .map((file) => file.baseName)
    .filter((fileName) => !SUPPORTED_REPLAY_FILES.has(fileName))

  if (unsupportedFiles.length) {
    throw new Error(buildUnsupportedImportError(unsupportedFiles))
  }

  const runtimeFile = importedFiles.find((file) => file.baseName === 'rootlens-runtime.json') ?? null
  const graphsFile = importedFiles.find((file) => file.baseName === 'unified-graphs.json') ?? null

  if (!runtimeFile || !graphsFile) {
    throw new Error(
      '当前版本仅支持完整回放导入：请同时选择 rootlens-runtime.json 与 unified-graphs.json。',
    )
  }

  const runtime = parseRootLensRuntimeFile(readJson(runtimeFile))
  const graphs = parseUnifiedGraphsFile(readJson(graphsFile))

  return {
    graphs,
    runtime,
    summary: buildSummary('runtime', importedFiles, graphs, runtime, []),
  }
}
