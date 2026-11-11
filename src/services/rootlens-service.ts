import { createApiClient, type ApiClient } from "@/api/client";
import type {
  DashboardBootstrap,
  KGDraftListRequest,
  KGDraftListResponse,
  KGDraftRequest,
  KGMaterialBuildSourcesRequest,
  KGMaterialBuildSourcesResponse,
  KGMaterialChunkListResponse,
  KGMaterialDetailResponse,
  KGMaterialExtractRequest,
  KGMaterialExtractResponse,
  KGMaterialExtractionArtifactListResponse,
  KGMaterialExtractionRunListResponse,
  KGMaterialListResponse,
  KGMaterialMutationResponse,
  KGMaterialRegisterUrlRequest,
  KGSourceDraftRequest,
  KGSourceDraftResponse,
  KGStudioPayload,
  KGConstructionBuildDetail,
  KGConstructionBuildListResponse,
  KGConstructionBuildRequest,
  KGConstructionBuildResponse,
  KGConstructionBuildValidationResponse,
  KGConstructionEdgeReviewRequest,
  KGConstructionEdgeReviewResponse,
  KGConstructionPublishRequest,
  KGConstructionPublishResponse,
  KGConstructionReviewQueueRequest,
  KGConstructionReviewQueueResponse,
  KGConstructionSourceListResponse,
  ReviewLedgerListRequest,
  ReviewLedgerListResponse,
  ReviewRequest,
  RunDetail,
  RunSourceContract,
  RunSummary,
  UploadRequest,
  WorkingGraphSummary,
  WorkingGraphPackage,
} from "@/api/contracts";
import { getAppPreferences } from "@/services/app-preferences";
import { getLocalSessionMeta } from "@/services/rootlens-data";
import { canSubmitReviewTarget, mockBackend } from "@/services/mock-backend";

export interface RootLensService {
  bootstrap: () => Promise<DashboardBootstrap>;
  kgStudio: (graphId?: string) => Promise<KGStudioPayload>;
  listWorkingGraphs: () => Promise<{ graphs: WorkingGraphSummary[] }>;
  getWorkingGraphPackage: (graphId: string) => Promise<WorkingGraphPackage>;
  saveWorkingGraphPackage: (graphId: string, body: WorkingGraphPackage) => Promise<WorkingGraphSummary>;
  importWorkingGraphPackage: (body: WorkingGraphPackage) => Promise<WorkingGraphSummary>;
  mutateWorkingGraph: (graphId: string, body: Record<string, unknown>) => Promise<WorkingGraphSummary>;
  enableWorkingGraph: (graphId: string, enabled: boolean) => Promise<WorkingGraphSummary>;
  activateWorkingGraph: (buildId: string, title: string, dataset?: "mvtec" | "wafer" | "tep", targetContract?: "legacy" | "unified-v2") => Promise<WorkingGraphSummary>;
  exportRunReplay: (runId: string) => Promise<import("@/services/session-export").RootLensSessionExport>;
  listRuns: () => Promise<RunSummary[]>;
  getRun: (runId: string, source?: RunSourceContract) => Promise<RunDetail>;
  uploadRun: (request: UploadRequest) => Promise<RunDetail>;
  submitReview: (
    request: ReviewRequest,
  ) => Promise<{ status: string; record: Record<string, unknown> }>;
  listReviewLedger: (
    request?: ReviewLedgerListRequest,
  ) => Promise<ReviewLedgerListResponse>;
  submitKGDraft: (
    request: KGDraftRequest,
  ) => Promise<{ status: string; record: Record<string, unknown> }>;
  listKGDrafts: (
    request?: KGDraftListRequest,
  ) => Promise<KGDraftListResponse>;
  generateKGSourceDraft: (
    request: KGSourceDraftRequest,
  ) => Promise<KGSourceDraftResponse>;
  listKGMaterials: () => Promise<KGMaterialListResponse>;
  getKGMaterial: (materialId: string) => Promise<KGMaterialDetailResponse>;
  uploadKGMaterial: (input: {
    file: File;
    title?: string;
    scenario?: string;
    source_type?: string;
    notes?: string;
    metadata?: Record<string, unknown>;
    material_id?: string;
    overwrite?: boolean;
  }) => Promise<KGMaterialMutationResponse>;
  registerKGMaterialUrl: (
    request: KGMaterialRegisterUrlRequest,
  ) => Promise<KGMaterialMutationResponse>;
  extractKGMaterial: (
    materialId: string,
    request?: KGMaterialExtractRequest,
  ) => Promise<KGMaterialExtractResponse>;
  buildKGMaterialSources: (
    request: KGMaterialBuildSourcesRequest,
  ) => Promise<KGMaterialBuildSourcesResponse>;
  getKGMaterialChunks: (
    materialId: string,
  ) => Promise<KGMaterialChunkListResponse>;
  getKGMaterialExtractions: (
    materialId: string,
  ) => Promise<KGMaterialExtractionRunListResponse>;
  getKGMaterialArtifacts: (
    materialId: string,
  ) => Promise<KGMaterialExtractionArtifactListResponse>;
  buildKGConstruction: (
    request: KGConstructionBuildRequest,
  ) => Promise<KGConstructionBuildResponse>;
  listKGConstructionBuilds: () => Promise<KGConstructionBuildListResponse>;
  getKGConstructionBuild: (runId: string) => Promise<KGConstructionBuildDetail>;
  validateKGConstructionBuild: (
    runId: string,
  ) => Promise<KGConstructionBuildValidationResponse>;
  publishKGConstructionBuild: (
    runId: string,
    request: KGConstructionPublishRequest,
  ) => Promise<KGConstructionPublishResponse>;
  reviewKGConstructionEdge: (
    runId: string,
    request: KGConstructionEdgeReviewRequest,
  ) => Promise<KGConstructionEdgeReviewResponse>;
  getKGConstructionReviewQueue: (
    runId: string,
    request?: KGConstructionReviewQueueRequest,
  ) => Promise<KGConstructionReviewQueueResponse>;
  listKGConstructionSources: () => Promise<KGConstructionSourceListResponse>;
  uploadKGConstructionSource: (input: {
    file: File;
    source_id: string;
    source_type?: string;
    scenario?: string;
    source_format?: string;
  }) => Promise<Record<string, unknown>>;
  artifactUrl: (runId: string, artifactName: string) => string;
}

