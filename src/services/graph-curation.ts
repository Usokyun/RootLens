import type { PathGraph } from '@/api/contracts'
import type { UnifiedGraphDataset, UnifiedGraphEdge, UnifiedGraphNode } from '@/types/graph'

const GRAPH_CURATION_STORAGE_PREFIX = 'rootlens.graph-curation'
const GRAPH_CURATION_SCHEMA = 'graph-curation.v1'

export type GraphSubgraphMode = 'path' | 'neighborhood'
export type GraphCurationDecision = 'accept' | 'reject' | 'revise' | 'needs_completion'

export interface MockGraphEdgeDraft {
  edge_id: string
  target_key: string | null
  review_decision: GraphCurationDecision
  relation: string | null
  confidence: number | null
  note: string | null
  updated_at: string
}

export interface MockGraphNodeDraft {
  node_id: string
  display_name: string | null
  aliases: string[] | null
  description: string | null
  note: string | null
  updated_at: string
}

export interface MockGraphCurationCaseDraft {
  case_id: string
  edge_drafts: MockGraphEdgeDraft[]
  node_drafts: MockGraphNodeDraft[]
}

type JsonRecord = Record<string, unknown>

const SEEDED_CASE_DRAFTS: Record<string, MockGraphCurationCaseDraft> = {
  mvtec_fixture_clean_scratch: {
    case_id: 'mvtec_fixture_clean_scratch',
    edge_drafts: [
      {
        edge_id: 'mvtec-rca-reference:2:ScratchDefect:HAS_PLAUSIBLE_CAUSE:MechanicalContact',
        target_key: 'mvtec-rca-reference:2:ScratchDefect:HAS_PLAUSIBLE_CAUSE:MechanicalContact',
        review_decision: 'revise',
        relation: 'SUGGESTS_PLAUSIBLE_CAUSE',
        confidence: 0.58,
        note: '建议把候选解释语气从 HAS 调整为 SUGGESTS，以匹配论文中的 claim boundary。',
        updated_at: '2026-05-15T00:00:00.000Z',
      },
    ],
    node_drafts: [
      {
        node_id: 'MechanicalContact',
        display_name: 'Mechanical contact',
        aliases: ['surface scrape', 'contact wear'],
        description: 'Mock curation note: treat as a plausible handling-related mechanism instead of a verified factory root cause.',
        note: '适合作为论文里的“专家将候选解释修正为更保守表述”的示例。',
        updated_at: '2026-05-15T00:00:00.000Z',
      },
    ],
  },
  mvtec_noisy_0001: {
    case_id: 'mvtec_noisy_0001',
    edge_drafts: [
      {
        edge_id: 'mvtec-rca-reference:4:ScratchDefect:HAS_PLAUSIBLE_CAUSE:SurfaceWear',
        target_key: 'mvtec-rca-reference:4:ScratchDefect:HAS_PLAUSIBLE_CAUSE:SurfaceWear',
        review_decision: 'needs_completion',
        relation: 'HAS_PLAUSIBLE_CAUSE',
        confidence: 0.37,
        note: '噪声案例下保留该边，但建议补充更多来源证据后再进入高置信解释。',
        updated_at: '2026-05-15T00:00:00.000Z',
      },
    ],
    node_drafts: [
      {
        node_id: 'SurfaceWear',
        display_name: 'Surface wear',
        aliases: ['abrasive wear'],
        description: 'Seeded mock suggestion for noisy morphology case review.',
        note: '展示“需要补全证据”的节点说明草稿。',
        updated_at: '2026-05-15T00:00:00.000Z',
      },
    ],
  },
  tep_0001: {
    case_id: 'tep_0001',
    edge_drafts: [
      {
        edge_id: 'fault_anchor_edge_c28368046a61642d',
        target_key: 'fault_anchor_edge_c28368046a61642d',
        review_decision: 'reject',
        relation: null,
        confidence: 0.41,
        note: '保留该候选边用于审阅，但在当前证据窗口下将其降为 rejected mock overlay。',
        updated_at: '2026-05-15T00:00:00.000Z',
      },
    ],
    node_drafts: [
      {
        node_id: 'faultanchor:stream_1_a_feed_loss',
        display_name: 'Stream 1 A-feed loss disturbance',
        aliases: ['feed loss candidate'],
        description: 'Primary TEP RCA candidate shown with a local curation note for discussion screenshots.',
        note: '用于展示过程故障场景中的候选节点策展。',
        updated_at: '2026-05-15T00:00:00.000Z',
      },
    ],
  },
  wafer_0001: {
    case_id: 'wafer_0001',
    edge_drafts: [
      {
        edge_id: 'base-edges:12:NearfullDefect:HAS_PLAUSIBLE_CAUSE:GlueRemovalInsufficient',
        target_key: 'base-edges:12:NearfullDefect:HAS_PLAUSIBLE_CAUSE:GlueRemovalInsufficient',
        review_decision: 'accept',
        relation: 'HAS_PLAUSIBLE_CAUSE',
        confidence: 0.72,
        note: '作为 wafer traceability 场景的已接受 mock curation 示例。',
        updated_at: '2026-05-15T00:00:00.000Z',
      },
    ],
    node_drafts: [
      {
        node_id: 'GlueRemovalInsufficient',
        display_name: 'Glue removal insufficient',
        aliases: ['glue residual'],
        description: 'Accepted local draft label used for wafer explanation review screenshots.',
        note: '展示节点 alias / description 的轻量策展能力。',
        updated_at: '2026-05-15T00:00:00.000Z',
      },
    ],
  },
}

