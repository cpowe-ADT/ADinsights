import { render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';

import CampaignsTabSection from '../tab-sections/CampaignsTabSection';
import type { GoogleAdsCampaignRow } from '../../../../lib/googleAdsAggregates';

const makeRow = (over: Partial<GoogleAdsCampaignRow> = {}): GoogleAdsCampaignRow => ({
  campaign_id: 'c-1',
  campaign_name: 'Brand Always-On',
  campaign_status: 'ENABLED',
  channel_type: 'SEARCH',
  spend: 1200,
  clicks: 300,
  impressions: 15000,
  conversions: 24,
  conversion_value: 3600,
  roas: 3,
  cpa: 50,
  ...over,
});

describe('CampaignsTabSection — integration', () => {
  const baseProps = {
    drawerCampaignId: '',
    onOpenDrawer: vi.fn(),
    onCloseDrawer: vi.fn(),
  };

  it('renders loading state', () => {
    render(
      <CampaignsTabSection
        data={null}
        status="loading"
        error=""
        {...baseProps}
      />,
    );
    expect(screen.getByText('Loading campaigns...')).toBeInTheDocument();
  });

  it('renders empty state', () => {
    render(
      <CampaignsTabSection
        data={{ count: 0, results: [] }}
        status="success"
        error=""
        {...baseProps}
      />,
    );
    expect(screen.getByText('No campaigns in range')).toBeInTheDocument();
  });

  it('renders populated state', () => {
    const payload = {
      count: 1,
      results: [makeRow()],
    };
    render(
      <CampaignsTabSection
        data={payload}
        status="success"
        error=""
        {...baseProps}
      />,
    );
    expect(
      screen.getByTestId('google-ads-campaigns-section'),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', {
        name: /Open campaign details for Brand Always-On/,
      }),
    ).toBeInTheDocument();
    expect(screen.getByText('ENABLED')).toBeInTheDocument();
  });
});
