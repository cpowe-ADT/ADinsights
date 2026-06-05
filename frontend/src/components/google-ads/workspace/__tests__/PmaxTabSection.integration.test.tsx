import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import PmaxTabSection from '../tab-sections/PmaxTabSection';
import type { GoogleAdsAssetGroupRow } from '../../../../lib/googleAdsCreativeConvAggregates';

const makeRow = (over: Partial<GoogleAdsAssetGroupRow> = {}): GoogleAdsAssetGroupRow => ({
  asset_group_id: 'ag-1',
  asset_group_name: 'Spring Promo',
  asset_group_status: 'ENABLED',
  spend: 800,
  impressions: 12000,
  clicks: 220,
  conversions: 18,
  conversion_value: 2400,
  cpa: 44,
  roas: 3,
  ...over,
});

describe('PmaxTabSection — integration', () => {
  it('renders loading state', () => {
    render(<PmaxTabSection data={null} status="loading" error="" />);
    expect(screen.getByText('Loading Performance Max asset groups...')).toBeInTheDocument();
  });

  it('renders empty state', () => {
    render(<PmaxTabSection data={{ count: 0, results: [] }} status="success" error="" />);
    expect(screen.getByText('No Performance Max asset groups')).toBeInTheDocument();
  });

  it('renders populated state', () => {
    const payload = {
      count: 2,
      results: [
        makeRow(),
        makeRow({
          asset_group_id: 'ag-2',
          asset_group_name: 'Summer Blitz',
          asset_group_status: 'PAUSED',
        }),
      ],
    };
    render(<PmaxTabSection data={payload} status="success" error="" />);
    expect(screen.getByTestId('google-ads-pmax-section')).toBeInTheDocument();
    expect(screen.getAllByText('Spring Promo').length).toBeGreaterThan(0);
    expect(screen.getByText('PAUSED')).toBeInTheDocument();
  });
});
