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
