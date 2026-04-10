import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsCampaignsPage from '../GoogleAdsCampaignsPage';

const fetchGoogleAdsListMock = vi.hoisted(() => vi.fn());

vi.mock('../../../lib/googleAdsDashboard', () => ({
  fetchGoogleAdsList: (...args: unknown[]) => fetchGoogleAdsListMock(...args),
}));

vi.mock('../../../lib/apiClient', () => ({
  appendQueryParams: (endpoint: string) => endpoint,
}));

describe('GoogleAdsCampaignsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchGoogleAdsListMock.mockResolvedValue({ count: 1, results: [{ campaign_id: 'c1', name: 'Brand', spend: 500 }] });
  });

  it('renders the page heading', async () => {
    render(
      <MemoryRouter>
        <GoogleAdsCampaignsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText('Performance by Campaign')).toBeInTheDocument();
  });

  it('renders data rows after loading', async () => {
    render(
      <MemoryRouter>
        <GoogleAdsCampaignsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(fetchGoogleAdsListMock).toHaveBeenCalled());
    await waitFor(() => expect(screen.getByText('Brand')).toBeInTheDocument());
  });

  it('shows error state when fetch fails', async () => {
    fetchGoogleAdsListMock.mockRejectedValue(new Error('Network error'));
    render(
      <MemoryRouter>
        <GoogleAdsCampaignsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('Network error')).toBeInTheDocument());
  });
});
