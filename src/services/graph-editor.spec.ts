import { describe, expect, it } from "vitest";
import {
  applyGraphPatch,
  emptyGraphPatch,
  graphPatchRequest,
  latestGraphPatch,
  parseGraphPatch,
  stageGraphEdit,
  validateGraphEdit,
  type GraphEdit,
} from "./graph-editor";
import type { KGDraftRecord } from "@/api/contracts";
import type {
  UnifiedGraphDataset,
  UnifiedGraphNode,
  UnifiedGraphEdge,
} from "@/types/graph";

const origin = {
  projectId: "demo",
  projectLabel: "Demo",
  filePath: "notes.md",
  layer: "seed",
  rowNumber: 1,
};
const node = (id: string): UnifiedGraphNode => ({
  id,
  name: id,
  kind: "Concept",
  category: "mvtec",
  description: "",
  aliases: [],
  degree: 0,
  inDegree: 0,
  outDegree: 0,
  attributes: {},
  origin,
});
const edge: UnifiedGraphEdge = {
  id: "ab",
  source: "a",
  target: "b",
  relation: "RELATED_TO",
  label: "RELATED_TO",
  category: "mvtec",
  confidence: 0.6,
  weight: 0.4,
  directed: true,
  attributes: { source: "registered", evidence: "old evidence" },
  origin,
};
const dataset: UnifiedGraphDataset = {
  id: "mvtec-project",
  label: "Demo",
  description: "",
  graphKind: "seed",
  projectRoot: "",
  sourceFiles: [],
  nodes: [node("a"), node("b")],
  edges: [edge],
  metadata: { scenario: "mvtec" },
};
const edit = (extra: Partial<GraphEdit> = {}): GraphEdit => ({
  kind: "node",
  operation: "upsert",
  id: "a",
  before: node("a"),
  after: { ...node("a"), name: "Revised" },
  source: "notes.md#L1",
  evidence: "Observed scratch",
  note: "Fix label",
  ...extra,
});

describe("graph editor draft safety", () => {
  it("requires traceable edits and valid directed endpoints", () => {
    expect(() => validateGraphEdit(edit(), dataset)).not.toThrow();
    for (const key of ["source", "evidence", "note"] as const)
      expect(() => validateGraphEdit(edit({ [key]: " " }), dataset)).toThrow();
    const e = edit({ kind: "edge", id: "ab", before: edge, after: edge });
    expect(() => validateGraphEdit(e, dataset)).not.toThrow();
    for (const after of [
      { ...edge, target: "missing" },
      { ...edge, relation: "arbitrary relation" },
      { ...edge, confidence: NaN },
      { ...edge, confidence: 1.2 },
    ])
      expect(() => validateGraphEdit({ ...e, after }, dataset)).toThrow();
    expect(() =>
      validateGraphEdit(
        edit({ operation: "disable", id: "missing", after: null }),
        dataset,
      ),
    ).toThrow();
  });
  it("retains original before state across revisions, without mutating inputs", () => {
    const first = stageGraphEdit(emptyGraphPatch("demo"), edit());
    const next = stageGraphEdit(
      first,
      edit({ before: node("Changed"), after: { ...node("a"), name: "Again" } }),
    );
    expect(next.changes).toHaveLength(1);
    expect(next.changes[0]!.before).toEqual(node("a"));
    expect(first.changes[0]!.after).toMatchObject({ name: "Revised" });
  });
  it("cancels newly added nodes with their dependent new relations", () => {
    let p = stageGraphEdit(
      emptyGraphPatch("demo"),
      edit({ id: "c", before: null, after: node("c") }),
    );
    p = stageGraphEdit(
      p,
      edit({
        kind: "edge",
        id: "ac",
        before: null,
        after: { ...edge, id: "ac", target: "c" },
      }),
    );
    p = stageGraphEdit(
      p,
      edit({ id: "c", before: node("c"), after: null, operation: "disable" }),
    );
    expect(p.changes).toEqual([]);
  });
  it("previews edits and soft-disables incident edges without mutating runtime data", () => {
    const p = stageGraphEdit(emptyGraphPatch("demo"), edit());
    const output = applyGraphPatch(dataset, p);
    expect(output.nodes[0]).toMatchObject({
      name: "Revised",
      degree: 1,
      attributes: { draft: true },
    });
    expect(dataset.nodes[0]!.name).toBe("a");
    const disabled = applyGraphPatch(
      dataset,
      stageGraphEdit(p, edit({ operation: "disable", after: null })),
    );
    expect(disabled.nodes.map((n) => n.id)).toEqual(["b"]);
    expect(disabled.edges).toEqual([]);
    expect(dataset.edges).toHaveLength(1);
  });
  it("binds requests to a scenario and scope; never requests runtime publication", () => {
    const p = stageGraphEdit(emptyGraphPatch("demo|mvtec-project"), edit());
    expect(graphPatchRequest(dataset, p)).toMatchObject({
      target_type: "graph_workspace",
      target_key: "editor:demo|mvtec-project",
      metadata: { dataset: "mvtec" },
      draft_action: "revise",
    });
    expect(() => graphPatchRequest({ ...dataset, metadata: {} }, p)).toThrow();
    expect(parseGraphPatch(p, "backend|mvtec-project")).toBeNull();
    expect(parseGraphPatch(p, p.scope)).toEqual(p);
  });
  it("rejects malformed persisted snapshots and duplicate changes before rendering", () => {
    const p = stageGraphEdit(emptyGraphPatch("demo"), edit());
    for (const bad of [
      { ...p, changes: [{ ...p.changes[0], after: { id: "a" } }] },
      { ...p, changes: [p.changes[0], p.changes[0]] },
      { ...p, changes: [{ ...p.changes[0], source: " " }] },
      { ...p, version: 2 },
    ])
      expect(parseGraphPatch(bad, "demo")).toBeNull();
    const parsed = parseGraphPatch(p, "demo")!;
    parsed.changes[0]!.note = "changed";
    expect(p.changes[0]!.note).toBe("Fix label");
  });
  it("restores newest valid scoped version, including an explicit empty reset", () => {
    const p = stageGraphEdit(emptyGraphPatch("demo"), edit());
    const record = (date: string, value: unknown) =>
      ({
        recorded_at: date,
        metadata: { editor_patch: value },
      }) as unknown as KGDraftRecord;
    expect(
      latestGraphPatch(
        [
          record("2026-11-01", p),
          record("2026-11-02", { ...p, scope: "other" }),
        ],
        "demo",
      ),
    ).toEqual(p);
    expect(
      latestGraphPatch(
        [
          record("2026-11-01", p),
          record("2026-11-03", emptyGraphPatch("demo")),
        ],
        "demo",
      ).changes,
    ).toEqual([]);
    expect(latestGraphPatch([], "demo")).toEqual(emptyGraphPatch("demo"));
  });
  it("blocks overwriting an incompatible saved version in the same scope", () => {
    const record = {
      recorded_at: "2026-11-11",
      metadata: { editor_patch: { version: 2, scope: "demo", changes: [] } },
    } as unknown as KGDraftRecord;
    expect(() => latestGraphPatch([record], "demo")).toThrow("已阻止覆盖");
  });
});
