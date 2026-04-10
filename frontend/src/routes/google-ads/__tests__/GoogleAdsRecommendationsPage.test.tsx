import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsRecommendationsPage from '../GoogleAdsRecommendationsPage';

const fetchGoogleAdsListMock = vi.hoisted(() => vi.fn());
const pendingAsync = () => new Promise<never>(() => {});

vi.mock('../../../lib/googleAdsDashboard', () => ({
  fetchGoogleAdsList: (...args: unknown[]) => fetchGoogleAdsListMock(...args),
}));

vi.mock('../../../lib/apiClient', () => ({
  appendQueryParams: (endpoint: string) => endpoint,
}));

describe('GoogleAdsRecommendationsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchGoogleAdsListMock.mockImplementation(() => pendingAsync());
  });

  it('renders the page heading', () => {
    render(
      <MemoryRouter>
        <GoogleAdsRecommendationsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText('Recommendations & Opportunities')).toBeInTheDocument();
  });

  it('renders recommendation rows after loading', async () => {
    fetchGoogleAdsListMock.mockResolvedValueOnce({
      count: 1,
      results: [{ type: 'keyword', impact: 'high', description: 'Add broad match' }],
    });
    render(
      <MemoryRouter>
        <GoogleAdsRecommendationsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('Add broad match')).toBeInTheDocument());
  });
});
