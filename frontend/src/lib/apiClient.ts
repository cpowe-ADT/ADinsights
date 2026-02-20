export type RequestOptions = {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  mockPath?: string;
  skipAuth?: boolean;
  signal?: AbortSignal;
};

export type QueryParamValue = string | number | boolean | null | undefined;
export type QueryParams = Record<string, QueryParamValue>;

export type ApiErrorPayload = {
  detail?: string;
  message?: string;
  errors?: string[];
  warnings?: string[];
};

export class ApiError extends Error {
  status: number;
  payload?: ApiErrorPayload;

  constructor(message: string, status: number, payload?: ApiErrorPayload) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.payload = payload;
  }
}

const resolvedEnv = typeof import.meta !== 'undefined' ? import.meta.env : undefined;
const resolvedProcessEnv = typeof process !== 'undefined' ? process.env : undefined;

export const API_BASE_URL = resolvedEnv?.VITE_API_BASE_URL ?? '/api';

function resolveBooleanFlag(value: unknown, defaultValue: boolean): boolean {
  if (typeof value !== 'string') {
    return defaultValue;
  }

  const normalized = value.trim().toLowerCase();
  if (['1', 'true', 'yes', 'y', 'on'].includes(normalized)) {
    return true;
  }
  if (['0', 'false', 'no', 'n', 'off'].includes(normalized)) {
    return false;
  }

  return defaultValue;
}

const mockModeEnv = resolvedProcessEnv?.VITE_MOCK_MODE ?? resolvedEnv?.VITE_MOCK_MODE;
const mockAssetsEnv = resolvedProcessEnv?.VITE_MOCK_ASSETS ?? resolvedEnv?.VITE_MOCK_ASSETS;

export const MOCK_MODE = resolveBooleanFlag(mockModeEnv, false);
export const MOCK_ASSETS_ENABLED = resolveBooleanFlag(mockAssetsEnv, MOCK_MODE);

type RefreshHandler = () => Promise<string | undefined>;
type UnauthorizedHandler = () => void;

let accessToken: string | undefined;
let refreshHandler: RefreshHandler | undefined;
let unauthorizedHandler: UnauthorizedHandler | undefined;

export function setAccessToken(token?: string): void {
  accessToken = token;
}

export function setRefreshHandler(handler?: RefreshHandler): void {
  refreshHandler = handler;
}

export function setUnauthorizedHandler(handler?: UnauthorizedHandler): void {
  unauthorizedHandler = handler;
}

function resolveUrl(path: string, mockPath?: string): string {
  if (MOCK_ASSETS_ENABLED && mockPath) {
    return mockPath;
  }

  if (path.startsWith('http://') || path.startsWith('https://')) {
    return path;
  }

  return `${API_BASE_URL.replace(/\/$/, '')}/${path.replace(/^\//, '')}`;
}

export function appendQueryParams(path: string, params: QueryParams): string {
  const [base, query] = path.split('?');
  const searchParams = new URLSearchParams(query ?? '');
  Object.entries(params).forEach(([key, value]) => {
    if (typeof value === 'string') {
      const trimmed = value.trim();
      if (trimmed) {
        searchParams.set(key, trimmed);
      }
      return;
    }
    if (typeof value === 'number' && Number.isFinite(value)) {
      searchParams.set(key, String(value));
      return;
    }
    if (typeof value === 'boolean') {
      searchParams.set(key, value ? 'true' : 'false');
    }
  });
  const serialized = searchParams.toString();
  return serialized ? `${base}?${serialized}` : base;
}

function buildHeaders(baseHeaders: RequestOptions['headers'], includeAuth: boolean): Headers {
  const headers = new Headers(baseHeaders);
  headers.set('Accept', headers.get('Accept') ?? 'application/json');

  if (includeAuth && accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }

  return headers;
}

async function parseErrorResponse(
  response: Response,
): Promise<{ message: string; payload?: ApiErrorPayload }> {
  const fallbackMessage =
    response.status >= 500
      ? `Server error (${response.status}). Please check backend logs.`
      : `Request failed with status ${response.status}`;
  try {
    const contentType = response.headers.get('content-type');
    if (contentType?.includes('application/json')) {
      const payload = (await response.json()) as ApiErrorPayload;
      const detail = typeof payload?.detail === 'string' ? payload.detail : null;
      const message = typeof payload?.message === 'string' ? payload.message : detail;
      if (message) {
        return { message, payload };
      }
      return { message: fallbackMessage, payload };
    } else {
      const text = await response.text();
      if (text) {
        if (response.status >= 500) {
          return { message: fallbackMessage };
        }
        return { message: text };
      }
    }
  } catch (error) {
    console.warn('Failed to parse API error response', error);
  }

  return { message: fallbackMessage };
}

async function requestInternal<T>(
  path: string,
  { method = 'GET', body, headers, mockPath, skipAuth, signal }: RequestOptions = {},
  attempt = 0,
): Promise<T> {
  const isMockRequest = Boolean(MOCK_MODE && mockPath);
  const url = resolveUrl(path, mockPath);
  const includeAuth = !isMockRequest && !skipAuth;
  const requestHeaders = buildHeaders(headers, includeAuth);

  let requestBody = body;
  if (
    typeof requestBody !== 'undefined' &&
    !(requestBody instanceof FormData) &&
    typeof requestBody !== 'string'
  ) {
    requestHeaders.set('Content-Type', requestHeaders.get('Content-Type') ?? 'application/json');
    requestBody = JSON.stringify(requestBody);
  }

  const response = await fetch(url, {
    method,
    headers: requestHeaders,
    body: requestBody as BodyInit | null | undefined,
    credentials: 'include',
    signal,
  });

  if (!response.ok) {
    if (response.status === 401 && includeAuth) {
      if (refreshHandler && attempt === 0) {
        try {
          const refreshedToken = await refreshHandler();
          if (refreshedToken) {
            return requestInternal<T>(
              path,
              { method, body, headers, mockPath, skipAuth, signal },
              attempt + 1,
            );
          }
        } catch (refreshError) {
          console.error('Token refresh failed', refreshError);
        }
      }
      unauthorizedHandler?.();
    }

    const { message, payload } = await parseErrorResponse(response);
    throw new ApiError(message, response.status, payload);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const contentType = response.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    return (await response.json()) as T;
  }

  return (await response.text()) as unknown as T;
}

export async function request<T>(path: string, options?: RequestOptions): Promise<T> {
  return requestInternal<T>(path, options);
}

export async function get<T>(
  path: string,
  options?: Omit<RequestOptions, 'method' | 'body'>,
): Promise<T> {
  return requestInternal<T>(path, { ...options, method: 'GET' });
}

export async function post<T>(
  path: string,
  body?: unknown,
  options?: Omit<RequestOptions, 'method' | 'body'>,
): Promise<T> {
  return requestInternal<T>(path, { ...options, body, method: 'POST' });
}

export async function patch<T>(
  path: string,
  body?: unknown,
  options?: Omit<RequestOptions, 'method' | 'body'>,
): Promise<T> {
  return requestInternal<T>(path, { ...options, body, method: 'PATCH' });
}

export async function del<T>(
  path: string,
  options?: Omit<RequestOptions, 'method' | 'body'>,
): Promise<T> {
  return requestInternal<T>(path, { ...options, method: 'DELETE' });
}

const apiClient = {
  request,
  get,
  post,
  patch,
  delete: del,
  setAccessToken,
  setRefreshHandler,
  setUnauthorizedHandler,
  MOCK_MODE,
  API_BASE_URL,
};

export default apiClient;
