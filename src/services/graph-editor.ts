import type { KGDraftRecord, KGDraftRequest } from "@/api/contracts";
import type {
  UnifiedGraphDataset,
  UnifiedGraphEdge,
  UnifiedGraphNode,
} from "@/types/graph";

export interface GraphEdit {
  kind: "node" | "edge";
  operation: "upsert" | "disable";
  id: string;
  before: UnifiedGraphNode | UnifiedGraphEdge | null;
  after: UnifiedGraphNode | UnifiedGraphEdge | null;
  source: string;
  evidence: string;
  note: string;
}
export interface GraphPatch {
  version: 1;
  scope: string;
  changes: GraphEdit[];
}
export const emptyGraphPatch = (scope: string): GraphPatch => ({
  version: 1,
  scope,
  changes: [],
});

export function validateGraphEdit(
  edit: GraphEdit,
  dataset: UnifiedGraphDataset,
) {
  if (
    !edit.id.trim() ||
    !edit.source.trim() ||
    !edit.evidence.trim() ||
    !edit.note.trim()
  )
    throw new Error("请填写来源、支持内容和修改理由。");
  if (edit.operation === "disable") {
    const collection = edit.kind === "node" ? dataset.nodes : dataset.edges;
    if (!collection.some((item) => item.id === edit.id))
      throw new Error("待停用对象已不存在。");
    return;
  }
  if (!edit.after || edit.after.id !== edit.id)
    throw new Error("草稿对象标识不匹配。");
  if (edit.kind === "node") {
    const node = edit.after as UnifiedGraphNode;
    if (!node.name.trim() || !node.kind.trim())
      throw new Error("请填写节点名称和类型。");
  } else {
    const edge = edit.after as UnifiedGraphEdge;
    if (
      !dataset.nodes.some((n) => n.id === edge.source) ||
      !dataset.nodes.some((n) => n.id === edge.target)
    )
      throw new Error("关系两端必须是当前草稿中的有效节点。");
    if (!/^[A-Z][A-Z0-9_]*$/.test(edge.relation))
      throw new Error("关系类型应使用大写字母与下划线。");
    if (
      edge.confidence === null ||
      !Number.isFinite(edge.confidence) ||
      edge.confidence < 0 ||
      edge.confidence > 1
    )
      throw new Error("关系置信度须在 0–1 之间。");
  }
}

export function stageGraphEdit(patch: GraphPatch, edit: GraphEdit): GraphPatch {
  const existing = patch.changes.find(
    (c) => c.kind === edit.kind && c.id === edit.id,
  );
  const cancelNewNode =
    edit.kind === "node" &&
    edit.operation === "disable" &&
    existing &&
    !existing.before;
  const changes = patch.changes.filter(
    (c) =>
      !(c.kind === edit.kind && c.id === edit.id) &&
      !(
        cancelNewNode &&
        c.kind === "edge" &&
        c.after &&
        "source" in c.after &&
        (c.after.source === edit.id || c.after.target === edit.id)
      ),
  );
  const next = { ...edit, before: existing ? existing.before : edit.before };
  // Adding then disabling an object cancels that addition; no dangling synthetic tombstone.
  if (!(existing && !existing.before && edit.operation === "disable"))
    changes.push(next);
  return JSON.parse(JSON.stringify({ ...patch, changes })) as GraphPatch;
}

export function applyGraphPatch(
  dataset: UnifiedGraphDataset,
  patch: GraphPatch,
): UnifiedGraphDataset {
  const nodes = new Map(dataset.nodes.map((n) => [n.id, n]));
  const edges = new Map(dataset.edges.map((e) => [e.id, e]));
  for (const c of patch.changes) {
    if (c.kind === "node") {
      if (c.operation === "disable") nodes.delete(c.id);
      else if (c.after)
        nodes.set(c.id, {
          ...(c.after as UnifiedGraphNode),
          attributes: {
            ...c.after.attributes,
            draft: true,
            draft_source: c.source,
            draft_evidence: c.evidence,
          },
        });
    } else if (c.operation === "disable") edges.delete(c.id);
    else if (c.after)
      edges.set(c.id, {
        ...(c.after as UnifiedGraphEdge),
        attributes: {
          ...c.after.attributes,
          source: c.source,
          evidence: c.evidence,
          draft: true,
          review_status: "draft",
        },
      });
  }
  const validEdges = [...edges.values()].filter(
    (e) => nodes.has(e.source) && nodes.has(e.target),
  );
  return {
    ...dataset,
    nodes: [...nodes.values()].map((n) => ({
      ...n,
      inDegree: validEdges.filter((e) => e.target === n.id).length,
      outDegree: validEdges.filter((e) => e.source === n.id).length,
      degree: validEdges.filter((e) => e.target === n.id || e.source === n.id)
        .length,
    })),
    edges: validEdges,
  };
}

