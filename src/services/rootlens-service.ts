import { createApiClient, type ApiClient } from '@/api/client'
import type {
  AnalyzeEnvelope,
  AnalyzeRequest,
  DashboardBootstrap,
  KGDraftRequest,
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
  ReviewRequest,
  RunDetail,
  RunSummary,
  UploadRequest,
  WhatIfRequest,
} from '@/api/contracts'
import { getAppPreferences } from '@/services/app-preferences'
import { canSubmitReviewTarget, mockBackend } from '@/services/mock-backend'

export interface RootLensService {
  bootstrap: () => Promise<DashboardBootstrap>
  kgStudio: () => Promise<KGStudioPayload>
  listRuns: () => Promise<RunSummary[]>
  getRun: (runId: string) => Promise<RunDetail>
  uploadRun: (request: UploadRequest) => Promise<RunDetail>
  analyze: (request: AnalyzeRequest) => Promise<AnalyzeEnvelope>
  whatIf: (request: WhatIfRequest) => Promise<AnalyzeEnvelope>
  submitReview: (request: ReviewRequest) => Promise<{ status: string; record: Record<string, unknown> }>
  submitKGDraft: (request: KGDraftRequest) => Promise<{ status: string; record: Record<string, unknown> }>
  generateKGSourceDraft: (request: KGSourceDraftRequest) => Promise<KGSourceDraftResponse>
  buildKGConstruction: (request: KGConstructionBuildRequest) => Promise<KGConstructionBuildResponse>
  listKGConstructionBuilds: () => Promise<KGConstructionBuildListResponse>
  getKGConstructionBuild: (runId: string) => Promise<KGConstructionBuildDetail>
  validateKGConstructionBuild: (runId: string) => Promise<KGConstructionBuildValidationResponse>
  publishKGConstructionBuild: (
    runId: string,
    request: KGConstructionPublishRequest,
  ) => Promise<KGConstructionPublishResponse>
  reviewKGConstructionEdge: (
    runId: string,
    request: KGConstructionEdgeReviewRequest,
  ) => Promise<KGConstructionEdgeReviewResponse>
  getKGConstructionReviewQueue: (
    runId: string,
    request?: KGConstructionReviewQueueRequest,
  ) => Promise<KGConstructionReviewQueueResponse>
  listKGConstructionSources: () => Promise<KGConstructionSourceListResponse>
  uploadKGConstructionSource: (input: {
    file: File
    source_id: string
    source_type?: string
    scenario?: string
    source_format?: string
  }) => Promise<Record<string, unknown>>
  artifactUrl: (runId: string, artifactName: string) => string
}

function getBackendClient(): ApiClient {
  const preferences = getAppPreferences()
  return createApiClient(preferences.apiBaseUrl)
}

function getCurrentService(): RootLensService {
  const preferences = getAppPreferences()
  if (preferences.dataSourceMode === 'backend') {
    return getBackendClient()
  }

  return {
    ...mockBackend,
    artifactUrl: (_runId: string, artifactName: string) => artifactName,
  }
}

export function getRootLensService(): RootLensService {
  return getCurrentService()
}

export async function withRootLensService<T>(execute: (service: RootLensService) => Promise<T>): Promise<T> {
  return execute(getCurrentService())
}

export function canSubmitReviewTargetType(targetType: string) {
  return canSubmitReviewTarget(targetType)
}
