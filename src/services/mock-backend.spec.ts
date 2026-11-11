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
        relativePath.startsWith("generated/") ? "public" : "",
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

  it("replays persisted backend details without rebuilding reasoning from current graphs", async () => {
    const { mockBackend } = await import("@/services/mock-backend");
    const { loadBundledRootLensRuntime, saveImportedSession } = await import("@/services/rootlens-data");
    const original = await mockBackend.getRun("paper-demo-curated");
    original.run.run_id = "saved-backend-run";
    original.summary = { working_graph_snapshot: { graph_id: "original-graph" } };
    original.cases[0].reasoning_metadata = {
      graph_id: "original-graph", outcome: "matched",
      query_results: [{ schema_version: 'rootlens-reasoning-result.v2', outcome: 'ambiguous', grounded_facts: [{ value: null, status: 'missing' }], candidate_evaluations: [{ score: -0.25, confidence: null }] }],
      evidence_frames: [{ schema_version: 'rootlens-evidence.v2', observations: [{ status: 'missing', value: null }] }],
    };
    const runtime = await loadBundledRootLensRuntime();
    await saveImportedSession({ graphs: null, runtime: { ...runtime, backend_runs: [original] } });
    expect((await mockBackend.listRuns())[0].run_id).toBe("saved-backend-run");
    expect(await mockBackend.getRun("saved-backend-run")).toEqual(original);
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

  it("keeps older stored records intact when adding local feedback", async () => {
    const { mockBackend } = await import("@/services/mock-backend");
    const key = "rootlens.mock-backend-state";
    const history = { construction_builds: [{ id: "old-build" }], uploaded_runs: [{ id: "old-run" }] };
    localStorage.setItem(key, JSON.stringify(history));
    await mockBackend.submitReview({ target_type: "path", target_id: "path", action: "accept", source: "test" });
    expect(JSON.parse(localStorage.getItem(key)!)).toMatchObject(history);
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
    await saveImportedSession({
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
    expect(detail.run.label).toContain("导入回放测试");
  });
});
