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
  provider: 'META' | 'GOOGLE' | 'LINKEDIN' | 'TIKTOK';
  account_id: string;
  access_token: string;
  refresh_token?: string | null;
  expires_at?: string | null;
}

export interface CreateAirbyteConnectionPayload {
  name: string;
  connection_id: string;
  workspace_id?: string | null;
  provider: 'META' | 'GOOGLE' | 'LINKEDIN' | 'TIKTOK';
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
