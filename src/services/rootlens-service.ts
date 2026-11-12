import { createApiClient, type ApiClient } from "@/api/client";
import type {
  DashboardBootstrap,
  KnowledgeSourceDetail,
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
  KGConstructionGraphPayload,
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
  RunSummary,
  UploadRequest,
} from "@/api/contracts";
import { getAppPreferences } from "@/services/app-preferences";
import { getLocalSessionMeta } from "@/services/rootlens-data";
import { canSubmitReviewTarget, mockBackend } from "@/services/mock-backend";

export interface RootLensService {
  bootstrap: () => Promise<DashboardBootstrap>;
  kgStudio: () => Promise<KGStudioPayload>;
  getKnowledgeSource: (sourceId: string) => Promise<KnowledgeSourceDetail>;
  listRuns: () => Promise<RunSummary[]>;
  getRun: (runId: string) => Promise<RunDetail>;
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
  listKGDrafts: (request?: KGDraftListRequest) => Promise<KGDraftListResponse>;
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
  getKGConstructionGraph: (
    runId: string,
  ) => Promise<KGConstructionGraphPayload>;
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

function buildMockService(): RootLensService {
  return {
    ...mockBackend,
    getKGConstructionGraph: async () => {
      throw new Error(
        "构图快照预览需要 Backend 模式；Demo 不读取本机构图资产。",
      );
    },
    artifactUrl: (_runId: string, artifactName: string) => artifactName,
  };
}

function withImportedReplayOverrides(
  baseService: RootLensService,
): RootLensService {
  if (!isImportedReplayActive()) {
    return baseService;
  }

  // Imported replay is entirely browser-scoped; never route maintenance writes to Backend.
  return buildMockService();
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
