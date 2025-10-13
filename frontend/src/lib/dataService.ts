import apiClient from "./apiClient";
import type {
  BudgetPacingRow,
  CampaignPerformanceResponse,
  CreativePerformanceRow,
  ParishAggregate,
} from "../state/useDashboardStore";

interface FetchOptions {
  path: string;
  mockPath: string;
}

async function fetchJson<T>({ path, mockPath }: FetchOptions): Promise<T> {
  return apiClient.get<T>(path, { mockPath });
}

export async function fetchCampaignPerformance(options: FetchOptions): Promise<CampaignPerformanceResponse> {
  return fetchJson<CampaignPerformanceResponse>(options);
}

export async function fetchCreativePerformance(options: FetchOptions): Promise<CreativePerformanceRow[]> {
  return fetchJson<CreativePerformanceRow[]>(options);
}

export async function fetchBudgetPacing(options: FetchOptions): Promise<BudgetPacingRow[]> {
  return fetchJson<BudgetPacingRow[]>(options);
}

export async function fetchParishAggregates(options: FetchOptions): Promise<ParishAggregate[]> {
  return fetchJson<ParishAggregate[]>(options);
}
