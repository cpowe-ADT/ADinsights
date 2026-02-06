import apiClient, { appendQueryParams, MOCK_ASSETS_ENABLED } from './apiClient';
import { formatRelativeTime } from './format';

export type RecentDashboard = {
  id: string;
  name: string;
  owner: string;
  lastViewedLabel: string;
  href: string;
};

type RecentDashboardApiItem = {
  id: string | number;
  name?: string | null;
  owner?: string | null;
  last_viewed_at?: string | null;
  last_viewed_label?: string | null;
  href?: string | null;
  route?: string | null;
};

type RecentDashboardsResponse = RecentDashboardApiItem[] | { results?: RecentDashboardApiItem[] };

const fallbackDashboards: RecentDashboard[] = [
  {
    id: 'campaign-performance',
    name: 'Campaign performance',
    owner: 'Growth team',
    lastViewedLabel: 'Today, 08:12',
    href: '/dashboards/campaigns',
  },
  {
    id: 'creative-insights',
    name: 'Creative insights',
    owner: 'Performance team',
    lastViewedLabel: 'Yesterday, 16:40',
    href: '/dashboards/creatives',
  },
  {
    id: 'budget-pacing',
    name: 'Budget pacing',
    owner: 'Ops team',
    lastViewedLabel: 'Mon, 09:05',
    href: '/dashboards/budget',
  },
];

const resolveRecentDashboards = (payload: RecentDashboardsResponse): RecentDashboard[] => {
  const items = Array.isArray(payload) ? payload : payload.results ?? [];
  return items
    .map((item) => {
      const id = item.id ? String(item.id) : '';
      const name = item.name?.trim() ?? '';
      const href = (item.href ?? item.route ?? '').trim();
      if (!id || !name || !href) {
        return null;
      }
      const owner = item.owner?.trim() || 'ADInsights';
      const lastViewedLabel =
        item.last_viewed_label?.trim() ||
        formatRelativeTime(item.last_viewed_at) ||
        'Recently viewed';
      return {
        id,
        name,
        owner,
        lastViewedLabel,
        href,
      };
    })
    .filter((item): item is RecentDashboard => Boolean(item));
};

export async function fetchRecentDashboards(limit = 3): Promise<RecentDashboard[]> {
  const path = appendQueryParams('/dashboards/recent/', { limit });
  try {
    const payload = await apiClient.get<RecentDashboardsResponse>(path, {
      mockPath: '/mock/recent_dashboards.json',
    });
    return resolveRecentDashboards(payload).slice(0, limit);
  } catch (error) {
    if (MOCK_ASSETS_ENABLED) {
      return fallbackDashboards.slice(0, limit);
    }
    throw error;
  }
}
