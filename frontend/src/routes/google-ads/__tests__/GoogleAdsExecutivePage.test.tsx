import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsExecutivePage from '../GoogleAdsExecutivePage';

const fetchGoogleAdsExecutiveMock = vi.hoisted(() => vi.fn());
const pendingAsync = () => new Promise<never>(() => {});

vi.mock('../../../lib/googleAdsDashboard', () => ({
  fetchGoogleAdsExecutive: (...args: unknown[]) => fetchGoogleAdsExecutiveMock(...args),
}));

const fixture = {
  source_engine: 'sdk',
  metrics: { spend: 1234.56, impressions: 100000, clicks: 9000 },
  pacing: { daily_budget: 500, spend_rate: 1.05 },
  movers: [{ campaign_id: 'c1', campaign_name: 'Brand', spend: 600, conversion_value: 1800, roas: 3.0 }],
  trend: [{ date: '2026-04-01', spend: 400, conversions: 20, roas: 3.2 }],
};

describe('GoogleAdsExecutivePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchGoogleAdsExecutiveMock.mockImplementation(() => pendingAsync());
  });

  it('renders the page heading', () => {
    render(
      <MemoryRouter>
        <GoogleAdsExecutivePage />
      </MemoryRouter>,
    );
    expect(screen.getByText('Executive Overview')).toBeInTheDocument();
  });

  it('renders KPI metrics after loading', async () => {
    fetchGoogleAdsExecutiveMock.mockResolvedValueOnce(fixture);
    render(
      <MemoryRouter>
        <GoogleAdsExecutivePage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('KPI Summary')).toBeInTheDocument());
    expect(screen.getByText('1234.56')).toBeInTheDocument();
  });

  it('renders top movers table', async () => {
    fetchGoogleAdsExecutiveMock.mockResolvedValueOnce(fixture);
    render(
      <MemoryRouter>
        <GoogleAdsExecutivePage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('Brand')).toBeInTheDocument());
  });

  it('shows error state when fetch fails', async () => {
    fetchGoogleAdsExecutiveMock.mockRejectedValueOnce(new Error('Service unavailable'));
    render(
      <MemoryRouter>
        <GoogleAdsExecutivePage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('Service unavailable')).toBeInTheDocument());
  });
});
