import { create } from 'zustand';

import { ApiError } from '../lib/apiClient';
import { toMetaPageDateParams } from '../lib/metaPageDateRange';
import {
  callbackMetaOAuth,
  listMetaMetrics,
  loadMetaPageOverview,
  loadMetaPagePosts,
  loadMetaPageTimeseries,
  loadMetaPages,
  loadMetaPostDetail,
  loadMetaPostTimeseries,
  META_OAUTH_FLOW_PAGE_INSIGHTS,
  META_OAUTH_FLOW_SESSION_KEY,
  refreshMetaPageInsights,
  selectMetaPage,
  startMetaOAuth,
  type MetaOverviewResponse,
  type MetaPagesResponse,
  type MetaPostDetailResponse,
  type MetaPostsResponse,
  type MetaMetricOption,
  type MetaTimeseriesResponse,
} from '../lib/metaPageInsights';

type AsyncStatus = 'idle' | 'loading' | 'loaded' | 'error';

type Filters = {
  datePreset: string;
  since: string;
  until: string;
  metric: string;
  period: string;
  showAllMetrics: boolean;
};

type PostsQuery = {
  q: string;
  mediaType: string;
  sort: string;
  metric: string;
  limit: number;
  offset: number;
};

type MetaPageInsightsState = {
  pagesStatus: AsyncStatus;
  oauthStatus: AsyncStatus;
  dashboardStatus: AsyncStatus;
  postsStatus: AsyncStatus;
  postStatus: AsyncStatus;
  postSeriesStatus: AsyncStatus;
  syncStatus: AsyncStatus;
  error?: string;
  pages: MetaPagesResponse['results'];
  missingRequiredPermissions: string[];
  selectedPageId: string;
  selectedPostId: string;
  filters: Filters;
  postsQuery: PostsQuery;
  overview: MetaOverviewResponse | null;
  timeseries: MetaTimeseriesResponse | null;
  posts: MetaPostsResponse | null;
  postDetail: MetaPostDetailResponse | null;
  postTimeseries: MetaTimeseriesResponse | null;
  metrics: {
    page: MetaMetricOption[];
    post: MetaMetricOption[];
  };
  setFilters: (value: Partial<Filters>) => void;
  setPostsQuery: (value: Partial<PostsQuery>) => void;
  setSelectedPageId: (pageId: string) => void;
  setSelectedPostId: (postId: string) => void;
  loadPages: () => Promise<void>;
  loadMetricRegistry: () => Promise<void>;
  connectOAuthStart: () => Promise<void>;
  connectOAuthCallback: (code: string, state: string) => Promise<void>;
  selectDefaultPage: (pageId: string) => Promise<void>;
  loadOverviewAndTimeseries: (pageId: string) => Promise<void>;
  loadTimeseries: (pageId: string) => Promise<void>;
  loadPosts: (pageId: string, overrides?: Partial<PostsQuery>) => Promise<void>;
  loadPostDetail: (postId: string) => Promise<void>;
  loadPostTimeseries: (postId: string) => Promise<void>;
  refreshPage: (pageId: string) => Promise<Record<string, string>>;
};

function classifyError(error: unknown, fallback: string): string {
  if (error instanceof ApiError) {
    return error.message || fallback;
  }
  if (error instanceof Error) {
    return error.message || fallback;
  }
  return fallback;
}

function setOAuthFlowMarker(flow: string): void {
  if (typeof window === 'undefined') {
    return;
  }
  window.sessionStorage.setItem(META_OAUTH_FLOW_SESSION_KEY, flow);
}

function clearOAuthFlowMarker(): void {
  if (typeof window === 'undefined') {
    return;
  }
  window.sessionStorage.removeItem(META_OAUTH_FLOW_SESSION_KEY);
}

