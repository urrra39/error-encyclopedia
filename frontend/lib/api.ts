/**
 * Typed HTTP client for the Error Encyclopedia API.
 *
 * Features:
 *  - A typed {@link ApiError} carrying the HTTP status (0 for network/timeout
 *    failures) and a human-readable message.
 *  - A base-URL resolver reading `NEXT_PUBLIC_API_BASE_URL`.
 *  - An internal `request<T>()` helper built on `fetch` with an
 *    `AbortController`-based timeout. It throws `ApiError` on non-2xx
 *    responses and on network/timeout failures.
 *  - Caller-friendly per-request options (`signal`, `revalidate`, `timeoutMs`)
 *    so consumers can integrate with Next.js fetch caching while defaulting to
 *    `cache: 'no-store'` for dynamic data.
 */

import type {
  AutocompleteResponse,
  ErrorCreate,
  ErrorDetail,
  ErrorSummary,
  SearchResponse,
} from "@/lib/types";

/** Default fallback base URL when the env var is not set. */
const DEFAULT_BASE_URL = "http://localhost:8000";

/** Default per-request timeout in milliseconds. */
const DEFAULT_TIMEOUT_MS = 8_000;

/**
 * Error thrown by the API client. `status` is the HTTP status code, or `0`
 * when the failure happened before a response was received (network error,
 * timeout, or abort).
 */
export class ApiError extends Error {
  public readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    // Restore prototype chain for instanceof checks across transpilation.
    Object.setPrototypeOf(this, ApiError.prototype);
  }

  /** True when no HTTP response was received (network failure / timeout). */
  get isNetworkError(): boolean {
    return this.status === 0;
  }
}

/**
 * Resolve the API base URL from the environment, stripping any trailing slash
 * so that path concatenation is predictable.
 */
export function getApiBaseUrl(): string {
  const fromEnv = process.env.NEXT_PUBLIC_API_BASE_URL;
  const base =
    typeof fromEnv === "string" && fromEnv.trim().length > 0
      ? fromEnv.trim()
      : DEFAULT_BASE_URL;
  return base.replace(/\/+$/, "");
}

/** Per-request options exposed to callers. */
export interface RequestOptions {
  /** External abort signal; merged with the internal timeout signal. */
  signal?: AbortSignal;
  /**
   * Next.js revalidation window in seconds. When provided, the request opts
   * into Next's data cache instead of the default `no-store` behaviour.
   */
  revalidate?: number;
  /** Override the default request timeout (milliseconds). */
  timeoutMs?: number;
}

interface InternalRequestConfig extends RequestOptions {
  method?: "GET" | "POST";
  /** JSON-serialisable request body for write operations. */
  body?: unknown;
}

/**
 * Build the Next.js-specific fetch options. Defaults to `no-store` for
 * dynamic data; switches to a revalidating cache when `revalidate` is given.
 */
function buildCacheOptions(
  revalidate: number | undefined,
): Pick<RequestInit, "cache"> & { next?: { revalidate: number } } {
  if (typeof revalidate === "number") {
    return { next: { revalidate } };
  }
  return { cache: "no-store" };
}

/**
 * Core request helper. Performs the fetch with a timeout, surfaces failures as
 * {@link ApiError}, and parses successful JSON bodies as `T`.
 */
