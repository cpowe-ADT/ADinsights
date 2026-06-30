import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsRecommendationsPage from '../GoogleAdsRecommendationsPage';

const fetchGoogleAdsListMock = vi.hoisted(() => vi.fn());
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

  it('renders KPI strip + PieComposition + severity chips for returned rows', async () => {
    fetchGoogleAdsListMock.mockResolvedValueOnce({
      count: 3,
      results: [
        // impact_metadata.severity explicit (danger)
        {
          recommendation_type: 'TEXT_AD',
          campaign_id: 'C1',
          impact_metadata: { severity: 'danger', primary_metric: 'ctr' },
          dismissed: false,
        },
        // type-heuristic fallback (warning for BUDGET)
        {
          recommendation_type: 'CAMPAIGN_BUDGET',
          campaign_id: 'C2',
          impact_metadata: null,
          dismissed: false,
        },
        // info default, dismissed
        {
          recommendation_type: 'UNKNOWN_TYPE',
          campaign_id: 'C3',
          impact_metadata: null,
          dismissed: true,
        },
      ],
    });
    render(
      <MemoryRouter>
        <GoogleAdsRecommendationsPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByTestId('google-ads-recommendations-section')).toBeInTheDocument(),
    );
    // KPI × 2 (Active / Dismissed) — use getAllByText because "Active" also
    // appears as the status-chip label on active rows.
    expect(screen.getAllByText('Active').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Dismissed').length).toBeGreaterThan(0);

    const chips = document.querySelectorAll('[data-severity]');
    const severities = Array.from(chips).map((el) => el.getAttribute('data-severity'));
    // Both derivation branches exercised
    expect(severities).toContain('danger'); // via impact_metadata.severity
    expect(severities).toContain('warning'); // via type heuristic
    expect(severities).toContain('info'); // default
  });

  it('does not render a Dismiss button (no backend PATCH endpoint)', async () => {
    fetchGoogleAdsListMock.mockResolvedValueOnce({
      count: 1,
      results: [
        {
          recommendation_type: 'TEXT_AD',
          campaign_id: 'C1',
          impact_metadata: null,
          dismissed: false,
        },
      ],
    });
    render(
      <MemoryRouter>
        <GoogleAdsRecommendationsPage />
      </MemoryRouter>,
    );
    await waitFor(() =>
      expect(screen.getByTestId('google-ads-recommendations-section')).toBeInTheDocument(),
    );
    expect(screen.queryByRole('button', { name: /dismiss/i })).toBeNull();
  });

  it('renders reasonCode=no_recommendations when empty', async () => {
    fetchGoogleAdsListMock.mockResolvedValueOnce({ count: 0, results: [] });
    render(
      <MemoryRouter>
        <GoogleAdsRecommendationsPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      const empty = document.querySelector('[data-reason-code="no_recommendations"]');
      expect(empty).not.toBeNull();
    });
  });
});
