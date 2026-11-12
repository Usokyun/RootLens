import fs from "node:fs";
import path from "node:path";

import { beforeEach, describe, expect, it, vi } from "vitest";

const repoRoot = process.cwd();
const curatedCaseIds = [
  "mvtec_fixture_clean_scratch",
  "mvtec_noisy_0001",
  "tep_0001",
  "wafer_0001",
];

function installGeneratedAssetFetchStub() {
  vi.stubGlobal(
    "fetch",
    vi.fn(async (input: string | URL | Request) => {
      const url =
        typeof input === "string"
          ? input
          : input instanceof URL
            ? input.pathname
            : input.url;
      const relativePath = url.startsWith("/") ? url.slice(1) : url;
      const filePath = path.join(
        repoRoot,
        relativePath.startsWith("generated/") ||
          relativePath.startsWith("demo-evidence/")
          ? "public"
          : "",
        relativePath,
      );

      if (!fs.existsSync(filePath)) {
        return {
          ok: false,
          status: 404,
          json: async () => ({}),
          text: async () => "",
        };
      }

      const body = fs.readFileSync(filePath, "utf8");
      return {
        ok: true,
        status: 200,
        json: async () => JSON.parse(body),
        text: async () => body,
      };
    }),
  );
}

describe("mock backend paper demo mode", () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.resetModules();
    vi.unstubAllGlobals();
    installGeneratedAssetFetchStub();
  });

  it("returns exactly one curated demo run with the four paper cases", async () => {
    const { mockBackend } = await import("@/services/mock-backend");

    const runs = await mockBackend.listRuns();
    expect(runs).toHaveLength(1);
    expect(runs[0].run_id).toBe("paper-demo-curated");

    const detail = await mockBackend.getRun(runs[0].run_id);
    expect(detail.cases.map((item) => item.case_id)).toEqual(curatedCaseIds);
  });

  it("lists append-only bounded review ledger records in reverse chronological order", async () => {
    const { mockBackend } = await import("@/services/mock-backend");

    const runs = await mockBackend.listRuns();
    const detail = await mockBackend.getRun(runs[0].run_id);
    const caseDetail = detail.cases[0];
    const pathTarget = caseDetail.review_targets?.find(
      (item) => item.target_type === "path",
    );
    const edgeTarget = caseDetail.review_targets?.find(
      (item) => item.target_type === "edge",
    );

    expect(pathTarget).toBeTruthy();
    expect(edgeTarget).toBeTruthy();

    await mockBackend.submitReview({
      run_id: detail.run.run_id,
      case_id: caseDetail.case_id,
      target_type: "path",
      target_id: pathTarget?.target_id,
      action: "accept",
      note: "path review",
      reviewer: "tester",
      source: "mock-test",
    });

    await mockBackend.submitReview({
      run_id: detail.run.run_id,
      case_id: caseDetail.case_id,
      target_type: "edge",
      target_id: edgeTarget?.target_id,
      action: "reject",
      note: "edge review",
      reviewer: "tester",
      source: "mock-test",
    });

    const ledger = await mockBackend.listReviewLedger({
      run_id: detail.run.run_id,
      case_id: caseDetail.case_id,
    });

    expect(ledger.total_count).toBe(2);
    expect(ledger.records.map((item) => item.target_type)).toEqual([
      "edge",
      "path",
    ]);
    expect(ledger.records[0].target_key).toBe(edgeTarget?.target_key ?? null);
    expect(ledger.records[1].target_key).toBe(pathTarget?.target_key ?? null);
  });

  it("rejects uploads in mock mode", async () => {
    const { mockBackend } = await import("@/services/mock-backend");

    await expect(
      mockBackend.uploadRun({
        file: new File(["{}"], "demo.json", { type: "application/json" }),
        mode: "evidence",
        top_k: 5,
      }),
    ).rejects.toThrow("内置 Demo 模式不支持上传");
  });

  it("uses imported runtime sessions as the active replay run source", async () => {
    const [
      { loadBundledRootLensRuntime, saveImportedSession },
      { mockBackend },
    ] = await Promise.all([
      import("@/services/rootlens-data"),
      import("@/services/mock-backend"),
    ]);

    const bundledRuntime = await loadBundledRootLensRuntime();
    saveImportedSession({
      graphs: null,
      runtime: {
        ...bundledRuntime,
        generator: "browser-import",
        cases: bundledRuntime.cases.slice(0, 1),
      },
      summary: "导入回放测试",
    });

    const runs = await mockBackend.listRuns();
    expect(runs).toHaveLength(1);
    expect(runs[0].run_id).toBe("imported-runtime-replay");

    const detail = await mockBackend.getRun(runs[0].run_id);
    expect(detail.cases).toHaveLength(1);
    expect(detail.cases[0]?.visual_evidence).toEqual([]);
    expect(detail.cases[0]?.generated_evidence?.fixture_type).toBeUndefined();
    expect(detail.run.label).toContain("导入回放测试");
  });
  it("isolates replay drafts and sources from the built-in demo", async () => {
    const { mockBackend } = await import("@/services/mock-backend");
    const {
      loadBundledRootLensRuntime,
      saveImportedSession,
      clearImportedSession,
    } = await import("@/services/rootlens-data");
    const draft = {
      target_type: "graph_workspace" as const,
      target_id: "mvtec",
      target_key: "editor:demo|mvtec",
      draft_action: "revise" as const,
      source: "rootlens-editor",
      metadata: {
        editor_patch: { version: 1, scope: "demo|mvtec", changes: [] },
      },
    };
    await mockBackend.submitKGDraft(draft);
    const runtime = await loadBundledRootLensRuntime();
    saveImportedSession({ graphs: null, runtime, summary: "Replay isolation" });
    expect((await mockBackend.listKGDrafts()).records).toEqual([]);
    await mockBackend.submitKGDraft({
      ...draft,
      target_key: "editor:replay|mvtec",
    });
    expect((await mockBackend.listKGDrafts()).records).toHaveLength(1);
    await expect(
      mockBackend.getKnowledgeSource("manual_curation"),
    ).rejects.toThrow("不以 Demo 原文替代");
    clearImportedSession();
    const demo = await mockBackend.listKGDrafts();
    expect(demo.records).toHaveLength(1);
    expect(demo.records[0]?.target_key).toBe("editor:demo|mvtec");
  });

  it("provides precomputed source notes but refuses browser construction", async () => {
    const { mockBackend } = await import("@/services/mock-backend");
    const result = await mockBackend.listKGMaterials();
    expect(result.materials.map((m) => m.material_id)).toContain(
      "demo-source-mvtec",
    );
    const chunks = await mockBackend.getKGMaterialChunks("demo-source-mvtec");
    expect(chunks.chunks[0]?.source_locator).toContain(
      "docs/sources/mvtec_sources.md",
    );
    expect(chunks.chunks[0]?.text_content).toContain(
      "not native MVTec factory",
    );
    await expect(
      mockBackend.buildKGConstruction({
        sources: [],
        output_name: "demo",
        overwrite: false,
      }),
    ).rejects.toThrow("真实构图请使用 Backend");
  });
});