export const useMetaPageInsightsStore = create<MetaPageInsightsState>((set, get) => ({
  pagesStatus: 'idle',
  oauthStatus: 'idle',
  dashboardStatus: 'idle',
  postsStatus: 'idle',
  postStatus: 'idle',
  postSeriesStatus: 'idle',
  syncStatus: 'idle',
  error: undefined,
  pages: [],
  missingRequiredPermissions: [],
  selectedPageId: '',
  selectedPostId: '',
  filters: {
    datePreset: 'last_28d',
    since: '',
    until: '',
    metric: 'page_post_engagements',
    period: 'day',
    showAllMetrics: false,
  },
  postsQuery: {
    q: '',
    mediaType: '',
    sort: 'created_desc',
    metric: 'post_media_view',
    limit: 50,
    offset: 0,
  },
  overview: null,
  timeseries: null,
  posts: null,
  postDetail: null,
  postTimeseries: null,
  metrics: {
    page: [],
    post: [],
  },
  setFilters: (value) => set((state) => ({ filters: { ...state.filters, ...value } })),
  setPostsQuery: (value) => set((state) => ({ postsQuery: { ...state.postsQuery, ...value } })),
  setSelectedPageId: (pageId) => set({ selectedPageId: pageId }),
  setSelectedPostId: (postId) => set({ selectedPostId: postId }),
  loadPages: async () => {
    set({ pagesStatus: 'loading', error: undefined });
    try {
      const payload = await loadMetaPages();
      const defaultPage = payload.results.find((page) => page.is_default) ?? payload.results[0] ?? null;
      set((state) => ({
        pagesStatus: 'loaded',
        pages: payload.results,
        selectedPageId: state.selectedPageId || defaultPage?.page_id || '',
      }));
    } catch (error) {
      set({ pagesStatus: 'error', error: classifyError(error, 'Unable to load Facebook Pages.') });
    }
  },
  loadMetricRegistry: async () => {
    try {
      const [page, post] = await Promise.all([
        listMetaMetrics({ level: 'PAGE' }),
        listMetaMetrics({ level: 'POST' }),
      ]);
      set({ metrics: { page: page.results ?? [], post: post.results ?? [] } });
    } catch {
      set({ metrics: { page: [], post: [] } });
    }
  },
  connectOAuthStart: async () => {
    set({ oauthStatus: 'loading', error: undefined });
    try {
      setOAuthFlowMarker(META_OAUTH_FLOW_PAGE_INSIGHTS);
      const payload = await startMetaOAuth();
      window.location.assign(payload.authorize_url);
    } catch (error) {
      clearOAuthFlowMarker();
      set({ oauthStatus: 'error', error: classifyError(error, 'Unable to start Meta OAuth.') });
    }
  },
  connectOAuthCallback: async (code, stateValue) => {
    set({ oauthStatus: 'loading', error: undefined });
    try {
      const payload = await callbackMetaOAuth(code, stateValue);
      set({
        oauthStatus: 'loaded',
        missingRequiredPermissions: payload.missing_required_permissions ?? [],
        selectedPageId: payload.default_page_id ?? get().selectedPageId,
      });
      await get().loadPages();
      clearOAuthFlowMarker();
    } catch (error) {
      clearOAuthFlowMarker();
      set({ oauthStatus: 'error', error: classifyError(error, 'Meta OAuth callback failed.') });
    }
  },
  selectDefaultPage: async (pageId) => {
    set({ selectedPageId: pageId, error: undefined });
    try {
      const response = await selectMetaPage(pageId);
      if (!response.selected) {
        throw new Error('Unable to select page.');
      }
      set((state) => ({
        selectedPageId: pageId,
        pages: state.pages.map((page) => ({
          ...page,
          is_default: page.page_id === pageId,
        })),
      }));
    } catch (error) {
      set({ error: classifyError(error, 'Unable to select page.') });
      throw error;
    }
  },
  loadOverviewAndTimeseries: async (pageId) => {
    const { filters } = get();
    set({ dashboardStatus: 'loading', error: undefined });
    try {
      const overviewParams = toMetaPageDateParams({
        datePreset: filters.datePreset,
        since: filters.since,
        until: filters.until,
      });
      const overview = await loadMetaPageOverview(pageId, overviewParams);
      const selectedMetric =
        filters.metric || overview.primary_metric || Object.keys(overview.daily_series)[0] || '';

      const timeseriesDateParams = toMetaPageDateParams({
        datePreset: filters.datePreset,
        since: overview.since || filters.since,
        until: overview.until || filters.until,
      });
      const timeseriesParams = {
        ...timeseriesDateParams,
        metric: selectedMetric,
        period: filters.period || 'day',
      };
      const timeseries = await loadMetaPageTimeseries(pageId, timeseriesParams);
      set({
        overview,
        timeseries,
        dashboardStatus: 'loaded',
        filters: {
          ...filters,
          metric: selectedMetric || filters.metric,
          since: overview.since || filters.since,
          until: overview.until || filters.until,
        },
      });
    } catch (error) {
      set({ dashboardStatus: 'error', error: classifyError(error, 'Unable to load page overview.') });
    }
  },
  loadTimeseries: async (pageId) => {
    const { filters, overview } = get();
    set({ dashboardStatus: 'loading', error: undefined });
    try {
      const timeseriesParams = {
        ...toMetaPageDateParams({
          datePreset: filters.datePreset,
          since: filters.since,
          until: filters.until,
        }),
        metric: filters.metric || overview?.primary_metric || 'page_post_engagements',
        period: filters.period || 'day',
      };
      const timeseries = await loadMetaPageTimeseries(pageId, timeseriesParams);
      set({ timeseries, dashboardStatus: 'loaded' });
    } catch (error) {
      set({ dashboardStatus: 'error', error: classifyError(error, 'Unable to load page timeseries.') });
    }
  },
  loadPosts: async (pageId, overrides) => {
    const { filters, postsQuery } = get();
    set({ postsStatus: 'loading', error: undefined });
    try {
      const nextQuery = { ...postsQuery, ...overrides };
      const params: Record<string, unknown> = {
        ...toMetaPageDateParams({
          datePreset: filters.datePreset,
          since: filters.since,
          until: filters.until,
        }),
        limit: nextQuery.limit,
        offset: nextQuery.offset,
        q: nextQuery.q || undefined,
        media_type: nextQuery.mediaType || undefined,
        sort: nextQuery.sort || undefined,
      };
      if (nextQuery.sort?.startsWith('metric_')) {
        params.sort_metric = nextQuery.metric || 'post_media_view';
      }
      const posts = await loadMetaPagePosts(pageId, params as never);
      set({ postsQuery: nextQuery, posts, postsStatus: 'loaded' });
    } catch (error) {
      set({ postsStatus: 'error', error: classifyError(error, 'Unable to load page posts.') });
    }
  },
  loadPostDetail: async (postId) => {
    set({ postStatus: 'loading', error: undefined });
    try {
      const postDetail = await loadMetaPostDetail(postId);
      set({ postDetail, postStatus: 'loaded' });
    } catch (error) {
      set({ postStatus: 'error', error: classifyError(error, 'Unable to load post details.') });
    }
  },
  loadPostTimeseries: async (postId) => {
    const { filters } = get();
    set({ postSeriesStatus: 'loading', error: undefined });
    try {
      const postTimeseries = await loadMetaPostTimeseries(postId, {
        metric: filters.metric,
        period: filters.period || 'lifetime',
        since: filters.since,
        until: filters.until,
      });
      set({ postTimeseries, postSeriesStatus: 'loaded' });
    } catch (error) {
      set({ postSeriesStatus: 'error', error: classifyError(error, 'Unable to load post timeseries.') });
    }
  },
  refreshPage: async (pageId) => {
    set({ syncStatus: 'loading', error: undefined });
    try {
      const response = await refreshMetaPageInsights(pageId, { mode: 'incremental' });
      set({ syncStatus: 'loaded' });
      return response.tasks;
    } catch (error) {
      set({ syncStatus: 'error', error: classifyError(error, 'Unable to trigger sync.') });
      throw error;
    }
  },
}));

export default useMetaPageInsightsStore;
