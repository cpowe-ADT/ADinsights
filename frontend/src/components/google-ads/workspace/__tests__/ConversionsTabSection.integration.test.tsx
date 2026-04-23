import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import ConversionsTabSection from '../tab-sections/ConversionsTabSection';
import type { GoogleAdsConversionActionRow } from '../../../../lib/googleAdsCreativeConvAggregates';
import type { SummaryRecord } from '../types';

const summaryWithMetrics = (
  metrics: Record<string, number> = {},
): SummaryRecord =>
  ({
    window: {
      start_date: '2026-04-01',
      end_date: '2026-04-23',
      compare_start_date: '2026-03-09',
      compare_end_date: '2026-03-31',
    },
    metrics: { impressions: 0, clicks: 0, conversions: 0, ...metrics },
    comparison: {},
    pacing: {},
    trend: [],
    movers: [],
    data_freshness_ts: null,
    source_engine: 'test',
    alerts_summary: {
      overspend_risk: false,
      underdelivery: false,
      spend_spike: false,
      conversion_drop: false,
    },
    governance_summary: {
      recent_changes_7d: 0,
      active_recommendations: 0,
      disapproved_ads: 0,
    },
    top_insights: [],
    workspace_generated_at: '2026-04-23T00:00:00Z',
  }) as unknown as SummaryRecord;

const convRow = (
  over: Partial<GoogleAdsConversionActionRow> = {},
): GoogleAdsConversionActionRow => ({
  conversion_action_id: 'ca-1',
  conversion_action_name: 'Purchase',
  conversions: 12,
  value: 2400,
  cpa: 50,
  ...over,
});

describe('ConversionsTabSection — integration', () => {
  it('renders loading state', () => {
    render(
      <ConversionsTabSection
        data={null}
        status="loading"
        error=""
        summary={null}
      />,
    );
    expect(screen.getByText('Loading conversions...')).toBeInTheDocument();
  });

  it('renders empty state', () => {
    render(
      <ConversionsTabSection
        data={{ count: 0, results: [] }}
        status="success"
        error=""
        summary={summaryWithMetrics()}
      />,
    );
    expect(screen.getByText('No conversion data')).toBeInTheDocument();
  });

  it('renders populated state', () => {
    const summary = summaryWithMetrics({
      impressions: 10000,
      clicks: 500,
      conversions: 12,
    });
    render(
      <ConversionsTabSection
        data={{ count: 1, results: [convRow()] }}
        status="success"
        error=""
        summary={summary}
      />,
    );
    expect(
      screen.getByTestId('google-ads-conversions-section'),
    ).toBeInTheDocument();
    expect(screen.getAllByText('Purchase').length).toBeGreaterThan(0);
  });
});