function deepClone<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T
}

function getStorageKey(caseId: string) {
  return `${GRAPH_CURATION_STORAGE_PREFIX}:${caseId}`
}

function canUseStorage() {
  return typeof window !== 'undefined' && typeof window.localStorage !== 'undefined'
}

function normalizeText(value: unknown): string | null {
  if (typeof value !== 'string') {
    return null
  }

  const normalized = value.trim()
  return normalized.length ? normalized : null
}

function normalizeStringArray(value: unknown): string[] | null {
  if (value == null) {
    return null
  }

  if (!Array.isArray(value)) {
    return null
  }

  const normalized = value
    .map((item) => normalizeText(item))
    .filter((item): item is string => Boolean(item))

  return [...new Set(normalized)]
}

function isDecision(value: unknown): value is GraphCurationDecision {
  return value === 'accept' || value === 'reject' || value === 'revise' || value === 'needs_completion'
}

function parseEdgeDraft(value: unknown): MockGraphEdgeDraft | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }

  const candidate = value as JsonRecord
  if (typeof candidate.edge_id !== 'string' || !isDecision(candidate.review_decision)) {
    return null
  }

  if (candidate.confidence != null && typeof candidate.confidence !== 'number') {
    return null
  }

  return {
    edge_id: candidate.edge_id,
    target_key: normalizeText(candidate.target_key),
    review_decision: candidate.review_decision,
    relation: normalizeText(candidate.relation),
    confidence: typeof candidate.confidence === 'number' ? candidate.confidence : null,
    note: normalizeText(candidate.note),
    updated_at: typeof candidate.updated_at === 'string' ? candidate.updated_at : new Date(0).toISOString(),
  }
}

function parseNodeDraft(value: unknown): MockGraphNodeDraft | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    return null
  }

  const candidate = value as JsonRecord
  if (typeof candidate.node_id !== 'string') {
    return null
  }

  return {
    node_id: candidate.node_id,
    display_name: normalizeText(candidate.display_name),
    aliases: normalizeStringArray(candidate.aliases),
    description: typeof candidate.description === 'string' ? candidate.description : null,
    note: normalizeText(candidate.note),
    updated_at: typeof candidate.updated_at === 'string' ? candidate.updated_at : new Date(0).toISOString(),
  }
}

function hasMeaningfulEdgeDraft(draft: MockGraphEdgeDraft): boolean {
  return Boolean(draft.relation || draft.confidence !== null || draft.note || draft.review_decision !== 'revise')
}

function hasMeaningfulNodeDraft(draft: MockGraphNodeDraft): boolean {
  return Boolean(
    draft.display_name !== null ||
      draft.aliases !== null ||
      draft.description !== null ||
      draft.note,
  )
}

function normalizeCaseDraft(caseId: string, candidate?: Partial<MockGraphCurationCaseDraft> | null): MockGraphCurationCaseDraft {
  return {
    case_id: caseId,
    edge_drafts: (candidate?.edge_drafts ?? [])
      .map((draft) => parseEdgeDraft(draft))
      .filter((draft): draft is MockGraphEdgeDraft => Boolean(draft))
      .filter((draft) => hasMeaningfulEdgeDraft(draft)),
    node_drafts: (candidate?.node_drafts ?? [])
      .map((draft) => parseNodeDraft(draft))
      .filter((draft): draft is MockGraphNodeDraft => Boolean(draft))
      .filter((draft) => hasMeaningfulNodeDraft(draft)),
  }
}

