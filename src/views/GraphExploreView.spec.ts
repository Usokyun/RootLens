import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import type {
  KGStudioPayload,
  RunCaseDetail,
  RunDetail,
} from "@/api/contracts";
import { updateAppPreferences } from "@/services/app-preferences";
import {
  getWorkbenchState,
  updateWorkbenchState,
} from "@/services/workbench-state";
import GraphExploreView from "./GraphExploreView.vue";
const { service } = vi.hoisted(() => ({
  service: {
    listRuns: vi.fn(),
    getRun: vi.fn(),
    kgStudio: vi.fn(),
    listReviewLedger: vi.fn(),
  },
}));
vi.mock("@/services/rootlens-service", () => ({
  getRootLensService: () => service,
  canSubmitReviewTargetType: () => true,
}));
vi.mock("@/services/rootlens-data", () => ({
  getLocalSessionMeta: () => null,
  getLocalSessionEventName: () => "test-session",
  getStoredImportedGraphs: () => null,
  loadUnifiedGraphs: vi.fn(),
}));
vi.mock("@/components/graphs/KnowledgeForceGraph.vue", () => ({
  default: defineComponent({
    props: ["dataset"],
    setup: (p) => () =>
      h("div", { "data-testid": "canonical-graph" }, p.dataset.id),
  }),
}));
vi.mock("@/components/knowledge/GraphEditor.vue", () => ({
  default: defineComponent({ setup: () => () => null }),
}));
const c = (id: string, dataset: string): RunCaseDetail =>
  ({
    case_id: id,
    case_label: id,
    dataset,
    generated_evidence: { observations: [] },
    ranked_root_causes: [
      {
        candidate_id: "one",
        ranking_id: "rank-one",
        rank: 1,
        candidate_name: "First",
      },
      {
        candidate_id: "two",
        ranking_id: "rank-two",
        rank: 2,
        candidate_name: "Second",
      },
    ],
    path_graph: { paths: [], path_count: 0, node_count: 0, edge_count: 0 },
    review_targets: [],
  }) as unknown as RunCaseDetail;
const run = (id: string): RunDetail =>
  ({
    run: { run_id: id, label: id, created_at: "2026-11-11T00:00:00Z" },
    cases: [c("mvtec-case", "mvtec"), c("tep-case", "tep")],
  }) as RunDetail;
