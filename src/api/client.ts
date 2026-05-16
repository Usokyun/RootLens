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
  ReviewLedgerListRequest,
  ReviewLedgerListResponse,
  ReviewRequest,
  RunDetail,
  RunSummary,
  UploadRequest,
  WhatIfRequest,
} from "@/api/contracts";

const DEFAULT_API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8001";
const BACKEND_PROXY_TARGET =
  import.meta.env.VITE_BACKEND_PROXY_TARGET ?? DEFAULT_API_BASE_URL;

function trimTrailingSlash(value: string): string {
  return value.replace(/\/+$/, "");
}

function isLoopbackHostname(hostname: string): boolean {
  return (
    hostname === "127.0.0.1" || hostname === "localhost" || hostname === "[::1]"
  );
}

function tryParseUrl(value: string, base: string): URL | null {
  try {
    return new URL(value, base);
  } catch {
    return null;
  }
}

function isProxyCompatibleTarget(targetUrl: URL, proxyUrl: URL): boolean {
  return (
    isLoopbackHostname(targetUrl.hostname) &&
    isLoopbackHostname(proxyUrl.hostname) &&
    targetUrl.protocol === proxyUrl.protocol &&
    targetUrl.port === proxyUrl.port
  );
}

export function resolveApiBaseUrl(
  baseUrl: string,
  currentOrigin = typeof window !== "undefined" ? window.location.origin : "",
): string {
  const normalizedBase = trimTrailingSlash(baseUrl || DEFAULT_API_BASE_URL);
  if (!normalizedBase || !currentOrigin) {
    return normalizedBase;
  }

  const targetUrl = tryParseUrl(normalizedBase, currentOrigin);
  const currentUrl = tryParseUrl(currentOrigin, currentOrigin);
  const proxyUrl = tryParseUrl(BACKEND_PROXY_TARGET, currentOrigin);

  if (!targetUrl || !currentUrl || !proxyUrl) {
    return normalizedBase;
  }

  if (!["http:", "https:"].includes(targetUrl.protocol)) {
    return normalizedBase;
  }

  if (targetUrl.origin === currentUrl.origin) {
    return normalizedBase;
  }

  if (!isLoopbackHostname(currentUrl.hostname)) {
    return normalizedBase;
  }

  if (!isProxyCompatibleTarget(targetUrl, proxyUrl)) {
    return normalizedBase;
  }

  return currentUrl.origin;
}

function buildUrl(
  baseUrl: string,
  path: string,
  search?: URLSearchParams,
): string {
  const normalizedBase = trimTrailingSlash(resolveApiBaseUrl(baseUrl));
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const query = search?.toString();
  return `${normalizedBase}${normalizedPath}${query ? `?${query}` : ""}`;
}

async function requestJson<T>(
  baseUrl: string,
  path: string,
  init?: RequestInit,
  search?: URLSearchParams,
): Promise<T> {
  const response = await fetch(buildUrl(baseUrl, path, search), init);

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `Request failed with ${response.status}`);
  }

  return (await response.json()) as T;
}

function jsonInit(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  };
}

