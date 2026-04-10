import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('./apiClient', () => ({
  __esModule: true,
  default: apiClientMock,
  get: apiClientMock.get,
  appendQueryParams: (path: string, params?: Record<string, unknown>) => {
    if (!params) return path;
    const qs = Object.entries(params)
      .map(([k, v]) => `${k}=${v}`)
      .join('&');
    return qs ? `${path}?${qs}` : path;
  },
}));

import { fetchGoogleAnalyticsWebRows, fetchSearchConsoleWebRows } from './webAnalytics';

describe('webAnalytics', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('fetchGoogleAnalyticsWebRows', () => {
    it('calls the GA4 endpoint', async () => {
      const mockResponse = { source: 'ga4', status: 'ok', count: 0, rows: [] };
      apiClientMock.get.mockResolvedValue(mockResponse);

      const result = await fetchGoogleAnalyticsWebRows();
      expect(apiClientMock.get).toHaveBeenCalledWith('/analytics/web/ga4/');
      expect(result).toEqual(mockResponse);
    });
  });

  describe('fetchSearchConsoleWebRows', () => {
    it('calls the search console endpoint', async () => {
      const mockResponse = { source: 'search_console', status: 'ok', count: 0, rows: [] };
      apiClientMock.get.mockResolvedValue(mockResponse);

      const result = await fetchSearchConsoleWebRows();
      expect(apiClientMock.get).toHaveBeenCalledWith('/analytics/web/search-console/');
      expect(result).toEqual(mockResponse);
    });
  });
});