function mergeEdgeDrafts(...draftLists: MockGraphEdgeDraft[][]): MockGraphEdgeDraft[] {
  const merged = new Map<string, MockGraphEdgeDraft>()

  for (const list of draftLists) {
    for (const draft of list) {
      merged.set(draft.edge_id, deepClone(draft))
    }
  }

  return [...merged.values()].sort((left, right) => left.edge_id.localeCompare(right.edge_id))
}

function mergeNodeDrafts(...draftLists: MockGraphNodeDraft[][]): MockGraphNodeDraft[] {
  const merged = new Map<string, MockGraphNodeDraft>()

  for (const list of draftLists) {
    for (const draft of list) {
      merged.set(draft.node_id, deepClone(draft))
    }
  }

  return [...merged.values()].sort((left, right) => left.node_id.localeCompare(right.node_id))
}

function readStoredCaseDraft(caseId: string): MockGraphCurationCaseDraft | null {
  if (!canUseStorage()) {
    return null
  }

  try {
    const raw = window.localStorage.getItem(getStorageKey(caseId))
    if (!raw) {
      return null
    }

    const parsed = JSON.parse(raw) as JsonRecord
    if (parsed.schema_version !== GRAPH_CURATION_SCHEMA) {
      return null
    }

    return normalizeCaseDraft(caseId, parsed as Partial<MockGraphCurationCaseDraft>)
  } catch {
    return null
  }
}

function buildStoredPayload(caseDraft: MockGraphCurationCaseDraft) {
  return {
    schema_version: GRAPH_CURATION_SCHEMA,
    case_id: caseDraft.case_id,
    edge_drafts: caseDraft.edge_drafts,
    node_drafts: caseDraft.node_drafts,
  }
}

function getSeedCaseDraft(caseId: string): MockGraphCurationCaseDraft {
  return normalizeCaseDraft(caseId, SEEDED_CASE_DRAFTS[caseId] ?? null)
}

function normalizeComparableCaseDraft(caseDraft: MockGraphCurationCaseDraft) {
  return normalizeCaseDraft(caseDraft.case_id, caseDraft)
}

export function buildEmptyGraphCurationCaseDraft(caseId: string): MockGraphCurationCaseDraft {
  return {
    case_id: caseId,
    edge_drafts: [],
    node_drafts: [],
  }
}

export function loadGraphCurationSeedDraft(caseId: string): MockGraphCurationCaseDraft {
  return getSeedCaseDraft(caseId)
}

export function loadGraphCurationCaseDraft(caseId: string): MockGraphCurationCaseDraft {
  const seed = getSeedCaseDraft(caseId)
  const stored = readStoredCaseDraft(caseId)

  return {
    case_id: caseId,
    edge_drafts: mergeEdgeDrafts(seed.edge_drafts, stored?.edge_drafts ?? []),
    node_drafts: mergeNodeDrafts(seed.node_drafts, stored?.node_drafts ?? []),
  }
}

export function saveGraphCurationCaseDraft(caseDraft: MockGraphCurationCaseDraft) {
  if (!canUseStorage()) {
    return
  }

  const normalized = normalizeComparableCaseDraft(caseDraft)
  if (!normalized.edge_drafts.length && !normalized.node_drafts.length) {
    window.localStorage.removeItem(getStorageKey(normalized.case_id))
    return
  }

  window.localStorage.setItem(
    getStorageKey(normalized.case_id),
    JSON.stringify(buildStoredPayload(normalized)),
  )
}

export function resetGraphCurationCaseDraft(caseId: string) {
  if (!canUseStorage()) {
    return
  }

  window.localStorage.removeItem(getStorageKey(caseId))
}

export function areGraphCurationDraftsEqual(
  left: MockGraphCurationCaseDraft | null | undefined,
  right: MockGraphCurationCaseDraft | null | undefined,
) {
  const normalizedLeft = normalizeComparableCaseDraft(left ?? buildEmptyGraphCurationCaseDraft(right?.case_id ?? 'default'))
  const normalizedRight = normalizeComparableCaseDraft(right ?? buildEmptyGraphCurationCaseDraft(left?.case_id ?? 'default'))
  return JSON.stringify(normalizedLeft) === JSON.stringify(normalizedRight)
}