export function graphPatchRequest(
  dataset: UnifiedGraphDataset,
  patch: GraphPatch,
): KGDraftRequest {
  const datasetName = dataset.metadata.scenario;
  if (!["mvtec", "tep", "wafer"].includes(String(datasetName)))
    throw new Error("草稿必须关联明确场景。");
  return {
    target_type: "graph_workspace",
    target_id: dataset.id,
    target_key: `editor:${patch.scope}`,
    draft_action: "revise",
    source: "rootlens-editor",
    note: "知识图谱草稿版本；不发布运行图，不重算已有分析。",
    metadata: { editor_patch: patch, dataset: datasetName },
  };
}

function validSnapshot(
  value: unknown,
  kind: GraphEdit["kind"],
  id: string,
  original = false,
): boolean {
  if (!value || typeof value !== "object") return false;
  const v = value as Record<string, unknown>;
  if (
    v.id !== id ||
    !v.attributes ||
    typeof v.attributes !== "object" ||
    Array.isArray(v.attributes) ||
    !v.origin ||
    typeof v.origin !== "object"
  )
    return false;
  const origin = v.origin as Record<string, unknown>;
  if (
    !["projectId", "projectLabel", "filePath", "layer"].every(
      (k) => typeof origin[k] === "string",
    ) ||
    !Number.isFinite(origin.rowNumber)
  )
    return false;
  if (kind === "node")
    return (
      ["name", "kind", "category", "description"].every(
        (k) => typeof v[k] === "string",
      ) &&
      String(v.name).trim().length > 0 &&
      String(v.kind).trim().length > 0 &&
      Array.isArray(v.aliases) &&
      v.aliases.every((a) => typeof a === "string")
    );
  return (
    ["source", "target", "relation", "category", "label"].every(
      (k) => typeof v[k] === "string",
    ) &&
    !!v.source &&
    !!v.target &&
    /^[A-Z][A-Z0-9_]*$/.test(String(v.relation)) &&
    ((original && v.confidence === null) ||
      (typeof v.confidence === "number" &&
        Number.isFinite(v.confidence) &&
        v.confidence >= 0 &&
        v.confidence <= 1)) &&
    typeof v.directed === "boolean"
  );
}
export function parseGraphPatch(
  value: unknown,
  scope: string,
): GraphPatch | null {
  if (!value || typeof value !== "object") return null;
  const p = value as GraphPatch;
  if (
    p.version !== 1 ||
    p.scope !== scope ||
    !Array.isArray(p.changes) ||
    p.changes.length > 1000
  )
    return null;
  const seen = new Set<string>();
  for (const c of p.changes) {
    if (
      !c ||
      !["node", "edge"].includes(c.kind) ||
      !["upsert", "disable"].includes(c.operation) ||
      !["id", "source", "evidence", "note"].every(
        (k) =>
          typeof c[k as keyof GraphEdit] === "string" &&
          String(c[k as keyof GraphEdit]).trim(),
      )
    )
      return null;
    const key = `${c.kind}:${c.id}`;
    if (seen.has(key)) return null;
    seen.add(key);
    if (c.before !== null && !validSnapshot(c.before, c.kind, c.id, true))
      return null;
    if (
      c.operation === "disable"
        ? c.after !== null
        : !validSnapshot(c.after, c.kind, c.id)
    )
      return null;
  }
  return JSON.parse(JSON.stringify(p)) as GraphPatch;
}

export function latestGraphPatch(
  records: KGDraftRecord[],
  scope: string,
): GraphPatch {
  const sorted = [...records].sort((a, b) =>
    String(b.recorded_at ?? b.created_at).localeCompare(
      String(a.recorded_at ?? a.created_at),
    ),
  );
  for (const r of sorted) {
    const p = parseGraphPatch(r.metadata?.editor_patch, scope);
    if (p) return p;
    const raw = r.metadata?.editor_patch as Record<string, unknown> | undefined;
    if (raw?.scope === scope)
      throw new Error("已有草稿格式不兼容，已阻止覆盖。请导出并核对原版本。");
  }
  return emptyGraphPatch(scope);
}
