export type JsonPrimitive = string | number | boolean | null

export type JsonValue =
  | JsonPrimitive
  | JsonValue[]
  | {
      [key: string]: JsonValue
    }

export interface UnifiedGraphOrigin {
  projectId: string
  projectLabel: string
  filePath: string
  layer: string
  rowNumber: number
}

export interface UnifiedGraphSourceFile {
  path: string
  role: string
  layer: string
  rowCount: number
  fields: string[]
}

export interface UnifiedGraphNode {
  id: string
  name: string
  category: string
  kind: string
  description: string
  aliases: string[]
  degree: number
  inDegree: number
  outDegree: number
  attributes: Record<string, JsonValue>
  origin: UnifiedGraphOrigin
}

export interface UnifiedGraphEdge {
  id: string
  source: string
  target: string
  relation: string
  category: string
  label: string
  confidence: number | null
  weight: number | null
  directed: boolean
  attributes: Record<string, JsonValue>
  origin: UnifiedGraphOrigin
}

export interface UnifiedGraphDataset {
  id: string
  label: string
  description: string
  graphKind: string
  projectRoot: string
  sourceFiles: UnifiedGraphSourceFile[]
  nodes: UnifiedGraphNode[]
  edges: UnifiedGraphEdge[]
  metadata: Record<string, JsonValue>
}

export interface UnifiedGraphsFile {
  schemaVersion: string
  generatedAt: string
  generator: string
  datasets: UnifiedGraphDataset[]
}
