import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiClientMock = vi.hoisted(() => ({
  get: vi.fn(),
}));

vi.mock('./apiClient', () => ({
  __esModule: true,
  default: apiClientMock,
  ApiError: class extends Error {
    status: number;
    constructor(msg: string, status: number) {
      super(msg);
      this.status = status;
    }
  },
  appendQueryParams: (path: string, params: Record<string, unknown>) => {
    const qs = Object.entries(params)
      .map(([k, v]) => `${k}=${v}`)
      .join('&');
    return qs ? `${path}?${qs}` : path;
  },
  MOCK_ASSETS_ENABLED: false,
}));

vi.mock('./format', () => ({
  formatRelativeTime: () => '5 minutes ago',
}));

import { fetchRecentDashboards } from './recentDashboards';

describe('fetchRecentDashboards', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('returns parsed dashboards from API response', async () => {
    apiClientMock.get.mockResolvedValue([
      {
        id: '1',
        name: 'Test Dashboard',
        owner: 'Team A',
        last_viewed_at: '2026-04-10T12:00:00Z',
        href: '/dashboards/campaigns',
      },
    ]);

    const result = await fetchRecentDashboards(3);
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('Test Dashboard');
    expect(result[0].href).toBe('/dashboards/campaigns');
  });

  it('handles paginated response format', async () => {
    apiClientMock.get.mockResolvedValue({
      results: [
        {
          id: '2',
          name: 'Another Dashboard',
          owner: 'Team B',
          href: '/dashboards/budget',
        },
      ],
    });

    const result = await fetchRecentDashboards(3);
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('Another Dashboard');
  });

  it('filters out items without required fields', async () => {
    apiClientMock.get.mockResolvedValue([
      { id: '1', name: '', href: '/dashboards/campaigns' },
      { id: '2', name: 'Valid', href: '/dashboards/budget' },
    ]);

    const result = await fetchRecentDashboards(3);
    expect(result).toHaveLength(1);
    expect(result[0].name).toBe('Valid');
  });
});
