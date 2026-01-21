export type RequestOptions = {
  method?: string;
  body?: unknown;
  headers?: Record<string, string>;
  mockPath?: string;
  skipAuth?: boolean;
  signal?: AbortSignal;
};

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

function buildHeaders(baseHeaders: RequestOptions['headers'], includeAuth: boolean): Headers {
  const headers = new Headers(baseHeaders);
  headers.set('Accept', headers.get('Accept') ?? 'application/json');

  if (includeAuth && accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }

  return headers;
}

async function parseErrorMessage(response: Response): Promise<string> {
  try {
    const contentType = response.headers.get('content-type');
    if (contentType?.includes('application/json')) {
      const payload = (await response.json()) as { detail?: unknown; message?: unknown };
      const detail =
        typeof payload?.detail === 'string'
          ? payload.detail
          : typeof payload?.message === 'string'
            ? payload.message
            : null;
      if (detail) {
        return detail;
      }
    } else {
      const text = await response.text();
      if (text) {
        return text;
      }
    }
  } catch (error) {
    console.warn('Failed to parse API error response', error);
  }

  return `Request failed with status ${response.status}`;
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

    const message = await parseErrorMessage(response);
    throw new Error(message);
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
