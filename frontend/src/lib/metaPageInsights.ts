import apiClient, { appendQueryParams, type QueryParams } from './apiClient';

export type MetricStatus = 'ACTIVE' | 'DEPRECATED' | 'INVALID' | 'UNKNOWN';
export const META_OAUTH_FLOW_SESSION_KEY = 'adinsights.meta.oauth.flow';
export const META_OAUTH_FLOW_PAGE_INSIGHTS = 'page_insights';

export interface MetricAvailabilityEntry {
  supported: boolean;
  status?: MetricStatus;
  last_checked_at: string | null;
  reason: string;
}

export interface MetaPageRecord {
  id: string;
  page_id: string;
  name: string;
  category?: string;
  can_analyze: boolean;
  is_default: boolean;
  tasks?: string[];
  perms?: string[];
  last_synced_at?: string | null;
  last_posts_synced_at?: string | null;
}

export interface MetaOAuthCallbackResponse {
  connection_id?: string;
  pages?: MetaPageRecord[];
  default_page_id?: string | null;
  missing_required_permissions?: string[];
  oauth_connected_but_missing_permissions?: boolean;
  tasks?: Record<string, string>;
}

export interface MetaPagesResponse {
  results: MetaPageRecord[];
  count: number;
}

export interface MetaKpi {
  metric: string;
  resolved_metric: string;
  value: number | null;
  today_value: number | null;
}

export interface MetaMetricOption {
  metric_key: string;
  level: 'PAGE' | 'POST';
  status: MetricStatus;
  replacement_metric_key: string;
  title: string;
  description: string;
}

export interface MetaOverviewCard {
  metric_key: string;
  status: MetricStatus;
  replacement_metric_key: string;
  value_today: string | null;
  value_range: string | null;
}

export interface MetaOverviewResponse {
  page_id: string;
  name: string;
  date_preset: string;
  since: string;
  until: string;
  last_synced_at: string | null;
  metric_availability: Record<string, MetricAvailabilityEntry>;
  kpis: MetaKpi[];
  daily_series: Record<string, Array<{ date: string; value: number | null }>>;
  primary_metric: string | null;
  cards: MetaOverviewCard[];
  metrics: MetaMetricOption[];
}

export interface MetaPostListItem {
  post_id: string;
  page_id: string;
  created_time: string | null;
  permalink: string;
  permalink_url?: string;
  media_type: string;
  message_snippet: string;
  message?: string;
  metrics: Record<string, number | null>;
  last_synced_at: string | null;
}

export interface MetaPostsResponse {
  page_id: string;
  date_preset: string;
  since: string;
  until: string;
  last_synced_at: string | null;
  metric_availability: Record<string, MetricAvailabilityEntry>;
  results: MetaPostListItem[];
}

export interface MetaPostDetailResponse {
  post_id: string;
  page_id: string;
  created_time: string | null;
  permalink: string;
  media_type: string;
  message: string;
  last_synced_at: string | null;
  metric_availability: Record<string, MetricAvailabilityEntry>;
  metrics: Record<string, number | null>;
}

export interface MetaTimeseriesPoint {
  end_time: string;
  value: number | null;
}

export interface MetaTimeseriesResponse {
  post_id?: string;
  page_id?: string;
  metric: string;
  resolved_metric?: string;
  period?: string;
  metric_availability: Record<string, MetricAvailabilityEntry>;
  points: MetaTimeseriesPoint[];
}

export interface MetaSyncResponse {
  page_id: string;
  tasks: Record<string, string>;
}

function withQuery(path: string, params?: QueryParams): string {
  return params ? appendQueryParams(path, params) : path;
}

export async function startMetaOAuth(authType?: 'rerequest') {
  return apiClient.post<{ authorize_url: string; state: string; redirect_uri: string }>(
    '/meta/connect/start/',
    authType ? { auth_type: authType } : {},
  );
}

export async function callbackMetaOAuth(code: string, state: string): Promise<MetaOAuthCallbackResponse> {
  return apiClient.post<MetaOAuthCallbackResponse>('/meta/connect/callback/', { code, state });
}

export async function selectMetaPage(pageId: string): Promise<{ page_id: string; selected: boolean }> {
  return apiClient.post<{ page_id: string; selected: boolean }>(`/integrations/meta/pages/${pageId}/select/`, {});
}

export async function loadMetaPages(): Promise<MetaPagesResponse> {
  return apiClient.get<MetaPagesResponse>('/meta/pages/');
}

export async function loadMetaPageOverview(
  pageId: string,
  params?: { date_preset?: string; since?: string; until?: string },
): Promise<MetaOverviewResponse> {
  const payload = await apiClient.get<MetaOverviewResponse>(withQuery(`/meta/pages/${pageId}/overview/`, params));
  return {
    ...payload,
    cards: payload.cards ?? [],
    metrics: payload.metrics ?? [],
  };
}

export async function loadMetaPagePosts(
  pageId: string,
  params?: { date_preset?: string; since?: string; until?: string; limit?: number },
): Promise<MetaPostsResponse> {
  const payload = await apiClient.get<MetaPostsResponse>(withQuery(`/meta/pages/${pageId}/posts/`, params));
  return {
    ...payload,
    results: payload.results.map((item) => ({
      ...item,
      permalink_url: item.permalink_url ?? item.permalink,
      message: item.message ?? item.message_snippet,
    })),
  };
}

export async function loadMetaPostDetail(postId: string): Promise<MetaPostDetailResponse> {
  return apiClient.get<MetaPostDetailResponse>(`/meta/posts/${postId}/`);
}

export async function loadMetaPostTimeseries(
  postId: string,
  params: { metric: string; period?: string; since?: string; until?: string },
): Promise<MetaTimeseriesResponse> {
  return apiClient.get<MetaTimeseriesResponse>(withQuery(`/meta/posts/${postId}/timeseries/`, params));
}

export async function refreshMetaPageInsights(
  pageId: string,
  payload?: { mode?: 'incremental' | 'backfill' },
): Promise<MetaSyncResponse> {
  return apiClient.post<MetaSyncResponse>(`/meta/pages/${pageId}/sync/`, payload ?? {});
}
