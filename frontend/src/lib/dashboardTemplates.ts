import type { DashboardMetricKey, DashboardTemplateKey } from './phase2Api';

export type DashboardTemplateDefinition = {
  key: DashboardTemplateKey;
  label: string;
  subtitle: string;
  routeKind: 'campaigns' | 'creatives' | 'budget' | 'map';
  defaultMetric: DashboardMetricKey;
  widgets: Array<{
    id: string;
    label: string;
    description: string;
  }>;
};

export const DASHBOARD_TEMPLATES: DashboardTemplateDefinition[] = [
  {
    key: 'meta_executive_overview',
    label: 'Meta executive overview',
    subtitle: 'KPI strip, trend, pacing summary, and map state for leadership check-ins.',
    routeKind: 'campaigns',
    defaultMetric: 'spend',
    widgets: [
      { id: 'kpis', label: 'KPI strip', description: 'Spend, reach, clicks, CTR, CPC, CPM, CPA, and ROAS.' },
      { id: 'trend', label: 'Trend chart', description: 'Daily campaign performance trend for the selected window.' },
      { id: 'campaign_table', label: 'Campaign table', description: 'Top campaign rows ordered by spend.' },
      { id: 'budget_summary', label: 'Budget summary', description: 'Projected spend and pacing context.' },
      { id: 'map', label: 'Map state', description: 'Graceful parish-map availability or unsupported state.' },
    ],
  },
  {
    key: 'meta_campaign_performance',
    label: 'Meta campaign performance',
    subtitle: 'Campaign-centric Meta Ads analysis with server-backed filters and coverage.',
    routeKind: 'campaigns',
    defaultMetric: 'spend',
    widgets: [
      { id: 'kpis', label: 'KPI strip', description: 'Primary campaign KPIs for the selected account and window.' },
      { id: 'trend', label: 'Trend chart', description: 'Daily spend and conversion trend for selected campaigns.' },
      { id: 'campaign_table', label: 'Campaign table', description: 'Campaign rows with efficiency metrics and dates.' },
      { id: 'map', label: 'Map card', description: 'Geo state shown truthfully when parish coverage is unavailable.' },
    ],
  },
  {
    key: 'meta_creative_insights',
    label: 'Meta creative insights',
    subtitle: 'Creative-level performance with thumbnails, leaderboard rows, and summary cards.',
    routeKind: 'creatives',
    defaultMetric: 'ctr',
    widgets: [
      { id: 'creative_summary', label: 'Creative summary', description: 'Top-line performance rollup across creative rows.' },
      { id: 'creative_table', label: 'Creative table', description: 'Creative leaderboard with campaign and thumbnail context.' },
      { id: 'coverage', label: 'Coverage status', description: 'Dataset freshness and range coverage for the saved view.' },
    ],
  },
  {
    key: 'meta_budget_pacing',
    label: 'Meta budget pacing',
    subtitle: 'Budget pacing with selected-window budget context and projected spend.',
    routeKind: 'budget',
    defaultMetric: 'cpa',
    widgets: [
      { id: 'budget_summary', label: 'Budget summary', description: 'On-track, under, and over pacing counts.' },
      { id: 'budget_table', label: 'Budget table', description: 'Campaign budgets, spend-to-date, and pacing status.' },
      { id: 'coverage', label: 'Coverage status', description: 'Selected account and date window applied to pacing.' },
    ],
  },
  {
    key: 'meta_parish_map',
    label: 'Meta parish map',
    subtitle: 'Geographic view that only renders when parish data is trustworthy.',
    routeKind: 'map',
    defaultMetric: 'spend',
    widgets: [
      { id: 'map', label: 'Parish map', description: 'Choropleth or graceful unsupported state when geography is unavailable.' },
      { id: 'coverage', label: 'Coverage status', description: 'Selected account/date coverage and map availability state.' },
    ],
  },
];

export function getDashboardTemplate(
  key: DashboardTemplateKey | string | undefined,
): DashboardTemplateDefinition {
  return (
    DASHBOARD_TEMPLATES.find((template) => template.key === key) ??
    DASHBOARD_TEMPLATES[1]
  );
}
