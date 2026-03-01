import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../lib/apiClient';

const apiMocks = vi.hoisted(() => ({
  startMetaOAuth: vi.fn(),
  callbackMetaOAuth: vi.fn(),
  listMetaMetrics: vi.fn(),
  loadMetaPages: vi.fn(),
  loadMetaPageOverview: vi.fn(),
  loadMetaPagePosts: vi.fn(),
  loadMetaPageTimeseries: vi.fn(),
  loadMetaPostDetail: vi.fn(),
  loadMetaPostTimeseries: vi.fn(),
  refreshMetaPageInsights: vi.fn(),
  selectMetaPage: vi.fn(),
}));

vi.mock('../lib/metaPageInsights', () => ({
  META_OAUTH_FLOW_PAGE_INSIGHTS: 'page_insights',
  META_OAUTH_FLOW_SESSION_KEY: 'adinsights.meta.oauth.flow',
  startMetaOAuth: apiMocks.startMetaOAuth,
  callbackMetaOAuth: apiMocks.callbackMetaOAuth,
  listMetaMetrics: apiMocks.listMetaMetrics,
  loadMetaPages: apiMocks.loadMetaPages,
  loadMetaPageOverview: apiMocks.loadMetaPageOverview,
  loadMetaPagePosts: apiMocks.loadMetaPagePosts,
  loadMetaPageTimeseries: apiMocks.loadMetaPageTimeseries,
  loadMetaPostDetail: apiMocks.loadMetaPostDetail,
  loadMetaPostTimeseries: apiMocks.loadMetaPostTimeseries,
  refreshMetaPageInsights: apiMocks.refreshMetaPageInsights,
  selectMetaPage: apiMocks.selectMetaPage,
}));

describe('useMetaPageInsightsStore', () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    vi.resetModules();
  });

  it('loads pages and selects default page', async () => {
    apiMocks.loadMetaPages.mockResolvedValue({
      results: [
        { id: '1', page_id: 'page-1', name: 'Page 1', can_analyze: true, is_default: true },
        { id: '2', page_id: 'page-2', name: 'Page 2', can_analyze: true, is_default: false },
      ],
      count: 2,
    });
    const { default: useMetaPageInsightsStore } = await import('./useMetaPageInsightsStore');
    await useMetaPageInsightsStore.getState().loadPages();
    const state = useMetaPageInsightsStore.getState();
    expect(state.pagesStatus).toBe('loaded');
    expect(state.selectedPageId).toBe('page-1');
    expect(state.pages).toHaveLength(2);
  });

  it('sets dashboard state and derived timeseries on overview load', async () => {
    apiMocks.loadMetaPageOverview.mockResolvedValue({
      page_id: 'page-1',
      name: 'Page',
      date_preset: 'last_28d',
      since: '2026-01-01',
      until: '2026-01-28',
      last_synced_at: null,
      metric_availability: {
        page_post_engagements: { supported: true, last_checked_at: null, reason: '' },
      },
      kpis: [],
      daily_series: {
        page_post_engagements: [{ date: '2026-01-20', value: 10 }],
      },
      primary_metric: 'page_post_engagements',
    });
    apiMocks.loadMetaPageTimeseries.mockResolvedValue({
      page_id: 'page-1',
      metric: 'page_post_engagements',
      resolved_metric: 'page_post_engagements',
      period: 'day',
      metric_availability: {
        page_post_engagements: { supported: true, last_checked_at: null, reason: '' },
      },
      points: [{ end_time: '2026-01-20T00:00:00Z', value: 10 }],
    });

    const { default: useMetaPageInsightsStore } = await import('./useMetaPageInsightsStore');
    await useMetaPageInsightsStore.getState().loadOverviewAndTimeseries('page-1');
    const state = useMetaPageInsightsStore.getState();
    expect(state.dashboardStatus).toBe('loaded');
    expect(state.timeseries?.points).toHaveLength(1);
    expect(state.filters.metric).toBe('page_post_engagements');
  });

  it('sets sync status and exposes task map when triggering sync', async () => {
    apiMocks.refreshMetaPageInsights.mockResolvedValue({
      page_id: 'page-1',
      tasks: { sync_page_insights: 'task-1', sync_post_insights: 'task-2' },
    });
    const { default: useMetaPageInsightsStore } = await import('./useMetaPageInsightsStore');
    const result = await useMetaPageInsightsStore.getState().refreshPage('page-1');
    const state = useMetaPageInsightsStore.getState();
    expect(state.syncStatus).toBe('loaded');
    expect(result.sync_page_insights).toBe('task-1');
  });

  it('captures errors on posts load', async () => {
    apiMocks.loadMetaPagePosts.mockRejectedValue(new ApiError('Forbidden', 403, { detail: 'Forbidden' }));
    const { default: useMetaPageInsightsStore } = await import('./useMetaPageInsightsStore');
    await useMetaPageInsightsStore.getState().loadPosts('page-1', { offset: 0 });
    const state = useMetaPageInsightsStore.getState();
    expect(state.postsStatus).toBe('error');
    expect(state.error).toContain('Forbidden');
  });

  it('persists default page selection through API', async () => {
    apiMocks.loadMetaPages.mockResolvedValue({
      results: [{ id: '1', page_id: 'page-1', name: 'Page 1', can_analyze: true, is_default: true }],
      count: 1,
    });
    apiMocks.selectMetaPage.mockResolvedValue({ page_id: 'page-1', selected: true });
    const { default: useMetaPageInsightsStore } = await import('./useMetaPageInsightsStore');

    await useMetaPageInsightsStore.getState().loadPages();
    await useMetaPageInsightsStore.getState().selectDefaultPage('page-1');

    expect(apiMocks.selectMetaPage).toHaveBeenCalledWith('page-1');
    expect(useMetaPageInsightsStore.getState().selectedPageId).toBe('page-1');
  });
});
