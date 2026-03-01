import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import GoogleAdsWorkspacePage from '../GoogleAdsWorkspacePage';

const useGoogleAdsWorkspaceDataMock = vi.hoisted(() => vi.fn());
const fetchGoogleAdsSavedViewsMock = vi.hoisted(() => vi.fn());
const createGoogleAdsSavedViewMock = vi.hoisted(() => vi.fn());
const updateGoogleAdsSavedViewMock = vi.hoisted(() => vi.fn());
const createGoogleAdsExportMock = vi.hoisted(() => vi.fn());

vi.mock('../../../hooks/useGoogleAdsWorkspaceData', () => ({
  default: (...args: unknown[]) => useGoogleAdsWorkspaceDataMock(...args),
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
  top_insights: [{ id: 'insight-1', title: 'ROAS up', detail: 'ROAS increased 18% week over week.' }],
  workspace_generated_at: '2026-02-23T10:01:00Z',
};

describe('GoogleAdsWorkspacePage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    fetchGoogleAdsSavedViewsMock.mockResolvedValue([]);
    createGoogleAdsSavedViewMock.mockResolvedValue({ id: 'view-1' });
    updateGoogleAdsSavedViewMock.mockResolvedValue({});
    createGoogleAdsExportMock.mockResolvedValue({ id: 'job-1', status: 'queued', download_url: null });
    useGoogleAdsWorkspaceDataMock.mockReturnValue({
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
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={['/dashboards/google-ads?tab=overview&start_date=2026-02-01&end_date=2026-02-10']}>
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
      expect(screen.getByTestId('location-search').textContent).toContain('search_mode=search_terms');
    });
  });

  it('updates compare filter in the URL query string', async () => {
    const user = userEvent.setup();

    render(
      <MemoryRouter initialEntries={['/dashboards/google-ads?tab=overview&start_date=2026-02-01&end_date=2026-02-10']}>
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
});