export function replaceGraphEdgeDraft(
  caseDraft: MockGraphCurationCaseDraft,
  nextDraft: MockGraphEdgeDraft | null,
): MockGraphCurationCaseDraft {
  const remaining = caseDraft.edge_drafts.filter((draft) => draft.edge_id !== nextDraft?.edge_id)
  if (nextDraft && hasMeaningfulEdgeDraft(nextDraft)) {
    remaining.push(nextDraft)
  }

  return normalizeCaseDraft(caseDraft.case_id, {
    ...caseDraft,
    edge_drafts: remaining,
  })
}

export function replaceGraphNodeDraft(
  caseDraft: MockGraphCurationCaseDraft,
  nextDraft: MockGraphNodeDraft | null,
): MockGraphCurationCaseDraft {
  const remaining = caseDraft.node_drafts.filter((draft) => draft.node_id !== nextDraft?.node_id)
  if (nextDraft && hasMeaningfulNodeDraft(nextDraft)) {
    remaining.push(nextDraft)
  }

  return normalizeCaseDraft(caseDraft.case_id, {
    ...caseDraft,
    node_drafts: remaining,
  })
}

function readEdgeReviewStatus(edge: UnifiedGraphEdge): string | null {
  const reviewStatus = edge.attributes.review_status
  return typeof reviewStatus === 'string' ? reviewStatus : null
}

function edgeReviewStatusFromDecision(decision: GraphCurationDecision) {
  if (decision === 'accept') {
    return 'reviewed'
  }

  if (decision === 'reject') {
    return 'rejected'
  }

  if (decision === 'needs_completion') {
    return 'needs_completion'
  }

  return 'revised'
}

export function applyGraphCurationToDataset(
  dataset: UnifiedGraphDataset,
  caseDraft: MockGraphCurationCaseDraft | null | undefined,
): UnifiedGraphDataset {
  if (!caseDraft) {
    return dataset
  }

  const edgeDraftById = new Map(caseDraft.edge_drafts.map((draft) => [draft.edge_id, draft]))
  const nodeDraftById = new Map(caseDraft.node_drafts.map((draft) => [draft.node_id, draft]))

  const nodes = dataset.nodes.map((node) => {
    const draft = nodeDraftById.get(node.id)
    if (!draft) {
      return node
    }

    return {
      ...node,
      name: draft.display_name ?? node.name,
      aliases: draft.aliases ?? node.aliases,
      description: draft.description ?? node.description,
      attributes: {
        ...node.attributes,
        curation_status: 'revised',
        curation_note: draft.note,
        curation_updated_at: draft.updated_at,
      },
    }
  })

  const edges = dataset.edges.map((edge) => {
    const draft = edgeDraftById.get(edge.id)
    if (!draft) {
      return edge
    }

    const reviewStatus = edgeReviewStatusFromDecision(draft.review_decision)
    return {
      ...edge,
      relation: draft.relation ?? edge.relation,
      label: draft.relation ?? edge.label,
      confidence: draft.confidence ?? edge.confidence,
      weight: draft.confidence ?? edge.weight,
      attributes: {
        ...edge.attributes,
        review_status: reviewStatus,
        original_review_status: readEdgeReviewStatus(edge),
        target_key:
          draft.target_key ??
          (typeof edge.attributes.target_key === 'string' ? edge.attributes.target_key : edge.id),
        curation_decision: draft.review_decision,
        curation_note: draft.note,
        curation_updated_at: draft.updated_at,
      },
    }
  })

  return {
    ...dataset,
    nodes,
    edges,
    metadata: {
      ...dataset.metadata,
      curation_case_id: caseDraft.case_id,
      curation_edge_draft_count: caseDraft.edge_drafts.length,
      curation_node_draft_count: caseDraft.node_drafts.length,
    },
  }
}