async function request<T>(
  path: string,
  config: InternalRequestConfig = {},
): Promise<T> {
  const {
    method = "GET",
    body,
    signal: callerSignal,
    revalidate,
    timeoutMs = DEFAULT_TIMEOUT_MS,
  } = config;

  const url = `${getApiBaseUrl()}${path}`;

  const timeoutController = new AbortController();
  const timeoutId = setTimeout(() => {
    timeoutController.abort();
  }, timeoutMs);

  // Forward an externally-provided abort to our internal controller so a
  // single signal governs the fetch.
  const onCallerAbort = (): void => timeoutController.abort();
  if (callerSignal) {
    if (callerSignal.aborted) {
      timeoutController.abort();
    } else {
      callerSignal.addEventListener("abort", onCallerAbort, { once: true });
    }
  }

  const headers: Record<string, string> = { Accept: "application/json" };
  const init: RequestInit = {
    method,
    headers,
    signal: timeoutController.signal,
    ...buildCacheOptions(revalidate),
  };

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (error) {
    // Distinguish a timeout/abort from a genuine network failure.
    if (timeoutController.signal.aborted) {
      const abortedByCaller = callerSignal?.aborted ?? false;
      const message = abortedByCaller
        ? `Request to ${path} was aborted.`
        : `Request to ${path} timed out after ${timeoutMs}ms.`;
      throw new ApiError(0, message);
    }
    const detail = error instanceof Error ? error.message : String(error);
    throw new ApiError(0, `Network request to ${path} failed: ${detail}`);
  } finally {
    clearTimeout(timeoutId);
    if (callerSignal) {
      callerSignal.removeEventListener("abort", onCallerAbort);
    }
  }

  if (!response.ok) {
    throw new ApiError(
      response.status,
      await buildErrorMessage(response, path),
    );
  }

  // 204 No Content (or an empty body) cannot be parsed as JSON.
  if (response.status === 204) {
    return undefined as T;
  }

  try {
    return (await response.json()) as T;
  } catch (error) {
    const detail = error instanceof Error ? error.message : String(error);
    throw new ApiError(
      response.status,
      `Failed to parse JSON response from ${path}: ${detail}`,
    );
  }
}

/**
 * Derive a descriptive error message from a non-2xx response, preferring the
 * FastAPI `detail` field when present.
 */
async function buildErrorMessage(
  response: Response,
  path: string,
): Promise<string> {
  const fallback = `Request to ${path} failed with status ${response.status} ${response.statusText}.`;
  try {
    const data: unknown = await response.clone().json();
    if (data && typeof data === "object" && "detail" in data) {
      const detail = (data as { detail: unknown }).detail;
      if (typeof detail === "string" && detail.length > 0) {
        return `${response.status}: ${detail}`;
      }
    }
  } catch {
    // Body was not JSON; fall through to the generic message.
  }
  return fallback;
}

// ---------------------------------------------------------------------------
// Public API functions
// ---------------------------------------------------------------------------

/**
 * Fetch a single error by its slug.
 * Returns `null` when the error does not exist (HTTP 404); throws
 * {@link ApiError} for any other failure.
 */
export async function getErrorBySlug(
  slug: string,
  options: RequestOptions = {},
): Promise<ErrorDetail | null> {
  try {
    return await request<ErrorDetail>(
      `/api/errors/${encodeURIComponent(slug)}`,
      options,
    );
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

/** Run a full-text search against the error catalogue. */
export async function searchErrors(
  query: string,
  limit?: number,
  options: RequestOptions = {},
): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query });
  if (typeof limit === "number") {
    params.set("limit", String(limit));
  }
  return request<SearchResponse>(`/api/search?${params.toString()}`, options);
}

/** Fetch typeahead suggestions for a partial query. */
export async function autocomplete(
  query: string,
  limit?: number,
  options: RequestOptions = {},
): Promise<AutocompleteResponse> {
  const params = new URLSearchParams({ q: query });
  if (typeof limit === "number") {
    params.set("limit", String(limit));
  }
  return request<AutocompleteResponse>(
    `/api/autocomplete?${params.toString()}`,
    options,
  );
}

/** List error summaries with pagination. */
export async function listErrors(
  limit?: number,
  offset?: number,
  options: RequestOptions = {},
): Promise<ErrorSummary[]> {
  const params = new URLSearchParams();
  if (typeof limit === "number") {
    params.set("limit", String(limit));
  }
  if (typeof offset === "number") {
    params.set("offset", String(offset));
  }
  const qs = params.toString();
  const path = qs.length > 0 ? `/api/errors?${qs}` : "/api/errors";
  return request<ErrorSummary[]>(path, options);
}

/** Create a new error document with its root causes and verified fixes. */
export async function createError(
  payload: ErrorCreate,
  options: RequestOptions = {},
): Promise<ErrorDetail> {
  return request<ErrorDetail>("/api/errors", {
    ...options,
    method: "POST",
    body: payload,
  });
}
