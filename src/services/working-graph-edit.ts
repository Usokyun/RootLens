import type { UnifiedWorkingGraphPackage, WorkingGraphPackage } from '@/api/contracts'

const nodeTables = [
  { key: 'entities', idKey: 'entity_id', kind: 'entity' },
  { key: 'hypotheses', idKey: 'hypothesis_id', kind: 'hypothesis' },
  { key: 'mechanisms', idKey: 'mechanism_id', kind: 'mechanism' },
  { key: 'pattern_definitions', idKey: 'pattern_id', kind: 'pattern' },
] as const

export interface EditableWorkingGraphNode {
  id: string
  kind: typeof nodeTables[number]['kind']
  name: string
  /** Only canonical entities expose aliases. */
  aliases: string[] | null
}

type Row = Record<string, unknown>

function isRow(value: unknown): value is Row {
  return !!value && typeof value === 'object' && !Array.isArray(value)
}

function nonblank(value: unknown): value is string {
  return typeof value === 'string' && !!value.trim()
}

function findNode(graph: UnifiedWorkingGraphPackage, id: string) {
  const matches = nodeTables.flatMap(table => {
    const rows = graph.knowledge[table.key]
    if (!Array.isArray(rows)) return []
    return rows.flatMap((row, index) => isRow(row) && row[table.idKey] === id
      ? [{ table, rows: rows as unknown[], row, index }] : [])
  })
  return matches.length === 1 ? matches[0] : undefined
}

/** The compiled phenomenon's identity is pattern_id, never the rule's definition_id. */
export function editableWorkingGraphNode(
  graph: WorkingGraphPackage | null,
  nodeId: string | null,
): EditableWorkingGraphNode | null {
  if (graph?.schema_version !== 'rootlens-working-graph.v2' || !nodeId) return null
  const match = findNode(graph, nodeId)
  if (!match || !nonblank(match.row.label)) return null
  const { table, row } = match
  return {
    id: nodeId,
    kind: table.kind,
    name: row.label as string,
    aliases: table.kind === 'entity' ? (
      Array.isArray(row.aliases) ? row.aliases.filter((alias): alias is string => typeof alias === 'string') : []
    ) : null,
  }
}

export function updateWorkingGraphNode(
  graph: WorkingGraphPackage,
  nodeId: string,
  edit: { name: string; aliases?: readonly string[] },
): UnifiedWorkingGraphPackage {
  const match = findNode(graph, nodeId)
  if (!match) throw new Error('所选节点没有可编辑的规范记录。')
  const label = edit.name.trim()
  if (!label) throw new Error('请输入节点名称。')
  const { table, rows, row, index } = match
  if (table.kind !== 'entity' && edit.aliases !== undefined) throw new Error('只有实体可编辑别名。')
  const next: Row = { ...row, label }
  if (edit.aliases !== undefined) {
    next.aliases = [...new Set(edit.aliases.map(alias => alias.trim()).filter(Boolean))]
  }
  return {
    ...graph,
    knowledge: { ...graph.knowledge, [table.key]: rows.map((item, i) => i === index ? next : item) },
  }
}

const requiredKnowledgeLists = [
  'feature_registry', 'observable_definitions', 'pattern_definitions',
  'hypotheses', 'expectation_rules', 'source_assertions',
] as const

/** Check the editable envelope; the backend validates all knowledge and references. */
export function parseWorkingGraphDraft(
  text: string,
  current?: WorkingGraphPackage,
): UnifiedWorkingGraphPackage {
  let value: unknown
  try {
    value = JSON.parse(text)
  } catch {
    throw new Error('JSON 格式不正确，请检查引号、括号和逗号。')
  }
  if (!isRow(value) || value.schema_version !== 'rootlens-working-graph.v2') {
    throw new Error('请选择或粘贴完整的 v2 工作图 JSON。')
  }
  const knowledge = value.knowledge
  if (
    !nonblank(value.title) || !nonblank(value.dataset) || !nonblank(value.build_id)
    || (value.graph_id != null && !nonblank(value.graph_id))
    || !isRow(knowledge) || knowledge.schema_version !== 'rootlens-knowledge-package.v2'
    || !nonblank(knowledge.graph_id) || !requiredKnowledgeLists.every(key => Array.isArray(knowledge[key]))
  ) throw new Error('工作图包缺少有效的标题、场景、来源或规范知识。')

  if (current && (
    current.schema_version !== 'rootlens-working-graph.v2' || current.graph_id !== value.graph_id
    || current.dataset !== value.dataset || current.build_id !== value.build_id
    || current.knowledge.graph_id !== knowledge.graph_id
  )) throw new Error('保存不能改变工作图的标识、场景、版本或来源。请导入为新图。')
  return value as unknown as UnifiedWorkingGraphPackage
}
