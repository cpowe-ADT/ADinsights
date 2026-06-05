import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import OverviewTabSection from '../tab-sections/OverviewTabSection';
import type { SummaryRecord } from '../types';
import type { GoogleAdsCampaignRow } from '../../../../lib/googleAdsAggregates';

const buildSummary = (): SummaryRecord =>
  ({
    window: {
      start_date: '2026-04-01',
      end_date: '2026-04-23',
      compare_start_date: '2026-03-09',
      compare_end_date: '2026-03-31',
    },
    metrics: {
      spend: 5000,
      conversions: 42,
      cpa: 119,
      roas: 2.4,
    },
    comparison: {},
    pacing: {},
    trend: [
      { date: '2026-04-01', spend: 100, conversions: 2 },
      { date: '2026-04-02', spend: 120, conversions: 3 },
    ],
    movers: [
      {
        campaign_id: 'c-1',
        campaign_name: 'Brand Always-On',
        spend: 1200,
        conversion_value: 2400,
        roas: 2,
      },
    ],
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

const campaignRow: GoogleAdsCampaignRow = {
  campaign_id: 'c-1',
  campaign_name: 'Brand Always-On',
  campaign_status: 'ENABLED',
  channel_type: 'SEARCH',
  spend: 1200,
  clicks: 300,
  impressions: 15000,
  conversions: 24,
};

describe('OverviewTabSection — integration', () => {
  it('renders loading state', () => {
    render(<OverviewTabSection summary={null} />);
    expect(screen.getByText('Loading overview...')).toBeInTheDocument();
  });

  it('renders empty state (no channel breakdown when campaignRows missing)', () => {
    render(<OverviewTabSection summary={buildSummary()} campaignRows={null} />);
    expect(screen.getByText('No channel breakdown available')).toBeInTheDocument();
  });

  it('renders populated state', () => {
    render(<OverviewTabSection summary={buildSummary()} campaignRows={[campaignRow]} />);
    expect(screen.getByTestId('google-ads-overview-section')).toBeInTheDocument();
    expect(screen.getByText('Brand Always-On')).toBeInTheDocument();
    expect(screen.getByText('Top movers')).toBeInTheDocument();
  });
});