export interface ApiClient {
  bootstrap: () => Promise<DashboardBootstrap>;
  kgStudio: () => Promise<KGStudioPayload>;
  listRuns: () => Promise<RunSummary[]>;
  getRun: (runId: string) => Promise<RunDetail>;
  uploadRun: (request: UploadRequest) => Promise<RunDetail>;
  analyze: (request: AnalyzeRequest) => Promise<AnalyzeEnvelope>;
  whatIf: (request: WhatIfRequest) => Promise<AnalyzeEnvelope>;
  submitReview: (
    request: ReviewRequest,
  ) => Promise<{ status: string; record: Record<string, unknown> }>;
  listReviewLedger: (
    request?: ReviewLedgerListRequest,
  ) => Promise<ReviewLedgerListResponse>;
  submitKGDraft: (
    request: KGDraftRequest,
  ) => Promise<{ status: string; record: Record<string, unknown> }>;
  generateKGSourceDraft: (
    request: KGSourceDraftRequest,
  ) => Promise<KGSourceDraftResponse>;
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

export function createApiClient(baseUrl = DEFAULT_API_BASE_URL): ApiClient {
  return {
    bootstrap: () =>
      requestJson<DashboardBootstrap>(baseUrl, "/api/dashboard/bootstrap"),
    kgStudio: () => requestJson<KGStudioPayload>(baseUrl, "/api/kg/studio"),
    listRuns: () => requestJson<RunSummary[]>(baseUrl, "/api/runs"),
    getRun: (runId) => requestJson<RunDetail>(baseUrl, `/api/runs/${runId}`),
    uploadRun: (request) => {
      const form = new FormData();
      form.append("file", request.file);
      form.append("mode", request.mode);
      form.append("top_k", String(request.top_k));
      if (request.dataset) form.append("dataset", request.dataset);
      if (request.object_name) form.append("object_name", request.object_name);
      if (request.defect_type) form.append("defect_type", request.defect_type);
      if (request.model_preset)
        form.append("model_preset", request.model_preset);

      return requestJson<RunDetail>(baseUrl, "/api/runs/upload", {
        method: "POST",
        body: form,
      });
    },
    analyze: (request) =>
      requestJson<AnalyzeEnvelope>(
        baseUrl,
        "/api/analyze",
        jsonInit("POST", request),
      ),
    whatIf: (request) =>
      requestJson<AnalyzeEnvelope>(
        baseUrl,
        "/api/what-if",
        jsonInit("POST", request),
      ),
    submitReview: (request) =>
      requestJson<{ status: string; record: Record<string, unknown> }>(
        baseUrl,
        "/api/feedback",
        jsonInit("POST", request),
      ),
    listReviewLedger: (request) => {
      const search = new URLSearchParams();
      if (request?.run_id) search.set("run_id", request.run_id);
      if (request?.case_id) search.set("case_id", request.case_id);
      if (request?.target_type) search.set("target_type", request.target_type);
      if (request?.target_id) search.set("target_id", request.target_id);
      if (typeof request?.offset === "number")
        search.set("offset", String(request.offset));
      if (typeof request?.limit === "number")
        search.set("limit", String(request.limit));

      return requestJson<ReviewLedgerListResponse>(
        baseUrl,
        "/api/feedback",
        undefined,
        search,
      );
    },
    submitKGDraft: (request) =>
      requestJson<{ status: string; record: Record<string, unknown> }>(
        baseUrl,
        "/api/kg/drafts",
        jsonInit("POST", request),
      ),
    generateKGSourceDraft: (request) =>
      requestJson<KGSourceDraftResponse>(
        baseUrl,
        "/api/kg/source-draft",
        jsonInit("POST", request),
      ),
    buildKGConstruction: (request) =>
      requestJson<KGConstructionBuildResponse>(
        baseUrl,
        "/api/kg/construction/build",
        jsonInit("POST", request),
      ),
    listKGConstructionBuilds: () =>
      requestJson<KGConstructionBuildListResponse>(
        baseUrl,
        "/api/kg/construction/builds",
      ),
    getKGConstructionBuild: (runId) =>
      requestJson<KGConstructionBuildDetail>(
        baseUrl,
        `/api/kg/construction/builds/${runId}`,
      ),
    validateKGConstructionBuild: (runId) =>
      requestJson<KGConstructionBuildValidationResponse>(
        baseUrl,
        `/api/kg/construction/builds/${runId}/validate`,
        { method: "POST" },
      ),
    publishKGConstructionBuild: (runId, request) =>
      requestJson<KGConstructionPublishResponse>(
        baseUrl,
        `/api/kg/construction/builds/${runId}/publish`,
        jsonInit("POST", request),
      ),
    reviewKGConstructionEdge: (runId, request) =>
      requestJson<KGConstructionEdgeReviewResponse>(
        baseUrl,
        `/api/kg/construction/builds/${runId}/review`,
        jsonInit("POST", request),
      ),
    getKGConstructionReviewQueue: (runId, request) => {
      const search = new URLSearchParams();
      if (request?.review_status)
        search.set("review_status", request.review_status);
      if (request?.source) search.set("source", request.source);
      if (request?.scenario) search.set("scenario", request.scenario);
      if (request?.relation) search.set("relation", request.relation);
      if (request?.query) search.set("query", request.query);
      if (typeof request?.offset === "number")
        search.set("offset", String(request.offset));
      if (typeof request?.limit === "number")
        search.set("limit", String(request.limit));
      return requestJson<KGConstructionReviewQueueResponse>(
        baseUrl,
        `/api/kg/construction/builds/${runId}/review-queue`,
        undefined,
        search,
      );
    },
    listKGConstructionSources: () =>
      requestJson<KGConstructionSourceListResponse>(
        baseUrl,
        "/api/kg/construction/sources",
      ),
    uploadKGConstructionSource: (input) => {
      const form = new FormData();
      form.append("file", input.file);
      form.append("source_id", input.source_id);
      if (input.source_type) form.append("source_type", input.source_type);
      if (input.scenario) form.append("scenario", input.scenario);
      if (input.source_format)
        form.append("source_format", input.source_format);
      return requestJson<Record<string, unknown>>(
        baseUrl,
        "/api/kg/construction/sources/upload",
        {
          method: "POST",
          body: form,
        },
      );
    },
    artifactUrl: (runId, artifactName) =>
      buildUrl(baseUrl, `/api/runs/${runId}/artifacts/${artifactName}`),
  };
}

export const apiClient = createApiClient(DEFAULT_API_BASE_URL);
