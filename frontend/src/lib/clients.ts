/**
 * Sprint 7 of Client grouping: frontend API client for `/api/clients/*`.
 *
 * Shape parity with the Django serializers in `integrations/clients/api.py`.
 * Keep this module thin — it only types and wraps; business logic lives in
 * the routes that consume it.
 */

import { appendQueryParams, del, get, patch, post } from './apiClient';

export const PLATFORM_KEYS = [
  'google_ads',
  'meta_ads',
  'meta_page',
  'ga4',
  'search_console',
  'linkedin',
  'tiktok',
] as const;
export type PlatformKey = (typeof PLATFORM_KEYS)[number];

export interface ClientPlatformAccountRecord {
  id: string;
  platform: PlatformKey;
  external_id: string;
  display_name?: string | null;
  is_primary: boolean;
  created_at: string;
}

export interface ClientSummary {
  id: string;
  name: string;
  slug: string;
  industry?: string | null;
  parish?: string | null;
  is_active: boolean;
  /** per-platform attached-account counts keyed by platform. */
  platform_counts: Partial<Record<PlatformKey, number>>;
  updated_at: string;
}

export interface ClientDetail extends ClientSummary {
  platform_accounts: ClientPlatformAccountRecord[];
  created_at: string;
  notes?: string | null;
}

export interface ClientListResponse {
  count: number;
  next?: string | null;
  previous?: string | null;
  results: ClientSummary[];
}

export interface SuggestedAccount {
  platform: PlatformKey;
  external_id: string;
  display_name: string;
  /** 0.0–1.0 confidence from the name-match scorer. */
  score: number;
}

export interface SuggestedGroup {
  /** Deterministic hash of the match key for stable React keys. */
  group_id: string;
  proposed_name: string;
  proposed_slug: string;
  /** Accounts we propose linking together. */
  accounts: SuggestedAccount[];
  /** When non-null, an existing Client that partially matches. */
  existing_client_id?: string | null;
  existing_client_name?: string | null;
}

export interface SuggestResponse {
  threshold: number;
  groups: SuggestedGroup[];
}

export interface AttachRequest {
  platform: PlatformKey;
  external_id: string;
  display_name?: string;
  is_primary?: boolean;
}

export interface AttachConflictPayload {
  detail?: string;
  claimed_by?: {
    client_id: string;
    client_name: string;
  };
}

export interface SuggestApplyRequest {
  /** Provide one or the other — not both. */
  client_id?: string;
  create_name?: string;
  accounts: AttachRequest[];
}

export interface SuggestApplyResponse {
  client_id: string;
  attached: number;
  client: ClientDetail;
}

// ---------------------------------------------------------------------------

const BASE = '/clients/';

export async function listClients(params?: {
  search?: string;
  active?: boolean;
  page?: number;
  page_size?: number;
}): Promise<ClientListResponse> {
  const path = appendQueryParams(BASE, {
    search: params?.search,
    active: params?.active,
    page: params?.page,
    page_size: params?.page_size,
  });
  return get<ClientListResponse>(path);
}

export async function getClient(id: string): Promise<ClientDetail> {
  return get<ClientDetail>(`${BASE}${id}/`);
}

export async function createClient(body: {
  name: string;
  slug?: string;
  industry?: string;
  parish?: string;
  notes?: string;
}): Promise<ClientDetail> {
  return post<ClientDetail>(BASE, body);
}

export async function updateClient(
  id: string,
  body: Partial<{
    name: string;
    industry: string;
    parish: string;
    notes: string;
    is_active: boolean;
  }>,
): Promise<ClientDetail> {
  return patch<ClientDetail>(`${BASE}${id}/`, body);
}

export async function deleteClient(id: string): Promise<void> {
  await del<void>(`${BASE}${id}/`);
}

export async function listClientAccounts(
  id: string,
): Promise<ClientPlatformAccountRecord[]> {
  // Server returns a bare array for this endpoint.
  const data = await get<
    ClientPlatformAccountRecord[] | { results: ClientPlatformAccountRecord[] }
  >(`${BASE}${id}/accounts/`);
  return Array.isArray(data) ? data : data.results;
}

export async function attachClientAccount(
  id: string,
  body: AttachRequest,
): Promise<ClientPlatformAccountRecord> {
  return post<ClientPlatformAccountRecord>(`${BASE}${id}/accounts/`, body);
}

export async function detachClientAccount(
  clientId: string,
  accountId: string,
): Promise<void> {
  await del<void>(`${BASE}${clientId}/accounts/${accountId}/`);
}

export async function suggestClients(
  params?: { threshold?: number },
): Promise<SuggestResponse> {
  const path = appendQueryParams(`${BASE}suggest/`, {
    threshold: params?.threshold,
  });
  return get<SuggestResponse>(path);
}

export async function applySuggestion(
  body: SuggestApplyRequest,
): Promise<SuggestApplyResponse> {
  return post<SuggestApplyResponse>(`${BASE}suggest/apply/`, body);
}

// ---------------------------------------------------------------------------
// Sprint 9a/9b: persisted snapshot surfaced via a dashboard banner.

export type SnapshotTriggerReason = 'meta_sync' | 'google_sync' | 'manual';

export interface SnapshotSuggestionAccount {
  platform: PlatformKey;
  external_id: string;
  display_name: string;
}

export interface SnapshotSuggestion {
  proposed_name: string;
  normalized_name: string;
  existing_client_id: string | null;
  confidence: number;
  unclaimed_accounts: SnapshotSuggestionAccount[];
}

export interface ClientSuggestionSnapshot {
  id: string;
  trigger_reason: SnapshotTriggerReason;
  threshold: number;
  suggestion_count: number;
  payload: SnapshotSuggestion[];
  generated_at: string;
  acknowledged_at: string | null;
  is_unacknowledged: boolean;
}

export interface SnapshotResponse {
  snapshot: ClientSuggestionSnapshot | null;
}

export async function getClientSuggestionSnapshot(): Promise<SnapshotResponse> {
  return get<SnapshotResponse>(`${BASE}suggestions/latest/`);
}

export async function acknowledgeClientSuggestionSnapshot(): Promise<{
  snapshot: ClientSuggestionSnapshot;
}> {
  return post<{ snapshot: ClientSuggestionSnapshot }>(
    `${BASE}suggestions/latest/acknowledge/`,
    {},
  );
}

export async function refreshClientSuggestionSnapshot(
  threshold?: number,
): Promise<{ status: string; threshold: number }> {
  return post<{ status: string; threshold: number }>(
    `${BASE}suggestions/latest/refresh/`,
    threshold === undefined ? {} : { threshold },
  );
}

// ---------------------------------------------------------------------------
// Helpers

/** Human label for a platform key, used in chips/badges. */
export function platformLabel(platform: PlatformKey): string {
  switch (platform) {
    case 'meta_ads':
      return 'Meta Ads';
    case 'meta_page':
      return 'Meta Page';
    case 'google_ads':
      return 'Google Ads';
    case 'ga4':
      return 'GA4';
    case 'search_console':
      return 'Search Console';
    case 'linkedin':
      return 'LinkedIn';
    case 'tiktok':
      return 'TikTok';
    default: {
      // Exhaustive check — fall through to typed string.
      const exhaustive: never = platform;
      return exhaustive;
    }
  }
}

/** Sum of configured platform counts for a client summary row. */
export function totalAccountCount(summary: ClientSummary): number {
  return Object.values(summary.platform_counts ?? {}).reduce(
    (acc, value) => acc + (value ?? 0),
    0,
  );
}
