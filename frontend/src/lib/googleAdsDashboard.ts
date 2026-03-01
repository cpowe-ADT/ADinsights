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

function withQuery(path: string, params?: QueryParams): string {
  return params ? appendQueryParams(path, params) : path;
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
  return get<GoogleAdsSavedView[]>('/analytics/google-ads/saved-views/');
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
  return patch<GoogleAdsSavedView>(`/analytics/google-ads/saved-views/${encodeURIComponent(id)}/`, payload);
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
