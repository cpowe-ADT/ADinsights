type CampaignRow = {
  id: string;
  name: string;
  platform: string;
  status: string;
  parish: string;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  roas: number;
  ctr?: number;
  cpc?: number;
  cpm?: number;
  startDate?: string;
  endDate?: string;
};

type TrendPoint = {
  date: string;
  spend: number;
  conversions: number;
  clicks: number;
  impressions: number;
};

type CampaignSnapshot = {
  summary: {
    currency: string;
    totalSpend: number;
    totalImpressions: number;
    totalClicks: number;
    totalConversions: number;
    averageRoas: number;
  };
  trend: TrendPoint[];
  rows: CampaignRow[];
};

type CreativeRow = {
  id: string;
  name: string;
  campaignId: string;
  campaignName: string;
  platform: string;
  parish?: string;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  roas: number;
  ctr?: number;
  thumbnailUrl?: string;
};

type BudgetRow = {
  id: string;
  campaignName: string;
  parishes?: string[];
  monthlyBudget: number;
  spendToDate: number;
  projectedSpend: number;
  pacingPercent: number;
  startDate?: string;
  endDate?: string;
};

export type ParishAggregate = {
  parish: string;
  spend: number;
  impressions: number;
  clicks: number;
  conversions: number;
  roas?: number;
  campaignCount?: number;
  currency?: string;
};

const campaignRows: CampaignRow[] = [
  {
    id: 'cmp_awareness',
    name: 'Awareness Boost',
    platform: 'Meta',
    status: 'Active',
    parish: 'Kingston',
    spend: 540,
    impressions: 120000,
    clicks: 3400,
    conversions: 120,
    roas: 3.5,
    ctr: 0.0283,
    cpc: 0.16,
    cpm: 4.5,
    startDate: '2024-08-01',
    endDate: '2024-09-30',
  },
  {
    id: 'cmp_search',
    name: 'Search Capture',
    platform: 'Google Ads',
    status: 'Active',
    parish: 'St James',
    spend: 430,
    impressions: 94000,
    clicks: 4200,
    conversions: 140,
    roas: 4.1,
    ctr: 0.0447,
    cpc: 0.1,
    cpm: 4.57,
    startDate: '2024-08-05',
    endDate: '2024-09-28',
  },
  {
    id: 'cmp_genz',
    name: 'GenZ Launch',
    platform: 'TikTok',
    status: 'Learning',
    parish: 'St Andrew',
    spend: 220,
    impressions: 68000,
    clicks: 2100,
    conversions: 95,
    roas: 3.2,
    ctr: 0.0309,
    cpc: 0.1,
    cpm: 3.24,
    startDate: '2024-08-18',
    endDate: '2024-10-02',
  },
];

const campaignSummary = campaignRows.reduce(
  (acc, row) => {
    acc.totalSpend += row.spend;
    acc.totalImpressions += row.impressions;
    acc.totalClicks += row.clicks;
    acc.totalConversions += row.conversions;
    acc.totalRoas += row.roas;
    return acc;
  },
  {
    currency: 'USD',
    totalSpend: 0,
    totalImpressions: 0,
    totalClicks: 0,
    totalConversions: 0,
    totalRoas: 0,
  },
);

const campaignTrend: TrendPoint[] = campaignRows.map((row, index) => ({
  date: `2024-09-0${index + 1}`,
  spend: row.spend,
  conversions: row.conversions,
  clicks: row.clicks,
  impressions: row.impressions,
}));

export const campaignSnapshot: CampaignSnapshot = {
  summary: {
    currency: campaignSummary.currency,
    totalSpend: Number(campaignSummary.totalSpend.toFixed(2)),
    totalImpressions: campaignSummary.totalImpressions,
    totalClicks: campaignSummary.totalClicks,
    totalConversions: campaignSummary.totalConversions,
    averageRoas: Number((campaignSummary.totalRoas / campaignRows.length).toFixed(2)),
  },
  trend: campaignTrend,
  rows: campaignRows,
};

export const creativeRows: CreativeRow[] = [
  {
    id: 'cr_awareness_video',
    name: 'Awareness Video',
    campaignId: 'cmp_awareness',
    campaignName: 'Awareness Boost',
    platform: 'Meta',
    parish: 'Kingston',
    spend: 180,
    impressions: 58000,
    clicks: 1500,
    conversions: 48,
    roas: 2.8,
    ctr: 0.0259,
  },
  {
    id: 'cr_search_carousel',
    name: 'Search Carousel',
    campaignId: 'cmp_search',
    campaignName: 'Search Capture',
    platform: 'Google Ads',
    parish: 'St James',
    spend: 140,
    impressions: 36000,
    clicks: 1320,
    conversions: 52,
    roas: 3.6,
    ctr: 0.0367,
  },
];

export const budgetRows: BudgetRow[] = [
  {
    id: 'budget_awareness',
    campaignName: 'Awareness Boost',
    parishes: ['Kingston'],
    monthlyBudget: 800,
    spendToDate: 540,
    projectedSpend: 760,
    pacingPercent: 95,
    startDate: '2024-08-01',
    endDate: '2024-09-30',
  },
  {
    id: 'budget_search',
    campaignName: 'Search Capture',
    parishes: ['St James'],
    monthlyBudget: 700,
    spendToDate: 430,
    projectedSpend: 680,
    pacingPercent: 97,
    startDate: '2024-08-05',
    endDate: '2024-09-28',
  },
];

export const parishAggregates: ParishAggregate[] = [
  {
    parish: 'Kingston',
    spend: 540,
    impressions: 120000,
    clicks: 3400,
    conversions: 120,
    roas: 3.5,
    campaignCount: 1,
    currency: 'USD',
  },
  {
    parish: 'St James',
    spend: 430,
    impressions: 94000,
    clicks: 4200,
    conversions: 140,
    roas: 4.1,
    campaignCount: 1,
    currency: 'USD',
  },
  {
    parish: 'St Andrew',
    spend: 220,
    impressions: 68000,
    clicks: 2100,
    conversions: 95,
    roas: 3.2,
    campaignCount: 1,
    currency: 'USD',
  },
];

export const aggregatedMetricsResponse = {
  campaign: campaignSnapshot,
  creative: creativeRows,
  budget: budgetRows,
  parish: parishAggregates,
};

export function fulfillJson(route: import('@playwright/test').Route, payload: unknown): void {
  void route.fulfill({
    status: 200,
    contentType: 'application/json',
    body: JSON.stringify(payload),
  });
}
