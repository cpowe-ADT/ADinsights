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
  login_configuration_id?: string | null;
}

export interface MetaOAuthStartPayload {
  auth_type?: 'rerequest';
}

export interface MetaOAuthPage {
  id: string;
  name: string;
  category?: string | null;
  tasks: string[];
  perms: string[];
}

export interface MetaAdAccount {
  id: string;
  account_id: string;
  name?: string | null;
  currency?: string | null;
  account_status?: number | null;
  business_name?: string | null;
}

export interface MetaInstagramAccount {
  id: string;
  username?: string | null;
  name?: string | null;
  profile_picture_url?: string | null;
  followers_count?: number | null;
  media_count?: number | null;
  source_page_id?: string | null;
  source_page_name?: string | null;
  source_field?: string | null;
}

export interface MetaOAuthExchangeResponse {
  selection_token: string;
  expires_in_seconds: number;
  pages: MetaOAuthPage[];
  ad_accounts: MetaAdAccount[];
  instagram_accounts: MetaInstagramAccount[];
  granted_permissions: string[];
  declined_permissions: string[];
  missing_required_permissions: string[];
  token_debug_valid: boolean;
  oauth_connected_but_missing_permissions: boolean;
}

export interface MetaPageConnectResponse {
  credential: PlatformCredentialRecord;
  page: MetaOAuthPage;
  ad_account?: MetaAdAccount | null;
  instagram_account?: MetaInstagramAccount | null;
  granted_permissions?: string[];
  declined_permissions?: string[];
  missing_required_permissions?: string[];
}

export interface MetaProvisionPayload {
  external_account_id?: string;
  workspace_id?: string | null;
  destination_id?: string | null;
  source_definition_id?: string | null;
  connection_name?: string;
  is_active?: boolean;
  schedule_type?: 'manual' | 'interval' | 'cron';
  interval_minutes?: number | null;
  cron_expression?: string;
}

export interface MetaProvisionResponse {
  provider: 'meta_ads';
  credential: PlatformCredentialRecord;
  connection: AirbyteConnectionRecord;
  source: {
    source_id: string;
    name: string;
  };
  source_reused: boolean;
  connection_reused: boolean;
}

export interface MetaSetupCheck {
  key: string;
  label: string;
  ok: boolean;
  using_fallback_default?: boolean;
  required_scopes?: string[];
  missing_scopes?: string[];
  env_vars?: string[];
  missing_env_vars?: string[];
}

export interface MetaSetupStatusResponse {
  provider: 'meta_ads';
  ready_for_oauth: boolean;
  ready_for_provisioning_defaults: boolean;
  checks: MetaSetupCheck[];
  missing_env_vars?: string[];
  oauth_scopes: string[];
  graph_api_version: string;
  redirect_uri?: string | null;
  source_definition_id: string;
  login_configuration_id_configured?: boolean;
  login_configuration_id?: string | null;
  login_configuration_required?: boolean;
  login_mode?: string;
}

export type SocialConnectionPlatform = 'meta' | 'instagram';
export type SocialConnectionStatus =
  | 'not_connected'
  | 'started_not_complete'
  | 'complete'
  | 'active';

export interface SocialPlatformStatusRecord {
  platform: SocialConnectionPlatform;
  display_name: string;
  status: SocialConnectionStatus;
  reason: {
    code: string;
    message: string;
    [key: string]: unknown;
  };
  last_checked_at?: string | null;
  last_synced_at?: string | null;
  actions: string[];
  metadata: Record<string, unknown>;
}

export interface SocialConnectionStatusResponse {
  generated_at: string;
  platforms: SocialPlatformStatusRecord[];
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

export async function loadAirbyteSummary(signal?: AbortSignal): Promise<AirbyteConnectionsSummary> {
  return apiClient.get<AirbyteConnectionsSummary>(SUMMARY_ENDPOINT, {
    mockPath: SUMMARY_FIXTURE,
    signal,
  });
}

export async function triggerAirbyteSync(
  connectionId: string,
): Promise<{ job_id?: string | null }> {
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

export async function startMetaOAuth(
  payload?: MetaOAuthStartPayload,
): Promise<MetaOAuthStartResponse> {
  return apiClient.post<MetaOAuthStartResponse>('/integrations/meta/oauth/start/', payload ?? {});
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
  ad_account_id: string;
  instagram_account_id?: string;
}): Promise<MetaPageConnectResponse> {
  return apiClient.post<MetaPageConnectResponse>('/integrations/meta/pages/connect/', payload);
}

export async function provisionMetaIntegration(
  payload: MetaProvisionPayload,
): Promise<MetaProvisionResponse> {
  return apiClient.post<MetaProvisionResponse>('/integrations/meta/provision/', payload);
}

export async function syncMetaIntegration(): Promise<{
  provider: 'meta_ads';
  connection_id: string;
  job_id?: string | null;
}> {
  return apiClient.post<{ provider: 'meta_ads'; connection_id: string; job_id?: string | null }>(
    '/integrations/meta/sync/',
  );
}

export async function logoutMetaOAuth(): Promise<{
  provider: 'meta_ads';
  disconnected: boolean;
  deleted_credentials: number;
}> {
  return apiClient.post<{
    provider: 'meta_ads';
    disconnected: boolean;
    deleted_credentials: number;
  }>('/integrations/meta/logout/');
}

export async function loadMetaSetupStatus(): Promise<MetaSetupStatusResponse> {
  return apiClient.get<MetaSetupStatusResponse>('/integrations/meta/setup/');
}

export async function loadSocialConnectionStatus(
  signal?: AbortSignal,
): Promise<SocialConnectionStatusResponse> {
  return apiClient.get<SocialConnectionStatusResponse>('/integrations/social/status/', { signal });
}
