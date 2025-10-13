import { describe, expect, it } from 'vitest';

import { validate } from './validate';

const metricsSample = {
  summary: {
    currency: 'USD',
    totalSpend: 1190,
    totalImpressions: 282000,
    totalClicks: 9700,
    totalConversions: 355,
    averageRoas: 3.6,
  },
  trend: [
    {
      date: '2024-09-01',
      spend: 540,
      conversions: 120,
      clicks: 3400,
      impressions: 120000,
    },
    {
      date: '2024-09-02',
      spend: 430,
      conversions: 140,
      clicks: 4200,
      impressions: 94000,
    },
  ],
  rows: [
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
  ],
};

describe('validate', () => {
  it('accepts metrics sample data', () => {
    expect(validate('metrics', metricsSample)).toBe(true);
  });
});
