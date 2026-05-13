import fs from 'node:fs/promises'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { parse } from 'csv-parse/sync'

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)
const repoRoot = path.resolve(__dirname, '..')

const externalProjects = {
  tep: {
    id: 'tep-kg',
    label: 'TEP_KG',
    root: '/Users/bytedance/my_project/TEP_KG',
  },
  mvtec: {
    id: 'mvtec-project',
    label: 'MVTec / KGTraceVis',
    root: '/Users/bytedance/my_project/MVTec/KGTraceVis',
  },
}

function splitAliases(value) {
  if (!value) {
    return []
  }

  return String(value)
    .split(/[|;,]/)
    .map((item) => item.trim())
    .filter(Boolean)
}

function parseNumber(value) {
  if (value === '' || value === null || value === undefined) {
    return null
  }

  const parsed = Number(value)
  return Number.isFinite(parsed) ? parsed : null
}

async function readJson(filePath) {
  return JSON.parse(await fs.readFile(filePath, 'utf8'))
}

async function readJsonlRecords(filePath) {
  const raw = await fs.readFile(filePath, 'utf8')
  return raw
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => JSON.parse(line))
}

async function readCsvRecords(filePath) {
  const raw = await fs.readFile(filePath, 'utf8')
  return parse(raw, {
    columns: true,
    skip_empty_lines: true,
    bom: true,
    trim: false,
  })
}

function buildSourceFile(pathname, role, layer, rows) {
  return {
    path: pathname,
    role,
    layer,
    rowCount: rows.length,
    fields: rows.length ? Object.keys(rows[0]) : [],
  }
}

function enrichNodesWithDegree(nodes, edges) {
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
        inDegree: metrics.inDegree,
        outDegree: metrics.outDegree,
        degree: metrics.inDegree + metrics.outDegree,
      },
    }
  })
}

async function buildTepGraphDataset() {
  const projectRoot = externalProjects.tep.root
  const nodesPath = path.join(projectRoot, 'data/processed/rca/nodes.jsonl')
  const edgesPath = path.join(projectRoot, 'data/processed/rca/edges.jsonl')
  const graphReportPath = path.join(projectRoot, 'outputs/rca/graph_report.json')
  const ontologyPath = path.join(projectRoot, 'ontology/tep_ontology.json')
  const kgManifestPath = path.join(projectRoot, 'outputs/kg/manifest.json')

  const [nodeRows, edgeRows, graphReport, ontology, kgManifest] = await Promise.all([
    readJsonlRecords(nodesPath),
    readJsonlRecords(edgesPath),
    readJson(graphReportPath),
    readJson(ontologyPath),
    readJson(kgManifestPath),
  ])

  const edges = edgeRows.map((row, index) => ({
    id: String(row.edge_id),
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
    },
    origin: {
      projectId: externalProjects.tep.id,
      projectLabel: externalProjects.tep.label,
      filePath: edgesPath,
      layer: 'rca-edges',
      rowNumber: index + 2,
    },
  }))

  const nodes = enrichNodesWithDegree(
    nodeRows.map((row, index) => ({
      id: String(row.node_id),
      name: String(row.name),
      category: String(row.entity_type),
      kind: String(row.candidate_role || row.entity_type),
      description: [
        row.candidate_role ? `candidate_role=${row.candidate_role}` : '',
        row.variable_role ? `variable_role=${row.variable_role}` : '',
        row.root_cause_candidate ? 'root_cause_candidate=true' : '',
      ]
        .filter(Boolean)
        .join('; '),
      aliases: Array.isArray(row.aliases) ? row.aliases : splitAliases(row.aliases),
      degree: 0,
      inDegree: 0,
      outDegree: 0,
      attributes: {
        ...row,
        aliases_list: Array.isArray(row.aliases) ? row.aliases : splitAliases(row.aliases),
      },
      origin: {
        projectId: externalProjects.tep.id,
        projectLabel: externalProjects.tep.label,
        filePath: nodesPath,
        layer: 'rca-nodes',
        rowNumber: index + 2,
      },
    })),
    edges,
  )

  return {
    id: externalProjects.tep.id,
    label: 'TEP_KG RCA Graph',
    description:
      'TEP_KG 最终用于 Root-KGD 与前端可视化的 RCA Graph，来自 data/processed/rca/nodes.jsonl 与 edges.jsonl。',
    graphKind: 'rca-graph',
    projectRoot,
    sourceFiles: [
      buildSourceFile(nodesPath, 'rca-node-table', 'rca-nodes', nodeRows),
      buildSourceFile(edgesPath, 'rca-edge-table', 'rca-edges', edgeRows),
    ],
    nodes,
    edges,
    metadata: {
      snapshotId: String(kgManifest.snapshot_id),
      snapshotHash: String(kgManifest.snapshot_hash),
      fullKgCounts: {
        assets: Number(kgManifest.assets),
        entities: Number(kgManifest.entities),
        triples: Number(kgManifest.triples),
      },
      rcaGraphReport: graphReport,
      ontologySummary: {
        entityTypes: Array.isArray(ontology.entity_types) ? ontology.entity_types : [],
        relationConstraintCount: Object.keys(
          ontology.relation_constraints ?? {},
        ).length,
        canonicalization: ontology.canonicalization ?? {},
      },
      originalOutputs: {
        rcaNodes: 'data/processed/rca/nodes.jsonl',
        rcaEdges: 'data/processed/rca/edges.jsonl',
        rcaGraphReport: 'outputs/rca/graph_report.json',
      },
    },
  }
}

