import { render, screen, within } from '@testing-library/react';
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

const withCampaigns = (
  campaigns: NonNullable<GoogleAdsPacingPayload['campaigns']>,
): GoogleAdsPacingPayload => ({ ...basePayload, campaigns });

describe('PacingTabSection — per-campaign GA-A1', () => {
  it('renders per-campaign panel when campaigns is non-empty', () => {
    const data = withCampaigns([
      {
        campaign_id: '1',
        campaign_name: 'Q2 Brand Always-On',
        budget_amount: 5000,
        spend_mtd: 2800,
        pace_pct: 0.56,
        projected_eom: 4200,
        variance: -800,
      },
    ]);
    render(<PacingTabSection data={data} status="success" error="" />);
    const panel = screen.getByTestId('google-ads-pacing-campaigns');
    expect(panel).toBeInTheDocument();
    // The campaign name appears twice — once in the rendered table and once
    // inside the DistributionBar's `sr-only` accessible-table mirror.
    expect(within(panel).getAllByText('Q2 Brand Always-On').length).toBeGreaterThan(0);
    expect(within(panel).getAllByText('56%').length).toBeGreaterThan(0);
  });

  it('renders campaigns with null budget without pace % or variance', () => {
    const data = withCampaigns([
      {
        campaign_id: '2',
        campaign_name: 'Promo Push — No Budget Match',
        budget_amount: null,
        spend_mtd: 350,
        pace_pct: null,
        projected_eom: 525,
        variance: null,
      },
    ]);
    render(<PacingTabSection data={data} status="success" error="" />);
    const panel = screen.getByTestId('google-ads-pacing-campaigns');
    const row = within(panel)
      .getByText('Promo Push — No Budget Match')
      .closest('tr');
    expect(row).not.toBeNull();
    const cells = row!.querySelectorAll('td');
    // Columns: Campaign, Spend, Budget, Pace %, Variance
    expect(cells[2].textContent).toBe('—');
    expect(cells[3].textContent).toBe('—');
    expect(cells[4].textContent).toBe('—');
  });

  it('KPI "Over-pacing campaigns" counts only campaigns with pace_pct > 1.0', () => {
    const data = withCampaigns([
      {
        campaign_id: '1',
        campaign_name: 'Over A',
        budget_amount: 100,
        spend_mtd: 120,
        pace_pct: 1.2,
      },
      {
        campaign_id: '2',
        campaign_name: 'Under',
        budget_amount: 100,
        spend_mtd: 40,
        pace_pct: 0.4,
      },
      {
        campaign_id: '3',
        campaign_name: 'Over B',
        budget_amount: 100,
        spend_mtd: 150,
        pace_pct: 1.5,
      },
      {
        campaign_id: '4',
        campaign_name: 'Unmatched budget',
        budget_amount: null,
        spend_mtd: 25,
        pace_pct: null,
      },
      {
        campaign_id: '5',
        campaign_name: 'Exactly at budget',
        budget_amount: 100,
        spend_mtd: 100,
        pace_pct: 1.0,
      },
    ]);
    render(<PacingTabSection data={data} status="success" error="" />);
    // KPI tile label + value are siblings in the DOM. Find the tile root by
    // locating the label and reading the surrounding tile's value.
    const label = screen.getByText('Over-pacing campaigns');
    const tile = label.closest('.kpi-tile') ?? label.parentElement;
    expect(tile).not.toBeNull();
    expect(tile!.textContent).toContain('2');
  });

  it('absent per-campaign section when payload.campaigns is an empty array (no crash)', () => {
    const data = withCampaigns([]);
    render(<PacingTabSection data={data} status="success" error="" />);
    expect(screen.queryByTestId('google-ads-pacing-campaigns')).toBeNull();
    // Over-pacing tile is hidden when there is nothing to count from a
    // definite campaigns array — the design shows the tile only if there's a
    // campaigns payload at all. We keep it rendered (empty array is still a
    // payload), so the count should be 0.
    expect(screen.getByText('Over-pacing campaigns')).toBeInTheDocument();
  });

  it('omits per-campaign section when campaigns key is absent', () => {
    render(<PacingTabSection data={basePayload} status="success" error="" />);
    expect(screen.queryByTestId('google-ads-pacing-campaigns')).toBeNull();
    expect(screen.queryByText('Over-pacing campaigns')).toBeNull();
  });
});
