import { beforeEach, afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref, type App } from "vue";
import GraphEditor from "./GraphEditor.vue";
import type { UnifiedGraphDataset } from "@/types/graph";
const { service } = vi.hoisted(() => ({
  service: { listKGDrafts: vi.fn(), submitKGDraft: vi.fn() },
}));
vi.mock("@/services/rootlens-service", () => ({
  getRootLensService: () => service,
}));
vi.mock("@/services/rootlens-data", () => ({
  getLocalSessionMeta: () => null,
}));
vi.mock("@/services/app-preferences", () => ({
  useAppPreferences: () => ({
    preferences: ref({ dataSourceMode: "mock", apiBaseUrl: "test" }),
  }),
}));
const dataset: UnifiedGraphDataset = {
  id: "mvtec",
  label: "Test",
  description: "",
  graphKind: "seed",
  projectRoot: "",
  sourceFiles: [],
  nodes: [],
  edges: [],
  metadata: { scenario: "mvtec" },
};
let app: App, host: HTMLDivElement;
const settle = async () => {
  for (let i = 0; i < 8; i++) {
    await nextTick();
    await Promise.resolve();
  }
};
async function mount() {
  host = document.createElement("div");
  document.body.append(host);
  app = createApp(GraphEditor, { dataset });
  app.directive("control-label", {});
  for (const name of [
    "a-select", "a-option", "a-popconfirm", "a-space",
    "a-tag",
    "a-form",
    "a-form-item",
    "a-divider",
    "a-collapse",
    "a-collapse-item",
  ])
    app.component(
      name,
      defineComponent({
        setup: (_, ctx) => () => h("div", ctx.slots.default?.()),
      }),
    );
  app.component(
    "a-alert",
    defineComponent({
      props: ["title"],
      setup: (p) => () => h("p", String(p.title ?? "")),
    }),
  );
  app.component(
    "a-button",
    defineComponent({
      setup: (_, ctx) => () => h("button", ctx.attrs, ctx.slots.default?.()),
    }),
  );
  for (const name of ["a-input", "a-textarea", "a-input-number"])
    app.component(
      name,
      defineComponent({
        props: ["modelValue"],
        emits: ["update:modelValue"],
        setup: (p, ctx) => () =>
          h("input", {
            ...ctx.attrs,
            value: p.modelValue,
            onInput: (e: Event) =>
              ctx.emit(
                "update:modelValue",
                (e.target as HTMLInputElement).value,
              ),
          }),
      }),
    );
  app.mount(host);
  await settle();
}
function button(text: string) {
  return [...host.querySelectorAll("button")].find(
    (b) => b.textContent === text,
  )!;
}
function input(label: string, value: string) {
  const el = host.querySelector<HTMLInputElement>(
    `input[aria-label="${label}"]`,
  )!;
  el.value = value;
  el.dispatchEvent(new Event("input"));
}
async function stage() {
  input("节点名称", "Check record");
  input("编辑来源", "Notes §1");
  input("支持内容", "Demo only");
  input("修改理由", "Clarify");
  await nextTick();
  button("预览修改").click();
  await settle();
}
beforeEach(() => {
  vi.clearAllMocks();
  service.listKGDrafts.mockResolvedValue({ records: [] });
  service.submitKGDraft.mockResolvedValue({ status: "recorded" });
});
afterEach(() => {
  app?.unmount();
  host?.remove();
});

describe("graph editor persistence UX", () => {
  it("previews a sourced node, retains failed saves, retries and restores saved version", async () => {
    await mount();
    await stage();
    expect(host.textContent).toContain("Notes §1");
    expect(button("保存草稿").disabled).toBe(false);
    service.submitKGDraft.mockRejectedValueOnce(new Error("offline"));
    button("保存草稿").click();
    await settle();
    expect(host.textContent).toContain("offline");
    expect(button("保存草稿").disabled).toBe(false);
    button("保存草稿").click();
    await settle();
    expect(button("保存草稿").disabled).toBe(true);
    const request = service.submitKGDraft.mock.calls[1]![0];
    expect(request.target_type).toBe("graph_workspace");
    service.listKGDrafts.mockResolvedValue({
      records: [
        { metadata: request.metadata, recorded_at: "2026-11-11T00:00:00Z" },
      ],
    });
    app.unmount();
    host.remove();
    await mount();
    expect(host.textContent).toContain("Check record");
    expect(button("保存草稿").disabled).toBe(true);
  });
  it("blocks saving if earlier drafts could not be read", async () => {
    service.listKGDrafts.mockRejectedValue(new Error("unavailable"));
    await mount();
    await stage();
    expect(host.textContent).toContain("请先成功读取已有草稿");
    expect(button("保存草稿").disabled).toBe(true);
    expect(service.submitKGDraft).not.toHaveBeenCalled();
  });
  it("requires previewing unstaged inputs and warns on unloading dirty forms", async () => {
    await mount();
    input("节点名称", "unsaved");
    await nextTick();
    expect(button("保存草稿").disabled).toBe(true);
    const event = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(event);
    expect(event.defaultPrevented).toBe(true);
    button("放弃未保存").click();
    await settle();
    const next = new Event("beforeunload", { cancelable: true });
    window.dispatchEvent(next);
    expect(next.defaultPrevented).toBe(false);
    expect(
      host.querySelector<HTMLInputElement>('input[aria-label="节点名称"]')!
        .value,
    ).toBe("");
  });
});
