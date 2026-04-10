import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsPmaxPage from '../GoogleAdsPmaxPage';

const fetchGoogleAdsListMock = vi.hoisted(() => vi.fn());
const pendingAsync = () => new Promise<never>(() => {});

vi.mock('../../../lib/googleAdsDashboard', () => ({
  fetchGoogleAdsList: (...args: unknown[]) => fetchGoogleAdsListMock(...args),
}));

vi.mock('../../../lib/apiClient', () => ({
  appendQueryParams: (endpoint: string) => endpoint,
}));

describe('GoogleAdsPmaxPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchGoogleAdsListMock.mockImplementation(() => pendingAsync());
  });

  it('renders the page heading', () => {
    render(
      <MemoryRouter>
        <GoogleAdsPmaxPage />
      </MemoryRouter>,
    );
    expect(screen.getByText('Performance Max')).toBeInTheDocument();
  });

  it('renders data rows after loading', async () => {
    fetchGoogleAdsListMock.mockResolvedValueOnce({
      count: 1,
      results: [{ asset_group: 'AG1', conversions: 15 }],
    });
    render(
      <MemoryRouter>
        <GoogleAdsPmaxPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('AG1')).toBeInTheDocument());
  });
});
