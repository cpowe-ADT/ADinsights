import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsChannelsPage from '../GoogleAdsChannelsPage';

const fetchGoogleAdsListMock = vi.hoisted(() => vi.fn());
const pendingAsync = () => new Promise<never>(() => {});

vi.mock('../../../lib/googleAdsDashboard', () => ({
  fetchGoogleAdsList: (...args: unknown[]) => fetchGoogleAdsListMock(...args),
}));

vi.mock('../../../lib/apiClient', () => ({
  appendQueryParams: (endpoint: string) => endpoint,
}));

describe('GoogleAdsChannelsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchGoogleAdsListMock.mockImplementation(() => pendingAsync());
  });

  it('renders the page heading', () => {
    render(
      <MemoryRouter>
        <GoogleAdsChannelsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText('Channel Views')).toBeInTheDocument();
  });

  it('renders data rows after loading', async () => {
    fetchGoogleAdsListMock.mockResolvedValueOnce({
      count: 1,
      results: [{ channel: 'Search', spend: 800 }],
    });
    render(
      <MemoryRouter>
        <GoogleAdsChannelsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('Search')).toBeInTheDocument());
  });
});
