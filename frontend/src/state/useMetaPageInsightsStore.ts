import { create } from 'zustand';

import { ApiError } from '../lib/apiClient';
import {
  callbackMetaOAuth,
  loadMetaPageOverview,
  loadMetaPagePosts,
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
  overview: MetaOverviewResponse | null;
  timeseries: MetaTimeseriesResponse | null;
  posts: MetaPostsResponse | null;
  postDetail: MetaPostDetailResponse | null;
  postTimeseries: MetaTimeseriesResponse | null;
  setFilters: (value: Partial<Filters>) => void;
  setSelectedPageId: (pageId: string) => void;
  setSelectedPostId: (postId: string) => void;
  loadPages: () => Promise<void>;
  connectOAuthStart: () => Promise<void>;
  connectOAuthCallback: (code: string, state: string) => Promise<void>;
  selectDefaultPage: (pageId: string) => Promise<void>;
  loadOverviewAndTimeseries: (pageId: string) => Promise<void>;
  loadPosts: (pageId: string) => Promise<void>;
  loadPostDetail: (postId: string) => Promise<void>;
  loadPostTimeseries: (postId: string) => Promise<void>;
  refreshPage: (pageId: string) => Promise<Record<string, string>>;
};

function formatDate(value: Date): string {
  return value.toISOString().slice(0, 10);
}

function defaultDateRange(): { since: string; until: string } {
  const until = new Date();
  until.setDate(until.getDate() - 1);
  const since = new Date(until);
  since.setDate(until.getDate() - 27);
  return { since: formatDate(since), until: formatDate(until) };
}

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

const defaultRange = defaultDateRange();

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
    since: defaultRange.since,
    until: defaultRange.until,
    metric: 'page_post_engagements',
    period: 'day',
    showAllMetrics: false,
  },
  overview: null,
  timeseries: null,
  posts: null,
  postDetail: null,
  postTimeseries: null,
  setFilters: (value) => set((state) => ({ filters: { ...state.filters, ...value } })),
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
      const overview = await loadMetaPageOverview(pageId, {
        date_preset: filters.datePreset,
        since: filters.since,
        until: filters.until,
      });
      const selectedMetric = filters.metric || overview.primary_metric || Object.keys(overview.daily_series)[0] || '';
      const series = overview.daily_series[selectedMetric] ?? [];
      const points = series.map((point) => ({
        end_time: `${point.date}T00:00:00Z`,
        value: point.value,
      }));
      const timeseries: MetaTimeseriesResponse = {
        page_id: pageId,
        metric: selectedMetric,
        period: 'day',
        metric_availability: overview.metric_availability,
        points,
      };
      set({
        overview,
        timeseries,
        dashboardStatus: 'loaded',
        filters: { ...filters, metric: selectedMetric || filters.metric },
      });
    } catch (error) {
      set({ dashboardStatus: 'error', error: classifyError(error, 'Unable to load page overview.') });
    }
  },
  loadPosts: async (pageId) => {
    const { filters } = get();
    set({ postsStatus: 'loading', error: undefined });
    try {
      const posts = await loadMetaPagePosts(pageId, {
        date_preset: filters.datePreset,
        since: filters.since,
        until: filters.until,
      });
      set({ posts, postsStatus: 'loaded' });
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
