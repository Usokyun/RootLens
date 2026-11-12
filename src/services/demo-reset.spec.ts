import { beforeEach, describe, expect, it, vi } from "vitest";
const mocks = vi.hoisted(() => ({
  mode: "mock",
  source: "demo",
  reset: vi.fn(),
}));
vi.mock("./app-preferences", () => ({
  getAppPreferences: () => ({ dataSourceMode: mocks.mode }),
}));
vi.mock("./rootlens-data", () => ({
  getLocalSessionMeta: () => ({ source: mocks.source }),
}));
vi.mock("./workbench-state", () => ({ resetWorkbenchState: mocks.reset }));
import { resetDemoWorkspace } from "./demo-reset";

describe("demo reset boundary", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    mocks.mode = "mock";
    mocks.source = "demo";
  });
  it("refuses Backend and imported Replay", () => {
    mocks.mode = "backend";
    expect(resetDemoWorkspace()).toBe(false);
    mocks.mode = "mock";
    mocks.source = "import";
    expect(resetDemoWorkspace()).toBe(false);
    expect(mocks.reset).not.toHaveBeenCalled();
  });
  it("only clears demonstration state, preserving backend overlays and replay versions", () => {
    const storage = window.localStorage;
    for (const key of [
      "rootlens.mock-backend-state",
      "rootlens.graph-curation:old",
      "rootlens.mock-backend-state.replay:session",
      "rootlens.app-preferences",
      "rootlens.local.runtime",
    ])
      storage.setItem(key, "preserved");
    const assign = vi.fn();
    vi.stubGlobal("window", { localStorage: storage, location: { assign } });
    try {
      expect(resetDemoWorkspace()).toBe(true);
      expect(storage.getItem("rootlens.mock-backend-state")).toBeNull();
      expect(storage.getItem("rootlens.graph-curation:old")).toBe("preserved");
      expect(
        storage.getItem("rootlens.mock-backend-state.replay:session"),
      ).toBe("preserved");
      expect(storage.getItem("rootlens.app-preferences")).toBe("preserved");
      expect(storage.getItem("rootlens.local.runtime")).toBe("preserved");
      expect(assign).toHaveBeenCalledWith("/evidence");
    } finally {
      vi.unstubAllGlobals();
    }
  });
});
