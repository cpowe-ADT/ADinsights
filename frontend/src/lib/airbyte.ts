import apiClient from './apiClient';

export interface AirbyteConnectionRecord {
  id: string;
  name: string;
  connection_id: string;
  workspace_id?: string | null;
  provider?: string | null;
  schedule_type?: string | null;
  interval_minutes?: number | null;
  cron_expression?: string | null;
  is_active?: boolean;
  last_synced_at?: string | null;
  last_job_id?: string | null;
  last_job_status?: string | null;
  last_job_created_at?: string | null;
  last_job_updated_at?: string | null;
  last_job_completed_at?: string | null;
  last_job_error?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface PlatformCredentialRecord {
  id: string;
  provider: string;
  account_id: string;
  expires_at?: string | null;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface CreatePlatformCredentialPayload {
  provider: 'META' | 'GOOGLE' | 'GA4' | 'SEARCH_CONSOLE' | 'LINKEDIN' | 'TIKTOK';
  account_id: string;
  access_token: string;
  refresh_token?: string | null;
  expires_at?: string | null;
}

export interface CreateAirbyteConnectionPayload {
  name: string;
  connection_id: string;
  workspace_id?: string | null;
  provider: 'META' | 'GOOGLE' | 'GA4' | 'SEARCH_CONSOLE' | 'LINKEDIN' | 'TIKTOK';
  schedule_type: 'manual' | 'interval' | 'cron';
  interval_minutes?: number | null;
  cron_expression?: string;
  is_active?: boolean;
}

export type IntegrationProviderSlug =
  | 'meta_ads'
  | 'facebook_pages'
  | 'google_ads'
  | 'ga4'
  | 'search_console';

export interface IntegrationOAuthStartResponse {
  provider: IntegrationProviderSlug;
  authorize_url: string;
  state: string;
  redirect_uri: string;
}

export interface IntegrationOAuthCallbackResponse {
  provider: IntegrationProviderSlug;
  status: string;
  credential?: PlatformCredentialRecord;
  selection_token?: string;
  expires_in_seconds?: number;
  pages?: MetaOAuthPage[];
}

export interface IntegrationProvisionPayload {
  external_account_id?: string;
  workspace_id?: string | null;
  destination_id?: string | null;
  source_definition_id?: string | null;
  source_configuration?: Record<string, unknown> | null;
  connection_name?: string;
  is_active?: boolean;
  schedule_type?: 'manual' | 'interval' | 'cron';
  interval_minutes?: number | null;
  cron_expression?: string;
}

export interface IntegrationProvisionResponse {
  provider: IntegrationProviderSlug;
  credential: PlatformCredentialRecord;
  connection: AirbyteConnectionRecord;
  source: {
    source_id: string;
    name: string;
  };
  source_reused: boolean;
  connection_reused: boolean;
}

export interface IntegrationStatusResponse {
  provider: IntegrationProviderSlug;
  label: string;
  state:
    | 'not_connected'
    | 'needs_provisioning'
    | 'needs_reauth'
    | 'connected'
    | 'syncing'
    | 'error'
    | 'paused';
  credentials: PlatformCredentialRecord[];
  connections: AirbyteConnectionRecord[];
  latest_connection_id?: string | null;
}

export interface IntegrationJobRecord {
  job_id: string;
  status: string;
  started_at: string;
  duration_seconds?: number | null;
  records_synced?: number | null;
  bytes_synced?: number | null;
  api_cost?: string | null;
  connection: {
    id: string;
    name: string;
    connection_id: string;
  };
}

export interface IntegrationJobsResponse {
  provider: IntegrationProviderSlug;
  count: number;
  jobs: IntegrationJobRecord[];
}

export interface AirbyteConnectionSummaryCounts {
  total: number;
  active: number;
  due: number;
}

export interface AirbyteSyncStatusSummary {
  tenant_id?: string;
  last_synced_at?: string | null;
  last_job_id?: string | null;
  last_job_status?: string | null;
  last_job_updated_at?: string | null;
  last_job_completed_at?: string | null;
  last_job_error?: string | null;
  connection?: {
    id: string;
    name: string;
    connection_id: string;
    workspace_id?: string | null;
    provider?: string | null;
  } | null;
}

export interface AirbyteConnectionsSummary {
  total: number;
  active: number;
  inactive: number;
  due: number;
  by_provider: Record<string, AirbyteConnectionSummaryCounts>;
  latest_sync?: AirbyteSyncStatusSummary | null;
}

export interface MetaOAuthStartResponse {
  authorize_url: string;
  state: string;
  redirect_uri: string;
}

export interface MetaOAuthPage {
  id: string;
  name: string;
  category?: string | null;
  tasks: string[];
  perms: string[];
}

export interface MetaOAuthExchangeResponse {
  selection_token: string;
  expires_in_seconds: number;
  pages: MetaOAuthPage[];
}

export interface MetaPageConnectResponse {
  credential: PlatformCredentialRecord;
  page: MetaOAuthPage;
}

const CONNECTIONS_ENDPOINT = '/airbyte/connections/';
const SUMMARY_ENDPOINT = '/airbyte/connections/summary/';
const CONNECTIONS_FIXTURE = '/mock/airbyte_connections.json';
const SUMMARY_FIXTURE = '/mock/airbyte_connections_summary.json';

export async function loadAirbyteConnections(
  signal?: AbortSignal,
): Promise<AirbyteConnectionRecord[]> {
  return apiClient.get<AirbyteConnectionRecord[]>(CONNECTIONS_ENDPOINT, {
    mockPath: CONNECTIONS_FIXTURE,
    signal,
  });
}

export async function loadAirbyteSummary(
  signal?: AbortSignal,
): Promise<AirbyteConnectionsSummary> {
  return apiClient.get<AirbyteConnectionsSummary>(SUMMARY_ENDPOINT, {
    mockPath: SUMMARY_FIXTURE,
    signal,
  });
}

export async function triggerAirbyteSync(connectionId: string): Promise<{ job_id?: string | null }> {
  return apiClient.post<{ job_id?: string | null }>(`${CONNECTIONS_ENDPOINT}${connectionId}/sync/`);
}

export async function createPlatformCredential(
  payload: CreatePlatformCredentialPayload,
): Promise<PlatformCredentialRecord> {
  return apiClient.post<PlatformCredentialRecord>('/platform-credentials/', payload);
}

export async function createAirbyteConnection(
  payload: CreateAirbyteConnectionPayload,
): Promise<AirbyteConnectionRecord> {
  return apiClient.post<AirbyteConnectionRecord>(CONNECTIONS_ENDPOINT, payload);
}

export async function startMetaOAuth(): Promise<MetaOAuthStartResponse> {
  return apiClient.post<MetaOAuthStartResponse>('/integrations/meta/oauth/start/');
}

export async function exchangeMetaOAuthCode(payload: {
  code: string;
  state: string;
}): Promise<MetaOAuthExchangeResponse> {
  return apiClient.post<MetaOAuthExchangeResponse>('/integrations/meta/oauth/exchange/', payload);
}

export async function connectMetaPage(payload: {
  selection_token: string;
  page_id: string;
}): Promise<MetaPageConnectResponse> {
  return apiClient.post<MetaPageConnectResponse>('/integrations/meta/pages/connect/', payload);
}

export async function startIntegrationOAuth(
  provider: IntegrationProviderSlug,
): Promise<IntegrationOAuthStartResponse> {
  return apiClient.post<IntegrationOAuthStartResponse>(`/integrations/${provider}/oauth/start/`);
}

export async function callbackIntegrationOAuth(
  provider: IntegrationProviderSlug,
  payload: {
    code: string;
    state: string;
    external_account_id?: string;
    page_id?: string;
  },
): Promise<IntegrationOAuthCallbackResponse> {
  return apiClient.post<IntegrationOAuthCallbackResponse>(
    `/integrations/${provider}/oauth/callback/`,
    payload,
  );
}

export async function provisionIntegration(
  provider: IntegrationProviderSlug,
  payload: IntegrationProvisionPayload,
): Promise<IntegrationProvisionResponse> {
  return apiClient.post<IntegrationProvisionResponse>(`/integrations/${provider}/provision/`, payload);
}

export async function syncIntegration(
  provider: IntegrationProviderSlug,
): Promise<{ provider: IntegrationProviderSlug; connection_id: string; job_id?: string | null }> {
  return apiClient.post<{ provider: IntegrationProviderSlug; connection_id: string; job_id?: string | null }>(
    `/integrations/${provider}/sync/`,
  );
}

export async function loadIntegrationStatus(
  provider: IntegrationProviderSlug,
  signal?: AbortSignal,
): Promise<IntegrationStatusResponse> {
  return apiClient.get<IntegrationStatusResponse>(`/integrations/${provider}/status/`, { signal });
}

export async function loadIntegrationJobs(
  provider: IntegrationProviderSlug,
  limit = 10,
  signal?: AbortSignal,
): Promise<IntegrationJobsResponse> {
  return apiClient.get<IntegrationJobsResponse>(`/integrations/${provider}/jobs/?limit=${limit}`, {
    signal,
  });
}

export async function disconnectIntegration(
  provider: IntegrationProviderSlug,
  payload?: { external_account_id?: string },
): Promise<{ provider: IntegrationProviderSlug; state: string }> {
  return apiClient.post<{ provider: IntegrationProviderSlug; state: string }>(
    `/integrations/${provider}/disconnect/`,
    payload ?? {},
  );
}

export async function reconnectIntegration(
  provider: IntegrationProviderSlug,
): Promise<IntegrationOAuthStartResponse> {
  return apiClient.post<IntegrationOAuthStartResponse>(`/integrations/${provider}/reconnect/`);
}
