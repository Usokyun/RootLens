import { parse as parseCsv } from 'csv-parse/browser/esm/sync'

import {
  parseRootLensRuntimeFile,
  parseUnifiedEvidenceContract,
  parseUnifiedGraphsFile,
} from '@/contracts/runtime'
import { buildLocalAnalysisResult } from '@/services/local-reasoning'
import {
  getLocalSessionMeta,
  getStoredImportedRuntime,
  loadUnifiedGraphs,
} from '@/services/rootlens-data'
import type {
  JsonValue,
  UnifiedGraphDataset,
  UnifiedGraphEdge,
  UnifiedGraphNode,
  UnifiedGraphSourceFile,
  UnifiedGraphsFile,
} from '@/types/graph'
import type {
  RootLensRuntimeCase,
  RootLensRuntimeFile,
  UnifiedEvidence,
} from '@/types/rootlens'

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

interface FileGroup {
  byBaseName: Map<string, ImportedTextFile>
  files: ImportedTextFile[]
}

function normalizeFileName(value: string): string {
  return value.split('/').pop()?.toLowerCase() ?? value.toLowerCase()
}

function parseNumber(value: unknown): number | null {
  if (value === '' || value === null || value === undefined) {
    return null
  }

  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

function splitAliases(value: unknown): string[] {
  if (!value) {
    return []
  }

  if (Array.isArray(value)) {
    return value.filter((item): item is string => typeof item === 'string')
  }

  return String(value)
    .split(/[|;,]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function buildSourceFileDescriptor(
  file: ImportedTextFile,
  role: string,
  layer: string,
  rows: Record<string, unknown>[],
): UnifiedGraphSourceFile {
  return {
    path: file.fullName,
    role,
    layer,
    rowCount: rows.length,
    fields: rows.length ? Object.keys(rows[0]) : [],
  }
}

function sanitizeJsonValue(value: unknown): JsonValue {
  if (
    value === null ||
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean'
  ) {
    return value
  }

  if (Array.isArray(value)) {
    return value.map((item) => sanitizeJsonValue(item))
  }

  if (value && typeof value === 'object') {
    return Object.fromEntries(
      Object.entries(value).map(([key, entry]) => [key, sanitizeJsonValue(entry)]),
    )
  }

  return String(value)
}

function enrichNodesWithDegree(
  nodes: Omit<UnifiedGraphNode, 'degree' | 'inDegree' | 'outDegree'>[],
  edges: UnifiedGraphEdge[],
): UnifiedGraphNode[] {
  const degreeMap = new Map(
    nodes.map((node) => [
      node.id,
      {
        inDegree: 0,
        outDegree: 0,
      },
    ]),
  )

  for (const edge of edges) {
    const sourceMetrics = degreeMap.get(edge.source)
    if (sourceMetrics) {
      sourceMetrics.outDegree += 1
    }

    const targetMetrics = degreeMap.get(edge.target)
    if (targetMetrics) {
      targetMetrics.inDegree += 1
    }
  }

  return nodes.map((node) => {
    const metrics = degreeMap.get(node.id) ?? {
      inDegree: 0,
      outDegree: 0,
    }

    return {
      ...node,
      degree: metrics.inDegree + metrics.outDegree,
      inDegree: metrics.inDegree,
      outDegree: metrics.outDegree,
      attributes: {
        ...node.attributes,
        degree: metrics.inDegree + metrics.outDegree,
        inDegree: metrics.inDegree,
        outDegree: metrics.outDegree,
      },
    }
  })
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

function buildFileGroup(files: ImportedTextFile[]): FileGroup {
  return {
    files,
    byBaseName: new Map(files.map((file) => [file.baseName, file])),
  }
}

function readJson(file: ImportedTextFile): unknown {
  return JSON.parse(file.content)
}

function readJsonl(file: ImportedTextFile): Record<string, unknown>[] {
  return file.content
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line) as Record<string, unknown>)
}

function readCsv(file: ImportedTextFile): Record<string, unknown>[] {
  return parseCsv(file.content, {
    columns: true,
    skip_empty_lines: true,
    bom: true,
  }) as Record<string, unknown>[]
}

function buildImportedTepDataset(group: FileGroup): UnifiedGraphDataset | null {
  const nodesFile = group.byBaseName.get('nodes.jsonl')
  const edgesFile = group.byBaseName.get('edges.jsonl')

  if (!nodesFile || !edgesFile) {
    return null
  }

  const nodeRows = readJsonl(nodesFile)
  const edgeRows = readJsonl(edgesFile)

  const edges: UnifiedGraphEdge[] = edgeRows.map((row, index) => ({
    id: String(row.edge_id ?? `local-tep-edge-${index + 1}`),
    source: String(row.head_id),
    target: String(row.tail_id),
    relation: String(row.relation),
    category: String(row.relation_family || row.edge_origin || row.relation),
    label: String(row.relation),
    confidence: parseNumber(row.confidence),
    weight: parseNumber(row.support_count ?? row.confidence),
    directed: true,
    attributes: {
      ...row,
      propagation_enabled: Boolean(row.propagation_enabled),
    } as Record<string, JsonValue>,
    origin: {
      projectId: 'local-tep',
      projectLabel: 'Imported TEP',
      filePath: edgesFile.fullName,
      layer: 'local-rca-edges',
      rowNumber: index + 1,
    },
  }))

  const nodes = enrichNodesWithDegree(
    nodeRows.map((row, index) => ({
      id: String(row.node_id),
      name: String(row.name),
      category: String(row.entity_type),
      kind: String(row.candidate_role || row.entity_type),
      description: String(row.summary || row.variable_role || ''),
      aliases: splitAliases(row.aliases),
      attributes: {
        ...row,
        aliases_list: splitAliases(row.aliases),
      } as Record<string, JsonValue>,
      origin: {
        projectId: 'local-tep',
        projectLabel: 'Imported TEP',
        filePath: nodesFile.fullName,
        layer: 'local-rca-nodes',
        rowNumber: index + 1,
      },
    })),
    edges,
  )

  return {
    id: 'local-tep',
    label: 'Imported TEP RCA Graph',
    description: 'Browser-generated unified graph from imported TEP nodes.jsonl and edges.jsonl.',
    graphKind: 'rca-graph',
    projectRoot: 'browser-import',
    sourceFiles: [
      buildSourceFileDescriptor(nodesFile, 'rca-node-table', 'local-rca-nodes', nodeRows),
      buildSourceFileDescriptor(edgesFile, 'rca-edge-table', 'local-rca-edges', edgeRows),
    ],
    nodes,
    edges,
    metadata: {
      importedFrom: 'browser',
      originalFiles: [nodesFile.fullName, edgesFile.fullName],
    },
  }
}

function buildImportedMvtecDataset(group: FileGroup): UnifiedGraphDataset | null {
  const nodesFile = group.byBaseName.get('nodes.csv')
  const edgesFile = group.byBaseName.get('edges.csv')

  if (!nodesFile || !edgesFile) {
    return null
  }

  const nodeRows = readCsv(nodesFile)
  const edgeRows = readCsv(edgesFile)
  const referenceFile = group.byBaseName.get('mvtec_rca_reference.csv')
  const referenceRows = referenceFile ? readCsv(referenceFile) : []
  const sourceRegistryFile = group.byBaseName.get('source_registry.csv')
  const sourceRegistryRows = sourceRegistryFile ? readCsv(sourceRegistryFile) : []

  const edgeLayers = [
    {
      rows: edgeRows,
      file: edgesFile,
      layer: 'base-edges',
    },
    ...(referenceFile
      ? [
          {
            rows: referenceRows,
            file: referenceFile,
            layer: 'mvtec-rca-reference',
          },
        ]
      : []),
  ]

  const edges: UnifiedGraphEdge[] = edgeLayers.flatMap(({ rows, file, layer }) =>
    rows.map((row, index) => ({
      id: `${layer}:${index + 1}:${String(row.head)}:${String(row.relation)}:${String(row.tail)}`,
      source: String(row.head),
      target: String(row.tail),
      relation: String(row.relation),
      category: String(row.scenario || row.relation),
      label: String(row.relation),
      confidence: parseNumber(row.confidence),
      weight: parseNumber(row.weight),
      directed: true,
      attributes: row as Record<string, JsonValue>,
      origin: {
        projectId: 'local-mvtec',
        projectLabel: 'Imported MVTec',
        filePath: file.fullName,
        layer,
        rowNumber: index + 1,
      },
    })),
  )

  const nodes = enrichNodesWithDegree(
    nodeRows.map((row, index) => ({
      id: String(row.id),
      name: String(row.name),
      category: String(row.label),
      kind: String(row.label),
      description: String(row.description || ''),
      aliases: splitAliases(row.aliases),
      attributes: {
        ...row,
        aliases_list: splitAliases(row.aliases),
      } as Record<string, JsonValue>,
      origin: {
        projectId: 'local-mvtec',
        projectLabel: 'Imported MVTec',
        filePath: nodesFile.fullName,
        layer: 'nodes',
        rowNumber: index + 1,
      },
    })),
    edges,
  )

  return {
    id: 'local-mvtec',
    label: 'Imported MVTec Runtime KG',
    description:
      'Browser-generated runtime graph from imported nodes.csv, edges.csv and optional mvtec_rca_reference.csv.',
    graphKind: 'runtime-kg',
    projectRoot: 'browser-import',
    sourceFiles: [
      buildSourceFileDescriptor(nodesFile, 'node-table', 'nodes', nodeRows),
      buildSourceFileDescriptor(edgesFile, 'edge-table', 'base-edges', edgeRows),
      ...(referenceFile
        ? [
            buildSourceFileDescriptor(
              referenceFile,
              'edge-table',
              'mvtec-rca-reference',
              referenceRows,
            ),
          ]
        : []),
      ...(sourceRegistryFile
        ? [
            buildSourceFileDescriptor(
              sourceRegistryFile,
              'source-registry',
              'source-registry',
              sourceRegistryRows,
            ),
          ]
        : []),
    ],
    nodes,
    edges,
    metadata: {
      importedFrom: 'browser',
      originalFiles: [
        nodesFile.fullName,
        edgesFile.fullName,
        ...(referenceFile ? [referenceFile.fullName] : []),
      ],
      sourceRegistryRows: sourceRegistryRows.map((row) => sanitizeJsonValue(row)),
    },
  }
}

function coerceEvidenceGraphDatasetId(
  evidence: UnifiedEvidence,
  datasets: UnifiedGraphDataset[],
): UnifiedEvidence {
  const existingDataset = datasets.find((dataset) => dataset.id === evidence.graph_dataset_id)
  if (existingDataset) {
    return evidence
  }

  const fallbackDataset =
    datasets.find((dataset) => {
      if (evidence.dataset === 'tep') {
        return dataset.id.includes('tep')
      }

      return dataset.id.includes('mvtec')
    }) ?? datasets[0]

  return {
    ...evidence,
    graph_dataset_id: fallbackDataset?.id ?? evidence.graph_dataset_id,
  }
}

function buildRuntimeCases(
  datasets: UnifiedGraphDataset[],
  evidenceList: UnifiedEvidence[],
): RootLensRuntimeCase[] {
  const datasetById = new Map(datasets.map((dataset) => [dataset.id, dataset]))

  return evidenceList
    .map((evidence) => coerceEvidenceGraphDatasetId(evidence, datasets))
    .map((evidence) => {
      const dataset = datasetById.get(evidence.graph_dataset_id)
      if (!dataset) {
        return null
      }

      return {
        case_id: evidence.case_id,
        case_label: evidence.case_label,
        dataset: evidence.dataset,
        source: evidence.source,
        summary: evidence.summary,
        graph_snapshot: {
          dataset_id: dataset.id,
          label: dataset.label,
          graph_kind: dataset.graphKind,
          description: dataset.description,
        },
        evidence,
        analysis: buildLocalAnalysisResult(dataset, evidence),
      }
    })
    .filter((item): item is RootLensRuntimeCase => Boolean(item))
}

function getEvidenceFiles(group: FileGroup): ImportedTextFile[] {
  return group.files.filter((file) => {
    if (!file.baseName.endsWith('.json')) {
      return false
    }

    return file.baseName.includes('evidence') || file.baseName.includes('case')
  })
}

function extractEvidenceContracts(group: FileGroup, datasets: UnifiedGraphDataset[]): UnifiedEvidence[] {
  const evidenceFiles = getEvidenceFiles(group)
  const evidences: UnifiedEvidence[] = []

  for (const file of evidenceFiles) {
    const parsed = readJson(file)
    const values = Array.isArray(parsed) ? parsed : [parsed]

    for (const value of values) {
      const evidence = parseUnifiedEvidenceContract(value)
      evidences.push(coerceEvidenceGraphDatasetId(evidence, datasets))
    }
  }

  return evidences
}

function mergeRuntimeCases(
  existingRuntime: RootLensRuntimeFile | null,
  nextCases: RootLensRuntimeCase[],
): RootLensRuntimeCase[] {
  if (!existingRuntime?.cases.length) {
    return nextCases
  }

  const nextCaseById = new Map(nextCases.map((caseItem) => [caseItem.case_id, caseItem]))
  const existingCaseIds = new Set(existingRuntime.cases.map((caseItem) => caseItem.case_id))

  const mergedCases = existingRuntime.cases.map(
    (caseItem) => nextCaseById.get(caseItem.case_id) ?? caseItem,
  )

  for (const caseItem of nextCases) {
    if (!existingCaseIds.has(caseItem.case_id)) {
      mergedCases.push(caseItem)
    }
  }

  return mergedCases
}

function buildSummary(
  sourceMode: LocalImportSummary['sourceMode'],
  importedFiles: ImportedTextFile[],
  graphs: UnifiedGraphsFile | null,
  runtime: RootLensRuntimeFile | null,
  warnings: string[],
): LocalImportSummary {
  return {
    sourceMode,
    detectedFiles: importedFiles.map((file) => file.fullName),
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
    warnings,
  }
}

export async function buildLocalImportResult(files: File[]): Promise<LocalImportResult> {
  if (!files.length) {
    throw new Error('请至少选择一个文件')
  }

  const importedFiles = await loadImportedTextFiles(files)
  const group = buildFileGroup(importedFiles)
  const warnings: string[] = []

  const runtimeFile = group.byBaseName.get('rootlens-runtime.json')
  const graphsFile = group.byBaseName.get('unified-graphs.json')
  const evidenceFiles = getEvidenceFiles(group)

  if (runtimeFile || graphsFile) {
    const runtime = runtimeFile ? parseRootLensRuntimeFile(readJson(runtimeFile)) : null
    const graphs = graphsFile ? parseUnifiedGraphsFile(readJson(graphsFile)) : null

    if (runtime && !graphs) {
      warnings.push('检测到 rootlens-runtime.json，但缺少 unified-graphs.json；图谱工作台将不可用。')
    }

    if (graphs && !runtime) {
      warnings.push('检测到 unified-graphs.json，但缺少 rootlens-runtime.json；Evidence 与 RCA 工作台将不可用。')
    }

    return {
      graphs,
      runtime,
      summary: buildSummary(
        graphs && !runtime ? 'graphs-only' : 'runtime',
        importedFiles,
        graphs,
        runtime,
        warnings,
      ),
    }
  }

  const datasets = [
    buildImportedTepDataset(group),
    buildImportedMvtecDataset(group),
  ].filter((dataset): dataset is UnifiedGraphDataset => Boolean(dataset))

  let graphs: UnifiedGraphsFile | null = null
  let reusedSessionGraphs = false

  if (datasets.length) {
    graphs = parseUnifiedGraphsFile({
      schemaVersion: 'graph.v1',
      generatedAt: new Date().toISOString(),
      generator: 'browser-import',
      datasets,
    })
  } else if (evidenceFiles.length) {
    try {
      graphs = await loadUnifiedGraphs()
      reusedSessionGraphs = true
      warnings.push('当前未选择图谱文件，已复用当前会话图谱生成 runtime case。')
    } catch {
      throw new Error(
        '当前只选择了 evidence/case 文件，但当前会话没有可复用的图谱。请先导入 nodes/edges 或 unified-graphs.json。',
      )
    }
  }

  if (!graphs) {
    throw new Error(
      '未识别到可导入的图谱文件。当前支持 TEP 的 nodes.jsonl + edges.jsonl，或 MVTec 的 nodes.csv + edges.csv。',
    )
  }

  const evidenceList = extractEvidenceContracts(group, graphs.datasets)
  if (!evidenceList.length) {
    warnings.push('未发现 evidence JSON，图谱已生成，但 Evidence 与 RCA 工作台不会显示本地案例。')
  }

  const nextCases = buildRuntimeCases(graphs.datasets, evidenceList)
  const existingRuntime =
    reusedSessionGraphs && getLocalSessionMeta()?.source === 'import'
      ? getStoredImportedRuntime()
      : null

  if (existingRuntime && nextCases.length) {
    const replacedCaseCount = nextCases.filter((caseItem) =>
      existingRuntime.cases.some((existingCase) => existingCase.case_id === caseItem.case_id),
    ).length
    const appendedCaseCount = nextCases.length - replacedCaseCount

    warnings.push(
      `已基于当前会话合并 case：覆盖 ${replacedCaseCount} 个，新增 ${appendedCaseCount} 个。`,
    )
  }

  const runtime =
    evidenceList.length > 0
      ? parseRootLensRuntimeFile({
          schema_version: 'rootlens-runtime.v1',
          generated_at: new Date().toISOString(),
          generator: 'browser-import',
          cases: mergeRuntimeCases(existingRuntime, nextCases),
        })
      : null

  return {
    graphs,
    runtime,
    summary: buildSummary(
      runtime ? 'graphs+evidence' : 'graphs-only',
      importedFiles,
      graphs,
      runtime,
      warnings,
    ),
  }
}
