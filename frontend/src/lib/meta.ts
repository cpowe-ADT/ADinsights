import apiClient, { appendQueryParams } from './apiClient';

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface MetaAccount {
  id: string;
  external_id: string;
  account_id: string;
  name: string;
  currency: string;
  status: string;
  business_name: string;
  metadata: Record<string, unknown>;
  created_time?: string | null;
  updated_time?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MetaCampaign {
  id: string;
  external_id: string;
  name: string;
  platform: string;
  status: string;
  objective: string;
  currency: string;
  account_external_id: string;
  ad_account_external_id?: string;
  metadata: Record<string, unknown>;
  created_time?: string | null;
  updated_time?: string | null;
  created_at: string;
  updated_at: string;
}

export interface MetaAdSet {
  id: string;
  external_id: string;
  name: string;
  status: string;
  bid_strategy: string;
  daily_budget: string;
  start_time?: string | null;
  end_time?: string | null;
  targeting: Record<string, unknown>;
  campaign_external_id: string;
  created_at: string;
  updated_at: string;
}

export interface MetaAd {
  id: string;
  external_id: string;
  name: string;
  status: string;
  creative: Record<string, unknown>;
  preview_url: string;
  adset_external_id: string;
  created_at: string;
  updated_at: string;
}

export interface MetaInsightRecord {
  id: string;
  external_id: string;
  date: string;
  source: string;
  level: 'account' | 'campaign' | 'adset' | 'ad';
  impressions: number;
  reach: number;
  clicks: number;
  spend: string;
  cpc: string;
  cpm: string;
  conversions: number;
  currency: string;
  actions: Array<Record<string, unknown>>;
  campaign_external_id?: string | null;
  adset_external_id?: string | null;
  ad_external_id?: string | null;
  account_external_id?: string | null;
  raw_payload: Record<string, unknown>;
  ingested_at: string;
  updated_at: string;
}

export type MetaListQuery = {
  page?: number;
  page_size?: number;
  search?: string;
  status?: string;
  since?: string;
  until?: string;
  account_id?: string;
  campaign_id?: string;
  adset_id?: string;
  ad_id?: string;
  level?: 'account' | 'campaign' | 'adset' | 'ad';
};

function withQuery(path: string, query?: MetaListQuery): string {
  if (!query) {
    return path;
  }
  return appendQueryParams(path, query);
}

export async function loadMetaAccounts(
  query?: MetaListQuery,
  signal?: AbortSignal,
): Promise<PaginatedResponse<MetaAccount>> {
  return apiClient.get<PaginatedResponse<MetaAccount>>(withQuery('/meta/accounts/', query), { signal });
}

export async function loadMetaCampaigns(
  query?: MetaListQuery,
  signal?: AbortSignal,
): Promise<PaginatedResponse<MetaCampaign>> {
  return apiClient.get<PaginatedResponse<MetaCampaign>>(withQuery('/meta/campaigns/', query), {
    signal,
  });
}

export async function loadMetaAdSets(
  query?: MetaListQuery,
  signal?: AbortSignal,
): Promise<PaginatedResponse<MetaAdSet>> {
  return apiClient.get<PaginatedResponse<MetaAdSet>>(withQuery('/meta/adsets/', query), { signal });
}

export async function loadMetaAds(
  query?: MetaListQuery,
  signal?: AbortSignal,
): Promise<PaginatedResponse<MetaAd>> {
  return apiClient.get<PaginatedResponse<MetaAd>>(withQuery('/meta/ads/', query), { signal });
}

export async function loadMetaInsights(
  query?: MetaListQuery,
  signal?: AbortSignal,
): Promise<PaginatedResponse<MetaInsightRecord>> {
  return apiClient.get<PaginatedResponse<MetaInsightRecord>>(withQuery('/meta/insights/', query), {
    signal,
  });
}
