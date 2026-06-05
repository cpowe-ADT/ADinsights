import { render, screen } from '@testing-library/react';
import { describe, expect, it } from 'vitest';

import AssetsTabSection from '../tab-sections/AssetsTabSection';
import type { GoogleAdsAssetRow } from '../../../../lib/googleAdsCreativeConvAggregates';

const makeRow = (over: Partial<GoogleAdsAssetRow> = {}): GoogleAdsAssetRow => ({
  asset_id: 'a-1',
  asset_type: 'IMAGE',
  asset_name: 'Hero image',
  policy_approval_status: 'APPROVED',
  impressions: 1000,
  clicks: 50,
  conversions: 5,
  cpa: 12.5,
  ...over,
});

describe('AssetsTabSection — integration', () => {
  it('renders loading state', () => {
    render(<AssetsTabSection data={null} status="loading" error="" />);
    expect(screen.getByText('Loading assets...')).toBeInTheDocument();
  });

  it('renders empty state', () => {
    render(<AssetsTabSection data={{ count: 0, results: [] }} status="success" error="" />);
    expect(screen.getByText('No assets in range')).toBeInTheDocument();
  });

  it('renders populated state', () => {
    const payload = {
      count: 2,
      results: [
        makeRow(),
        makeRow({
          asset_id: 'a-2',
          asset_type: 'TEXT',
          asset_name: 'Headline',
          policy_approval_status: 'DISAPPROVED',
          conversions: 2,
        }),
      ],
    };
    render(<AssetsTabSection data={payload} status="success" error="" />);
    expect(screen.getByTestId('google-ads-assets-section')).toBeInTheDocument();
    expect(screen.getByText(/Asset performance/)).toBeInTheDocument();
    expect(screen.getByText('APPROVED')).toBeInTheDocument();
    expect(screen.getByText('DISAPPROVED')).toBeInTheDocument();
  });
});
