import {
  fetchDashboardLibrary as fetchDashboardLibraryFromApi,
  type DashboardLibraryResponse,
} from './phase2Api';

export type { DashboardLibraryItem, DashboardLibraryResponse } from './phase2Api';

export type DashboardLibraryFilters = {
  search?: string;
  type?: string;
  owner?: string;
};

export async function fetchDashboardLibrary(
  filters?: DashboardLibraryFilters,
): Promise<DashboardLibraryResponse> {
  void filters;
  return fetchDashboardLibraryFromApi();
}
