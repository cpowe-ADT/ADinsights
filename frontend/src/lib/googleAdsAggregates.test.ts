import { describe, expect, it } from 'vitest';

import {
  buildCampaignBubblePoints,
  buildChannelPie,
  buildQsCpcBubblePoints,
  buildTopSpendBars,
  channelTypeToBubbleShape,
  countChanges7d,
  deriveCampaignStatusTone,
  deriveChangeSeverity,
  deriveExportJobStatusTone,
  derivePacingPct,
  deriveRecommendationSeverity,
  deriveTrendSeries,
  formatRecommendationImpact,
  groupChangesByResourceType,
  groupRecommendationsByType,
  matchTypeToBubbleShape,
  rollupCampaignKpis,
  rollupKeywordKpis,
  rollupOverviewKpis,
  rollupPacingKpis,
  rollupRecommendationKpis,
  safeDivide,
  toNumber,
  topSearchTermsByConv,
} from './googleAdsAggregates';

describe('googleAdsAggregates — primitives', () => {
  it('toNumber handles null/undefined/NaN/strings', () => {
    expect(toNumber(null)).toBe(0);
    expect(toNumber(undefined)).toBe(0);
    expect(toNumber('')).toBe(0);
    expect(toNumber('abc')).toBe(0);
    expect(toNumber('3.5')).toBe(3.5);
    expect(toNumber(7)).toBe(7);
    expect(toNumber(Number.NaN)).toBe(0);
  });

  it('safeDivide returns 0 on zero denominator', () => {
    expect(safeDivide(10, 0)).toBe(0);
    expect(safeDivide(10, 2)).toBe(5);
    expect(safeDivide(0, 0)).toBe(0);
  });
});

describe('rollupOverviewKpis', () => {
  it('uses metrics when present', () => {
    const kpis = rollupOverviewKpis({
      metrics: { spend: 100, conversions: 10, cpa: 10, roas: 2.5 },
    });
    expect(kpis).toEqual({ spend: 100, conversions: 10, cpa: 10, roas: 2.5 });
  });

  it('derives cpa from spend/conversions when metrics.cpa missing', () => {
    const kpis = rollupOverviewKpis({ metrics: { spend: 50, conversions: 5 } });
    expect(kpis.cpa).toBe(10);
  });

  it('handles null summary', () => {
    expect(rollupOverviewKpis(null)).toEqual({ spend: 0, conversions: 0, cpa: 0, roas: 0 });
  });
});

describe('deriveTrendSeries', () => {
  it('sorts by date and coerces values', () => {
    const out = deriveTrendSeries([
      { date: '2026-02-02', spend: '5', conversions: '1' },
      { date: '2026-02-01', spend: 10, conversions: 2 },
    ]);
    expect(out).toHaveLength(2);
    expect(out[0].date).toBe('2026-02-01');
    expect(out[0].spend).toBe(10);
    expect(out[1].conversions).toBe(1);
  });

  it('filters out rows with empty date', () => {
    const out = deriveTrendSeries([{ spend: 1 }, { date: '', spend: 2 }]);
    expect(out).toHaveLength(0);
  });

  it('returns [] on null', () => {
    expect(deriveTrendSeries(null)).toEqual([]);
  });
});

describe('buildChannelPie', () => {
  it('aggregates spend by channel_type (uppercased) and sorts desc', () => {
    const pie = buildChannelPie([
      { channel_type: 'search', spend: 50 },
      { channel_type: 'SEARCH', spend: 25 },
      { channel_type: 'DISPLAY', spend: 100 },
    ]);
    expect(pie).toEqual([
      { label: 'DISPLAY', value: 100 },
      { label: 'SEARCH', value: 75 },
    ]);
  });

  it('returns empty array when no rows', () => {
    expect(buildChannelPie(null)).toEqual([]);
    expect(buildChannelPie([])).toEqual([]);
  });

  it('buckets missing channel_type as OTHER', () => {
    const pie = buildChannelPie([{ spend: 10 }]);
    expect(pie).toEqual([{ label: 'OTHER', value: 10 }]);
  });
});

