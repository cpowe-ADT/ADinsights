import { describe, expect, it } from 'vitest';

import type { MetaCampaign, MetaInsightRecord } from './meta';
import {
  aggregatedRoas,
  computePeerMedian,
  derivedRoas,
  groupCtrCpmByDate,
  groupSpendByDateAccount,
  hasPurchaseActions,
  spendByObjective,
  sumInsights,
  topAccountsBySpend,
} from './metaAggregates';

const makeRow = (overrides: Partial<MetaInsightRecord>): MetaInsightRecord => ({
  id: 'i1',
  external_id: 'ext1',
  date: '2026-04-01',
  source: 'meta_ads',
  level: 'account',
  impressions: 0,
  reach: 0,
  clicks: 0,
  spend: '0',
  cpc: '0',
  cpm: '0',
  conversions: 0,
  currency: 'USD',
  actions: [],
  raw_payload: {},
  ingested_at: '2026-04-01T00:00:00Z',
  updated_at: '2026-04-01T00:00:00Z',
  ...overrides,
});

describe('metaAggregates.sumInsights', () => {
  it('sums numeric fields and derives CTR/CPM/CPC', () => {
    const rows = [
      makeRow({ spend: '100', impressions: 1000, clicks: 50, reach: 800 }),
      makeRow({ spend: '50', impressions: 500, clicks: 25, reach: 400 }),
    ];
    const kpi = sumInsights(rows);
    expect(kpi.spend).toBe(150);
    expect(kpi.impressions).toBe(1500);
    expect(kpi.clicks).toBe(75);
    expect(kpi.reach).toBe(1200);
    expect(kpi.ctr).toBeCloseTo(0.05, 4);
    expect(kpi.cpm).toBeCloseTo(100, 4);
    expect(kpi.cpc).toBeCloseTo(2, 4);
  });

  it('returns zeros on empty input without dividing by zero', () => {
    const kpi = sumInsights([]);
    expect(kpi.spend).toBe(0);
    expect(kpi.ctr).toBe(0);
    expect(kpi.cpm).toBe(0);
    expect(kpi.cpc).toBe(0);
  });
});

describe('metaAggregates.groupSpendByDateAccount', () => {
  it('groups by date and fills missing account values with 0', () => {
    const rows = [
      makeRow({ date: '2026-04-01', account_external_id: 'a1', spend: '10' }),
      makeRow({ date: '2026-04-01', account_external_id: 'a2', spend: '20' }),
      makeRow({ date: '2026-04-02', account_external_id: 'a1', spend: '15' }),
    ];
    const { points, accountIds } = groupSpendByDateAccount(rows);
    expect(accountIds.sort()).toEqual(['a1', 'a2']);
    expect(points).toHaveLength(2);
    const d1 = points.find((p) => p.date === '2026-04-01');
    expect(d1?.a1).toBe(10);
    expect(d1?.a2).toBe(20);
    const d2 = points.find((p) => p.date === '2026-04-02');
    expect(d2?.a1).toBe(15);
    expect(d2?.a2).toBe(0);
  });
});

describe('metaAggregates.computePeerMedian', () => {
  it('returns median per date', () => {
    const rows = [
      makeRow({ date: '2026-04-01', account_external_id: 'a1', spend: '10' }),
      makeRow({ date: '2026-04-01', account_external_id: 'a2', spend: '30' }),
      makeRow({ date: '2026-04-01', account_external_id: 'a3', spend: '20' }),
    ];
    const med = computePeerMedian(rows);
    expect(med).toEqual([{ date: '2026-04-01', value: 20 }]);
  });
});

describe('metaAggregates.topAccountsBySpend', () => {
  it('returns accounts sorted by descending total spend', () => {
    const rows = [
      makeRow({ account_external_id: 'a1', spend: '5' }),
      makeRow({ account_external_id: 'a2', spend: '15' }),
      makeRow({ account_external_id: 'a1', spend: '5' }),
      makeRow({ account_external_id: 'a3', spend: '50' }),
    ];
    expect(topAccountsBySpend(rows, 2)).toEqual(['a3', 'a2']);
  });
});

describe('metaAggregates.spendByObjective', () => {
  it('joins insights to campaigns on external_id and groups spend', () => {
    const insights = [
      makeRow({ campaign_external_id: 'c1', spend: '10' }),
      makeRow({ campaign_external_id: 'c2', spend: '20' }),
      makeRow({ campaign_external_id: 'c3', spend: '5' }), // unknown
    ];
    const campaigns: MetaCampaign[] = [
      {
        id: '1',
        external_id: 'c1',
        name: 'C1',
        platform: 'meta',
        status: 'ACTIVE',
        objective: 'TRAFFIC',
        currency: 'USD',
        account_external_id: 'a1',
        metadata: {},
        created_at: '',
        updated_at: '',
      },
      {
        id: '2',
        external_id: 'c2',
        name: 'C2',
        platform: 'meta',
        status: 'ACTIVE',
        objective: 'CONVERSIONS',
        currency: 'USD',
        account_external_id: 'a1',
        metadata: {},
        created_at: '',
        updated_at: '',
      },
    ];
    const slices = spendByObjective(insights, campaigns);
    const byLabel = Object.fromEntries(slices.map((s) => [s.label, s.value]));
    expect(byLabel.TRAFFIC).toBe(10);
    expect(byLabel.CONVERSIONS).toBe(20);
    expect(byLabel.UNKNOWN).toBe(5);
  });
});

describe('metaAggregates.derivedRoas + hasPurchaseActions + aggregatedRoas', () => {
  it('returns null when no purchase action present', () => {
    const row = makeRow({ spend: '100', actions: [{ action_type: 'link_click', value: 4 }] });
    expect(derivedRoas(row)).toBeNull();
    expect(hasPurchaseActions([row])).toBe(false);
    expect(aggregatedRoas([row])).toBeNull();
  });

  it('computes ROAS from omni_purchase action', () => {
    const row = makeRow({
      spend: '50',
      actions: [{ action_type: 'omni_purchase', value: 150 }],
    });
    expect(derivedRoas(row)).toBeCloseTo(3, 4);
    expect(hasPurchaseActions([row])).toBe(true);
    expect(aggregatedRoas([row])).toBeCloseTo(3, 4);
  });

  it('aggregates ROAS across rows', () => {
    const rows = [
      makeRow({ spend: '100', actions: [{ action_type: 'purchase', value: 200 }] }),
      makeRow({ spend: '100', actions: [{ action_type: 'omni_purchase', value: 100 }] }),
    ];
    expect(aggregatedRoas(rows)).toBeCloseTo(1.5, 4);
  });
});

describe('metaAggregates.groupCtrCpmByDate', () => {
  it('produces CTR + CPM per day', () => {
    const rows = [
      makeRow({ date: '2026-04-01', spend: '100', impressions: 1000, clicks: 50 }),
      makeRow({ date: '2026-04-01', spend: '50', impressions: 1000, clicks: 50 }),
      makeRow({ date: '2026-04-02', spend: '20', impressions: 400, clicks: 8 }),
    ];
    const pts = groupCtrCpmByDate(rows);
    expect(pts).toHaveLength(2);
    expect(pts[0].date).toBe('2026-04-01');
    expect(pts[0].ctr).toBeCloseTo(100 / 2000, 4);
    expect(pts[0].cpm).toBeCloseTo(75, 4); // (150/2000)*1000
    expect(pts[1].ctr).toBeCloseTo(0.02, 4);
    expect(pts[1].cpm).toBeCloseTo(50, 4);
  });
});