const graph = {
  graph_nodes: [
    { node_id: "a", label: "A", node_type: "Concept", scenario: "mvtec" },
    { node_id: "b", label: "B", node_type: "Concept", scenario: "tep" },
  ],
  graph_edges: [],
} as unknown as KGStudioPayload;
function deferred<T>() {
  let resolve!: (v: T) => void;
  const promise = new Promise<T>((yes) => (resolve = yes));
  return { resolve, promise };
}
let app: App, host: HTMLElement;
const settle = async () => {
  for (let i = 0; i < 12; i++) {
    await nextTick();
    await Promise.resolve();
  }
};
async function mount() {
  host = document.createElement("div");
  document.body.append(host);
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: "/graphs", name: "graphs", component: { render: () => null } },
    ],
  });
  await router.push("/graphs");
  app = createApp(GraphExploreView);
  app.use(router);
  app.directive("control-label", {});
  for (const name of [
    "a-collapse",
    "a-collapse-item",
    "a-spin",
    "a-space",
    "a-tag",
    "a-tabs",
    "a-tab-pane",
    "a-form",
    "a-form-item",
    "a-radio-group",
    "a-radio",
    "a-input-search",
    "a-checkbox",
    "a-alert",
    "a-empty",
    "a-divider",
  ])
    app.component(
      name,
      defineComponent({
        setup: (_, ctx) => () => h("div", ctx.slots.default?.()),
      }),
    );
  app.component(
    "a-button",
    defineComponent({
      setup: (_, ctx) => () => h("button", ctx.attrs, ctx.slots.default?.()),
    }),
  );
  app.component(
    "a-modal",
    defineComponent({
      props: ["visible"],
      setup: (p, ctx) => () =>
        p.visible ? h("div", ctx.slots.default?.()) : null,
    }),
  );
  app.component("a-drawer", defineComponent({ setup: () => () => null }));
  app.component("a-textarea", defineComponent({ setup: () => () => null }));
  app.component(
    "a-select",
    defineComponent({
      props: ["modelValue"],
      emits: ["change"],
      setup: (p, ctx) => () =>
        h(
          "select",
          {
            ...ctx.attrs,
            value: p.modelValue,
            onChange: (e: Event) =>
              ctx.emit("change", (e.target as HTMLSelectElement).value),
          },
          ctx.slots.default?.(),
        ),
    }),
  );
  app.component(
    "a-option",
    defineComponent({
      props: ["value", "label"],
      setup: (p) => () =>
        h("option", { value: p.value }, String(p.label ?? p.value)),
    }),
  );
  app.mount(host);
  await settle();
}
async function choose(label: string, id: string) {
  const el = host.querySelector<HTMLSelectElement>(
    `select[aria-label="${label}"]`,
  )!;
  el.value = id;
  el.dispatchEvent(new Event("change"));
  await settle();
}
beforeEach(() => {
  vi.clearAllMocks();
  updateAppPreferences({ dataSourceMode: "backend" });
  updateWorkbenchState({
    selectedRunId: null,
    selectedCaseId: null,
    selectedCandidateId: null,
    selectedPathId: null,
  });
  service.listRuns.mockResolvedValue([run("run-one").run, run("run-two").run]);
  service.getRun.mockImplementation(async (id: string) => run(id));
  service.kgStudio.mockResolvedValue(graph);
  service.listReviewLedger.mockResolvedValue({ records: [] });
});
afterEach(() => {
  app?.unmount();
  host?.remove();
});
describe("reasoning workspace context safety", () => {
  it("presents one selectable candidate for multiple ranked paths to the same entity", async () => {
    const detail = run("run-one");
    const candidates = detail.cases[0]!.ranked_root_causes!;
    candidates.push({
      ...candidates[0]!,
      rank: 3,
      ranking_id: "lower-path",
      score: 0.2,
    });
    service.getRun.mockResolvedValue(detail);
    await mount();
    expect(host.querySelectorAll(".candidate-item")).toHaveLength(2);
    expect(host.querySelectorAll(".candidate-item.is-active")).toHaveLength(1);
  });

  it("ignores a late run result after a newer run selection", async () => {
    const old = deferred<RunDetail>();
    service.getRun.mockImplementation((id: string) =>
      id === "run-one" ? old.promise : Promise.resolve(run(id)),
    );
    await mount();
    await choose("分析记录", "run-two");
    old.resolve(run("run-one"));
    await settle();
    expect(getWorkbenchState().selectedRunId).toBe("run-two");
  });
  it("never lets an older scenario graph overwrite the currently selected case", async () => {
    const old = deferred<KGStudioPayload>();
    service.kgStudio.mockReturnValueOnce(old.promise).mockResolvedValue(graph);
    await mount();
    await choose("当前案例", "tep-case");
    old.resolve(graph);
    await settle();
    [...host.querySelectorAll("button")]
      .find((b) => b.textContent === "查看知识图谱")!
      .click();
    await settle();
    expect(
      host.querySelector('[data-testid="canonical-graph"]')!.textContent,
    ).toBe("runtime-tep");
    expect(service.kgStudio).toHaveBeenCalledTimes(2);
  });
  it("preserves a valid candidate selection when returning to the same case", async () => {
    updateWorkbenchState({
      selectedRunId: "run-one",
      selectedCaseId: "mvtec-case",
      selectedCandidateId: "two",
    });
    await mount();
    expect(getWorkbenchState().selectedCandidateId).toBe("two");
    expect(
      host.querySelector(".candidate-item.is-active")!.textContent,
    ).toContain("Second");
  });
});