describe('rollupCampaignKpis', () => {
  it('sums spend/conversions and derives weighted CPA/ROAS', () => {
    const kpis = rollupCampaignKpis([
      { spend: 100, conversions: 10, conversion_value: 300 },
      { spend: 50, conversions: 5, conversion_value: 100 },
    ]);
    expect(kpis.totalSpend).toBe(150);
    expect(kpis.totalConversions).toBe(15);
    expect(kpis.avgCpa).toBe(10); // 150/15
    expect(kpis.avgRoas).toBeCloseTo(400 / 150, 5);
  });

  it('returns zeros on empty rows', () => {
    expect(rollupCampaignKpis([])).toEqual({
      totalSpend: 0,
      totalConversions: 0,
      avgCpa: 0,
      avgRoas: 0,
    });
  });
});

describe('buildCampaignBubblePoints', () => {
  it('derives conv_rate divide-safe', () => {
    const bubbles = buildCampaignBubblePoints([
      { campaign_id: 'a', campaign_name: 'A', channel_type: 'SEARCH', spend: 100, clicks: 50, conversions: 5, impressions: 1000 },
      { campaign_id: 'b', campaign_name: 'B', channel_type: 'DISPLAY', spend: 80, clicks: 0, conversions: 0, impressions: 400 },
    ]);
    expect(bubbles).toHaveLength(2);
    expect(bubbles[0].y).toBe(5 / 50);
    expect(bubbles[1].y).toBe(0); // divide-safe
    expect(bubbles[0].shape).toBe('circle');
    expect(bubbles[1].shape).toBe('triangle');
  });

  it('filters out rows with all-zero metrics', () => {
    const bubbles = buildCampaignBubblePoints([
      { campaign_id: 'empty', spend: 0, clicks: 0, conversions: 0, impressions: 0 },
    ]);
    expect(bubbles).toHaveLength(0);
  });
});

describe('channelTypeToBubbleShape', () => {
  it('maps known channels and falls back to circle', () => {
    expect(channelTypeToBubbleShape('SEARCH')).toBe('circle');
    expect(channelTypeToBubbleShape('display')).toBe('triangle');
    expect(channelTypeToBubbleShape('VIDEO')).toBe('square');
    expect(channelTypeToBubbleShape('PERFORMANCE_MAX')).toBe('square');
    expect(channelTypeToBubbleShape('UNKNOWN')).toBe('circle');
    expect(channelTypeToBubbleShape(undefined)).toBe('circle');
  });
});

describe('buildTopSpendBars', () => {
  it('returns top-N by spend desc, ignoring zeros', () => {
    const rows = [
      { campaign_name: 'a', spend: 10 },
      { campaign_name: 'b', spend: 50 },
      { campaign_name: 'c', spend: 20 },
      { campaign_name: 'd', spend: 0 },
    ];
    const bars = buildTopSpendBars(rows, 2);
    expect(bars).toEqual([
      { label: 'b', value: 50 },
      { label: 'c', value: 20 },
    ]);
  });

  it('returns empty array when no rows', () => {
    expect(buildTopSpendBars(null)).toEqual([]);
  });
});

describe('rollupKeywordKpis', () => {
  it('counts rows, averages QS, tracks top conversions', () => {
    const kpis = rollupKeywordKpis([
      { keyword_text: 'a', quality_score: 8, conversions: 2 },
      { keyword_text: 'b', quality_score: 6, conversions: 10 },
      { keyword_text: 'c', quality_score: null, conversions: 1 },
    ]);
    expect(kpis.count).toBe(3);
    expect(kpis.avgQualityScore).toBe(7); // (8+6)/2
    expect(kpis.topConversions).toBe(10);
  });

  it('returns avgQualityScore=null when no row has QS', () => {
    const kpis = rollupKeywordKpis([{ keyword_text: 'x', quality_score: null, conversions: 0 }]);
    expect(kpis.avgQualityScore).toBeNull();
  });

  it('handles empty rows', () => {
    expect(rollupKeywordKpis([])).toEqual({ count: 0, avgQualityScore: null, topConversions: 0 });
  });
});

describe('buildQsCpcBubblePoints', () => {
  it('derives cpc = spend/clicks divide-safe and maps match_type', () => {
    const bubbles = buildQsCpcBubblePoints([
      { keyword_text: 'brand', match_type: 'EXACT', quality_score: 9, spend: 50, clicks: 25, impressions: 500 },
      { keyword_text: 'generic', match_type: 'BROAD', quality_score: 4, spend: 20, clicks: 0, impressions: 100 },
    ]);
    expect(bubbles[0].y).toBe(2);
    expect(bubbles[0].shape).toBe('circle');
    expect(bubbles[1].y).toBe(0);
    expect(bubbles[1].shape).toBe('square');
  });
});