function getBackendClient(): ApiClient {
  const preferences = getAppPreferences();
  return createApiClient(preferences.apiBaseUrl);
}

function isImportedReplayActive() {
  return getLocalSessionMeta()?.source === "import";
}

async function requiresBackendProcessing():Promise<never> {
  throw new Error("Demo / Replay 只展示成品快照。资料解析、构图与模型处理请切换 Backend；浏览器不执行这些步骤。");
}
function buildMockService(): RootLensService {
  return {
    ...mockBackend,
    getRun: (id, source) => source === "analysis-v2"
      ? Promise.reject(new Error("已保存分析属于 Backend；请退出回放并连接保存本次分析的服务。"))
      : mockBackend.getRun(id),
    uploadKGMaterial:requiresBackendProcessing,
    registerKGMaterialUrl:requiresBackendProcessing,
    extractKGMaterial:requiresBackendProcessing,
    generateKGSourceDraft:requiresBackendProcessing,
    buildKGMaterialSources:requiresBackendProcessing,
    buildKGConstruction:requiresBackendProcessing,
    validateKGConstructionBuild:requiresBackendProcessing,
    publishKGConstructionBuild:requiresBackendProcessing,
    uploadKGConstructionSource:requiresBackendProcessing,
    exportRunReplay: async () => { throw new Error("请用现有 Session 导出保存当前回放。"); },
    listWorkingGraphs: async () => ({ graphs: [] }),
    getWorkingGraphPackage: async () => { throw new Error("工作图管理需要 Backend 模式。"); },
    saveWorkingGraphPackage: async () => { throw new Error("工作图管理需要 Backend 模式。"); },
    importWorkingGraphPackage: async () => { throw new Error("工作图管理需要 Backend 模式。"); },
    mutateWorkingGraph: async () => { throw new Error("工作图管理需要 Backend 模式。"); },
    enableWorkingGraph: async () => { throw new Error("启用工作图需要 Backend 模式。"); },
    activateWorkingGraph: async () => { throw new Error("装载工作图需要 Backend 模式。"); },
    artifactUrl: (_runId: string, artifactName: string) => artifactName,
  };
}

function withImportedReplayOverrides(
  baseService: RootLensService,
): RootLensService {
  if (!isImportedReplayActive()) {
    return baseService;
  }

  const replayService = buildMockService();
  return {
    ...baseService,
    bootstrap: replayService.bootstrap,
    listRuns: replayService.listRuns,
    getRun: replayService.getRun,
    submitReview: replayService.submitReview,
    listReviewLedger: replayService.listReviewLedger,
  };
}

function getCurrentService(): RootLensService {
  const preferences = getAppPreferences();
  const baseService =
    preferences.dataSourceMode === "backend"
      ? getBackendClient()
      : buildMockService();
  return withImportedReplayOverrides(baseService);
}

export function getRootLensService(): RootLensService {
  return getCurrentService();
}

export async function withRootLensService<T>(
  execute: (service: RootLensService) => Promise<T>,
): Promise<T> {
  return execute(getCurrentService());
}

export function canSubmitReviewTargetType(targetType: string) {
  return canSubmitReviewTarget(targetType);
}