export function buildPathSubgraphDataset(pathGraph: PathGraph): UnifiedGraphDataset {
  const nodeSeed = new Map<
    string,
    {
      node_id: string
      label: string
      role: string
      pathIds: Set<string>
    }
  >()
  const edgeSeed = new Map<
    string,
    {
      edge_id: string
      source_node_id: string
      target_node_id: string
      relation: string
      confidence: number | null
      review_status: string | null
      evidence: string | null
      source: string | null
      target_key: string
      pathIds: Set<string>
    }
  >()

  for (const path of pathGraph.paths) {
    for (const node of path.nodes) {
      const current = nodeSeed.get(node.node_id)
      if (current) {
        current.pathIds.add(path.path_id)
        continue
      }

      nodeSeed.set(node.node_id, {
        node_id: node.node_id,
        label: node.label,
        role: node.role,
        pathIds: new Set([path.path_id]),
      })
    }

    for (const edge of path.edges) {
      const current = edgeSeed.get(edge.edge_id)
      if (current) {
        current.pathIds.add(path.path_id)
        continue
      }

      edgeSeed.set(edge.edge_id, {
        edge_id: edge.edge_id,
        source_node_id: edge.source_node_id,
        target_node_id: edge.target_node_id,
        relation: edge.relation,
        confidence: edge.confidence ?? null,
        review_status: edge.review_status ?? null,
        evidence: edge.evidence ?? null,
        source: edge.source ?? null,
        target_key: edge.target_key,
        pathIds: new Set([path.path_id]),
      })
    }
  }

  const inDegree = new Map<string, number>()
  const outDegree = new Map<string, number>()
  for (const edge of edgeSeed.values()) {
    outDegree.set(edge.source_node_id, (outDegree.get(edge.source_node_id) ?? 0) + 1)
    inDegree.set(edge.target_node_id, (inDegree.get(edge.target_node_id) ?? 0) + 1)
  }

  const nodes: UnifiedGraphNode[] = [...nodeSeed.values()].map((node) => ({
    id: node.node_id,
    name: node.label,
    category: node.role,
    kind: 'path-node',
    description: `${node.role} · ${node.pathIds.size} 条路径`,
    aliases: [],
    degree: (inDegree.get(node.node_id) ?? 0) + (outDegree.get(node.node_id) ?? 0),
    inDegree: inDegree.get(node.node_id) ?? 0,
    outDegree: outDegree.get(node.node_id) ?? 0,
    attributes: {
      role: node.role,
      path_ids: [...node.pathIds],
    },
    origin: {
      projectId: 'run-path-graph',
      projectLabel: 'Run Path Graph',
      filePath: 'path_graph',
      layer: 'path-subgraph',
      rowNumber: 0,
    },
  }))

  const edges: UnifiedGraphEdge[] = [...edgeSeed.values()].map((edge) => ({
    id: edge.edge_id,
    source: edge.source_node_id,
    target: edge.target_node_id,
    relation: edge.relation,
    category: 'path',
    label: edge.relation,
    confidence: edge.confidence,
    weight: edge.confidence,
    directed: true,
    attributes: {
      target_key: edge.target_key,
      review_status: edge.review_status,
      evidence: edge.evidence,
      source: edge.source,
      path_ids: [...edge.pathIds],
    },
    origin: {
      projectId: 'run-path-graph',
      projectLabel: 'Run Path Graph',
      filePath: 'path_graph',
      layer: 'path-subgraph',
      rowNumber: 0,
    },
  }))

  return {
    id: 'run-path-subgraph',
    label: 'Path Graph 子图',
    description: '当前 case 的 path_graph union subgraph',
    graphKind: 'path-subgraph',
    projectRoot: 'path_graph',
    sourceFiles: [],
    nodes,
    edges,
    metadata: {
      path_count: pathGraph.path_count,
      node_count: pathGraph.node_count,
      edge_count: pathGraph.edge_count,
      subgraph_mode: 'path',
    },
  }
}

export function buildNeighborhoodSubgraphDataset(
  dataset: UnifiedGraphDataset,
  centerNodeId: string,
): UnifiedGraphDataset | null {
  const centerNode = dataset.nodes.find((node) => node.id === centerNodeId)
  if (!centerNode) {
    return null
  }

  const incidentEdges = dataset.edges.filter(
    (edge) => edge.source === centerNodeId || edge.target === centerNodeId,
  )

  const neighborhoodNodeIds = new Set<string>([centerNodeId])
  incidentEdges.forEach((edge) => {
    neighborhoodNodeIds.add(edge.source)
    neighborhoodNodeIds.add(edge.target)
  })

  const nodes = dataset.nodes
    .filter((node) => neighborhoodNodeIds.has(node.id))
    .map((node) => ({
      ...node,
      attributes: {
        ...node.attributes,
        neighborhood_center: node.id === centerNodeId,
      },
    }))

  return {
    id: `${dataset.id}:neighborhood:${centerNodeId}`,
    label: `${centerNode.name} 邻域子图`,
    description: '总图节点的一阶邻域子图',
    graphKind: 'neighborhood-subgraph',
    projectRoot: dataset.projectRoot,
    sourceFiles: dataset.sourceFiles,
    nodes,
    edges: incidentEdges,
    metadata: {
      ...dataset.metadata,
      center_node_id: centerNodeId,
      center_node_name: centerNode.name,
      subgraph_mode: 'neighborhood',
      node_count: nodes.length,
      edge_count: incidentEdges.length,
    },
  }
}
