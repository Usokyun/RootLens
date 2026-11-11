import type {
  KGMaterialChunkListResponse,
  KGMaterialDetailResponse,
  KGMaterialExtractionArtifactListResponse,
  KGMaterialExtractionRunListResponse,
  KGMaterialListResponse,
  KGMaterialMutationResponse,
  KGMaterialRegisterUrlRequest,
  KGStudioPayload,
  WorkingGraphSummary,
  WorkingGraphPackage,
} from "@/api/contracts";

const DEFAULT_API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";
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

export function buildUrl(
  baseUrl: string,
  path: string,
  search?: URLSearchParams,
): string {
  const normalizedBase = trimTrailingSlash(resolveApiBaseUrl(baseUrl));
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const query = search?.toString();
  return `${normalizedBase}${normalizedPath}${query ? `?${query}` : ""}`;
}

export class ApiError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export async function requestJson<T>(
  baseUrl: string,
  path: string,
  init?: RequestInit,
  search?: URLSearchParams,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(buildUrl(baseUrl, path, search), init);
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new ApiError(`无法连接后端服务，请确认地址和服务状态。${detail ? `（${detail}）` : ""}`, 0);
  }

  if (!response.ok) {
    const body = await response.text();
    let message = body || `请求失败（${response.status}）`;
    try {
      const detail = JSON.parse(body)?.detail;
      if (typeof detail === "string") message = detail;
      else if (Array.isArray(detail)) message = detail.map((item) => item?.msg ?? String(item)).join("；");
    } catch { /* Non-JSON errors retain their original response text. */ }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}

export function jsonInit(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(body),
  };
}

export interface ApiClient {
  kgStudio: (graphId: string) => Promise<KGStudioPayload>;
  listWorkingGraphs: () => Promise<{ graphs: WorkingGraphSummary[] }>;
  getWorkingGraphPackage: (graphId: string) => Promise<WorkingGraphPackage>;
  saveWorkingGraphPackage: (graphId: string, body: WorkingGraphPackage) => Promise<WorkingGraphSummary>;
  importWorkingGraphPackage: (body: WorkingGraphPackage) => Promise<WorkingGraphSummary>;
  enableWorkingGraph: (graphId: string, enabled: boolean) => Promise<WorkingGraphSummary>;
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
  getKGMaterialChunks: (
    materialId: string,
  ) => Promise<KGMaterialChunkListResponse>;
  getKGMaterialExtractions: (
    materialId: string,
  ) => Promise<KGMaterialExtractionRunListResponse>;
  getKGMaterialArtifacts: (
    materialId: string,
  ) => Promise<KGMaterialExtractionArtifactListResponse>;
}

export function createApiClient(baseUrl = DEFAULT_API_BASE_URL): ApiClient {
  return {
    kgStudio: (graphId) => requestJson<KGStudioPayload>(baseUrl, "/api/kg/studio", undefined,
      new URLSearchParams({ graph_id: graphId })),
    listWorkingGraphs: () => requestJson(baseUrl, "/api/kg/working-graphs"),
    getWorkingGraphPackage: (id) => requestJson(baseUrl, `/api/kg/working-graphs/${encodeURIComponent(id)}/package`),
    saveWorkingGraphPackage: (id, body) => requestJson(baseUrl, `/api/kg/working-graphs/${encodeURIComponent(id)}/package`, jsonInit("PUT", body)),
    importWorkingGraphPackage: (body) => requestJson(baseUrl, "/api/kg/working-graphs/import", jsonInit("POST", body)),
    enableWorkingGraph: (id, enabled) => requestJson(baseUrl, `/api/kg/working-graphs/${encodeURIComponent(id)}/enable`, jsonInit("POST", { enabled })),
    listKGMaterials: () =>
      requestJson<KGMaterialListResponse>(baseUrl, "/api/kg/materials"),
    getKGMaterial: (materialId) =>
      requestJson<KGMaterialDetailResponse>(
        baseUrl,
        `/api/kg/materials/${materialId}`,
      ),
    uploadKGMaterial: (input) => {
      const form = new FormData();
      form.append("file", input.file);
      if (input.title) form.append("title", input.title);
      if (input.scenario) form.append("scenario", input.scenario);
      if (input.source_type) form.append("source_type", input.source_type);
      if (input.notes) form.append("notes", input.notes);
      if (input.material_id) form.append("material_id", input.material_id);
      if (typeof input.overwrite === "boolean") form.append("overwrite", String(input.overwrite));
      if (input.metadata && Object.keys(input.metadata).length) {
        form.append("metadata", JSON.stringify(input.metadata));
      }
      return requestJson<KGMaterialMutationResponse>(
        baseUrl,
        "/api/kg/materials/upload",
        {
          method: "POST",
          body: form,
        },
      );
    },
    registerKGMaterialUrl: (request) =>
      requestJson<KGMaterialMutationResponse>(
        baseUrl,
        "/api/kg/materials/register-url",
        jsonInit("POST", request),
      ),
    getKGMaterialChunks: (materialId) =>
      requestJson<KGMaterialChunkListResponse>(
        baseUrl,
        `/api/kg/materials/${materialId}/chunks`,
      ),
    getKGMaterialExtractions: (materialId) =>
      requestJson<KGMaterialExtractionRunListResponse>(
        baseUrl,
        `/api/kg/materials/${materialId}/extractions`,
      ),
    getKGMaterialArtifacts: (materialId) =>
      requestJson<KGMaterialExtractionArtifactListResponse>(
        baseUrl,
        `/api/kg/materials/${materialId}/artifacts`,
      ),
  };
}
