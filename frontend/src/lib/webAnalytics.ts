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

export interface SearchConsoleWebRow {
  date_day: string;
  site_url: string;
  country: string;
  device: string;
  query: string;
  page: string;
  clicks: number;
  impressions: number;
  ctr: number;
  position: number;
}

export interface SearchConsoleWebResponse {
  source: 'search_console';
  status: 'ok' | 'unavailable';
  count: number;
  rows: SearchConsoleWebRow[];
  detail?: string;
}

export function fetchSearchConsoleWebRows(params?: QueryParams) {
  return get<SearchConsoleWebResponse>(withQuery('/analytics/web/search-console/', params));
}
