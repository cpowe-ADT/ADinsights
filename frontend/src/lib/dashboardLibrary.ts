import { fetchDashboardLibrary as fetchDashboardLibraryFromApi } from './phase2Api';

export type DashboardLibraryItem = {
  id: string;
  name: string;
  type: 'Campaigns' | 'Creatives' | 'Budget pacing' | 'Parish map';
  owner: string;
  updatedAt: string;
  tags: string[];
  description: string;
  route: string;
};

export type DashboardLibraryFilters = {
  search?: string;
  type?: DashboardLibraryItem['type'];
  owner?: string;
};

export async function fetchDashboardLibrary(
  filters?: DashboardLibraryFilters,
): Promise<DashboardLibraryItem[]> {
  void filters;
  return fetchDashboardLibraryFromApi();
}
