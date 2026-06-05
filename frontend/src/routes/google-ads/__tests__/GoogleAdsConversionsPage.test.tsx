import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsConversionsPage from '../GoogleAdsConversionsPage';

const getMock = vi.hoisted(() => vi.fn());
const fetchSummaryMock = vi.hoisted(() => vi.fn());
const pendingAsync = () => new Promise<never>(() => {});

vi.mock('../../../lib/apiClient', () => ({
  appendQueryParams: (endpoint: string) => endpoint,
  get: (...args: unknown[]) => getMock(...args),
}));

vi.mock('../../../lib/googleAdsDashboard', () => ({
  fetchGoogleAdsWorkspaceSummary: (...args: unknown[]) => fetchSummaryMock(...args),
}));

describe('GoogleAdsConversionsPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMock.mockImplementation(() => pendingAsync());
    fetchSummaryMock.mockImplementation(() => pendingAsync());
  });

  it('renders the page heading', () => {
    render(
      <MemoryRouter>
        <GoogleAdsConversionsPage />
      </MemoryRouter>,
    );
    expect(screen.getByText('Conversions & Attribution')).toBeInTheDocument();
  });

  it('renders KPIs + funnel + source-mix on load', async () => {
    getMock.mockResolvedValueOnce({
      count: 2,
      results: [
        {
          conversion_action_id: 'c1',
          conversion_action_name: 'Purchase',
          conversions: 42,
          value: 3200,
          cpa: 12.5,
        },
        {
          conversion_action_id: 'c2',
          conversion_action_name: 'SignUp',
          conversions: 18,
          value: 900,
          cpa: 9.1,
        },
      ],
    });
    fetchSummaryMock.mockResolvedValueOnce({
      metrics: { impressions: 100000, clicks: 2500, conversions: 60 },
      trend: [],
      movers: [],
    });
    render(
      <MemoryRouter>
        <GoogleAdsConversionsPage />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByText('Total Conversions')).toBeInTheDocument());
    expect(screen.getByText('Total Value')).toBeInTheDocument();
    expect(screen.getByText('Avg CPA')).toBeInTheDocument();

    // Funnel (DistributionBar) renders three ordered stages.
    const funnel = screen.getByRole('img', {
      name: /google ads conversion funnel stages/i,
    });
    expect(funnel).toBeInTheDocument();

    // Source mix pie includes both actions via the sr-only accessible table.
    expect(screen.getAllByText('Purchase').length).toBeGreaterThan(0);
    expect(screen.getAllByText('SignUp').length).toBeGreaterThan(0);
  });

  it('renders empty state when both rows and summary metrics are zero', async () => {
    getMock.mockResolvedValueOnce({ count: 0, results: [] });
    fetchSummaryMock.mockResolvedValueOnce({
      metrics: { impressions: 0, clicks: 0, conversions: 0 },
      trend: [],
      movers: [],
    });
    const { container } = render(
      <MemoryRouter>
        <GoogleAdsConversionsPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(container.querySelector('[data-reason-code="no_conversions"]')).toBeInTheDocument(),
    );
  });

  it('shows error state when fetch fails', async () => {
    getMock.mockRejectedValueOnce(new Error('Conv boom'));
    fetchSummaryMock.mockRejectedValueOnce(new Error('Conv boom'));
    render(
      <MemoryRouter>
        <GoogleAdsConversionsPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('Conv boom')).toBeInTheDocument());
  });
});
