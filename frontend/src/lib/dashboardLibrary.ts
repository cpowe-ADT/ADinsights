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

export const dashboardLibraryMock: DashboardLibraryItem[] = [
  {
    id: 'dash-campaigns-core',
    name: 'Campaign performance overview',
    type: 'Campaigns',
    owner: 'Lina H.',
    updatedAt: '2026-02-02',
    tags: ['ROAS', 'Spend', 'Conversions'],
    description: 'Daily campaign KPIs with trend and map context.',
    route: '/dashboards/campaigns',
  },
  {
    id: 'dash-creatives-top',
    name: 'Creative leaderboard',
    type: 'Creatives',
    owner: 'Joel M.',
    updatedAt: '2026-01-28',
    tags: ['CTR', 'Clicks', 'Thumbnails'],
    description: 'Top creative performance with preview thumbnails.',
    route: '/dashboards/creatives',
  },
  {
    id: 'dash-budget-pace',
    name: 'Budget pacing check-in',
    type: 'Budget pacing',
    owner: 'Sofia R.',
    updatedAt: '2026-01-25',
    tags: ['Pacing', 'Forecast', 'Risk'],
    description: 'Monitor monthly pacing and spend risk flags.',
    route: '/dashboards/budget',
  },
  {
    id: 'dash-parish-map',
    name: 'Parish map snapshot',
    type: 'Parish map',
    owner: 'Andre W.',
    updatedAt: '2026-01-19',
    tags: ['Geo', 'Map', 'Reach'],
    description: 'Geo performance map with metric toggles.',
    route: '/dashboards/map',
  },
];

export async function fetchDashboardLibrary(
  _filters?: DashboardLibraryFilters,
): Promise<DashboardLibraryItem[]> {
  return Promise.resolve(dashboardLibraryMock);
}
