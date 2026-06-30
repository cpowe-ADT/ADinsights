import { appendQueryParams, get, patch, post, type QueryParams } from './apiClient';

export type GoogleAdsListResponse<T> = {
  count: number;
  results: T[];
  page?: number;
  page_size?: number;
  num_pages?: number;
  source_engine?: string;
};

export type GoogleAdsExecutiveResponse = {
  window: {
    start_date: string;
    end_date: string;
    compare_start_date: string;
    compare_end_date: string;
  };
  metrics: Record<string, number>;
  comparison: Record<string, number>;
  pacing: Record<string, number | null>;
  trend: Array<Record<string, number | string>>;
  movers: Array<Record<string, number | string>>;
  data_freshness_ts: string | null;
  source_engine: string;
};

export type GoogleAdsWorkspaceSummaryResponse = GoogleAdsExecutiveResponse & {
  alerts_summary: {
    overspend_risk: boolean;
    underdelivery: boolean;
    spend_spike: boolean;
    conversion_drop: boolean;
  };
  governance_summary: {
    recent_changes_7d: number;
    active_recommendations: number;
    disapproved_ads: number;
  };
  top_insights: Array<{
    id: string;
    title: string;
    detail: string;
  }>;
  workspace_generated_at: string;
};

export type GoogleAdsExportJob = {
  id: string;
  name: string;
  export_format: 'csv' | 'pdf';
  status: 'queued' | 'running' | 'completed' | 'failed';
  artifact_path: string;
  error_message: string;
  metadata: Record<string, unknown>;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
  download_url?: string | null;
};

export type GoogleAdsSavedView = {
  id: string;
  name: string;
  description: string;
  filters: Record<string, unknown>;
  columns: string[];
  is_shared: boolean;
  created_at: string;
  updated_at: string;
};

/**
 * GA-B1: typed payload for the change-events endpoint. `next_cursor` is
 * the Phase B cursor token (string-encoded next page number) and is `null`
 * on the last page. Field is optional so older mock payloads keep typing.
 */
export type GoogleAdsChangeEventsPayload = {
  count: number;
  page?: number;
  page_size?: number;
  num_pages?: number;
  next_cursor?: string | null;
  results: Array<Record<string, unknown>>;
};

/**
 * GA-B2: response shape for the saved-view verify endpoint.
 */
export type GoogleAdsSavedViewVerifyResult = {
  id: string;
  name: string;
  drift: boolean;
  unknown_filter_keys: string[];
  unknown_columns: string[];
  checked_against_version: string;
};

function withQuery(path: string, params?: QueryParams): string {
  return params ? appendQueryParams(path, params) : path;
}

function ensureSavedViewsArray(
  payload: GoogleAdsSavedView[] | GoogleAdsListResponse<GoogleAdsSavedView>,
): GoogleAdsSavedView[] {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (payload && Array.isArray(payload.results)) {
    return payload.results;
  }
  return [];
}

export function fetchGoogleAdsExecutive(params?: QueryParams) {
  return get<GoogleAdsExecutiveResponse>(withQuery('/analytics/google-ads/executive/', params));
}

export function fetchGoogleAdsWorkspaceSummary(params?: QueryParams) {
  return get<GoogleAdsWorkspaceSummaryResponse>(
    withQuery('/analytics/google-ads/workspace/summary/', params),
  );
}

export function fetchGoogleAdsList<T>(endpoint: string, params?: QueryParams) {
  return get<GoogleAdsListResponse<T>>(withQuery(endpoint, params));
}

export function fetchGoogleAdsCampaignDetail(campaignId: string, params?: QueryParams) {
  return get<Record<string, unknown>>(
    withQuery(`/analytics/google-ads/campaigns/${encodeURIComponent(campaignId)}/`, params),
  );
}

export function fetchGoogleAdsExportStatus(jobId: string) {
  return get<GoogleAdsExportJob>(`/analytics/google-ads/exports/${encodeURIComponent(jobId)}/`);
}

export function createGoogleAdsExport(payload: {
  export_format: 'csv' | 'pdf';
  name?: string;
  filters?: Record<string, unknown>;
}) {
  return post<GoogleAdsExportJob>('/analytics/google-ads/exports/', payload);
}

export function fetchGoogleAdsSavedViews() {
  return get<GoogleAdsSavedView[] | GoogleAdsListResponse<GoogleAdsSavedView>>(
    '/analytics/google-ads/saved-views/',
  ).then(ensureSavedViewsArray);
}

export function updateGoogleAdsSavedView(
  id: string,
  payload: Partial<{
    name: string;
    description: string;
    filters: Record<string, unknown>;
    columns: string[];
    is_shared: boolean;
  }>,
) {
  return patch<GoogleAdsSavedView>(
    `/analytics/google-ads/saved-views/${encodeURIComponent(id)}/`,
    payload,
  );
}

export function createGoogleAdsSavedView(payload: {
  name: string;
  description?: string;
  filters?: Record<string, unknown>;
  columns?: string[];
  is_shared?: boolean;
}) {
  return post<GoogleAdsSavedView>('/analytics/google-ads/saved-views/', payload);
}

/**
 * GA-A2: dismiss a Google Ads recommendation. POST body is empty — the
 * action is a state toggle. Returns the updated recommendation row.
 * Idempotent on the backend; 404 when the id is outside the tenant scope.
 */
export function dismissGoogleAdsRecommendation(id: number) {
  return post<Record<string, unknown>>(
    `/analytics/google-ads/recommendations/${encodeURIComponent(String(id))}/dismiss/`,
    {},
  );
}

/**
 * GA-B1: fetch a single page of Google Ads change events. The page param is
 * used as the cursor token — the backend emits `next_cursor = str(page+1)`
 * while more pages remain. Returns the typed payload including
 * `next_cursor`.
 */
export function fetchGoogleAdsChangeEventsPage(params: {
  page: number;
  page_size?: number;
  start_date?: string;
  end_date?: string;
  customer_id?: string;
}) {
  const query: QueryParams = {
    page: params.page,
    page_size: params.page_size,
    start_date: params.start_date,
    end_date: params.end_date,
    customer_id: params.customer_id,
  };
  return get<GoogleAdsChangeEventsPayload>(
    withQuery('/analytics/google-ads/change-events/', query),
  );
}

/**
 * GA-B2: verify a saved view against the current backend vocabulary. The
 * backend returns a drift flag plus lists of any unknown filter keys /
 * column names, so the UI can surface a dismissible banner.
 */
export function verifyGoogleAdsSavedView(id: string) {
  return get<GoogleAdsSavedViewVerifyResult>(
    `/analytics/google-ads/saved-views/${encodeURIComponent(id)}/verify/`,
  );
}
