import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsCampaignsPage from '../GoogleAdsCampaignsPage';

const fetchGoogleAdsListMock = vi.hoisted(() => vi.fn());
const pendingAsync = () => new Promise<never>(() => {});

vi.mock('../../../lib/googleAdsDashboard', async () => {
  const actual = await vi.importActual<typeof import('../../../lib/googleAdsDashboard')>(
    '../../../lib/googleAdsDashboard',
  );
  return {
    ...actual,
    fetchGoogleAdsList: (...args: unknown[]) => fetchGoogleAdsListMock(...args),
  };
});

vi.mock('../../../lib/apiClient', () => ({
  appendQueryParams: (endpoint: string) => endpoint,
}));

const mockFilters = {
  accountId: 'cust-001',
  clientId: '',
  startDate: '',
  endDate: '',
  dateRange: '30d',
};
vi.mock('../../../state/useDashboardStore', () => ({
  default: Object.assign(
    (selector: (state: { filters: typeof mockFilters }) => unknown) =>
      selector({ filters: mockFilters }),
    {
      getState: () => ({ filters: mockFilters }),
    },
  ),
}));

const fixture = {
  count: 2,
  source_engine: 'sdk',
  results: [
    {
      campaign_id: 'c1',
      campaign_name: 'Brand',
      campaign_status: 'ENABLED',
      channel_type: 'SEARCH',
      spend: 500,
      clicks: 100,
      impressions: 10000,
      conversions: 10,
      conversion_value: 1500,
      cpa: 50,
      roas: 3,
    },
    {
      campaign_id: 'c2',
      campaign_name: 'Display',
      campaign_status: 'PAUSED',
      channel_type: 'DISPLAY',
      spend: 200,
      clicks: 50,
      impressions: 5000,
      conversions: 4,
      conversion_value: 600,
      cpa: 50,
      roas: 3,
    },
  ],
};

describe('GoogleAdsCampaignsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchGoogleAdsListMock.mockImplementation(() => pendingAsync());
  });

  it('renders the page heading', () => {
    render(
      <MemoryRouter>
        <GoogleAdsCampaignsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText('Performance by Campaign')).toBeInTheDocument();
  });

  it('renders the KPI strip (4 tiles) after loading', async () => {
    fetchGoogleAdsListMock.mockResolvedValueOnce(fixture);
    render(
      <MemoryRouter>
        <GoogleAdsCampaignsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('Campaign KPIs')).toBeInTheDocument());
    expect(screen.getByText('Total Cost')).toBeInTheDocument();
    expect(screen.getByText('Total Conversions')).toBeInTheDocument();
    expect(screen.getByText('Avg CPA')).toBeInTheDocument();
    expect(screen.getByText('Avg ROAS')).toBeInTheDocument();
  });

  it('renders the bubble scatter and the top-10 bar (per-campaign daily trend fallback)', async () => {
    fetchGoogleAdsListMock.mockResolvedValueOnce(fixture);
    render(
      <MemoryRouter>
        <GoogleAdsCampaignsPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByRole('img', { name: /cost vs conversion rate/i })).toBeInTheDocument(),
    );
    expect(
      screen.getByRole('img', { name: /top 10 google ads campaigns by cost/i }),
    ).toBeInTheDocument();
  });

  it('renders campaign rows with severity chips', async () => {
    fetchGoogleAdsListMock.mockResolvedValueOnce(fixture);
    render(
      <MemoryRouter>
        <GoogleAdsCampaignsPage />
      </MemoryRouter>,
    );
    // "Brand" may appear in both the bar chart label and the campaigns table —
    // use getAllByText to avoid multiple-match errors.
    await waitFor(() => expect(screen.getAllByText('Brand').length).toBeGreaterThan(0));
    // Status chips
    const enabled = document.querySelector('[data-status-tone="success"]');
    const paused = document.querySelector('[data-status-tone="warning"]');
    expect(enabled).not.toBeNull();
    expect(paused).not.toBeNull();
  });

  it('renders EmptyState with reasonCode when no rows', async () => {
    fetchGoogleAdsListMock.mockResolvedValueOnce({ count: 0, results: [] });
    render(
      <MemoryRouter>
        <GoogleAdsCampaignsPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      const empty = document.querySelector('[data-reason-code="no_campaigns"]');
      expect(empty).not.toBeNull();
    });
  });

  it('shows error state when fetch fails', async () => {
    fetchGoogleAdsListMock.mockRejectedValueOnce(new Error('Network error'));
    render(
      <MemoryRouter>
        <GoogleAdsCampaignsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('Network error')).toBeInTheDocument());
  });
});
