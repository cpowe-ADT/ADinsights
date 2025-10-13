import apiClient from './apiClient';
import { validate, type SchemaKey } from './validate';
import type {
  BudgetPacingRow,
  CampaignPerformanceResponse,
  CreativePerformanceRow,
  ParishAggregate,
  TenantMetricsSnapshot,
} from '../state/useDashboardStore';

export interface MetricsResponse {
  campaign: CampaignPerformanceResponse;
  creative: CreativePerformanceRow[];
  budget: BudgetPacingRow[];
  parish: ParishAggregate[];
}

interface FetchOptions {
  path: string;
  mockPath: string;
  schema?: SchemaKey;
}

async function fetchJson<T>({ path, mockPath, schema }: FetchOptions): Promise<T> {
  const payload = await apiClient.get<T>(path, { mockPath });
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
