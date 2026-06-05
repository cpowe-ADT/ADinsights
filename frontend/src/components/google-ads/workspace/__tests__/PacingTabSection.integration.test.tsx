import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import PacingTabSection from '../tab-sections/PacingTabSection';
import type { GoogleAdsPacingPayload } from '../../../../lib/googleAdsAggregates';

const basePayload: GoogleAdsPacingPayload = {
  month: '2026-04',
  spend_mtd: 12345,
  budget_month: 20000,
  forecast_month_end: 18500,
  over_under: -1500,
  runway_days: 14.2,
  alerts: { overspend_risk: false, underdelivery: false },
};

describe('PacingTabSection — integration', () => {
  it('renders loading state', () => {
    render(<PacingTabSection data={null} status="loading" error="" />);
    expect(screen.getByText('Loading pacing...')).toBeInTheDocument();
  });

  it('renders empty state', () => {
    render(<PacingTabSection data={{ spend_mtd: 0, budget_month: 0 }} status="success" error="" />);
    expect(screen.getByText('No pacing data')).toBeInTheDocument();
  });

  it('renders populated state with per-campaign panel', () => {
    const data: GoogleAdsPacingPayload = {
      ...basePayload,
      campaigns: [
        {
          campaign_id: '1',
          campaign_name: 'Q2 Brand Always-On',
          budget_amount: 5000,
          spend_mtd: 2800,
          pace_pct: 0.56,
          projected_eom: 4200,
          variance: -800,
        },
      ],
    };
    render(<PacingTabSection data={data} status="success" error="" />);
    expect(screen.getByTestId('google-ads-pacing-section')).toBeInTheDocument();
    expect(screen.getByTestId('google-ads-pacing-campaigns')).toBeInTheDocument();
    expect(screen.getAllByText('Q2 Brand Always-On').length).toBeGreaterThan(0);
  });
});
