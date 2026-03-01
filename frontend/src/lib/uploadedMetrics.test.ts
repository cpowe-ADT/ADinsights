import { describe, expect, it } from 'vitest';

import {
  buildMetricsFromUpload,
  parseBudgetCsv,
  parseCampaignCsv,
  type UploadedDataset,
} from './uploadedMetrics';
import type { FilterBarState } from './dashboardFilters';

describe('uploadedMetrics', () => {
  it('parses campaign CSV rows', () => {
    const csv = [
      'date,campaign_id,campaign_name,platform,parish,spend,impressions,clicks,conversions',
      '2024-10-01,cmp-1,Launch,Meta,Kingston,120,12000,420,33',
    ].join('\n');

    const result = parseCampaignCsv(csv);

    expect(result.errors).toHaveLength(0);
    expect(result.rows).toHaveLength(1);
    expect(result.rows[0]?.campaignId).toBe('cmp-1');
    expect(result.rows[0]?.spend).toBe(120);
  });

  it('normalizes budget month values', () => {
    const csv = ['month,campaign_name,planned_budget', '2024-11,Brand Push,8000'].join('\n');

    const result = parseBudgetCsv(csv);

    expect(result.errors).toHaveLength(0);
    expect(result.rows[0]?.month).toBe('2024-11-01');
  });

  it('builds a resolved snapshot from uploads', () => {
    const dataset: UploadedDataset = {
      uploadedAt: '2024-10-15T00:00:00Z',
      campaignMetrics: [
        {
          date: '2024-10-01',
          campaignId: 'cmp-1',
          campaignName: 'Launch',
          platform: 'Meta',
          parish: 'Kingston',
          spend: 100,
          impressions: 1000,
          clicks: 50,
          conversions: 5,
          revenue: 400,
        },
        {
          date: '2024-10-02',
          campaignId: 'cmp-1',
          campaignName: 'Launch',
          platform: 'Meta',
          parish: 'Kingston',
          spend: 200,
          impressions: 2000,
          clicks: 70,
          conversions: 8,
          revenue: 600,
        },
      ],
      parishMetrics: [],
      budgets: [],
    };

    const filters: FilterBarState = {
      dateRange: 'custom',
      customRange: { start: '2024-10-01', end: '2024-10-31' },
      channels: [],
      campaignQuery: '',
    };

    const resolved = buildMetricsFromUpload(dataset, filters, 'tenant-1');

    expect(resolved.campaign.summary.totalSpend).toBe(300);
    expect(resolved.campaign.summary.totalClicks).toBe(120);
    expect(resolved.campaign.trend).toHaveLength(2);
    expect(resolved.parish[0]?.parish).toBe('Kingston');
  });
});