async function buildMvtecGraphDataset() {
  const projectRoot = externalProjects.mvtec.root
  const nodesPath = path.join(projectRoot, 'data/kg/nodes.csv')
  const edgesPath = path.join(projectRoot, 'data/kg/edges.csv')
  const referencePath = path.join(projectRoot, 'data/kg/mvtec_rca_reference.csv')
  const sourceRegistryPath = path.join(projectRoot, 'data/kg/source_registry.csv')
  const reservedPaths = [
    path.join(projectRoot, 'data/kg/mvtec_nodes.csv'),
    path.join(projectRoot, 'data/kg/mvtec_edges.csv'),
    path.join(projectRoot, 'data/kg/tep_nodes.csv'),
    path.join(projectRoot, 'data/kg/tep_edges.csv'),
    path.join(projectRoot, 'data/kg/wafer_nodes.csv'),
    path.join(projectRoot, 'data/kg/wafer_edges.csv'),
  ]

  const [nodeRows, baseEdgeRows, referenceRows, sourceRegistryRows, ...reservedRows] =
    await Promise.all([
      readCsvRecords(nodesPath),
      readCsvRecords(edgesPath),
      readCsvRecords(referencePath),
      readCsvRecords(sourceRegistryPath),
      ...reservedPaths.map((item) => readCsvRecords(item)),
    ])

  const layeredEdges = [
    {
      rows: baseEdgeRows,
      filePath: edgesPath,
      layer: 'base-edges',
    },
    {
      rows: referenceRows,
      filePath: referencePath,
      layer: 'mvtec-rca-reference',
    },
  ]

  const edges = layeredEdges.flatMap(({ rows, filePath, layer }) =>
    rows.map((row, index) => ({
      id: `${layer}:${index + 1}:${row.head}:${row.relation}:${row.tail}`,
      source: String(row.head),
      target: String(row.tail),
      relation: String(row.relation),
      category: String(row.scenario || row.relation),
      label: String(row.relation),
      confidence: parseNumber(row.confidence),
      weight: parseNumber(row.weight),
      directed: true,
      attributes: {
        ...row,
      },
      origin: {
        projectId: externalProjects.mvtec.id,
        projectLabel: externalProjects.mvtec.label,
        filePath,
        layer,
        rowNumber: index + 2,
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
      degree: 0,
      inDegree: 0,
      outDegree: 0,
      attributes: {
        ...row,
        aliases_list: splitAliases(row.aliases),
      },
      origin: {
        projectId: externalProjects.mvtec.id,
        projectLabel: externalProjects.mvtec.label,
        filePath: nodesPath,
        layer: 'nodes',
        rowNumber: index + 2,
      },
    })),
    edges,
  )

  return {
    id: externalProjects.mvtec.id,
    label: externalProjects.mvtec.label,
    description:
      'MVTec/KGTraceVis 当前默认运行时图谱，来自 nodes.csv、edges.csv 与 mvtec_rca_reference.csv 的合并层。',
    graphKind: 'runtime-kg',
    projectRoot,
    sourceFiles: [
      buildSourceFile(nodesPath, 'node-table', 'nodes', nodeRows),
      buildSourceFile(edgesPath, 'edge-table', 'base-edges', baseEdgeRows),
      buildSourceFile(
        referencePath,
        'edge-table',
        'mvtec-rca-reference',
        referenceRows,
      ),
      buildSourceFile(
        sourceRegistryPath,
        'source-registry',
        'source-registry',
        sourceRegistryRows,
      ),
      ...reservedPaths.map((filePath, index) =>
        buildSourceFile(
          filePath,
          'reserved-layer',
          path.basename(filePath, '.csv'),
          reservedRows[index],
        ),
      ),
    ],
    nodes,
    edges,
    metadata: {
      sourceRegistry: sourceRegistryRows,
      emptyReservedLayers: reservedPaths
        .map((filePath, index) => ({
          path: filePath,
          rowCount: reservedRows[index].length,
        }))
        .filter((item) => item.rowCount === 0),
      scenarioCounts: nodes.reduce((accumulator, node) => {
        const scenario = String(node.attributes.scenario || 'unknown')
        accumulator[scenario] = (accumulator[scenario] || 0) + 1
        return accumulator
      }, {}),
    },
  }
}

function findNode(dataset, nodeId) {
  const node = dataset.nodes.find((item) => item.id === nodeId)
  if (!node) {
    throw new Error(`node not found in ${dataset.id}: ${nodeId}`)
  }
  return node
}

function findEdge(dataset, source, relation, target) {
  const edge = dataset.edges.find(
    (item) =>
      item.source === source && item.relation === relation && item.target === target,
  )
  if (!edge) {
    throw new Error(`edge not found in ${dataset.id}: ${source} -${relation}-> ${target}`)
  }
  return edge
}

function buildEvidenceRef(origin, role) {
  return {
    ref_id: `${path.basename(origin.filePath)}:${origin.rowNumber}:${role}`,
    label: `${path.basename(origin.filePath)}:${origin.rowNumber}`,
    role,
    file_path: origin.filePath,
    line: origin.rowNumber,
  }
}

function buildCandidate(node, score) {
  return {
    entity_id: node.id,
    entity_name: node.name,
    entity_type: node.category,
    score,
  }
}

function buildPathEdgeDetail(edge) {
  return {
    edge_id: edge.id,
    source: edge.source,
    target: edge.target,
    relation: edge.relation,
    confidence: edge.confidence,
  }
}

function buildGraphSnapshot(dataset) {
  return {
    dataset_id: dataset.id,
    label: dataset.label,
    graph_kind: dataset.graphKind,
    description: dataset.description,
  }
}

function buildTepDemoCase(dataset) {
  const xmeas1 = findNode(dataset, 'variable:xmeas_1')
  const xmv3 = findNode(dataset, 'variable:manipulated_variable_3_a_feed')
  const xmeas4 = findNode(dataset, 'variable:xmeas_4')
  const stream1 = findNode(dataset, 'stream:stream_1_a_feed')
  const faultAnchor = findNode(dataset, 'faultanchor:stream_1_a_feed_loss')

  const stream1ObservedByXmeas1 = findEdge(
    dataset,
    'stream:stream_1_a_feed',
    'OBSERVED_BY',
    'variable:xmeas_1',
  )
  const xmv3ActsOnStream1 = findEdge(
    dataset,
    'variable:manipulated_variable_3_a_feed',
    'ACTS_ON',
    'stream:stream_1_a_feed',
  )
  const faultCausesStream1 = findEdge(
    dataset,
    'faultanchor:stream_1_a_feed_loss',
    'CAUSES',
    'stream:stream_1_a_feed',
  )
  const faultCausesXmv3 = findEdge(
    dataset,
    'faultanchor:stream_1_a_feed_loss',
    'CAUSES',
    'variable:manipulated_variable_3_a_feed',
  )

  return {
    case_id: 'tep_fault_06_stream_1_a_feed_loss',
    case_label: 'TEP Fault 06 / Stream 1 A-feed loss',
    dataset: 'tep',
    source: 'time_series',
    summary:
      '使用真实 RCA Graph 节点构造的时序案例，RBC 贡献集中在 XMEAS_1 与 XMV_3，A 进料流与 A 进料阀共同指向 Stream 1 A-feed loss。',
    graph_snapshot: buildGraphSnapshot(dataset),
    evidence: {
      case_id: 'tep_fault_06_stream_1_a_feed_loss',
      case_label: 'TEP Fault 06 / Stream 1 A-feed loss',
      dataset: 'tep',
      source: 'time_series',
      timestamp: '2026-05-11T01:12:00.000Z',
      summary:
        'RBC top channels show depleted A-feed flow and actuator-side response around stream 1.',
      graph_dataset_id: dataset.id,
      observations: [
        {
          obs_id: 'obs_tep_001',
          facet: 'variable',
          variable_name: 'xmeas_1',
          contribution: 0.82,
          direction: 'decrease',
          confidence: 0.95,
          linked_entity_hints: [xmeas1.id, stream1.id],
          raw_evidence_refs: [
            buildEvidenceRef(xmeas1.origin, 'graph_node'),
            buildEvidenceRef(stream1ObservedByXmeas1.origin, 'graph_edge'),
          ],
          time_window: {
            start: '2026-05-11T01:10:00.000Z',
            end: '2026-05-11T01:14:00.000Z',
          },
          attributes: {
            channel_rank: 1,
            variable_role: 'sensor',
            tep_channel: 'xmeas_1',
          },
        },
        {
          obs_id: 'obs_tep_002',
          facet: 'variable',
          variable_name: 'xmv_3',
          contribution: 0.61,
          direction: 'increase',
          confidence: 0.91,
          linked_entity_hints: [xmv3.id, stream1.id],
          raw_evidence_refs: [
            buildEvidenceRef(xmv3.origin, 'graph_node'),
            buildEvidenceRef(xmv3ActsOnStream1.origin, 'graph_edge'),
          ],
          time_window: {
            start: '2026-05-11T01:10:00.000Z',
            end: '2026-05-11T01:14:00.000Z',
          },
          attributes: {
            channel_rank: 2,
            variable_role: 'actuator',
            tep_channel: 'xmv_3',
          },
        },
      ],
    },
    analysis: {
      case_id: 'tep_fault_06_stream_1_a_feed_loss',
      timestamp: '2026-05-11T01:12:00.000Z',
      graph_dataset_id: dataset.id,
      route1: {
        linked_entities: [
          {
            link_id: 'link_tep_001',
            field: 'variable',
            mention: 'xmeas_1',
            selected_entity_id: xmeas1.id,
            selected_entity_name: xmeas1.name,
            score: 0.99,
            match_type: 'exact',
            ambiguous: false,
            candidates: [buildCandidate(xmeas1, 0.99), buildCandidate(stream1, 0.52)],
            obs_id: 'obs_tep_001',
            facet: 'variable',
          },
          {
            link_id: 'link_tep_002',
            field: 'variable',
            mention: 'xmv_3',
            selected_entity_id: xmv3.id,
            selected_entity_name: xmv3.name,
            score: 0.93,
            match_type: 'alias',
            ambiguous: false,
            candidates: [buildCandidate(xmv3, 0.93), buildCandidate(stream1, 0.41)],
            obs_id: 'obs_tep_002',
            facet: 'variable',
          },
        ],
        consistency_score: 0.93,
        inconsistent_fields: [],
        consistency_checks: [
          {
            source_field: 'variable',
            target_field: 'process_stream',
            source_entity_id: xmeas1.id,
            target_entity_id: stream1.id,
            relations: ['OBSERVED_BY'],
            passed: true,
            matched_relation: 'OBSERVED_BY',
          },
          {
            source_field: 'variable',
            target_field: 'process_stream',
            source_entity_id: xmv3.id,
            target_entity_id: stream1.id,
            relations: ['ACTS_ON'],
            passed: true,
            matched_relation: 'ACTS_ON',
          },
        ],
        correction_candidates: [],
        ranked_paths: [
          {
            path_id: 'path_tep_001',
            source_entity_id: xmeas1.id,
            target_entity_id: faultAnchor.id,
            target_entity_name: faultAnchor.name,
            nodes: [xmeas1.id, stream1.id, faultAnchor.id],
            node_names: [xmeas1.name, stream1.name, faultAnchor.name],
            relations: ['OBSERVED_BY', 'CAUSES'],
            score: 0.91,
            confidence: 0.89,
            evidence_match: 0.95,
            length: 2,
            source_edges: [
              buildPathEdgeDetail(stream1ObservedByXmeas1),
              buildPathEdgeDetail(faultCausesStream1),
            ],
            support_obs_ids: ['obs_tep_001'],
          },
          {
            path_id: 'path_tep_002',
            source_entity_id: xmv3.id,
            target_entity_id: faultAnchor.id,
            target_entity_name: faultAnchor.name,
            nodes: [xmv3.id, stream1.id, faultAnchor.id],
            node_names: [xmv3.name, stream1.name, faultAnchor.name],
            relations: ['ACTS_ON', 'CAUSES'],
            score: 0.87,
            confidence: 0.89,
            evidence_match: 0.88,
            length: 2,
            source_edges: [
              buildPathEdgeDetail(xmv3ActsOnStream1),
              buildPathEdgeDetail(faultCausesStream1),
            ],
            support_obs_ids: ['obs_tep_002'],
          },
          {
            path_id: 'path_tep_003',
            source_entity_id: xmv3.id,
            target_entity_id: faultAnchor.id,
            target_entity_name: faultAnchor.name,
            nodes: [xmv3.id, faultAnchor.id],
            node_names: [xmv3.name, faultAnchor.name],
            relations: ['CAUSES'],
            score: 0.84,
            confidence: 0.95,
            evidence_match: 0.78,
            length: 1,
            source_edges: [buildPathEdgeDetail(faultCausesXmv3)],
            support_obs_ids: ['obs_tep_002'],
          },
        ],
      },
      route2: {
        fault_signature: {
          contribution_vector: {
            [xmeas1.id]: 0.82,
            [xmv3.id]: 0.61,
            [xmeas4.id]: 0.33,
          },
          ordered_variables: [xmeas1.id, xmv3.id, xmeas4.id],
          top_channels: [
            {
              entity_id: xmeas1.id,
              name: xmeas1.name,
              contribution: 0.82,
              rank: 1,
            },
            {
              entity_id: xmv3.id,
              name: xmv3.name,
              contribution: 0.61,
              rank: 2,
            },
            {
              entity_id: xmeas4.id,
              name: xmeas4.name,
              contribution: 0.33,
              rank: 3,
            },
          ],
          graph_contributions: {
            [xmeas1.id]: 0.82,
            [xmv3.id]: 0.61,
            [stream1.id]: 0.74,
            [faultAnchor.id]: 0.91,
          },
        },
        ranked_candidates: [
          {
            scenario_id: 'tep-fault-06',
            fault_number: 6,
            simulation_run: 1,
            rank: 1,
            candidate_id: faultAnchor.id,
            candidate_name: faultAnchor.name,
            candidate_type: faultAnchor.category,
            candidate_role: faultAnchor.kind,
            priority_level: 1,
            seed_variable_id: xmeas1.id,
            seed_score: 0.82,
            root_score: 0.91,
            ranking_score: 0.94,
            structural_ranking_score: 0.88,
            ranking_adjustment: 0.06,
            covered_contribution_mass: 0.93,
            active_variable_count: 3,
            pattern_entropy: 0.18,
            discriminator_alignment: 0.88,
            anchor_contribution_alignment: 0.9,
            anchor_dynamic_alignment: 0.76,
            anchor_unique_contribution_alignment: 0.83,
            anchor_memory_bonus: 0.04,
            anchor_memory_scenario_count: 4,
            top_affected_variables: [
              {
                entity_id: xmeas1.id,
                name: xmeas1.name,
                propagated_score: 0.78,
                rbc_contribution: 0.82,
              },
              {
                entity_id: xmv3.id,
                name: xmv3.name,
                propagated_score: 0.63,
                rbc_contribution: 0.61,
              },
              {
                entity_id: xmeas4.id,
                name: xmeas4.name,
                propagated_score: 0.37,
                rbc_contribution: 0.33,
              },
            ],
            top_support_paths: [
              [faultAnchor.name, stream1.name, xmeas1.name],
              [faultAnchor.name, xmv3.name],
            ],
            support_evidence_ids: ['obs_tep_001', 'obs_tep_002'],
          },
          {
            scenario_id: 'tep-fault-06',
            fault_number: 6,
            simulation_run: 1,
            rank: 2,
            candidate_id: xmv3.id,
            candidate_name: xmv3.name,
            candidate_type: xmv3.category,
            candidate_role: xmv3.kind,
            priority_level: 1,
            seed_variable_id: xmv3.id,
            seed_score: 0.61,
            root_score: 0.83,
            ranking_score: 0.81,
            structural_ranking_score: 0.79,
            ranking_adjustment: 0.02,
            covered_contribution_mass: 0.71,
            active_variable_count: 2,
            pattern_entropy: 0.22,
            discriminator_alignment: 0.64,
            anchor_contribution_alignment: 0.59,
            anchor_dynamic_alignment: 0.52,
            anchor_unique_contribution_alignment: 0.57,
            anchor_memory_bonus: 0,
            anchor_memory_scenario_count: 0,
            top_affected_variables: [
              {
                entity_id: xmv3.id,
                name: xmv3.name,
                propagated_score: 0.61,
                rbc_contribution: 0.61,
              },
              {
                entity_id: xmeas1.id,
                name: xmeas1.name,
                propagated_score: 0.44,
                rbc_contribution: 0.82,
              },
            ],
            top_support_paths: [[xmv3.name, stream1.name, xmeas1.name]],
            support_evidence_ids: ['obs_tep_002'],
          },
          {
            scenario_id: 'tep-fault-06',
            fault_number: 6,
            simulation_run: 1,
            rank: 3,
            candidate_id: stream1.id,
            candidate_name: stream1.name,
            candidate_type: stream1.category,
            candidate_role: stream1.kind,
            priority_level: 2,
            seed_variable_id: xmeas1.id,
            seed_score: 0.82,
            root_score: 0.78,
            ranking_score: 0.74,
            structural_ranking_score: 0.73,
            ranking_adjustment: 0.01,
            covered_contribution_mass: 0.69,
            active_variable_count: 2,
            pattern_entropy: 0.25,
            discriminator_alignment: 0.51,
            anchor_contribution_alignment: 0.48,
            anchor_dynamic_alignment: 0.44,
            anchor_unique_contribution_alignment: 0.46,
            anchor_memory_bonus: 0,
            anchor_memory_scenario_count: 0,
            top_affected_variables: [
              {
                entity_id: xmeas1.id,
                name: xmeas1.name,
                propagated_score: 0.58,
                rbc_contribution: 0.82,
              },
              {
                entity_id: xmv3.id,
                name: xmv3.name,
                propagated_score: 0.42,
                rbc_contribution: 0.61,
              },
            ],
            top_support_paths: [[stream1.name, xmeas1.name]],
            support_evidence_ids: ['obs_tep_001'],
          },
        ],
      },
      cross_route_signals: [
        {
          candidate_id: faultAnchor.id,
          candidate_name: faultAnchor.name,
          route1_path_ids: ['path_tep_001', 'path_tep_002', 'path_tep_003'],
          route2_rank: 1,
          shared_obs_ids: ['obs_tep_001', 'obs_tep_002'],
        },
      ],
      notes: [
        '该案例为基于 RCA Graph 的前端 demo，字段命名与 Phase 1 contract 保持一致。',
        '路线 2 保留了 TEP 场景的 FaultAnchor 表达，但当前页面只展示结果，不在前端重算传播。',
      ],
    },
  }
}

function buildMvtecDemoCase(dataset) {
  const objectNode = findNode(dataset, 'MetalNutObject')
  const defectNode = findNode(dataset, 'ScratchDefect')
  const morphologyNode = findNode(dataset, 'LinearMorphology')
  const locationNode = findNode(dataset, 'SurfaceLocation')
  const rootCauseNode = findNode(dataset, 'MechanicalContact')
  const categoryNode = findNode(dataset, 'HandlingDamage')

  const objectHasAnomaly = findEdge(dataset, 'MetalNutObject', 'HAS_ANOMALY', 'ScratchDefect')
  const defectHasMorphology = findEdge(
    dataset,
    'ScratchDefect',
    'HAS_MORPHOLOGY',
    'LinearMorphology',
  )
  const defectOccursOn = findEdge(dataset, 'ScratchDefect', 'OCCURS_ON', 'SurfaceLocation')
  const defectHasCause = findEdge(
    dataset,
    'ScratchDefect',
    'HAS_PLAUSIBLE_CAUSE',
    'MechanicalContact',
  )
  const mechanicalPartOfHandling = findEdge(
    dataset,
    'MechanicalContact',
    'PART_OF',
    'HandlingDamage',
  )

  return {
    case_id: 'mvtec_metal_nut_scratch',
    case_label: 'MVTec / Metal Nut scratch',
    dataset: 'mvtec',
    source: 'image',
    summary:
      '视觉缺陷案例复用 KGTraceVis 的多源线索组织路线，缺陷类型、位置和 morphology 都绑定到真实图节点。',
    graph_snapshot: buildGraphSnapshot(dataset),
    evidence: {
      case_id: 'mvtec_metal_nut_scratch',
      case_label: 'MVTec / Metal Nut scratch',
      dataset: 'mvtec',
      source: 'image',
      timestamp: '2026-05-11T02:08:00.000Z',
      summary:
        'A metal nut image contains a linear surface scratch with strong localization confidence.',
      graph_dataset_id: dataset.id,
      observations: [
        {
          obs_id: 'obs_mvtec_001',
          facet: 'image_defect',
          object: 'metal nut',
          anomaly_type: 'scratch',
          location: 'surface',
          morphology: {
            canonical: 'linear',
            area_ratio: 0.014,
            eccentricity: 0.81,
            component_count: 1,
          },
          severity: 0.84,
          confidence: 0.93,
          linked_entity_hints: [
            objectNode.id,
            defectNode.id,
            locationNode.id,
            morphologyNode.id,
          ],
          raw_evidence_refs: [
            buildEvidenceRef(objectNode.origin, 'graph_node'),
            buildEvidenceRef(defectHasMorphology.origin, 'graph_edge'),
            buildEvidenceRef(defectOccursOn.origin, 'graph_edge'),
          ],
          image_region: {
            x: 184,
            y: 76,
            w: 44,
            h: 18,
          },
          attributes: {
            mask_source: 'caption_mask_stats',
            dataset_object: 'metal_nut',
          },
        },
      ],
    },
    analysis: {
      case_id: 'mvtec_metal_nut_scratch',
      timestamp: '2026-05-11T02:08:00.000Z',
      graph_dataset_id: dataset.id,
      route1: {
        linked_entities: [
          {
            link_id: 'link_mvtec_001',
            field: 'object',
            mention: 'metal nut',
            selected_entity_id: objectNode.id,
            selected_entity_name: objectNode.name,
            score: 0.96,
            match_type: 'alias',
            ambiguous: false,
            candidates: [buildCandidate(objectNode, 0.96)],
            obs_id: 'obs_mvtec_001',
            facet: 'image_defect',
          },
          {
            link_id: 'link_mvtec_002',
            field: 'anomaly_type',
            mention: 'scratch',
            selected_entity_id: defectNode.id,
            selected_entity_name: defectNode.name,
            score: 0.99,
            match_type: 'exact',
            ambiguous: false,
            candidates: [buildCandidate(defectNode, 0.99)],
            obs_id: 'obs_mvtec_001',
            facet: 'image_defect',
          },
          {
            link_id: 'link_mvtec_003',
            field: 'location',
            mention: 'surface',
            selected_entity_id: locationNode.id,
            selected_entity_name: locationNode.name,
            score: 0.9,
            match_type: 'alias',
            ambiguous: false,
            candidates: [buildCandidate(locationNode, 0.9)],
            obs_id: 'obs_mvtec_001',
            facet: 'image_defect',
          },
          {
            link_id: 'link_mvtec_004',
            field: 'morphology',
            mention: 'linear',
            selected_entity_id: morphologyNode.id,
            selected_entity_name: morphologyNode.name,
            score: 0.95,
            match_type: 'alias',
            ambiguous: false,
            candidates: [buildCandidate(morphologyNode, 0.95)],
            obs_id: 'obs_mvtec_001',
            facet: 'image_defect',
          },
        ],
        consistency_score: 0.94,
        inconsistent_fields: [],
        consistency_checks: [
          {
            source_field: 'object',
            target_field: 'anomaly_type',
            source_entity_id: objectNode.id,
            target_entity_id: defectNode.id,
            relations: ['HAS_ANOMALY'],
            passed: true,
            matched_relation: 'HAS_ANOMALY',
          },
          {
            source_field: 'anomaly_type',
            target_field: 'morphology',
            source_entity_id: defectNode.id,
            target_entity_id: morphologyNode.id,
            relations: ['HAS_MORPHOLOGY'],
            passed: true,
            matched_relation: 'HAS_MORPHOLOGY',
          },
          {
            source_field: 'anomaly_type',
            target_field: 'location',
            source_entity_id: defectNode.id,
            target_entity_id: locationNode.id,
            relations: ['OCCURS_ON'],
            passed: true,
            matched_relation: 'OCCURS_ON',
          },
        ],
        correction_candidates: [],
        ranked_paths: [
          {
            path_id: 'path_mvtec_001',
            source_entity_id: defectNode.id,
            target_entity_id: rootCauseNode.id,
            target_entity_name: rootCauseNode.name,
            nodes: [defectNode.id, rootCauseNode.id],
            node_names: [defectNode.name, rootCauseNode.name],
            relations: ['HAS_PLAUSIBLE_CAUSE'],
            score: 0.86,
            confidence: 0.75,
            evidence_match: 0.93,
            length: 1,
            source_edges: [buildPathEdgeDetail(defectHasCause)],
            support_obs_ids: ['obs_mvtec_001'],
          },
          {
            path_id: 'path_mvtec_002',
            source_entity_id: defectNode.id,
            target_entity_id: categoryNode.id,
            target_entity_name: categoryNode.name,
            nodes: [defectNode.id, rootCauseNode.id, categoryNode.id],
            node_names: [defectNode.name, rootCauseNode.name, categoryNode.name],
            relations: ['HAS_PLAUSIBLE_CAUSE', 'PART_OF'],
            score: 0.81,
            confidence: 0.72,
            evidence_match: 0.88,
            length: 2,
            source_edges: [
              buildPathEdgeDetail(defectHasCause),
              buildPathEdgeDetail(mechanicalPartOfHandling),
            ],
            support_obs_ids: ['obs_mvtec_001'],
          },
        ],
      },
      route2: null,
      cross_route_signals: [],
      notes: [
        '图像场景当前只启用路线 1，路线 2 维持为空。',
        '路径排序直接绑定到 mvtec_rca_reference.csv 中的可解释 cause 链。',
      ],
    },
  }
}

function buildWaferDemoCase(dataset) {
  const objectNode = findNode(dataset, 'WaferObject')
  const defectNode = findNode(dataset, 'NearfullDefect')
  const morphologyNode = findNode(dataset, 'DenseParticles')
  const locationNode = findNode(dataset, 'WaferSurface')
  const eventNode = findNode(dataset, 'ExampleAlarm')
  const rootCauseNode = findNode(dataset, 'GlueRemovalInsufficient')

  const objectHasAnomaly = findEdge(dataset, 'WaferObject', 'HAS_ANOMALY', 'NearfullDefect')
  const defectHasMorphology = findEdge(
    dataset,
    'NearfullDefect',
    'HAS_MORPHOLOGY',
    'DenseParticles',
  )
  const defectOccursOn = findEdge(dataset, 'NearfullDefect', 'OCCURS_ON', 'WaferSurface')
  const defectEvent = findEdge(
    dataset,
    'NearfullDefect',
    'ASSOCIATED_WITH_EVENT',
    'ExampleAlarm',
  )
  const defectCause = findEdge(
    dataset,
    'NearfullDefect',
    'HAS_PLAUSIBLE_CAUSE',
    'GlueRemovalInsufficient',
  )

  return {
    case_id: 'wafer_nearfull_dense_particles',
    case_label: 'Wafer / Nearfull dense particles',
    dataset: 'wafer',
    source: 'multimodal',
    summary:
      'Wafer 案例展示 image + log 双模态 evidence 合流后的路线 1 解释链，当前仍不启用路线 2。',
    graph_snapshot: buildGraphSnapshot(dataset),
    evidence: {
      case_id: 'wafer_nearfull_dense_particles',
      case_label: 'Wafer / Nearfull dense particles',
      dataset: 'wafer',
      source: 'multimodal',
      timestamp: '2026-05-11T03:24:00.000Z',
      summary:
        'Nearfull defect and alarm event co-occur on the wafer surface, suggesting glue-removal issues.',
      graph_dataset_id: dataset.id,
      observations: [
        {
          obs_id: 'obs_wafer_001',
          facet: 'image_defect',
          object: 'wafer',
          anomaly_type: 'nearfull',
          location: 'wafer surface',
          morphology: {
            canonical: 'dense_particles',
            area_ratio: 0.41,
            component_count: 14,
            distribution: 'dense',
          },
          severity: 0.89,
          confidence: 0.9,
          linked_entity_hints: [
            objectNode.id,
            defectNode.id,
            morphologyNode.id,
            locationNode.id,
          ],
          raw_evidence_refs: [
            buildEvidenceRef(objectNode.origin, 'graph_node'),
            buildEvidenceRef(defectHasMorphology.origin, 'graph_edge'),
            buildEvidenceRef(defectOccursOn.origin, 'graph_edge'),
          ],
          image_region: {
            x: 42,
            y: 38,
            w: 168,
            h: 168,
          },
          attributes: {
            source_adapter: 'wafer_adapter',
            event_alignment: 'same-run-window',
          },
        },
        {
          obs_id: 'obs_wafer_002',
          facet: 'log_event',
          event_type: 'alarm',
          event_code: 'EXAMPLE_ALARM',
          message: 'Example alarm fired during nearfull defect window',
          equipment: 'wafer surface',
          confidence: 0.78,
          linked_entity_hints: [eventNode.id, defectNode.id],
          raw_evidence_refs: [
            buildEvidenceRef(eventNode.origin, 'graph_node'),
            buildEvidenceRef(defectEvent.origin, 'graph_edge'),
          ],
          attributes: {
            event_source: 'fab_log',
            aligned_window: '2026-05-11T03:20:00.000Z/2026-05-11T03:26:00.000Z',
          },
        },
      ],
    },
    analysis: {
      case_id: 'wafer_nearfull_dense_particles',
      timestamp: '2026-05-11T03:24:00.000Z',
      graph_dataset_id: dataset.id,
      route1: {
        linked_entities: [
          {
            link_id: 'link_wafer_001',
            field: 'object',
            mention: 'wafer',
            selected_entity_id: objectNode.id,
            selected_entity_name: objectNode.name,
            score: 0.99,
            match_type: 'exact',
            ambiguous: false,
            candidates: [buildCandidate(objectNode, 0.99)],
            obs_id: 'obs_wafer_001',
            facet: 'image_defect',
          },
          {
            link_id: 'link_wafer_002',
            field: 'anomaly_type',
            mention: 'nearfull',
            selected_entity_id: defectNode.id,
            selected_entity_name: defectNode.name,
            score: 0.97,
            match_type: 'alias',
            ambiguous: false,
            candidates: [buildCandidate(defectNode, 0.97)],
            obs_id: 'obs_wafer_001',
            facet: 'image_defect',
          },
          {
            link_id: 'link_wafer_003',
            field: 'morphology',
            mention: 'dense_particles',
            selected_entity_id: morphologyNode.id,
            selected_entity_name: morphologyNode.name,
            score: 0.94,
            match_type: 'alias',
            ambiguous: false,
            candidates: [buildCandidate(morphologyNode, 0.94)],
            obs_id: 'obs_wafer_001',
            facet: 'image_defect',
          },
          {
            link_id: 'link_wafer_004',
            field: 'location',
            mention: 'wafer surface',
            selected_entity_id: locationNode.id,
            selected_entity_name: locationNode.name,
            score: 0.95,
            match_type: 'alias',
            ambiguous: false,
            candidates: [buildCandidate(locationNode, 0.95)],
            obs_id: 'obs_wafer_001',
            facet: 'image_defect',
          },
          {
            link_id: 'link_wafer_005',
            field: 'log_event',
            mention: 'example alarm',
            selected_entity_id: eventNode.id,
            selected_entity_name: eventNode.name,
            score: 0.92,
            match_type: 'alias',
            ambiguous: false,
            candidates: [buildCandidate(eventNode, 0.92)],
            obs_id: 'obs_wafer_002',
            facet: 'log_event',
          },
        ],
        consistency_score: 0.9,
        inconsistent_fields: [],
        consistency_checks: [
          {
            source_field: 'object',
            target_field: 'anomaly_type',
            source_entity_id: objectNode.id,
            target_entity_id: defectNode.id,
            relations: ['HAS_ANOMALY'],
            passed: true,
            matched_relation: 'HAS_ANOMALY',
          },
          {
            source_field: 'anomaly_type',
            target_field: 'morphology',
            source_entity_id: defectNode.id,
            target_entity_id: morphologyNode.id,
            relations: ['HAS_MORPHOLOGY'],
            passed: true,
            matched_relation: 'HAS_MORPHOLOGY',
          },
          {
            source_field: 'anomaly_type',
            target_field: 'log_event',
            source_entity_id: defectNode.id,
            target_entity_id: eventNode.id,
            relations: ['ASSOCIATED_WITH_EVENT'],
            passed: true,
            matched_relation: 'ASSOCIATED_WITH_EVENT',
          },
        ],
        correction_candidates: [],
        ranked_paths: [
          {
            path_id: 'path_wafer_001',
            source_entity_id: eventNode.id,
            target_entity_id: rootCauseNode.id,
            target_entity_name: rootCauseNode.name,
            nodes: [eventNode.id, defectNode.id, rootCauseNode.id],
            node_names: [eventNode.name, defectNode.name, rootCauseNode.name],
            relations: ['ASSOCIATED_WITH_EVENT', 'HAS_PLAUSIBLE_CAUSE'],
            score: 0.83,
            confidence: 0.69,
            evidence_match: 0.91,
            length: 2,
            source_edges: [
              buildPathEdgeDetail(defectEvent),
              buildPathEdgeDetail(defectCause),
            ],
            support_obs_ids: ['obs_wafer_001', 'obs_wafer_002'],
          },
          {
            path_id: 'path_wafer_002',
            source_entity_id: defectNode.id,
            target_entity_id: rootCauseNode.id,
            target_entity_name: rootCauseNode.name,
            nodes: [defectNode.id, rootCauseNode.id],
            node_names: [defectNode.name, rootCauseNode.name],
            relations: ['HAS_PLAUSIBLE_CAUSE'],
            score: 0.8,
            confidence: 0.78,
            evidence_match: 0.87,
            length: 1,
            source_edges: [buildPathEdgeDetail(defectCause)],
            support_obs_ids: ['obs_wafer_001'],
          },
        ],
      },
      route2: null,
      cross_route_signals: [],
      notes: [
        'Wafer 案例以双模态 evidence 组织为主，当前不回退到时序传播仿真。',
        'log_event 通过 ASSOCIATED_WITH_EVENT 边接入同一张 KG，适合做证据审查与路径对比。',
      ],
    },
  }
}

function buildRuntimeCases(datasets) {
  const byId = new Map(datasets.map((dataset) => [dataset.id, dataset]))
  const tepDataset = byId.get('tep-kg')
  const mvtecDataset = byId.get('mvtec-project')

  if (!tepDataset || !mvtecDataset) {
    throw new Error('required graph datasets are missing for runtime case generation')
  }

  return [
    buildTepDemoCase(tepDataset),
    buildMvtecDemoCase(mvtecDataset),
    buildWaferDemoCase(mvtecDataset),
  ]
}

async function main() {
  const datasets = await Promise.all([
    buildTepGraphDataset(),
    buildMvtecGraphDataset(),
  ])

  const output = {
    schemaVersion: 'graph.v1',
    generatedAt: new Date().toISOString(),
    generator: 'scripts/build-unified-graphs.mjs',
    datasets,
  }

  const outputDir = path.join(
    repoRoot,
    'public/generated',
  )
  const outputPath = path.join(outputDir, 'unified-graphs.json')
  const legacyTsPath = path.join(
    repoRoot,
    'src/data/generated/unified-graphs.ts',
  )

  await fs.mkdir(outputDir, {
    recursive: true,
  })
  await fs.writeFile(outputPath, JSON.stringify(output, null, 2), 'utf8')
  await fs.rm(legacyTsPath, {
    force: true,
  })
  console.log(`wrote ${outputPath}`)
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})
