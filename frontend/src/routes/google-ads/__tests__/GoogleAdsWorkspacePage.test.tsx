import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsWorkspacePage from '../GoogleAdsWorkspacePage';

const googleAdsWorkspaceDataHookMock = vi.hoisted(() => vi.fn());
const fetchGoogleAdsSavedViewsMock = vi.hoisted(() => vi.fn());
const createGoogleAdsSavedViewMock = vi.hoisted(() => vi.fn());
const updateGoogleAdsSavedViewMock = vi.hoisted(() => vi.fn());
const createGoogleAdsExportMock = vi.hoisted(() => vi.fn());

// Mock store accountId so the workspace renders content instead of empty state.
const mockDashboardStoreFilters = vi.hoisted(() => ({
  accountId: 'test-customer-123',
  clientId: '',
}));
const mockSetFilters = vi.hoisted(() => vi.fn());

vi.mock('../../../hooks/useGoogleAdsWorkspaceData', () => ({
  default: (...args: unknown[]) => googleAdsWorkspaceDataHookMock(...args),
}));

vi.mock('../../../lib/googleAdsDashboard', () => ({
  fetchGoogleAdsSavedViews: (...args: unknown[]) => fetchGoogleAdsSavedViewsMock(...args),
  createGoogleAdsSavedView: (...args: unknown[]) => createGoogleAdsSavedViewMock(...args),
  updateGoogleAdsSavedView: (...args: unknown[]) => updateGoogleAdsSavedViewMock(...args),
  createGoogleAdsExport: (...args: unknown[]) => createGoogleAdsExportMock(...args),
}));

vi.mock('../../../lib/apiClient', async () => {
  const actual = await vi.importActual('../../../lib/apiClient');
  return {
    ...actual,
    download: vi.fn(),
  };
});

vi.mock('../../../lib/download', () => ({
  saveBlobAsFile: vi.fn(),
}));

vi.mock('../../../state/useDashboardStore', () => ({
  default: Object.assign(
    (selector: (state: { filters: { accountId: string; clientId: string } }) => unknown) =>
      selector({ filters: mockDashboardStoreFilters }),
    {
      getState: () => ({
        filters: mockDashboardStoreFilters,
        setFilters: mockSetFilters,
      }),
    },
  ),
}));

const LocationProbe = () => {
  const location = useLocation();
  return <div data-testid="location-search">{location.search}</div>;
};

const summaryFixture = {
  window: {
    start_date: '2026-02-01',
    end_date: '2026-02-10',
    compare_start_date: '2026-01-22',
    compare_end_date: '2026-01-31',
  },
  metrics: {
    spend: 1234.56,
    impressions: 100000,
    clicks: 9000,
    conversions: 250,
    roas: 3.2,
    cpa: 4.94,
    conversion_value: 3950.12,
  },
  comparison: {},
  pacing: {},
  trend: [],
  movers: [],
  data_freshness_ts: '2026-02-23T10:00:00Z',
  source_engine: 'sdk',
  alerts_summary: {
    overspend_risk: false,
    underdelivery: false,
    spend_spike: false,
    conversion_drop: false,
  },
  governance_summary: {
    recent_changes_7d: 2,
    active_recommendations: 5,
    disapproved_ads: 1,
  },
  top_insights: [
    { id: 'insight-1', title: 'ROAS up', detail: 'ROAS increased 18% week over week.' },
  ],
  workspace_generated_at: '2026-02-23T10:01:00Z',
};

describe('GoogleAdsWorkspacePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockDashboardStoreFilters.accountId = 'test-customer-123';
    mockDashboardStoreFilters.clientId = '';
    fetchGoogleAdsSavedViewsMock.mockResolvedValue([]);
    createGoogleAdsSavedViewMock.mockResolvedValue({ id: 'view-1' });
    updateGoogleAdsSavedViewMock.mockResolvedValue({});
    createGoogleAdsExportMock.mockResolvedValue({
      id: 'job-1',
      status: 'queued',
      download_url: null,
    });
    googleAdsWorkspaceDataHookMock.mockReturnValue({
      summary: summaryFixture,
      summaryStatus: 'success',
      summaryError: '',
      tabStates: {},
      loadSummary: vi.fn(),
      loadTab: vi.fn(),
      filterKey: '2026-02-01|2026-02-10|none||',
    });
  });

  it('syncs workspace tabs and search mode with URL query params', async () => {
    const user = userEvent.setup({ delay: null });

    render(
      <MemoryRouter
        initialEntries={[
          '/dashboards/google-ads?tab=overview&start_date=2026-02-01&end_date=2026-02-10',
        ]}
      >
        <Routes>
          <Route
            path="/dashboards/google-ads"
            element={
              <>
                <GoogleAdsWorkspacePage />
                <LocationProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole('tab', { name: 'Overview' })).toHaveAttribute('aria-selected', 'true');

    await user.click(screen.getByRole('tab', { name: 'Campaigns' }));
    await waitFor(() => {
      expect(screen.getByTestId('location-search').textContent).toContain('tab=campaigns');
    });

    await user.click(screen.getByRole('tab', { name: 'Search & Keywords' }));
    await waitFor(() => {
      expect(screen.getByTestId('location-search').textContent).toContain('tab=search');
    });

    await user.click(screen.getByRole('button', { name: 'Search Terms' }));
    await waitFor(() => {
      expect(screen.getByTestId('location-search').textContent).toContain(
        'search_mode=search_terms',
      );
    });
  });

  it('updates compare filter in the URL query string', async () => {
    const user = userEvent.setup({ delay: null });

    render(
      <MemoryRouter
        initialEntries={[
          '/dashboards/google-ads?tab=overview&start_date=2026-02-01&end_date=2026-02-10',
        ]}
      >
        <Routes>
          <Route
            path="/dashboards/google-ads"
            element={
              <>
                <GoogleAdsWorkspacePage />
                <LocationProbe />
              </>
            }
          />
        </Routes>
      </MemoryRouter>,
    );

    await user.selectOptions(screen.getByLabelText('Compare'), 'wow');
    await waitFor(() => {
      expect(screen.getByTestId('location-search').textContent).toContain('compare=wow');
    });
  });

  it('reads customer from useDashboardStore (store accountId drives fetch, not URL)', () => {
    // The mock store has accountId='test-customer-123'
    googleAdsWorkspaceDataHookMock.mockReturnValue({
      summary: summaryFixture,
      summaryStatus: 'success',
      summaryError: '',
      tabStates: {},
      loadSummary: vi.fn(),
      loadTab: vi.fn(),
      filterKey: '2026-02-01|2026-02-10|none|test-customer-123||',
    });

    render(
      <MemoryRouter
        initialEntries={[
          '/dashboards/google-ads?tab=overview&start_date=2026-02-01&end_date=2026-02-10',
        ]}
      >
        <Routes>
          <Route path="/dashboards/google-ads" element={<GoogleAdsWorkspacePage />} />
        </Routes>
      </MemoryRouter>,
    );

    // The hook should have been called with the store's accountId as customerId
    expect(googleAdsWorkspaceDataHookMock).toHaveBeenCalledWith(
      expect.objectContaining({
        filters: expect.objectContaining({ customerId: 'test-customer-123' }),
      }),
    );
  });

  it('shows empty state when store has no accountId and no clientId', () => {
    // Temporarily override the mock store to return empty IDs
    mockDashboardStoreFilters.accountId = '';
    mockDashboardStoreFilters.clientId = '';

    render(
      <MemoryRouter initialEntries={['/dashboards/google-ads']}>
        <Routes>
          <Route path="/dashboards/google-ads" element={<GoogleAdsWorkspacePage />} />
        </Routes>
      </MemoryRouter>,
    );

    expect(screen.getByRole('status')).toHaveAttribute('data-reason-code', 'no_customer_selected');
    expect(screen.getByText('No account selected')).toBeInTheDocument();

    // Restore
    mockDashboardStoreFilters.accountId = 'test-customer-123';
  });

  it('hook receives customer_id from store when store has accountId', () => {
    render(
      <MemoryRouter
        initialEntries={[
          '/dashboards/google-ads?tab=campaigns&start_date=2026-02-01&end_date=2026-02-10',
        ]}
      >
        <Routes>
          <Route path="/dashboards/google-ads" element={<GoogleAdsWorkspacePage />} />
        </Routes>
      </MemoryRouter>,
    );

    // The hook is called with customerId from the global store, and activeTab 'campaigns'
    const calls = googleAdsWorkspaceDataHookMock.mock.calls;
    const lastCall = calls[calls.length - 1][0] as {
      filters: { customerId: string };
      activeTab: string;
    };
    expect(lastCall.filters.customerId).toBe('test-customer-123');
    expect(lastCall.activeTab).toBe('campaigns');
  });

  // CC2 fix: saved-view restore writes client_id back to the store.
  it('restores client_id from saved view into the dashboard store on saved-view select', async () => {
    const user = userEvent.setup({ delay: null });

    const savedViewWithClientId = {
      id: 'view-with-client',
      name: 'MCC View',
      filters: {
        start_date: '2026-02-01',
        end_date: '2026-02-28',
        compare: 'none',
        customer_id: 'mcc-account',
        client_id: 'client-456',
      },
    };
    fetchGoogleAdsSavedViewsMock.mockResolvedValue([savedViewWithClientId]);

    render(
      <MemoryRouter
        initialEntries={[
          '/dashboards/google-ads?tab=overview&start_date=2026-02-01&end_date=2026-02-10',
        ]}
      >
        <Routes>
          <Route path="/dashboards/google-ads" element={<GoogleAdsWorkspacePage />} />
        </Routes>
      </MemoryRouter>,
    );

    // Wait for saved views to load
    await waitFor(() => {
      expect(fetchGoogleAdsSavedViewsMock).toHaveBeenCalled();
    });

    // Select the saved view via the WorkspaceHeader select
    const select = screen.getByLabelText('Saved view');
    await user.selectOptions(select, 'view-with-client');

    // CC2: setFilters should have been called with the client_id from the saved view
    await waitFor(() => {
      expect(mockSetFilters).toHaveBeenCalledWith(
        expect.objectContaining({ clientId: 'client-456' }),
      );
    });
  });
});
