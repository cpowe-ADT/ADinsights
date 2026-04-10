import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsBudgetPage from '../GoogleAdsBudgetPage';

const getMock = vi.hoisted(() => vi.fn());
const pendingAsync = () => new Promise<never>(() => {});

vi.mock('../../../lib/apiClient', () => ({
  get: (...args: unknown[]) => getMock(...args),
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

  it('renders pacing data after loading', async () => {
    getMock.mockResolvedValueOnce(fixture);
    render(
      <MemoryRouter>
        <GoogleAdsBudgetPage />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByText('April 2026')).toBeInTheDocument());
    expect(screen.getByText('Spend MTD')).toBeInTheDocument();
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
