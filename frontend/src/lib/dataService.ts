import type { FeatureCollection } from 'geojson';

import apiClient from './apiClient';
import { validate, type SchemaKey } from './validate';
import type {
  BudgetPacingRow,
  CampaignPerformanceResponse,
  CreativePerformanceRow,
  ParishAggregate,
  TenantMetricsSnapshot,
} from '../state/useDashboardStore';

export interface TenantRecord {
  id: string | number;
  name: string;
  slug?: string;
  status?: string;
  [key: string]: unknown;
}

export interface MetricsResponse {
  campaign: CampaignPerformanceResponse;
  creative: CreativePerformanceRow[];
  budget: BudgetPacingRow[];
  parish: ParishAggregate[];
}

export interface UploadMetricsStatus {
  has_upload?: boolean;
  snapshot_generated_at?: string;
  counts?: {
    campaign_rows: number;
    parish_rows: number;
    budget_rows: number;
  };
  warnings?: string[];
}

interface FetchOptions {
  path: string;
  mockPath: string;
  schema?: SchemaKey;
  signal?: AbortSignal;
}

async function fetchJson<T>({ path, mockPath, schema, signal }: FetchOptions): Promise<T> {
  const payload = await apiClient.get<T>(path, { mockPath, signal });
  validate(schema, payload);
  return payload;
}

export async function fetchCampaignPerformance(
  options: FetchOptions,
): Promise<CampaignPerformanceResponse> {
  return fetchJson<CampaignPerformanceResponse>({ ...options, schema: 'metrics' });
}

export async function fetchCreativePerformance(
  options: FetchOptions,
): Promise<CreativePerformanceRow[]> {
  return fetchJson<CreativePerformanceRow[]>({ ...options, schema: 'creative' });
}

export async function fetchBudgetPacing(options: FetchOptions): Promise<BudgetPacingRow[]> {
  return fetchJson<BudgetPacingRow[]>({ ...options, schema: 'budget' });
}

export async function fetchParishAggregates(options: FetchOptions): Promise<ParishAggregate[]> {
  return fetchJson<ParishAggregate[]>({ ...options, schema: 'parish' });
}

export async function fetchTenants(options: FetchOptions): Promise<TenantRecord[]> {
  return fetchJson<TenantRecord[]>({ ...options, schema: 'tenants' });
}

export async function fetchMetrics(path: string): Promise<MetricsResponse> {
  const payload = await apiClient.get<MetricsResponse>(path);
  validate('metrics', payload.campaign);
  validate('creative', payload.creative);
  validate('budget', payload.budget);
  validate('parish', payload.parish);
  return payload;
}

export async function fetchDashboardMetrics(options: FetchOptions): Promise<TenantMetricsSnapshot> {
  return fetchJson<TenantMetricsSnapshot>(options);
}

export async function fetchParishGeometry(options: FetchOptions): Promise<FeatureCollection> {
  return fetchJson<FeatureCollection>({ ...options, schema: 'parishGeometry' });
}

export async function fetchUploadStatus(): Promise<UploadMetricsStatus> {
  return apiClient.get<UploadMetricsStatus>('/uploads/metrics/');
}

export async function uploadMetrics(formData: FormData): Promise<UploadMetricsStatus> {
  return apiClient.post<UploadMetricsStatus>('/uploads/metrics/', formData);
}

export async function clearUploadedMetrics(): Promise<void> {
  await apiClient.delete('/uploads/metrics/');
}
