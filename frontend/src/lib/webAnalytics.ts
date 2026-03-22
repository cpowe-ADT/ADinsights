import { appendQueryParams, get, type QueryParams } from './apiClient';

export interface GoogleAnalyticsWebRow {
  tenant_id: string;
  date_day: string;
  property_id: string;
  channel_group: string;
  country: string;
  city: string;
  campaign_name: string;
  sessions: number;
  engaged_sessions: number;
  conversions: number;
  purchase_revenue: number;
  engagement_rate: number;
  conversion_rate: number;
}

export interface GoogleAnalyticsWebResponse {
  source: 'ga4';
  status: 'ok' | 'unavailable';
  count: number;
  rows: GoogleAnalyticsWebRow[];
  detail?: string;
}

function withQuery(path: string, params?: QueryParams): string {
  return params ? appendQueryParams(path, params) : path;
}

export function fetchGoogleAnalyticsWebRows(params?: QueryParams) {
  return get<GoogleAnalyticsWebResponse>(withQuery('/analytics/web/ga4/', params));
}
