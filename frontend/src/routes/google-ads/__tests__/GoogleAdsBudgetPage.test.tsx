import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsBudgetPage from '../GoogleAdsBudgetPage';

const getMock = vi.hoisted(() => vi.fn());
const pendingAsync = () => new Promise<never>(() => {});

const mockFilters = { accountId: '', clientId: '', startDate: '', endDate: '', dateRange: '30d' };
vi.mock('../../../state/useDashboardStore', () => ({
  default: Object.assign(
    (selector: (state: { filters: typeof mockFilters }) => unknown) =>
      selector({ filters: mockFilters }),
    {
      getState: () => ({ filters: mockFilters }),
    },
  ),
}));

vi.mock('../../../lib/apiClient', () => ({
  get: (...args: unknown[]) => getMock(...args),
  appendQueryParams: (url: string) => url,
}));

const fixture = {
  month: 'April 2026',
  spend_mtd: 1234.56,
  budget_month: 5000,
  forecast_month_end: 4800,
  over_under: -200,
  runway_days: 12,
  alerts: { overspend_risk: false, underdelivery: true },
};

describe('GoogleAdsBudgetPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    getMock.mockImplementation(() => pendingAsync());
  });

  it('renders the page heading', () => {
    render(
      <MemoryRouter>
        <GoogleAdsBudgetPage />
      </MemoryRouter>,
    );
    expect(screen.getByText('Budget & Pacing')).toBeInTheDocument();
  });

  it('renders GaugeRing + KPI tiles + summary with pacing_pct derived', async () => {
    getMock.mockResolvedValueOnce(fixture);
    render(
      <MemoryRouter>
        <GoogleAdsBudgetPage />
      </MemoryRouter>,
    );
    // Heading from the legacy page header still renders (preserve section identity).
    await waitFor(() => expect(screen.getByText('April 2026')).toBeInTheDocument());
    // GaugeRing renders with role="meter" and aria-label based on derived pct.
    const meter = screen.getByRole('meter');
    expect(meter).toBeInTheDocument();
    expect(meter.getAttribute('aria-label')).toMatch(/Pacing/);
    // KPI tiles
    expect(screen.getByText('Spend MTD')).toBeInTheDocument();
    expect(screen.getByText('Budget Month')).toBeInTheDocument();
    expect(screen.getByText('Forecast Month End')).toBeInTheDocument();
    // Variance bar MUST NOT render (architect §4 / §6.7 deferral).
    expect(screen.queryByText(/Variance/i)).not.toBeInTheDocument();
  });

  it('renders reasonCode=no_pacing_data when both values are zero', async () => {
    getMock.mockResolvedValueOnce({
      month: 'April 2026',
      spend_mtd: 0,
      budget_month: 0,
      forecast_month_end: 0,
      over_under: 0,
      runway_days: null,
      alerts: { overspend_risk: false, underdelivery: false },
    });
    render(
      <MemoryRouter>
        <GoogleAdsBudgetPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      const empty = document.querySelector('[data-reason-code="no_pacing_data"]');
      expect(empty).not.toBeNull();
    });
  });

  it('shows error state when fetch fails', async () => {
    getMock.mockRejectedValueOnce(new Error('Budget fetch failed'));
    render(
      <MemoryRouter>
        <GoogleAdsBudgetPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('Budget fetch failed')).toBeInTheDocument());
  });
});
