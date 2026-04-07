import apiClient, { appendQueryParams } from './apiClient';

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

type AirbyteConnectionsListResponse =
  | AirbyteConnectionRecord[]
  | {
      results?: AirbyteConnectionRecord[];
    };

export interface MetaOAuthStartResponse {
  authorize_url: string;
  state: string;
  redirect_uri: string;
  login_configuration_id?: string | null;
}

export interface RuntimeContextPayload {
  client_origin?: string;
  client_port?: number;
  dataset_source?: string;
}

export interface MetaOAuthStartPayload {
  auth_type?: 'rerequest';
  runtime_context?: RuntimeContextPayload;
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
  default_page_id?: string | null;
  default_ad_account_id?: string | null;
  default_instagram_account_id?: string | null;
  source?: string | null;
  recovered_from_existing_token?: boolean;
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

export interface MetaRecoveryPreviewResponse extends MetaOAuthExchangeResponse {
  source: 'existing_meta_connection';
  recovered_from_existing_token: true;
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
  details?: string | null;
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
  runtime_context?: {
    redirect_uri?: string | null;
    redirect_source?: string | null;
    request_origin?: string | null;
    request_referer_origin?: string | null;
    request_host?: string | null;
    request_port?: number | null;
    resolved_frontend_origin?: string | null;
    frontend_base_url_origin?: string | null;
    configured_redirect_origin?: string | null;
    observed_runtime_origin?: string | null;
    redirect_origin_matches_runtime?: boolean | null;
    redirect_origin_mismatch_message?: string | null;
    dev_active_profile?: string | null;
    dev_backend_url?: string | null;
    dev_frontend_url?: string | null;
    dataset_source?: string | null;
  };
}

export interface GoogleAnalyticsSetupStatusResponse {
  provider: 'google_analytics';
  ready_for_oauth: boolean;
  oauth_scopes: string[];
  redirect_uri?: string | null;
  checks?: MetaSetupCheck[];
  runtime_context?: {
    redirect_uri?: string | null;
    redirect_source?: string | null;
    request_origin?: string | null;
    request_referer_origin?: string | null;
    request_host?: string | null;
    request_port?: number | null;
    resolved_frontend_origin?: string | null;
    frontend_base_url_origin?: string | null;
    configured_redirect_origin?: string | null;
    observed_runtime_origin?: string | null;
    redirect_origin_matches_runtime?: boolean | null;
    redirect_origin_mismatch_message?: string | null;
    dataset_source?: string | null;
  };
}

export interface GoogleAdsSetupStatusResponse {
  provider: 'google_ads';
  ready_for_oauth: boolean;
  ready_for_provisioning_defaults: boolean;
  checks: MetaSetupCheck[];
  oauth_scopes: string[];
  redirect_uri?: string | null;
  source_definition_id: string;
  runtime_context?: {
    redirect_uri?: string | null;
    redirect_source?: string | null;
    request_origin?: string | null;
    request_referer_origin?: string | null;
    request_host?: string | null;
    request_port?: number | null;
    resolved_frontend_origin?: string | null;
    frontend_base_url_origin?: string | null;
    configured_redirect_origin?: string | null;
    observed_runtime_origin?: string | null;
    redirect_origin_matches_runtime?: boolean | null;
    redirect_origin_mismatch_message?: string | null;
    dataset_source?: string | null;
  };
}

export interface GoogleAdsOAuthStartPayload {
  runtime_context?: RuntimeContextPayload;
}

export interface GoogleAdsOAuthStartResponse {
  authorize_url: string;
  state: string;
  redirect_uri: string;
  oauth_scopes: string[];
}

export interface GoogleAdsOAuthExchangeResponse {
  credential: PlatformCredentialRecord;
  refresh_token_received: boolean;
}

export interface GoogleAdsProvisionPayload {
  external_account_id?: string;
  login_customer_id?: string;
  workspace_id?: string | null;
  destination_id?: string | null;
  source_definition_id?: string | null;
  connection_name?: string;
  is_active?: boolean;
  schedule_type?: 'manual' | 'interval' | 'cron';
  interval_minutes?: number | null;
  cron_expression?: string;
  sync_engine?: 'sdk' | 'airbyte';
}

export interface GoogleAdsProvisionResponse {
  provider: 'google_ads';
  credential: PlatformCredentialRecord;
  connection: AirbyteConnectionRecord;
  sync_engine: 'sdk' | 'airbyte';
  fallback_active: boolean;
  source_reused: boolean;
  connection_reused: boolean;
}

export interface GoogleAdsStatusResponse {
  provider: 'google_ads';
  status: 'not_connected' | 'started_not_complete' | 'complete' | 'active';
  reason: {
    code?: string;
    message: string;
    [key: string]: unknown;
  };
  actions: string[];
  last_checked_at?: string | null;
  last_synced_at?: string | null;
  sync_engine?: 'sdk' | 'airbyte';
  fallback_active?: boolean;
  parity_state?: 'unknown' | 'pass' | 'fail';
  last_parity_passed_at?: string | null;
  metadata: Record<string, unknown>;
}

export interface GoogleAnalyticsOAuthStartPayload {
  runtime_context?: RuntimeContextPayload;
}

export interface GoogleAnalyticsOAuthStartResponse {
  authorize_url: string;
  state: string;
}

export interface GoogleAnalyticsOAuthExchangeResponse {
  credential: PlatformCredentialRecord;
  refresh_token_received: boolean;
}

export interface GoogleAnalyticsPropertyRecord {
  property: string;
  property_id: string;
  property_name: string;
  account_name: string;
}

export interface GoogleAnalyticsPropertiesResponse {
  credential_id: string;
  properties: GoogleAnalyticsPropertyRecord[];
}

export interface GoogleAnalyticsProvisionResponse {
  connection: {
    id: string;
    credential_id: string;
    property_id: string;
    property_name: string;
    is_active: boolean;
    sync_frequency: string;
    last_synced_at?: string | null;
    created_at?: string | null;
    updated_at?: string | null;
  };
}

export interface GoogleAnalyticsStatusResponse {
  provider: 'google_analytics';
  status: 'not_connected' | 'started_not_complete' | 'complete' | 'active';
  reason: {
    message: string;
    [key: string]: unknown;
  };
  actions: string[];
  last_checked_at?: string | null;
  last_synced_at?: string | null;
  metadata: Record<string, unknown>;
}

export type SocialConnectionPlatform = 'meta' | 'instagram';
export type SocialConnectionStatus =
  | 'not_connected'
  | 'started_not_complete'
  | 'complete'
  | 'active';

export interface SocialReportingReadiness {
  stage: string;
  message: string;
  auth_status: SocialConnectionStatus;
  direct_sync_status: string;
  warehouse_status: string;
  dataset_live_reason: 'adapter_disabled' | 'missing_snapshot' | 'stale_snapshot' | 'default_snapshot' | 'ready';
  warehouse_adapter_enabled: boolean;
  snapshot_generated_at?: string | null;
}

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
  reporting_readiness?: SocialReportingReadiness;
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

function normalizeAirbyteConnections(
  payload: AirbyteConnectionsListResponse | null | undefined,
): AirbyteConnectionRecord[] {
  if (Array.isArray(payload)) {
    return payload;
  }
  if (Array.isArray(payload?.results)) {
    return payload.results;
  }
  return [];
}

export async function loadAirbyteConnections(
  signal?: AbortSignal,
): Promise<AirbyteConnectionRecord[]> {
  const payload = await apiClient.get<AirbyteConnectionsListResponse>(CONNECTIONS_ENDPOINT, {
    mockPath: CONNECTIONS_FIXTURE,
    signal,
  });
  return normalizeAirbyteConnections(payload);
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
  runtime_context?: RuntimeContextPayload;
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

export async function previewMetaRecovery(): Promise<MetaRecoveryPreviewResponse> {
  return apiClient.post<MetaRecoveryPreviewResponse>('/integrations/meta/recovery/preview/', {});
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
  reused_existing_job?: boolean;
  sync_status?: 'queued' | 'already_running';
  task_dispatch_mode?: 'queued' | 'inline';
}> {
  return apiClient.post<{
    provider: 'meta_ads';
    connection_id: string;
    job_id?: string | null;
    reused_existing_job?: boolean;
    sync_status?: 'queued' | 'already_running';
    task_dispatch_mode?: 'queued' | 'inline';
  }>(
    '/integrations/meta/sync/',
  );
}

export async function logoutMetaOAuth(): Promise<{
  provider: 'meta_ads';
  disconnected: boolean;
  deleted_credentials: number;
  deleted_page_connections: number;
  deleted_pages: number;
  deleted_sync_states: number;
  disabled_airbyte_connections: number;
}> {
  return apiClient.post<{
    provider: 'meta_ads';
    disconnected: boolean;
    deleted_credentials: number;
    deleted_page_connections: number;
    deleted_pages: number;
    deleted_sync_states: number;
    disabled_airbyte_connections: number;
  }>('/integrations/meta/logout/');
}

export async function loadMetaSetupStatus(
  runtimeContext?: RuntimeContextPayload,
): Promise<MetaSetupStatusResponse> {
  const params = new URLSearchParams();
  if (runtimeContext?.dataset_source?.trim()) {
    params.set('dataset_source', runtimeContext.dataset_source.trim());
  }
  if (runtimeContext?.client_origin?.trim()) {
    params.set('client_origin', runtimeContext.client_origin.trim());
  }
  if (typeof runtimeContext?.client_port === 'number' && Number.isFinite(runtimeContext.client_port)) {
    params.set('client_port', String(runtimeContext.client_port));
  }
  const suffix = params.toString();
  const path = suffix ? `/integrations/meta/setup/?${suffix}` : '/integrations/meta/setup/';
  return apiClient.get<MetaSetupStatusResponse>(path);
}

export async function loadGoogleAnalyticsSetupStatus(
  runtimeContext?: RuntimeContextPayload,
): Promise<GoogleAnalyticsSetupStatusResponse> {
  const params = new URLSearchParams();
  if (runtimeContext?.dataset_source?.trim()) {
    params.set('dataset_source', runtimeContext.dataset_source.trim());
  }
  if (runtimeContext?.client_origin?.trim()) {
    params.set('client_origin', runtimeContext.client_origin.trim());
  }
  if (typeof runtimeContext?.client_port === 'number' && Number.isFinite(runtimeContext.client_port)) {
    params.set('client_port', String(runtimeContext.client_port));
  }
  const suffix = params.toString();
  const path = suffix
    ? `/integrations/google_analytics/setup/?${suffix}`
    : '/integrations/google_analytics/setup/';
  return apiClient.get<GoogleAnalyticsSetupStatusResponse>(path);
}

export async function loadGoogleAdsSetupStatus(
  runtimeContext?: RuntimeContextPayload,
): Promise<GoogleAdsSetupStatusResponse> {
  const params = new URLSearchParams();
  if (runtimeContext?.dataset_source?.trim()) {
    params.set('dataset_source', runtimeContext.dataset_source.trim());
  }
  if (runtimeContext?.client_origin?.trim()) {
    params.set('client_origin', runtimeContext.client_origin.trim());
  }
  if (typeof runtimeContext?.client_port === 'number' && Number.isFinite(runtimeContext.client_port)) {
    params.set('client_port', String(runtimeContext.client_port));
  }
  const suffix = params.toString();
  const path = suffix ? `/integrations/google_ads/setup/?${suffix}` : '/integrations/google_ads/setup/';
  return apiClient.get<GoogleAdsSetupStatusResponse>(path);
}

export async function startGoogleAnalyticsOAuth(
  payload?: GoogleAnalyticsOAuthStartPayload,
): Promise<GoogleAnalyticsOAuthStartResponse> {
  return apiClient.post<GoogleAnalyticsOAuthStartResponse>(
    '/integrations/google_analytics/oauth/start/',
    payload ?? {},
  );
}

export async function exchangeGoogleAnalyticsOAuthCode(payload: {
  code: string;
  state: string;
  runtime_context?: RuntimeContextPayload;
}): Promise<GoogleAnalyticsOAuthExchangeResponse> {
  return apiClient.post<GoogleAnalyticsOAuthExchangeResponse>(
    '/integrations/google_analytics/oauth/exchange/',
    payload,
  );
}

export async function startGoogleAdsOAuth(
  payload?: GoogleAdsOAuthStartPayload,
): Promise<GoogleAdsOAuthStartResponse> {
  return apiClient.post<GoogleAdsOAuthStartResponse>('/integrations/google_ads/oauth/start/', payload ?? {});
}

export async function exchangeGoogleAdsOAuthCode(payload: {
  code: string;
  state: string;
  customer_id: string;
  login_customer_id?: string;
  runtime_context?: RuntimeContextPayload;
}): Promise<GoogleAdsOAuthExchangeResponse> {
  return apiClient.post<GoogleAdsOAuthExchangeResponse>(
    '/integrations/google_ads/oauth/exchange/',
    payload,
  );
}

export async function provisionGoogleAds(
  payload: GoogleAdsProvisionPayload,
): Promise<GoogleAdsProvisionResponse> {
  return apiClient.post<GoogleAdsProvisionResponse>('/integrations/google_ads/provision/', payload);
}

export async function loadGoogleAdsStatus(): Promise<GoogleAdsStatusResponse> {
  return apiClient.get<GoogleAdsStatusResponse>('/integrations/google_ads/status/');
}

export async function loadGoogleAnalyticsProperties(query?: {
  credential_id?: string;
}): Promise<GoogleAnalyticsPropertiesResponse> {
  const path = query
    ? appendQueryParams('/integrations/google_analytics/properties/', query)
    : '/integrations/google_analytics/properties/';
  return apiClient.get<GoogleAnalyticsPropertiesResponse>(path);
}

export async function provisionGoogleAnalytics(payload: {
  credential_id: string;
  property_id: string;
  property_name: string;
  is_active?: boolean;
  sync_frequency?: string;
}): Promise<GoogleAnalyticsProvisionResponse> {
  return apiClient.post<GoogleAnalyticsProvisionResponse>(
    '/integrations/google_analytics/provision/',
    payload,
  );
}

export async function loadGoogleAnalyticsStatus(): Promise<GoogleAnalyticsStatusResponse> {
  return apiClient.get<GoogleAnalyticsStatusResponse>('/integrations/google_analytics/status/');
}

export async function loadSocialConnectionStatus(
  signal?: AbortSignal,
): Promise<SocialConnectionStatusResponse> {
  return apiClient.get<SocialConnectionStatusResponse>('/integrations/social/status/', { signal });
}
