/**
 * Base URL of the RepoPilot API. Empty means same origin, which works with the Vite dev and
 * preview proxy (see vite.config.ts). Set VITE_API_BASE_URL to call the API directly.
 */
export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '');

/** A failed API call. `status` is 0 when the API could not be reached at all. */
export class ApiError extends Error {
  readonly status: number;
  /** The backend's `detail` message when it is a plain, safe-to-show string. */
  readonly detail: string | null;
  readonly retryAfterSeconds: number | null;

  constructor(status: number, detail: string | null, retryAfterSeconds: number | null = null) {
    super(detail ?? `Request failed with status ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

type QueryValue = string | number | boolean | null | undefined;

interface RequestOptions {
  method?: 'GET' | 'POST';
  query?: Record<string, QueryValue>;
  body?: unknown;
  signal?: AbortSignal;
}

export function buildUrl(path: string, query?: Record<string, QueryValue>): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== '') params.set(key, String(value));
  }
  const search = params.toString();
  return `${API_BASE_URL}${path}${search ? `?${search}` : ''}`;
}

export async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = 'GET', query, body, signal } = options;
  let response: Response;
  try {
    response = await fetch(buildUrl(path, query), {
      method,
      signal,
      headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError(0, null);
  }

  if (!response.ok) {
    throw new ApiError(
      response.status,
      await readDetail(response),
      parseRetryAfter(response.headers.get('Retry-After')),
    );
  }
  return (await response.json()) as T;
}

const MAX_DETAIL_LENGTH = 300;

/**
 * Backend errors look like `{"detail": "..."}` with fixed, user-safe messages. Anything else
 * (validation arrays, HTML error pages from a proxy, huge bodies) is discarded.
 */
async function readDetail(response: Response): Promise<string | null> {
  try {
    const data: unknown = await response.json();
    if (typeof data === 'object' && data !== null && 'detail' in data) {
      const { detail } = data as { detail: unknown };
      if (
        typeof detail === 'string' &&
        detail.length <= MAX_DETAIL_LENGTH &&
        !/[<>]/.test(detail)
      ) {
        return detail;
      }
    }
  } catch {
    // Not JSON (e.g. an HTML error page): ignore the body.
  }
  return null;
}

function parseRetryAfter(value: string | null): number | null {
  if (value === null || !/^\d+$/.test(value)) return null;
  return Number(value);
}
