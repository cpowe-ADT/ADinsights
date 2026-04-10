import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
  patch: vi.fn(),
  delete: vi.fn(),
}));

vi.mock('./apiClient', () => ({
  __esModule: true,
  default: apiClientMock,
  appendQueryParams: (path: string, params?: Record<string, unknown>) => {
    if (!params) return path;
    const qs = Object.entries(params)
      .filter(([, v]) => v !== undefined)
      .map(([k, v]) => `${k}=${v}`)
      .join('&');
    return qs ? `${path}?${qs}` : path;
  },
}));

import {
  createReport,
  fetchDashboardLibrary,
  fetchHealthOverview,
  fetchSyncHealth,
  getAlert,
  getDashboardDefinition,
  getReport,
  listAlerts,
  listReports,
  listSummaries,
} from './phase2Api';

describe('phase2Api', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  describe('fetchDashboardLibrary', () => {
    it('normalizes response with systemTemplates and savedDashboards', async () => {
      apiClientMock.get.mockResolvedValue({
        generatedAt: '2026-04-10',
        systemTemplates: [
          { id: 't1', name: 'Template', template_key: 'meta_campaign_performance', type: 'System', owner: 'System', tags: [], description: '', route: '/a' },
        ],
        savedDashboards: [],
      });

      const result = await fetchDashboardLibrary();
      expect(result.systemTemplates).toHaveLength(1);
      expect(result.systemTemplates[0].name).toBe('Template');
    });
  });

  describe('getDashboardDefinition', () => {
    it('fetches by id', async () => {
      apiClientMock.get.mockResolvedValue({ id: 'd1', name: 'Test' });
      const result = await getDashboardDefinition('d1');
      expect(result.id).toBe('d1');
    });
  });

  describe('listReports', () => {
    it('handles array response', async () => {
      apiClientMock.get.mockResolvedValue([]);
      const result = await listReports();
      expect(result).toEqual([]);
    });
  });

  describe('createReport', () => {
    it('posts report data', async () => {
      apiClientMock.post.mockResolvedValue({ id: 'r1', name: 'New Report' });
      const result = await createReport({ name: 'New Report', description: '' });
      expect(apiClientMock.post).toHaveBeenCalled();
      expect(result.name).toBe('New Report');
    });
  });

  describe('getReport', () => {
    it('fetches by id', async () => {
      apiClientMock.get.mockResolvedValue({ id: 'r1', name: 'Report' });
      const result = await getReport('r1');
      expect(result.id).toBe('r1');
    });
  });

  describe('listAlerts', () => {
    it('handles array response', async () => {
      apiClientMock.get.mockResolvedValue([{ id: 'a1' }]);
      const result = await listAlerts();
      expect(result).toHaveLength(1);
    });
  });

  describe('getAlert', () => {
    it('fetches by id', async () => {
      apiClientMock.get.mockResolvedValue({ id: 'a1', name: 'Alert' });
      const result = await getAlert('a1');
      expect(result.id).toBe('a1');
    });
  });

  describe('listSummaries', () => {
    it('handles array response', async () => {
      apiClientMock.get.mockResolvedValue([]);
      const result = await listSummaries();
      expect(result).toEqual([]);
    });
  });

  describe('fetchSyncHealth', () => {
    it('returns sync health data', async () => {
      const mockData = { generated_at: '2026-04-10', stale_after_minutes: 60, counts: { total: 0, fresh: 0, stale: 0, failed: 0, missing: 0, inactive: 0 }, rows: [] };
      apiClientMock.get.mockResolvedValue(mockData);
      const result = await fetchSyncHealth();
      expect(result.rows).toEqual([]);
    });
  });

  describe('fetchHealthOverview', () => {
    it('returns health overview data', async () => {
      const mockData = { generated_at: '2026-04-10', overall_status: 'ok', cards: [] };
      apiClientMock.get.mockResolvedValue(mockData);
      const result = await fetchHealthOverview();
      expect(result.overall_status).toBe('ok');
    });
  });
});
