import { createApiClient, type ApiClient } from "@/api/client";
import { getAppPreferences } from "@/services/app-preferences";
import { getLocalSessionMeta } from "@/services/rootlens-data";
import { canSubmitReviewTarget, mockBackend } from "@/services/mock-backend";

type GraphService = Pick<ApiClient,
  "kgStudio" | "listWorkingGraphs" | "getWorkingGraphPackage" | "saveWorkingGraphPackage"
  | "importWorkingGraphPackage" | "mutateWorkingGraph" | "enableWorkingGraph"
  | "listRuns" | "getRun" | "submitReview" | "listReviewLedger"
>;

async function requiresBackendGraph(): Promise<never> {
  throw new Error("工作图管理需要 Backend；请先退出成品回放。");
}

const offlineGraphService: GraphService = {
  listRuns: mockBackend.listRuns,
  getRun: (id, source) => source === "analysis-v2"
    ? Promise.reject(new Error("已保存分析属于 Backend；请退出回放并连接保存本次分析的服务。"))
    : mockBackend.getRun(id),
  submitReview: mockBackend.submitReview,
  listReviewLedger: mockBackend.listReviewLedger,
  kgStudio: requiresBackendGraph,
  listWorkingGraphs: async () => ({ graphs: [] }),
  getWorkingGraphPackage: requiresBackendGraph,
  saveWorkingGraphPackage: requiresBackendGraph,
  importWorkingGraphPackage: requiresBackendGraph,
  mutateWorkingGraph: requiresBackendGraph,
  enableWorkingGraph: requiresBackendGraph,
};

export function getRootLensService(): GraphService {
  const preferences = getAppPreferences();
  return preferences.dataSourceMode === "backend" && getLocalSessionMeta()?.source !== "import"
    ? createApiClient(preferences.apiBaseUrl)
    : offlineGraphService;
}

export function canSubmitReviewTargetType(targetType: string) {
  return canSubmitReviewTarget(targetType);
}
