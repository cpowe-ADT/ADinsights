import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsAssetsPage from '../GoogleAdsAssetsPage';

const getMock = vi.hoisted(() => vi.fn());
const pendingAsync = () => new Promise<never>(() => {});

vi.mock('../../../lib/apiClient', () => ({
  appendQueryParams: (endpoint: string) => endpoint,
  get: (...args: unknown[]) => getMock(...args),
}));

describe('GoogleAdsAssetsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMock.mockImplementation(() => pendingAsync());
  });

  it('renders the page heading', () => {
    render(
      <MemoryRouter>
        <GoogleAdsAssetsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText('Ads & Assets')).toBeInTheDocument();
  });

  it('renders KpiTile + PieComposition after loading', async () => {
    getMock.mockResolvedValueOnce({
      count: 2,
      results: [
        {
          asset_id: 'a1',
          asset_name: 'Buy Now',
          asset_type: 'IMAGE',
          impressions: 1000,
          clicks: 100,
          conversions: 5,
          policy_approval_status: 'APPROVED',
        },
        {
          asset_id: 'a2',
          asset_name: 'Shop Now',
          asset_type: 'TEXT',
          impressions: 500,
          clicks: 20,
          conversions: 1,
          policy_approval_status: 'DISAPPROVED',
        },
      ],
    });
    render(
      <MemoryRouter>
        <GoogleAdsAssetsPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getAllByText('Buy Now').length).toBeGreaterThan(0),
    );
    expect(screen.getByText('Total Assets')).toBeInTheDocument();
    expect(screen.getByText('Disapproved')).toBeInTheDocument();
    expect(screen.getByText('Top Asset Conv')).toBeInTheDocument();
    // PieComposition renders the sr-only table header 'Label'
    expect(screen.getAllByText('Label').length).toBeGreaterThan(0);
    // Status chip for DISAPPROVED row.
    expect(screen.getByText('DISAPPROVED')).toBeInTheDocument();
  });

  it('shows empty state with reasonCode when no assets', async () => {
    getMock.mockResolvedValueOnce({ count: 0, results: [] });
    const { container } = render(
      <MemoryRouter>
        <GoogleAdsAssetsPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(
        container.querySelector('[data-reason-code="no_assets"]'),
      ).toBeInTheDocument(),
    );
  });

  it('shows error state when fetch fails', async () => {
    getMock.mockRejectedValueOnce(new Error('Server error'));
    render(
      <MemoryRouter>
        <GoogleAdsAssetsPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByText('Server error')).toBeInTheDocument(),
    );
  });
});
