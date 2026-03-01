import { beforeEach, describe, expect, it, vi } from 'vitest';

const apiMocks = vi.hoisted(() => ({
  get: vi.fn(),
  post: vi.fn(),
}));

vi.mock('./apiClient', () => ({
  default: {
    get: apiMocks.get,
    post: apiMocks.post,
  },
  appendQueryParams: (path: string, params: Record<string, string>) => {
    const search = new URLSearchParams(params).toString();
    return search ? `${path}?${search}` : path;
  },
}));

describe('metaPageInsights client', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads pages from new meta endpoint', async () => {
    apiMocks.get.mockResolvedValue({ results: [], count: 0 });
    const { loadMetaPages } = await import('./metaPageInsights');
    await loadMetaPages();
    expect(apiMocks.get).toHaveBeenCalledWith('/meta/pages/');
  });

  it('starts meta oauth with runtime context payload', async () => {
    apiMocks.post.mockResolvedValue({
      authorize_url: 'https://facebook.com/dialog/oauth',
      state: 'state',
      redirect_uri: 'http://localhost:5175/dashboards/data-sources',
    });
    const { startMetaOAuth } = await import('./metaPageInsights');
    await startMetaOAuth();
    expect(apiMocks.post).toHaveBeenCalledWith(
      '/meta/connect/start/',
      expect.objectContaining({
        runtime_context: expect.objectContaining({
          client_origin: expect.any(String),
        }),
      }),
    );
  });

  it('loads overview with date preset query params', async () => {
    apiMocks.get.mockResolvedValue({
      page_id: '1',
      name: 'Page',
      date_preset: 'last_28d',
      since: '2026-01-01',
      until: '2026-01-28',
      last_synced_at: null,
      metric_availability: {
        page_post_engagements: { supported: false, last_checked_at: null, reason: 'Not available for this Page' },
      },
      kpis: [],
      daily_series: {},
      primary_metric: null,
    });
    const { loadMetaPageOverview } = await import('./metaPageInsights');
    const payload = await loadMetaPageOverview('123', { date_preset: 'last_28d' });
    expect(apiMocks.get).toHaveBeenCalledWith('/meta/pages/123/overview/?date_preset=last_28d');
    expect(payload.metric_availability.page_post_engagements.supported).toBe(false);
  });

  it('triggers sync from new endpoint', async () => {
    apiMocks.post.mockResolvedValue({ page_id: '123', tasks: { sync_page_insights: 'task-1' } });
    const { refreshMetaPageInsights } = await import('./metaPageInsights');
    const payload = await refreshMetaPageInsights('123', { mode: 'incremental' });
    expect(apiMocks.post).toHaveBeenCalledWith('/meta/pages/123/sync/', { mode: 'incremental' });
    expect(payload.tasks.sync_page_insights).toBe('task-1');
  });

  it('persists selected default page through integrations endpoint', async () => {
    apiMocks.post.mockResolvedValue({ page_id: '123', selected: true });
    const { selectMetaPage } = await import('./metaPageInsights');
    await selectMetaPage('123');
    expect(apiMocks.post).toHaveBeenCalledWith('/integrations/meta/pages/123/select/', {});
  });
});
