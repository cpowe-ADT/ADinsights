import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsExecutivePage from '../GoogleAdsExecutivePage';

const fetchGoogleAdsExecutiveMock = vi.hoisted(() => vi.fn());
const pendingAsync = () => new Promise<never>(() => {});

vi.mock('../../../lib/googleAdsDashboard', () => ({
  fetchGoogleAdsExecutive: (...args: unknown[]) => fetchGoogleAdsExecutiveMock(...args),
}));

const mockFilters = { accountId: 'cust-001', clientId: '', startDate: '', endDate: '', dateRange: '30d' };
vi.mock('../../../state/useDashboardStore', () => ({
  default: Object.assign(
    (selector: (state: { filters: typeof mockFilters }) => unknown) => selector({ filters: mockFilters }),
    {
      getState: () => ({ filters: mockFilters }),
    },
  ),
}));

const fixture = {
  source_engine: 'sdk',
  metrics: { spend: 1234.56, impressions: 100000, clicks: 9000, conversions: 20, cpa: 61.73, roas: 2.5 },
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

  it('renders KPI tiles after loading (Cost, Conversions, CPA, ROAS) — IS% deferred per architect §4', async () => {
    fetchGoogleAdsExecutiveMock.mockResolvedValueOnce(fixture);
    render(
      <MemoryRouter>
        <GoogleAdsExecutivePage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText(/KPI Summary/)).toBeInTheDocument());
    // 4 KpiTile cards — no IS% tile. "Cost"/"ROAS" also appear in Top Movers table headers,
    // so assert inside the KPI grid specifically.
    const kpiGrid = screen.getByRole('list', { name: /Google Ads executive KPIs/i });
    expect(kpiGrid).toHaveTextContent('Cost');
    expect(kpiGrid).toHaveTextContent('Conversions');
    expect(kpiGrid).toHaveTextContent('CPA');
    expect(kpiGrid).toHaveTextContent('ROAS');
    expect(screen.queryByText(/impression share|IS %/i)).not.toBeInTheDocument();
  });

  it('renders the TrendLine dual-axis chart after loading', async () => {
    fetchGoogleAdsExecutiveMock.mockResolvedValueOnce(fixture);
    render(
      <MemoryRouter>
        <GoogleAdsExecutivePage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(
        screen.getByRole('img', { name: /Google Ads executive daily cost and conversions/i }),
      ).toBeInTheDocument(),
    );
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