describe('matchTypeToBubbleShape', () => {
  it('maps exact/phrase/broad and falls back', () => {
    expect(matchTypeToBubbleShape('EXACT')).toBe('circle');
    expect(matchTypeToBubbleShape('phrase')).toBe('triangle');
    expect(matchTypeToBubbleShape('BROAD')).toBe('square');
    expect(matchTypeToBubbleShape('other')).toBe('circle');
  });
});

describe('topSearchTermsByConv', () => {
  it('returns top terms by conversions desc', () => {
    const bars = topSearchTermsByConv([
      { search_term: 'a', conversions: 3 },
      { search_term: 'b', conversions: 10 },
      { search_term: 'c', conversions: 0 },
    ]);
    expect(bars).toEqual([
      { label: 'b', value: 10 },
      { label: 'a', value: 3 },
    ]);
  });
});

describe('deriveChangeSeverity', () => {
  it('maps operations per architect §6.8', () => {
    expect(deriveChangeSeverity('CREATE')).toBe('info');
    expect(deriveChangeSeverity('created')).toBe('info');
    expect(deriveChangeSeverity('UPDATE')).toBe('warning');
    expect(deriveChangeSeverity('REMOVE')).toBe('danger');
    expect(deriveChangeSeverity('DELETE')).toBe('danger');
    expect(deriveChangeSeverity(undefined)).toBe('info');
  });
});

describe('deriveCampaignStatusTone', () => {
  it('maps status to tone', () => {
    expect(deriveCampaignStatusTone('ENABLED')).toBe('success');
    expect(deriveCampaignStatusTone('PAUSED')).toBe('warning');
    expect(deriveCampaignStatusTone('REMOVED')).toBe('danger');
    expect(deriveCampaignStatusTone('DRAFT')).toBe('neutral');
    expect(deriveCampaignStatusTone(undefined)).toBe('neutral');
  });
});

// ---------------------------------------------------------------------------
// S3c pacing helpers
// ---------------------------------------------------------------------------
describe('derivePacingPct', () => {
  it('uses payload pacing_pct when finite', () => {
    expect(derivePacingPct({ pacing_pct: 0.87, spend_mtd: 1, budget_month: 2 })).toBe(0.87);
  });
  it('derives from spend_mtd / budget_month when pacing_pct missing', () => {
    expect(derivePacingPct({ spend_mtd: 250, budget_month: 1000 })).toBe(0.25);
  });
  it('returns null when budget is zero (avoid divide-by-zero)', () => {
    expect(derivePacingPct({ spend_mtd: 10, budget_month: 0 })).toBeNull();
  });
  it('returns null for null/undefined payload', () => {
    expect(derivePacingPct(null)).toBeNull();
    expect(derivePacingPct(undefined)).toBeNull();
  });
});

describe('rollupPacingKpis', () => {
  it('coerces strings and nulls to zero', () => {
    expect(rollupPacingKpis({ spend_mtd: 100, budget_month: 200, forecast_month_end: 180, over_under: -20 }))
      .toEqual({ spendMtd: 100, budgetMonth: 200, forecast: 180, overUnder: -20 });
  });
  it('handles missing payload', () => {
    expect(rollupPacingKpis(null)).toEqual({ spendMtd: 0, budgetMonth: 0, forecast: 0, overUnder: 0 });
  });
});

// ---------------------------------------------------------------------------
// S3c changes helpers
// ---------------------------------------------------------------------------
describe('groupChangesByResourceType', () => {
  it('groups by change_resource_type, descending by count', () => {
    const bars = groupChangesByResourceType([
      { change_resource_type: 'campaign' },
      { change_resource_type: 'campaign' },
      { change_resource_type: 'ad' },
    ]);
    expect(bars).toEqual([
      { label: 'CAMPAIGN', value: 2 },
      { label: 'AD', value: 1 },
    ]);
  });
  it('returns empty array when no rows', () => {
    expect(groupChangesByResourceType([])).toEqual([]);
  });
});

