import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsAssetsPage from '../GoogleAdsAssetsPage';

const fetchGoogleAdsListMock = vi.hoisted(() => vi.fn());

vi.mock('../../../lib/googleAdsDashboard', () => ({
  fetchGoogleAdsList: (...args: unknown[]) => fetchGoogleAdsListMock(...args),
}));

vi.mock('../../../lib/apiClient', () => ({
  appendQueryParams: (endpoint: string) => endpoint,
}));

describe('GoogleAdsAssetsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchGoogleAdsListMock.mockResolvedValue({ count: 1, results: [{ ad_id: 'a1', headline: 'Buy Now', status: 'approved' }] });
  });

  it('renders the page heading', () => {
    render(
      <MemoryRouter>
        <GoogleAdsAssetsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText('Ads & Assets')).toBeInTheDocument();
  });

  it('renders data rows after loading', async () => {
    render(
      <MemoryRouter>
        <GoogleAdsAssetsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('Buy Now')).toBeInTheDocument());
  });

  it('shows error state when fetch fails', async () => {
    fetchGoogleAdsListMock.mockRejectedValue(new Error('Server error'));
    render(
      <MemoryRouter>
        <GoogleAdsAssetsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('Server error')).toBeInTheDocument());
  });
});