describe('countChanges7d', () => {
  it('counts rows whose change_date_time is within last 7 days', () => {
    const now = new Date('2026-04-15T00:00:00Z');
    const rows = [
      { change_date_time: '2026-04-14T10:00:00Z' }, // within 7d
      { change_date_time: '2026-04-01T00:00:00Z' }, // > 7d
      { change_date_time: '2026-04-10T00:00:00Z' }, // within 7d
      {}, // no ts
    ];
    expect(countChanges7d(rows, now)).toBe(2);
  });
  it('handles empty/null', () => {
    expect(countChanges7d(null)).toBe(0);
    expect(countChanges7d(undefined)).toBe(0);
  });
});

// ---------------------------------------------------------------------------
// S3c recommendations helpers
// ---------------------------------------------------------------------------
describe('deriveRecommendationSeverity', () => {
  it('prefers impact_metadata.severity when present', () => {
    expect(deriveRecommendationSeverity({ impact_metadata: { severity: 'danger' } })).toBe('danger');
    expect(deriveRecommendationSeverity({ impact_metadata: { severity: 'WARNING' } })).toBe('warning');
    expect(deriveRecommendationSeverity({ impact_metadata: { severity: 'info' } })).toBe('info');
    expect(deriveRecommendationSeverity({ impact_metadata: { severity: 'HIGH' } })).toBe('danger');
  });
  it('falls back to type heuristic — budget/bid → warning', () => {
    expect(deriveRecommendationSeverity({ recommendation_type: 'CAMPAIGN_BUDGET' })).toBe('warning');
    expect(deriveRecommendationSeverity({ recommendation_type: 'KEYWORD_BID' })).toBe('warning');
  });
  it('falls back to type heuristic — policy → danger', () => {
    expect(deriveRecommendationSeverity({ recommendation_type: 'POLICY_VIOLATION' })).toBe('danger');
    expect(deriveRecommendationSeverity({ recommendation_type: 'DISAPPROVED_AD' })).toBe('danger');
  });
  it('defaults to info for unknown types', () => {
    expect(deriveRecommendationSeverity({ recommendation_type: 'TEXT_AD' })).toBe('info');
    expect(deriveRecommendationSeverity({})).toBe('info');
    expect(deriveRecommendationSeverity(null)).toBe('info');
  });
});

describe('rollupRecommendationKpis', () => {
  it('counts active vs dismissed', () => {
    expect(rollupRecommendationKpis([
      { dismissed: false },
      { dismissed: true },
      { dismissed: false },
    ])).toEqual({ active: 2, dismissed: 1 });
  });
  it('handles empty', () => {
    expect(rollupRecommendationKpis([])).toEqual({ active: 0, dismissed: 0 });
  });
});

describe('groupRecommendationsByType', () => {
  it('groups by recommendation_type descending', () => {
    expect(groupRecommendationsByType([
      { recommendation_type: 'BUDGET' },
      { recommendation_type: 'BUDGET' },
      { recommendation_type: 'KEYWORD' },
    ])).toEqual([
      { label: 'BUDGET', value: 2 },
      { label: 'KEYWORD', value: 1 },
    ]);
  });
});

describe('formatRecommendationImpact', () => {
  it('extracts known keys', () => {
    expect(formatRecommendationImpact({
      impact_metadata: { primary_metric: 'conversions', impact_percentage: 0.15, description: 'Add extensions' },
    })).toBe('conversions · 15.0% · Add extensions');
  });
  it('falls back to JSON preview', () => {
    const s = formatRecommendationImpact({ impact_metadata: { other: 'value' } });
    expect(s).toContain('other');
  });
  it('returns dash when metadata missing', () => {
    expect(formatRecommendationImpact({})).toBe('—');
  });
});

// ---------------------------------------------------------------------------
// S3c reports helpers
// ---------------------------------------------------------------------------
describe('deriveExportJobStatusTone', () => {
  it('maps export job status to tones', () => {
    expect(deriveExportJobStatusTone('complete')).toBe('success');
    expect(deriveExportJobStatusTone('queued')).toBe('warning');
    expect(deriveExportJobStatusTone('running')).toBe('warning');
    expect(deriveExportJobStatusTone('failed')).toBe('danger');
    expect(deriveExportJobStatusTone('unknown-status')).toBe('neutral');
  });
});
